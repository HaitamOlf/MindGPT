// MindGPT — IaC entry point.
// Subscription-scoped: creates the resource group, then composes the BUILD-tier modules
// (deployed) and, when deployDocumentTier=true, the DOCUMENT-tier modules (authored but
// not deployed by default — see docs/ARCHITECTURE.md §3 and infra/README.md).

targetScope = 'subscription'

@description('Short project name used throughout resource naming.')
param projectName string = 'mindgpt'

@allowed(['build', 'document'])
@description('Deployment environment label, also used in resource naming.')
param environmentName string = 'build'

@description('Azure region for most resources. AI services (OpenAI, Content Safety, Language, Search) must all be available in this region.')
param location string = 'francecentral'

@description('Azure region for the Static Web App. Microsoft.Web/staticSites only supports a small fixed region list (centralus, eastus2, westus2, westeurope, eastasia) independent of `location` — see infra/README.md.')
param staticWebAppLocation string = 'westeurope'

@description('Deploy the Static Web App. Default false: on subscriptions with an "Allowed resource deployment regions" policy that doesn\'t include any Static Web Apps region (e.g. this one — see infra/README.md "Static Web Apps region conflict"), this resource cannot be created at all, in any region. Flip on only where allowed.')
param deployStaticWebApp bool = false

@description('Frontend origin for API CORS when deployStaticWebApp=false — e.g. the local dev server, or wherever the SPA ends up hosted. Ignored once deployStaticWebApp=true (the Static Web App\'s own hostname is used instead).')
param frontendOrigin string = 'http://localhost:5173'

@description('Deploy the DOCUMENT-tier resources (Front Door/WAF, APIM, VNet+Private Endpoints, Defender plans). Design-only by default — costs money, not covered by student free-tier SKUs.')
param deployDocumentTier bool = false

@description('Deploy Azure OpenAI. May not be provisionable on a student subscription (docs/ARCHITECTURE.md §8) — the backend falls back to its Foundry/local LLMProvider when false.')
param deployAzureOpenAI bool = false

@description('Container image for the FastAPI API. Placeholder until Phase 3 ships a real image; the deploy workflow overrides this on every push to main.')
param apiContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@allowed(['free', 'basic', 'standard'])
param searchSkuName string = 'free'

@description('Publisher email for APIM (DOCUMENT tier only, required by the resource provider).')
param apimPublisherEmail string = 'haitam.oualif@gmail.com'

@description('Entra External ID (CIAM) tenant ID — lives in a separate account from this subscription; see docs/ARCHITECTURE.md §11. Empty disables real auth (app/auth/ will reject every request).')
param entraTenantId string = ''
@description('CIAM subdomain, e.g. "mindgpt" for mindgpt.ciamlogin.com.')
param entraCiamDomain string = ''
@description('The API app registration\'s client ID — the expected JWT audience.')
param entraApiClientId string = ''

var tags = {
  project: 'mindgpt'
  environment: environmentName
  managedBy: 'bicep'
}

var resourceToken = toLower(uniqueString(subscription().id, projectName, environmentName))
var baseName = '${projectName}-${environmentName}-${resourceToken}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${projectName}-${environmentName}-rg'
  location: location
  tags: tags
}

module identities 'modules/build/managed-identities.bicep' = {
  name: 'identities'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
  }
}

module logAnalytics 'modules/build/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
  }
}

module keyVault 'modules/build/key-vault.bicep' = {
  name: 'key-vault'
  scope: rg
  params: {
    resourceToken: resourceToken
    location: location
    tags: tags
    readerPrincipalIds: [identities.outputs.apiPrincipalId, identities.outputs.functionsPrincipalId]
  }
}

module storage 'modules/build/storage-blob.bicep' = {
  name: 'storage-blob'
  scope: rg
  params: {
    resourceToken: resourceToken
    location: location
    tags: tags
    contributorPrincipalIds: [identities.outputs.apiPrincipalId, identities.outputs.functionsPrincipalId]
  }
}

module cosmos 'modules/build/cosmos-db.bicep' = {
  name: 'cosmos-db'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    dataContributorPrincipalIds: [identities.outputs.apiPrincipalId, identities.outputs.functionsPrincipalId]
  }
}

module search 'modules/build/ai-search.bicep' = {
  name: 'ai-search'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    skuName: searchSkuName
    dataContributorPrincipalIds: [identities.outputs.apiPrincipalId]
  }
}

module contentSafety 'modules/build/content-safety.bicep' = {
  name: 'content-safety'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    userPrincipalIds: [identities.outputs.apiPrincipalId]
  }
}

module language 'modules/build/ai-language.bicep' = {
  name: 'ai-language'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    userPrincipalIds: [identities.outputs.apiPrincipalId]
  }
}

module openai 'modules/build/openai.bicep' = if (deployAzureOpenAI) {
  name: 'openai'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    userPrincipalIds: [identities.outputs.apiPrincipalId]
  }
}

module staticWebApp 'modules/build/static-web-app.bicep' = if (deployStaticWebApp) {
  name: 'static-web-app'
  scope: rg
  params: {
    baseName: baseName
    location: staticWebAppLocation
    tags: tags
  }
}

module containerRegistry 'modules/build/container-registry.bicep' = {
  name: 'container-registry'
  scope: rg
  params: {
    resourceToken: resourceToken
    location: location
    tags: tags
    pullPrincipalIds: [identities.outputs.apiPrincipalId]
  }
}

module containerApps 'modules/build/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    containerRegistryServer: containerRegistry.outputs.loginServer
    logAnalyticsCustomerId: logAnalytics.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalytics.outputs.logAnalyticsSharedKey
    appInsightsConnectionString: logAnalytics.outputs.appInsightsConnectionString
    apiIdentityResourceId: identities.outputs.apiResourceId
    apiIdentityClientId: identities.outputs.apiClientId
    containerImage: apiContainerImage
    cosmosEndpoint: cosmos.outputs.endpoint
    cosmosDatabaseName: cosmos.outputs.databaseName
    blobEndpoint: storage.outputs.primaryBlobEndpoint
    searchEndpoint: search.outputs.endpoint
    contentSafetyEndpoint: contentSafety.outputs.endpoint
    languageEndpoint: language.outputs.endpoint
    openAiEndpoint: deployAzureOpenAI ? openai!.outputs.endpoint : ''
    openAiChatDeployment: deployAzureOpenAI ? openai!.outputs.chatDeploymentName : ''
    openAiEmbeddingDeployment: deployAzureOpenAI ? openai!.outputs.embeddingDeploymentName : ''
    corsAllowedOrigin: deployStaticWebApp ? 'https://${staticWebApp!.outputs.defaultHostname}' : frontendOrigin
    entraTenantId: entraTenantId
    entraCiamDomain: entraCiamDomain
    entraApiClientId: entraApiClientId
  }
}

module functionApp 'modules/build/function-app.bicep' = {
  name: 'function-app'
  scope: rg
  params: {
    baseName: baseName
    resourceToken: resourceToken
    location: location
    tags: tags
    functionsIdentityResourceId: identities.outputs.functionsResourceId
    functionsIdentityPrincipalId: identities.outputs.functionsPrincipalId
    functionsIdentityClientId: identities.outputs.functionsClientId
    appInsightsConnectionString: logAnalytics.outputs.appInsightsConnectionString
    cosmosEndpoint: cosmos.outputs.endpoint
    cosmosDatabaseName: cosmos.outputs.databaseName
    blobEndpoint: storage.outputs.primaryBlobEndpoint
  }
}

// DOCUMENT tier — authored for completeness (ARCHITECTURE.md §3), deployed only if/when
// budget allows. Each module is independently toggled by deployDocumentTier; none of them
// run against the free/low-cost student credits this project otherwise relies on.
module vnetPrivateEndpoints 'modules/document/vnet-private-endpoints.bicep' = if (deployDocumentTier) {
  name: 'document-vnet-pe'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    cosmosAccountId: cosmos.outputs.accountId
    storageAccountId: storage.outputs.storageAccountId
    keyVaultId: keyVault.outputs.keyVaultId
    searchServiceId: search.outputs.searchServiceId
  }
}

module frontDoorWaf 'modules/document/front-door-waf.bicep' = if (deployDocumentTier) {
  name: 'document-front-door-waf'
  scope: rg
  params: {
    baseName: baseName
    tags: tags
    staticWebAppDefaultHostname: deployStaticWebApp ? staticWebApp!.outputs.defaultHostname : ''
    containerAppFqdn: containerApps.outputs.fqdn
  }
}

module apim 'modules/document/apim.bicep' = if (deployDocumentTier) {
  name: 'document-apim'
  scope: rg
  params: {
    baseName: baseName
    location: location
    tags: tags
    publisherEmail: apimPublisherEmail
    containerAppFqdn: containerApps.outputs.fqdn
    entraTenantId: entraTenantId
    entraCiamDomain: entraCiamDomain
    entraApiClientId: entraApiClientId
    frontendOrigins: frontendOrigin
  }
}

module defender 'modules/document/defender.bicep' = if (deployDocumentTier) {
  name: 'document-defender'
}

output resourceGroupName string = rg.name
output apiFqdn string = containerApps.outputs.fqdn
output staticWebAppHostname string = deployStaticWebApp ? staticWebApp!.outputs.defaultHostname : ''
output keyVaultUri string = keyVault.outputs.keyVaultUri
output cosmosEndpoint string = cosmos.outputs.endpoint
output searchEndpoint string = search.outputs.endpoint
