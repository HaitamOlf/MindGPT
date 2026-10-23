// DOCUMENT tier (ARCHITECTURE.md §3/§7.2) — authored, not deployed by default.
//
// A secured edge gateway in front of the Container Apps API. Its primary control is
// **edge authentication**: validate-jwt checks the Entra External ID (CIAM) token at the
// gateway before a request ever reaches the backend — defense in depth with the backend's
// own JWT validation. CORS is pinned to the SPA origin(s). Because the SPA already sends a
// bearer JWT, routing it through APIM is a pure base-URL change — no API key in the browser
// bundle (which is why subscriptionRequired is false).
//
// Rate limiting is deliberately NOT enforced here: the Consumption SKU supports neither
// `rate-limit-by-key` nor, without a subscription, a keyed counter — so DoS throttling stays
// in-app at the BUILD tier (THREAT_MODEL.md "Denial of service"). A per-key APIM quota is a
// higher-SKU upgrade, noted rather than faked.

param baseName string
param location string
param tags object

param publisherEmail string
param publisherName string = 'MindGPT'
param containerAppFqdn string

@description('Entra External ID (CIAM) tenant GUID — the token issuer validate-jwt trusts.')
param entraTenantId string
@description('CIAM domain label, e.g. "mindgpt" for mindgpt.ciamlogin.com.')
param entraCiamDomain string
@description('API app registration (client) ID — the expected token audience.')
param entraApiClientId string
@description('Comma-separated SPA origins allowed through CORS (e.g. the Vercel URL + localhost).')
param frontendOrigins string

var openIdConfigUrl = 'https://${entraCiamDomain}.ciamlogin.com/${entraTenantId}/v2.0/.well-known/openid-configuration'
var corsOriginsXml = join(map(split(frontendOrigins, ','), origin => '        <origin>${trim(origin)}</origin>'), '\n')

// CORS (handles OPTIONS preflight) + validate-jwt at the edge. No `@()` expressions here, so
// there are no policy-expression escaping concerns.
var apiPolicyXml = '<policies>\n  <inbound>\n    <cors allow-credentials="false">\n      <allowed-origins>\n${corsOriginsXml}\n      </allowed-origins>\n      <allowed-methods>\n        <method>GET</method>\n        <method>POST</method>\n        <method>PUT</method>\n        <method>DELETE</method>\n        <method>OPTIONS</method>\n      </allowed-methods>\n      <allowed-headers>\n        <header>Authorization</header>\n        <header>Content-Type</header>\n      </allowed-headers>\n    </cors>\n    <validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized. A valid Entra token is required.">\n      <openid-config url="${openIdConfigUrl}" />\n      <audiences>\n        <audience>api://${entraApiClientId}</audience>\n        <audience>${entraApiClientId}</audience>\n      </audiences>\n    </validate-jwt>\n    <base />\n  </inbound>\n  <backend>\n    <base />\n  </backend>\n  <outbound>\n    <base />\n  </outbound>\n  <on-error>\n    <base />\n  </on-error>\n</policies>'

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: '${baseName}-apim'
  location: location
  tags: tags
  sku: {
    name: 'Consumption'
    capacity: 0
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'mindgpt-api'
  properties: {
    displayName: 'MindGPT API'
    path: 'api'
    protocols: ['https']
    serviceUrl: 'https://${containerAppFqdn}'
    // Auth is the Entra JWT (validate-jwt below), not a subscription key — so a public SPA
    // needs no secret in its bundle.
    subscriptionRequired: false
  }
}

// APIM only routes paths that match a defined operation, so catch-all operations per method
// are what let the gateway front the whole backend. In a full build these would be imported
// from the backend's OpenAPI spec; the wildcards keep the module self-contained.
var catchAllMethods = ['GET', 'POST', 'PUT', 'DELETE']
resource catchAllOps 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [
  for method in catchAllMethods: {
    parent: api
    name: '${toLower(method)}-all'
    properties: {
      displayName: '${method} (catch-all)'
      method: method
      urlTemplate: '/*'
    }
  }
]

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: api
  name: 'policy'
  dependsOn: [catchAllOps]
  properties: {
    format: 'rawxml'
    value: apiPolicyXml
  }
}

output gatewayUrl string = apim.properties.gatewayUrl
