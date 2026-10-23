// AI Language — PII detection/redaction before persistence or logging, plus sentiment
// (ARCHITECTURE.md §7.4). Free tier (5K records/mo).

param baseName string
param location string
param tags object

@description('Principal IDs granted Cognitive Services User (data-plane inference only).')
param userPrincipalIds array

var accountName = take('${baseName}-lang', 64)

resource language 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'TextAnalytics'
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
    name: guid(language.id, principalId, cognitiveServicesUserRoleId)
    scope: language
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output accountName string = language.name
output endpoint string = language.properties.endpoint
