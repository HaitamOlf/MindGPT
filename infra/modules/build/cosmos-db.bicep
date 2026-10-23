// Cosmos DB for NoSQL (ARCHITECTURE.md §7.3 — closes v1 F06). disableLocalAuth kills the
// master-key auth path entirely; data-plane access is Entra RBAC only, and every container
// is partitioned by /userId so cross-user reads require a different partition key, not just
// a different query — authorization is still enforced server-side (THREAT_MODEL.md Tampering).

param baseName string
param location string
param tags object

@description('Principal IDs granted the Cosmos DB Built-in Data Contributor role.')
param dataContributorPrincipalIds array

var accountName = take('${baseName}-cosmos', 44)

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: true
    disableLocalAuth: true // no primary/secondary keys usable — Entra RBAC only
    disableKeyBasedMetadataWriteAccess: true
    publicNetworkAccess: 'Enabled' // BUILD tier: no Private Endpoints yet (see ARCHITECTURE.md §3 DOCUMENT gap)
    minimalTlsVersion: 'Tls12'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: []
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'mindgpt'
  properties: {
    resource: {
      id: 'mindgpt'
    }
  }
}

resource conversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      defaultTtl: -1 // retention enforced explicitly by app logic / Functions cleanup, not a blanket TTL
    }
  }
}

resource memoryContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'memory'
  properties: {
    resource: {
      id: 'memory'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

// One profile document per user (id == userId), holding the self-reported fullName / date
// of birth / country the account dashboard shows. Partitioned by /userId like every other
// container so a profile read can only ever touch the caller's own partition.
resource profileContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'profile'
  properties: {
    resource: {
      id: 'profile'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

// Daily wellness aggregates (one doc per user per day, id == the YYYY-MM-DD date) powering
// the dashboard's wellness trend. Stores only a derived sentiment average, never message
// text (data minimization — ARCHITECTURE.md §7.4).
resource wellnessContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'wellness'
  properties: {
    resource: {
      id: 'wellness'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

// Built-in "Cosmos DB Built-in Data Contributor" role — a Cosmos-native SQL role, distinct
// from Microsoft.Authorization roles; must be assigned via sqlRoleAssignments.
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource dataRoleAssignments 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = [
  for principalId in dataContributorPrincipalIds: {
    parent: cosmos
    name: guid(cosmos.id, principalId, cosmosDataContributorRoleId)
    properties: {
      roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
      principalId: principalId
      scope: cosmos.id
    }
  }
]

output accountName string = cosmos.name
output accountId string = cosmos.id
output endpoint string = cosmos.properties.documentEndpoint
output databaseName string = database.name
