// One user-assigned identity per workload (threat model §3 "Elevation of privilege" —
// over-privileged identity reused across services). Created ahead of the workloads that
// use them so RBAC role assignments don't create a circular dependency with Container Apps
// env vars that reference the data-plane endpoints.

@description('Base name used for all identities, e.g. mindgpt-build-x1y2')
param baseName string

param location string
param tags object

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-api-id'
  location: location
  tags: tags
}

resource functionsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-func-id'
  location: location
  tags: tags
}

output apiPrincipalId string = apiIdentity.properties.principalId
output apiClientId string = apiIdentity.properties.clientId
output apiResourceId string = apiIdentity.id

output functionsPrincipalId string = functionsIdentity.properties.principalId
output functionsClientId string = functionsIdentity.properties.clientId
output functionsResourceId string = functionsIdentity.id
