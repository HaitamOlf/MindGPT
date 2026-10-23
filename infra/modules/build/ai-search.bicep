// Azure AI Search — real vector/semantic index replacing v1's brute-force Firestore
// cosine scan (ARCHITECTURE.md §4, closes v1 F23). Free tier is ample for the 14-doc
// RAG corpus. Semantic ranking needs Basic+; free tier runs vector + keyword search only
// — acceptable for a 14-document corpus, called out here rather than silently degraded.

param baseName string
param location string
param tags object

@allowed(['free', 'basic', 'standard'])
param skuName string = 'free'

@description('Principal IDs granted Search Index Data Contributor (query + index).')
param dataContributorPrincipalIds array

var searchServiceName = take('${baseName}-search', 60)

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    disableLocalAuth: true // no API keys — Entra RBAC only
    authOptions: null
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (see ARCHITECTURE.md §3 DOCUMENT gap)
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

resource dataRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in dataContributorPrincipalIds: {
    name: guid(search.id, principalId, searchIndexDataContributorRoleId)
    scope: search
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output searchServiceName string = search.name
output searchServiceId string = search.id
output endpoint string = 'https://${search.name}.search.windows.net'
