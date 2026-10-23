// DOCUMENT tier (ARCHITECTURE.md §3/§7.2) — authored, not deployed by default.
// Edge protection: Front Door + a WAF policy running the OWASP managed ruleset and a
// rate-limit rule, fronting the Container Apps API (and a Static Web App if one exists).
//
// SKU is **Premium_AzureFrontDoor**: managed rule sets (OWASP DRS / Bot Manager) require
// Premium — Standard supports custom rules only. Verified design-only here for a hard reason,
// not just cost: an Azure for Students subscription is *forbidden* from creating Front Door
// resources at all ("Free Trial and Student account is forbidden for Azure Frontdoor
// resources", confirmed on a real deploy attempt 2026-10-22). See docs/SECURITY_VALIDATION.md §2.4.

param baseName string
param location string = 'global'
param tags object

param staticWebAppDefaultHostname string
param containerAppFqdn string

resource wafPolicy 'Microsoft.Network/frontdoorWebApplicationFirewallPolicies@2022-05-01' = {
  name: '${replace(baseName, '-', '')}wafpolicy'
  location: location
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    }
    customRules: {
      rules: [
        {
          name: 'RateLimitPerIP'
          priority: 1
          enabledState: 'Enabled'
          ruleType: 'RateLimitRule'
          rateLimitThreshold: 100
          rateLimitDurationInMinutes: 1
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'Any'
              matchValue: []
            }
          ]
          action: 'Block'
        }
      ]
    }
  }
}

resource profile 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: '${baseName}-fd'
  location: location
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2023-05-01' = {
  parent: profile
  name: '${baseName}-fd-ep'
  location: location
  tags: tags
  properties: {
    enabledState: 'Enabled'
  }
}

resource originGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = {
  parent: profile
  name: 'api-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    healthProbeSettings: {
      probePath: '/health'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = {
  parent: originGroup
  name: 'api-origin'
  properties: {
    hostName: containerAppFqdn
    httpPort: 80
    httpsPort: 443
    originHostHeader: containerAppFqdn
    priority: 1
    weight: 1000
  }
}

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = {
  parent: endpoint
  name: 'api-route'
  properties: {
    originGroup: {
      id: originGroup.id
    }
    supportedProtocols: ['Https']
    patternsToMatch: ['/api/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
  dependsOn: [apiOrigin]
}

// SWA origin/route only when a Static Web App hostname is supplied. This project hosts the
// frontend on Vercel (ARCHITECTURE.md §10), so by default Front Door fronts just the API and
// these are skipped — the module stays deployable with or without an SWA.
resource swaOriginGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = if (!empty(staticWebAppDefaultHostname)) {
  parent: profile
  name: 'swa-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    healthProbeSettings: {
      probePath: '/'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

resource swaOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = if (!empty(staticWebAppDefaultHostname)) {
  parent: swaOriginGroup
  name: 'swa-origin'
  properties: {
    hostName: staticWebAppDefaultHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: staticWebAppDefaultHostname
    priority: 1
    weight: 1000
  }
}

resource swaRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = if (!empty(staticWebAppDefaultHostname)) {
  parent: endpoint
  name: 'swa-route'
  properties: {
    originGroup: {
      id: swaOriginGroup.id
    }
    supportedProtocols: ['Https']
    patternsToMatch: ['/*']
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
  dependsOn: [swaOrigin]
}

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2023-05-01' = {
  parent: profile
  name: 'waf-security-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            {
              id: endpoint.id
            }
          ]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

output endpointHostname string = endpoint.properties.hostName
