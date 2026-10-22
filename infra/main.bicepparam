using 'main.bicep'

param projectName = 'mindgpt'
param environmentName = 'build'
param location = 'francecentral'
param staticWebAppLocation = 'westeurope'
param deployStaticWebApp = false
param frontendOrigin = 'https://mindgpt-h8am.vercel.app,http://localhost:5173'
param deployDocumentTier = false
param deployAzureOpenAI = true
param apiContainerImage = 'acrrdye3f7vd4bkg.azurecr.io/mindgpt-api:6'
param searchSkuName = 'free'

// Entra External ID (CIAM) — separate personal-account tenant, docs/ARCHITECTURE.md §11.
param entraTenantId = 'cdae0a70-3b69-46b1-abb0-d9957189cbdd'
param entraCiamDomain = 'mindgpt'
param entraApiClientId = 'c1f92635-804d-4d67-9376-72b4e08080e1'
