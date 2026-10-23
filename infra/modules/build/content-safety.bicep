// AI Content Safety — Prompt Shields (user + document/indirect-injection) and harm-category
// output moderation (ARCHITECTURE.md §7.4, closes v1 F13). F0 free tier.

param baseName string
param location string
param tags object

@description('Principal IDs granted Cognitive Services User (data-plane inference only).')
param userPrincipalIds array

var accountName = take('${baseName}-safety', 64)

resource contentSafety 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'ContentSafety'
  sku: {
    name: 'F0'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: true // no API keys — Entra RBAC only
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (see ARCHITECTURE.md §3 DOCUMENT gap)
  }
  identity: {
    type: 'None'
  }
}

var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource userRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in userPrincipalIds: {
    name: guid(contentSafety.id, principalId, cognitiveServicesUserRoleId)
    scope: contentSafety
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output accountName string = contentSafety.name
output endpoint string = contentSafety.properties.endpoint
