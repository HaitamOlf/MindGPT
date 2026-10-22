// Azure OpenAI — optional (ARCHITECTURE.md §8 "LLM access contingency"). Deployed only
// when deployAzureOpenAI=true; the backend's LLMProvider abstraction falls back to a
// Foundry open model or a local stub when this module is skipped, so a student
// subscription without OpenAI access still deploys the rest of the BUILD tier.

param baseName string
param location string
param tags object

@description('Principal IDs granted Cognitive Services OpenAI User (data-plane inference only).')
param userPrincipalIds array

var accountName = take('${baseName}-aoai', 64)

resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
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

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openai
  name: 'gpt-5-mini'
  sku: {
    // francecentral offers these models only as GlobalStandard (verified against the live
    // model catalog) — plain 'Standard' isn't available here. gpt-4o-mini is retired as of
    // this deployment; gpt-5-mini is the current GA cheap-but-capable chat model.
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openai
  name: 'text-embedding-3-small'
  sku: {
    // francecentral offers gpt-4o-mini / text-embedding-3-small only as GlobalStandard
    // (verified against the live model catalog) — plain 'Standard' isn't available here.
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
  dependsOn: [
    chatDeployment // deployments on the same account must be sequential
  ]
}

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource userRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in userPrincipalIds: {
    name: guid(openai.id, principalId, cognitiveServicesOpenAIUserRoleId)
    scope: openai
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output accountName string = openai.name
output endpoint string = openai.properties.endpoint
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
