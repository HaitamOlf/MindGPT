// Private Blob Storage for user uploads (ARCHITECTURE.md §7.3 — closes v1 F07/F08).
// No public access, no shared-key access at all: every client read goes through a
// short-lived, user-bound, Entra-signed *user-delegation* SAS minted by the API after it
// has verified the requesting user owns the blob path (uploads/{uid}/...).

@description('Short unique token (e.g. uniqueString output) — storage account names are capped at 24 chars, so this is used directly rather than the full baseName.')
param resourceToken string
param location string
param tags object

@description('Principal IDs granted Storage Blob Data Contributor.')
param contributorPrincipalIds array

var storageAccountName = toLower(take('st${resourceToken}', 24))

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // forces Entra ID auth; user-delegation SAS still works (it's Entra-signed)
    defaultToOAuthAuthentication: true
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (see ARCHITECTURE.md §3 DOCUMENT gap)
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    isVersioningEnabled: true
  }
}

resource uploadsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'uploads'
  properties: {
    publicAccess: 'None'
  }
}

var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource contributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in contributorPrincipalIds: {
    name: guid(storage.id, principalId, storageBlobDataContributorRoleId)
    scope: storage
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output storageAccountName string = storage.name
output primaryBlobEndpoint string = storage.properties.primaryEndpoints.blob
output storageAccountId string = storage.id
