# Entra External ID (CIAM) Setup

This guide covers the one-time identity configuration required for frontend authentication (MSAL) and backend token validation. The setup is performed in the Microsoft Entra admin center for the CIAM tenant (see [`ARCHITECTURE.md`](./ARCHITECTURE.md) for details on identity tenant separation).

> **Why this configuration is required:** The Single-Page Application (SPA) needs an access token whose audience (`aud`) matches the API app client ID (`c1f92635…`). An ID token cannot be used because its audience is the SPA's own client ID, which the backend rejects. Exposing a custom scope on the API and granting it to the SPA allows the frontend to acquire the proper API-scoped access token.

## Identity Configuration Overview

| Identifier | Value | Description |
|---|---|---|
| Tenant ID | `cdae0a70-3b69-46b1-abb0-d9957189cbdd` | External ID tenant directory |
| CIAM Domain | `mindgpt` | Resolves to `mindgpt.ciamlogin.com` |
| API App Registration | `c1f92635-804d-4d67-9376-72b4e08080e1` | Backend service (token audience) |
| SPA App Registration | `79f16370-a10e-4851-bf6b-fb5dfbac210d` | React client frontend |

Sign in at **https://entra.microsoft.com** with the account owning the CIAM tenant, and ensure the directory switcher (top right) selects the **MindGPT external tenant** before proceeding.

---

## Part A: Expose a Scope on the API App

Navigate to: **Entra admin center → Applications → App registrations → All applications → select API app (`c1f92635…`).**

1. Go to **Manage → Expose an API**.
2. **Application ID URI**: If not set, click **Add** and accept the default `api://c1f92635-804d-4d67-9376-72b4e08080e1`. Keep the GUID default rather than a custom name so the access token's `aud` claim matches the client ID verified by the backend.
3. Click **Add a scope** and enter:
   - **Scope name:** `access_as_user`
   - **Who can consent:** **Admins and users**
   - **Admin consent display name:** `Access MindGPT API as the signed-in user`
   - **Admin consent description:** `Allows the MindGPT web app to call the MindGPT API on behalf of the signed-in user.`
   - **State:** **Enabled**
   - Click **Add scope**.
4. The full scope string is:
   **`api://c1f92635-804d-4d67-9376-72b4e08080e1/access_as_user`**
   This value corresponds to `VITE_API_SCOPE` in the frontend environment configuration.

> Leave "Authorized client applications" blank; permissions are granted explicitly on the SPA side in Part B for clear auditing.

---

## Part B: Configure the SPA App Registration

Navigate to: **App registrations → select SPA app (`79f16370…`).**

### B1. Redirect URIs (Single-Page Application platform)

1. Go to **Manage → Authentication**.
2. If the platform does not exist yet: click **Add a platform → Single-page application**. (The platform must be "Single-page application" to use PKCE without client secrets, rather than "Web".)
3. Add the redirect URIs:
   - `http://localhost:5173` (local Vite development server).
   - Production URL (e.g. `https://<project>.vercel.app`) once deployed to Vercel.
4. **Front-channel logout URL** (optional): `http://localhost:5173`.
5. Under **Implicit grant and hybrid flows**, leave both "Access tokens" and "ID tokens" **unchecked** (the SPA uses authorization code flow with PKCE).
6. Click **Save**.

### B2. Grant the SPA Permission to the API Scope

1. Go to **Manage → API permissions**.
2. Click **Add a permission → My APIs → select the API app (`c1f92635…`)**.
3. Under **Delegated permissions**, check **`access_as_user`** and click **Add permissions**.
4. Click **Grant admin consent for \<tenant\>** and confirm **Yes**. Verify that the **Status** column displays a green **Granted** badge for `access_as_user`.

---

## Part C: User Flow Configuration (Sign-Up / Sign-In)

The authentication experience (email and password, password reset, and optional social identity providers) is managed by an Entra user flow.

1. Navigate to: **Entra admin center → External Identities → User flows**.
2. If no user flow exists: click **New user flow**, name it (e.g. `mindgpt-signupsignin`), and select the desired identity providers (Email with password as baseline; Google or Microsoft accounts can be added later).
3. Open the user flow → **Applications → Add application**, and select both the SPA (`79f16370…`) and the API app.

---

## Part D: Configuration Checklist

Before running the application, verify that:

1. **Admin Consent:** The status column in the SPA permissions shows **Granted** for `access_as_user`.
2. **Redirect URI:** `http://localhost:5173` is registered with no trailing slash.
3. **Environment Variables:** The frontend `.env` (or Vercel project settings) includes:
   ```env
   VITE_ENTRA_CLIENT_ID=79f16370-a10e-4851-bf6b-fb5dfbac210d
   VITE_ENTRA_AUTHORITY=https://cdae0a70-3b69-46b1-abb0-d9957189cbdd.ciamlogin.com/cdae0a70-3b69-46b1-abb0-d9957189cbdd/v2.0
   VITE_ENTRA_REDIRECT_URI=http://localhost:5173
   VITE_API_SCOPE=api://c1f92635-804d-4d67-9376-72b4e08080e1/access_as_user
   ```

---

## How the Backend Validates Tokens

The backend (`backend/app/auth/entra.py`) validates each incoming bearer token against four criteria:

- **Signature:** Verified against the public keys published in the tenant JWKS endpoint.
- **Issuer:** Pinned to `https://cdae0a70-3b69-46b1-abb0-d9957189cbdd.ciamlogin.com/cdae0a70-3b69-46b1-abb0-d9957189cbdd/v2.0` (the standard OIDC discovery issuer).
- **Audience:** Pinned to `c1f92635-804d-4d67-9376-72b4e08080e1` (the API client ID).
- **Expiration:** Standard token lifetime validation.

Parts A and B ensure that access tokens issued to the SPA contain the exact audience and scope required by the backend security checks.
