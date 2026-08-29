// Azure Container Apps deployment for paper-podcasts.
//
// Provisions, into the existing rg-chatbot resource group (shared ACR with
// copilot-kit-exp and Portfolio -- nothing else is shared, this project gets
// its own Container Apps environment: cae-podcasts, matching the real
// precedent those two set, not a literal shared-environment deployment):
//   - a Container Apps environment (no Log Analytics -- same as the other two)
//   - a user-assigned managed identity granted:
//       - AcrPull on the EXISTING registry
//       - Storage Blob Data Contributor, scoped to the NEW `paper-podcasts`
//         blob container only (not account-wide, so it can't touch
//         Portfolio's `portfolio-documents` container)
//   - a new `paper-podcasts` blob container in the EXISTING fhstorageportfolio
//     storage account
//   - the backend app  (ca-podcasts-agent): internal ingress only
//   - the frontend app (ca-podcasts-web):    external ingress
//
// Reuses the EXISTING fhstorageportfolio storage account and fhdbplayground
// SQL server/PlaygroundDB database (Portfolio's Playground resources) --
// decision #6 in docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md. The SQL
// grant (CREATE USER + role membership for this identity) is NOT expressible
// in Bicep -- run backend/sql/schema.sql then backend/sql/grant_identity.sql
// once, manually, after this deploys (same reason Portfolio's
// grant_identity.sql isn't in its Bicep either).
//
// No Easy Auth here -- per-user appRoleAssignedTo grants can't be expressed
// in Bicep, so all of auth stays in scripts/setup-easyauth.sh (CLI), same
// reasoning as copilot-kit-exp's main.bicep.
//
// Deploy with infra/deploy.sh (sources the repo-root .env for the OpenAI key).

@description('Region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Existing Azure Container Registry name (shared with copilot-kit-exp and Portfolio).')
param acrName string = 'acrchatbotfredheda'

@description('Container Apps environment name.')
param environmentName string = 'cae-podcasts'

@description('Backend (FastAPI) container app name.')
param backendAppName string = 'ca-podcasts-agent'

@description('Frontend (Express/Vite) container app name.')
param frontendAppName string = 'ca-podcasts-web'

@description('User-assigned managed identity name.')
param identityName string = 'id-podcasts-acrpull'

@description('Resource group holding the shared Playground data resources (storage account + SQL server) -- separate from rg-chatbot, where this deployment itself lands.')
param playgroundResourceGroupName string = 'FrederikHedaPlayground'

@description('Existing storage account (shared with Portfolio -- decision #6).')
param storageAccountName string = 'fhstorageportfolio'

@description('Blob container for paper artifacts.')
param blobContainerName string = 'paper-podcasts'

@description('Existing Azure SQL logical server name (shared with Portfolio -- decision #6).')
param sqlServerName string = 'fhdbplayground'

@description('Existing Azure SQL database name.')
param sqlDatabaseName string = 'PlaygroundDB'

@description('Image tag to deploy for both images (e.g. a git commit SHA).')
param imageTag string

@secure()
param openaiApiKey string

// Built-in role definition IDs (constant across all tenants).
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var loginServer = '${acrName}.azurecr.io'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// Creates the new blob container + its scoped role assignment AT the
// Playground resource group's scope -- see playground-storage.bicep for why
// this has to be a module rather than inline resources here (BCP165).
module playgroundStorage 'playground-storage.bicep' = {
  name: 'podcasts-playground-storage'
  scope: resourceGroup(playgroundResourceGroupName)
  params: {
    storageAccountName: storageAccountName
    blobContainerName: blobContainerName
    principalId: identity.properties.principalId
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  properties: {}
}

resource backend 'Microsoft.App/containerApps@2025-01-01' = {
  name: backendAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  dependsOn: [
    acrPull
    playgroundStorage
  ]
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: loginServer
          identity: identity.id
        }
      ]
      secrets: [
        { name: 'openai-api-key', value: openaiApiKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'podcasts-agent'
          image: '${loginServer}/podcasts-agent:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'STORAGE_BACKEND', value: 'azure' }
            { name: 'AZURE_STORAGE_ACCOUNT', value: storageAccountName }
            { name: 'AZURE_SQL_SERVER', value: '${sqlServerName}.database.windows.net' }
            { name: 'AZURE_SQL_DATABASE', value: sqlDatabaseName }
            // Presence of this var is what makes azure_sql_metadata_service.py
            // pick ActiveDirectoryMSI auth (this identity) over ActiveDirectoryDefault.
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource frontend 'Microsoft.App/containerApps@2025-01-01' = {
  name: frontendAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  dependsOn: [
    acrPull
    backend
  ]
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        // ARM's PUT on this Container App treats the whole `ingress` object
        // as authoritative, so any redeploy that omits customDomains wipes
        // the production domain binding (this exact bug took down a sibling
        // Portfolio project's custom domain). podcasts.frederikheda.com was
        // originally bound imperatively (outside Bicep); declaring it here
        // makes every future deploy preserve it instead of resetting it.
        customDomains: [
          {
            name: 'podcasts.frederikheda.com'
            bindingType: 'SniEnabled'
            certificateId: '${environment.id}/managedCertificates/mc-cae-podcasts-podcasts-frederi-9882'
          }
        ]
      }
      registries: [
        {
          server: loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'podcasts-web'
          image: '${loginServer}/podcasts-web:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL', value: 'http://${backendAppName}' }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output frontendFqdn string = frontend.properties.configuration.ingress.fqdn
output backendFqdn string = backend.properties.configuration.ingress.fqdn
output identityName string = identity.name
output identityClientId string = identity.properties.clientId
