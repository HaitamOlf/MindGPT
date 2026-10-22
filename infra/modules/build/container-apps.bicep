// FastAPI API on Container Apps (ARCHITECTURE.md §4). System identity is a user-assigned
// managed identity created up front in managed-identities.bicep so RBAC role assignments on
// every downstream service don't create a dependency cycle with this module's env vars.
//
// Every env var below is an endpoint/name, never a key or connection string — the app
// resolves credentials at runtime via DefaultAzureCredential(managed_identity_client_id=...).
// apiContainerImage defaults to a public placeholder until Phase 3 ships a real image; the
// CI/CD workflow updates it to the built image on deploy.

param baseName string
param location string
param tags object
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param appInsightsConnectionString string
param apiIdentityResourceId string
param apiIdentityClientId string
param containerImage string
@description('ACR login server to pull the image from, via the API managed identity (AcrPull).')
param containerRegistryServer string

param cosmosEndpoint string
param cosmosDatabaseName string
param blobEndpoint string
param searchEndpoint string
param contentSafetyEndpoint string
param languageEndpoint string
@description('Empty string when Azure OpenAI is not deployed — the backend falls back to its Foundry/local provider.')
param openAiEndpoint string
param openAiChatDeployment string
param openAiEmbeddingDeployment string

@description('Allowed CORS origins for the API — the Static Web App\'s hostname.')
param corsAllowedOrigin string

@description('Entra External ID (CIAM) tenant ID. Lives in a separate account/tenant from these resources — docs/ARCHITECTURE.md §11.')
param entraTenantId string
@description('CIAM subdomain, e.g. "mindgpt" for mindgpt.ciamlogin.com.')
param entraCiamDomain string
@description('The API app registration\'s client ID — the expected JWT audience.')
param entraApiClientId string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${baseName}-cae'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      // Pull the image from ACR using the API's managed identity — no registry secret.
      registries: [
        {
          server: containerRegistryServer
          identity: apiIdentityResourceId
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        // CORS is handled by the FastAPI app itself (one authority, pinned to exactly
        // corsAllowedOrigin, PUT included) rather than also at the ingress — two CORS
        // layers would emit duplicate Access-Control-Allow-Origin headers.
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: apiIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'COSMOS_DATABASE_NAME', value: cosmosDatabaseName }
            { name: 'BLOB_ENDPOINT', value: blobEndpoint }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'CONTENT_SAFETY_ENDPOINT', value: contentSafetyEndpoint }
            { name: 'LANGUAGE_ENDPOINT', value: languageEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: openAiChatDeployment }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: openAiEmbeddingDeployment }
            { name: 'CORS_ALLOWED_ORIGIN', value: corsAllowedOrigin }
            { name: 'PROMPT_LOGGING_ENABLED', value: 'false' } // ARCHITECTURE.md §7.4 — off by default
            { name: 'ENTRA_TENANT_ID', value: entraTenantId }
            { name: 'ENTRA_CIAM_DOMAIN', value: entraCiamDomain }
            { name: 'ENTRA_API_CLIENT_ID', value: entraApiClientId }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0 // scale-to-zero stays inside the Consumption free monthly grant
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = api.properties.configuration.ingress.fqdn
output name string = api.name
