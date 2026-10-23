# Deployment Guide

This guide explains how MindGPT is deployed to the cloud: the **backend** on Azure Container Apps and the **frontend** on Vercel (see [`ARCHITECTURE.md`](./ARCHITECTURE.md) for details on the frontend hosting architecture).

## 1. Infrastructure Deployment (Bicep)

Deploy the Azure resources using the Azure CLI:

```bash
az deployment sub create \
  --location francecentral \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

This provisions the core cloud infrastructure:
- Managed identities
- Log Analytics workspace and Application Insights
- Azure Key Vault
- Private Azure Blob Storage
- Azure Cosmos DB
- Azure AI Search
- Azure AI Content Safety
- Azure AI Language
- Azure OpenAI (`gpt-5-mini` and `text-embedding-3-small`)
- Azure Container Registry (ACR) and Azure Container Apps

All services use keyless authentication (managed identities and Azure RBAC) rather than shared connection strings. For additional details, see [`../infra/README.md`](../infra/README.md).

## 2. Backend Container Image Deployment

The Container App pulls its image from Azure Container Registry using its system-assigned managed identity (`AcrPull`), avoiding stored registry credentials.

Build and publish the container image directly in ACR:

```bash
az acr build --registry <acrName> --image mindgpt-api:<tag> --platform linux/amd64 --no-logs backend/
```

> **Note on Windows builds:** `--no-logs` avoids character-encoding issues with pip's Unicode progress bar in certain Windows consoles. The Dockerfile also disables progress bars.

Update the container image reference in `infra/main.bicepparam` (`apiContainerImage = '<acrName>.azurecr.io/mindgpt-api:<tag>'`) and redeploy the infrastructure:

```bash
az deployment sub create --location francecentral \
  --template-file infra/main.bicep --parameters infra/main.bicepparam
```

The API will be accessible at the Container App FQDN (`https://<app>.<region>.azurecontainerapps.io`). The service scales down to zero instances when idle to conserve resources.

## 3. Frontend Deployment (Vercel)

The frontend is a static React application built with Vite. It is hosted on Vercel using `frontend/vercel.json` for client-side routing and security headers.

Deploy the application by importing the repository through the Vercel dashboard or by running the Vercel CLI from the `frontend/` directory:

```bash
npm install -g vercel
vercel
```

### Environment Variables

Configure the following environment variables in your Vercel project settings:

| Variable | Value | Description |
|---|---|---|
| `VITE_API_BASE_URL` | Container App FQDN | Backend API endpoint |
| `VITE_ENTRA_CLIENT_ID` | SPA App Registration Client ID | Entra client ID for the frontend |
| `VITE_ENTRA_AUTHORITY` | `https://<ciamDomain>.ciamlogin.com/<tenantId>` | Entra External ID authority URL |
| `VITE_ENTRA_REDIRECT_URI` | Vercel production URL | Callback URL after user sign-in |
| `VITE_API_SCOPE` | `api://<apiClientId>/access_as_user` | Backend API scope requested by the SPA |

### Linking Frontend, Backend, and Identity

After completing the initial Vercel deployment:

1. **Copy the Vercel URL** (e.g. `https://mindgpt.vercel.app`).
2. **Update Entra Redirect URIs:** In the Entra admin center, add the Vercel production URL as a Single-page application redirect URI.
3. **Set Frontend Environment Variables:** In Vercel, assign `VITE_ENTRA_REDIRECT_URI` to the production URL, ensure all environment variables are saved, and trigger a redeployment.
4. **Configure Backend CORS:** In `infra/main.bicepparam`, update `frontendOrigin` with the production Vercel URL and run `az deployment sub create` so the backend accepts requests from the production domain.

## Running Locally with the Cloud Backend

For local development against the deployed cloud backend:

1. Set `VITE_API_BASE_URL` in `frontend/.env` to the Container App FQDN.
2. Run `npm run dev` inside `frontend/`.
3. Ensure `http://localhost:5173` is listed in `frontendOrigin` and in the Entra SPA redirect URIs.
