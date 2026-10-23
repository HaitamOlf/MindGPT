// Azure Container Registry for the API image (ARCHITECTURE.md §4). Admin user is disabled
// — the Container App pulls via its managed identity (AcrPull role), so there are no
// registry credentials anywhere, consistent with the identity-over-secrets principle.

@description('Short unique token — registry names are globally unique, alphanumeric, 5-50 chars.')
param resourceToken string
param location string
param tags object

@description('Principal IDs granted AcrPull (the Container App managed identity).')
param pullPrincipalIds array

var registryName = toLower('acr${resourceToken}')

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false // no admin credentials — managed-identity pull only
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (DOCUMENT gap)
  }
}

// AcrPull — lets the Container App's managed identity pull images without any secret.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource pullRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in pullPrincipalIds: {
    name: guid(acr.id, principalId, acrPullRoleId)
    scope: acr
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output loginServer string = acr.properties.loginServer
output name string = acr.name
