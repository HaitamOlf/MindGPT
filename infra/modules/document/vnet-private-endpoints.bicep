// DOCUMENT tier (ARCHITECTURE.md §3/§7) — **design-only; intentionally not deployed.**
// Takes the data plane off the public internet: private endpoints for Cosmos, Storage,
// Key Vault and Search, replacing the BUILD-tier's "Entra auth + firewall rules" substitute
// (THREAT_MODEL.md §5 residual risk, boundary ⑤).
//
// Standing this up for real against THIS environment requires three changes beyond a param
// flip — which is exactly why it stays design-only (see docs/SECURITY_VALIDATION.md):
//   1. Private DNS zones (privatelink.documents.azure.com, .blob.core.windows.net,
//      .vaultcore.azure.net, .search.windows.net) + VNet links + zone groups — NOT created
//      below; without them the private IPs don't resolve. This module would need them added.
//   2. The Container Apps environment must be VNet-integrated, which can only be set at
//      creation — the running env was not, so it would have to be recreated on the
//      `container-apps` subnet below.
//   3. AI Search must move off the Free SKU (Free rejects private endpoints; needs Basic+).

param baseName string
param location string
param tags object

param cosmosAccountId string
param storageAccountId string
param keyVaultId string
param searchServiceId string

var vnetAddressPrefix = '10.42.0.0/16'
var privateEndpointSubnetPrefix = '10.42.1.0/24'
var containerAppsSubnetPrefix = '10.42.2.0/23' // /23 minimum for Container Apps VNet integration

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${baseName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
    subnets: [
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'container-apps'
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

var peTargets = [
  {
    key: 'cosmos'
    resourceId: cosmosAccountId
    groupId: 'Sql'
  }
  {
    key: 'blob'
    resourceId: storageAccountId
    groupId: 'blob'
  }
  {
    key: 'vault'
    resourceId: keyVaultId
    groupId: 'vault'
  }
  {
    key: 'search'
    resourceId: searchServiceId
    groupId: 'searchService'
  }
]

resource privateEndpoints 'Microsoft.Network/privateEndpoints@2023-11-01' = [
  for t in peTargets: {
    name: '${baseName}-pe-${t.key}'
    location: location
    tags: tags
    properties: {
      subnet: {
        id: '${vnet.id}/subnets/private-endpoints'
      }
      privateLinkServiceConnections: [
        {
          name: '${baseName}-plsc-${t.key}'
          properties: {
            privateLinkServiceId: t.resourceId
            groupIds: [t.groupId]
          }
        }
      ]
    }
  }
]

output vnetId string = vnet.id
output containerAppsSubnetId string = '${vnet.id}/subnets/container-apps'
