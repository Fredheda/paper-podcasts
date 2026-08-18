// Module deployed AT the Playground resource group's scope (via a `module`
// block with `scope:` in main.bicep) -- Bicep requires this: you can't
// create a new child resource under a cross-resource-group `existing`
// reference in the same file (BCP165), only reference `existing` resources
// there for reads like role-assignment targets. This module exists purely
// to get the blob container CREATE onto the right scope.
//
// Creates the new `paper-podcasts` blob container in the existing
// fhstorageportfolio storage account, and grants the given managed identity
// Storage Blob Data Contributor scoped to that one container only.

@description('Existing storage account name, in this module\'s target resource group.')
param storageAccountName string

@description('Blob container to create for paper artifacts.')
param blobContainerName string

@description('Principal ID of the managed identity to grant container access to.')
param principalId string

var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storageAccount
  name: 'default'
}

// New container for this project -- scoped separately from Portfolio's
// existing `portfolio-documents` container so RBAC can isolate the two.
resource podcastsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: blobContainerName
  properties: {
    publicAccess: 'None'
  }
}

// Scoped to the CONTAINER, not the storage account -- this identity can
// read/write paper-podcasts artifacts but has no access to
// portfolio-documents or any other container in the shared account.
resource blobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(podcastsContainer.id, principalId, blobDataContributorRoleId)
  scope: podcastsContainer
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
  }
}
