// DOCUMENT tier (ARCHITECTURE.md §3/§7) — authored, not deployed by default.
// Microsoft.Security/pricings is a subscription-level resource, so this module targets
// the subscription directly rather than the resource group (unlike the rest of infra/).

targetScope = 'subscription'

@description('Defender plan tier — Standard enables the paid protections; this is DOCUMENT-tier and costs money per resource.')
@allowed(['Standard', 'Free'])
param pricingTier string = 'Standard'

// Plan names must match Defender's pricing-bundle identifiers exactly. Note there is NO
// standalone 'ContainerApps' bundle — the API's Container Apps compute has no dedicated
// Defender plan; its data dependencies (Cosmos, Blob, Key Vault) and the Functions/App
// Service surface are what these plans cover. 'Api' (Defender for APIs) is a possible
// addition now that APIM fronts the API, but it requires per-API onboarding and is left as a
// portal-side follow-up rather than blanket-enabled here.
var defenderPlans = [
  'CosmosDbs'
  'StorageAccounts'
  'KeyVaults'
  'AppServices'
]

resource pricings 'Microsoft.Security/pricings@2024-01-01' = [
  for plan in defenderPlans: {
    name: plan
    properties: {
      pricingTier: pricingTier
    }
  }
]
