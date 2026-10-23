// Scheduled cleanup (ARCHITECTURE.md §4 "FUNC") — a Python timer-triggered function with
// no inbound HTTP surface at all: a scheduled data-deletion job must have nothing to spoof.
//
// Hosted on the **Flex Consumption** plan (FC1). This is a deliberate choice: classic Linux
// Consumption (Y1) mounts app content from an Azure Files share that can only be referenced
// by a storage *connection string* — i.e. a key — which is incompatible with this project's
// "no storage keys anywhere" rule. Flex Consumption reaches BOTH the runtime storage AND the
// code-deployment blob container through the function's managed identity, so the keyless
// posture holds end to end (allowSharedKeyAccess stays false).

param baseName string
@description('Short unique token (e.g. uniqueString output) — storage account names are capped at 24 chars, so this is used directly rather than the full baseName, prefixed with "func" to stay distinct from storage-blob.bicep\'s "st"-prefixed account.')
param resourceToken string
param location string
param tags object
param functionsIdentityResourceId string
param functionsIdentityPrincipalId string
param functionsIdentityClientId string
param appInsightsConnectionString string
param cosmosEndpoint string
param cosmosDatabaseName string
param blobEndpoint string

var runtimeStorageAccountName = toLower(take('func${resourceToken}', 24))
var deploymentContainerName = 'app-package'

resource runtimeStorage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: runtimeStorageAccountName
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
    allowSharedKeyAccess: false // keyless — identity-based runtime AND deployment storage
    defaultToOAuthAuthentication: true
  }
}

// The Flex deployment container must exist *before* the app is created (the site's
// functionAppConfig.deployment.storage points straight at it).
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: runtimeStorage
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageQueueDataContributorRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'

// Blob Data Owner covers both the runtime's blob needs and read/write of the deployment
// container (the code package lands here on every deploy).
resource blobOwnerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(runtimeStorage.id, functionsIdentityResourceId, storageBlobDataOwnerRoleId)
  scope: runtimeStorage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalId: functionsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource queueContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(runtimeStorage.id, functionsIdentityResourceId, storageQueueDataContributorRoleId)
  scope: runtimeStorage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorRoleId)
    principalId: functionsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${baseName}-func-plan'
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: '${baseName}-func'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${functionsIdentityResourceId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${runtimeStorage.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: functionsIdentityResourceId
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      // Flex Consumption does NOT use FUNCTIONS_EXTENSION_VERSION / FUNCTIONS_WORKER_RUNTIME /
      // linuxFxVersion / SCM_DO_BUILD_DURING_DEPLOYMENT — the runtime is declared in
      // functionAppConfig.runtime and remote build is the platform default.
      appSettings: [
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__accountName', value: runtimeStorage.name }
        { name: 'AzureWebJobsStorage__clientId', value: functionsIdentityClientId }
        { name: 'AZURE_CLIENT_ID', value: functionsIdentityClientId }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
        { name: 'COSMOS_DATABASE_NAME', value: cosmosDatabaseName }
        { name: 'BLOB_ENDPOINT', value: blobEndpoint }
        { name: 'RETENTION_DAYS', value: '90' }
        { name: 'CLEANUP_DRY_RUN', value: 'false' } // armed: dry-run until the cleanup logic + 10 tests were verified in Phase 6 (docs/SECURITY_VALIDATION.md), then switched to active deletion
      ]
    }
  }
  dependsOn: [
    deploymentContainer
    blobOwnerRoleAssignment
    queueContributorRoleAssignment
  ]
}

output name string = functionApp.name
