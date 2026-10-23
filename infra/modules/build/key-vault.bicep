// Minimal secrets only (ARCHITECTURE.md §7.3) — everything else uses managed identity.
// RBAC authorization (not access policies), purge protection + soft delete on.

@description('Short unique token (e.g. uniqueString output) — Key Vault names are capped at 24 chars, so this is used directly rather than the full baseName.')
param resourceToken string
param location string
param tags object

@description('Principal IDs granted Key Vault Secrets User (read-only data plane).')
param readerPrincipalIds array

var keyVaultName = toLower(take('kv${resourceToken}', 24))

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (see ARCHITECTURE.md §3 DOCUMENT gap)
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource readerRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in readerPrincipalIds: {
    name: guid(keyVault.id, principalId, keyVaultSecretsUserRoleId)
    scope: keyVault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
