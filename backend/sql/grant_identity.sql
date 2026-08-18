-- One-time: grant the deployed podcasts identity read+write access to the
-- `papers` table. Run once against Azure SQL (Portal Query Editor, signed in
-- as the Entra ID admin) after infra/deploy.sh has created the identity. Not
-- part of deploy.sh -- re-running CREATE USER on an existing user errors.
--
-- db_datareader + db_datawriter: unlike Portfolio's write-only identity,
-- this one also powers the library list/content/audio reads, so it needs
-- SELECT too. No schema-modification rights.
--
-- [id-podcasts-acrpull] is the identityName Bicep param's default
-- (infra/main.bicep) -- update this if you ever rename it.
CREATE USER [id-podcasts-acrpull] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [id-podcasts-acrpull];
ALTER ROLE db_datawriter ADD MEMBER [id-podcasts-acrpull];
