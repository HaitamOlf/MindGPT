// Static Web Apps — React SPA host (ARCHITECTURE.md §4). Free sku: managed TLS + default
// security headers, substituting for Front Door/WAF at the BUILD tier.

param baseName string
param location string
param tags object

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${baseName}-swa'
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    provider: 'GitHub'
    buildProperties: {
      skipGithubActionWorkflowGeneration: true // CI/CD is hand-authored under .github/workflows, not auto-generated
    }
  }
}

output name string = staticWebApp.name
output defaultHostname string = staticWebApp.properties.defaultHostname
