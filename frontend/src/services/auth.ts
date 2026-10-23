// Microsoft Entra External ID (CIAM) authentication for the SPA.
// The SPA signs the user in against the CIAM tenant and acquires an ACCESS TOKEN scoped to
// the MindGPT API app, whose `aud` the backend (app/auth/entra.py) validates. An ID token
// would not work — its audience is this SPA's own client ID. See docs/ENTRA_SETUP.md.

import {
  PublicClientApplication,
  InteractionRequiredAuthError,
  BrowserAuthError,
  type Configuration,
  type RedirectRequest,
} from "@azure/msal-browser";

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID as string;
const authority = import.meta.env.VITE_ENTRA_AUTHORITY as string;
const redirectUri = import.meta.env.VITE_ENTRA_REDIRECT_URI as string;
const apiScope = import.meta.env.VITE_API_SCOPE as string;

// The endpoints live on mindgpt.ciamlogin.com while the token issuer is the tenant-ID
// subdomain (verified against the live OIDC discovery doc) — MSAL reads the issuer from
// that host's metadata, so knownAuthorities only needs the authority host.
export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority,
    knownAuthorities: [new URL(authority).host],
    redirectUri,
    postLogoutRedirectUri: redirectUri,
  },
  cache: {
    cacheLocation: "localStorage", // survives reloads; no credentials, only MSAL's own cache
  },
  system: {
    // CIAM silent-renewal iframes can be slow; allow more than the ~6s default before the
    // timeout triggers the interactive-redirect fallback in acquireApiToken().
    iframeHashTimeout: 10000,
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

// Requesting the API scope at sign-in gets consent and a usable access token up front.
// MSAL adds openid/profile/offline_access automatically.
export const loginRequest: RedirectRequest = {
  scopes: [apiScope],
};

const apiRequest = { scopes: [apiScope] };

/**
 * Returns a bearer access token for the MindGPT API. Tries the silent cache/refresh path
 * first; on an interaction-required error it falls back to a full-page redirect (the
 * promise never resolves in that case — the app reloads after sign-in).
 */
export async function acquireApiToken(): Promise<string> {
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
  if (!account) {
    await msalInstance.acquireTokenRedirect(loginRequest);
    throw new Error("Redirecting to sign in");
  }
  try {
    const result = await msalInstance.acquireTokenSilent({ ...apiRequest, account });
    return result.accessToken;
  } catch (error) {
    // Silent acquisition fails not only with interaction_required but also with a hidden-iframe
    // timeout / empty-window error — common with CIAM when third-party cookies are blocked or
    // the authority can't be framed. All are resolved by an interactive redirect, which also
    // (re)obtains consent for the API scope; the SPA reloads out of it rather than dead-ending
    // on a "timed_out" error.
    if (error instanceof InteractionRequiredAuthError || error instanceof BrowserAuthError) {
      await msalInstance.acquireTokenRedirect({ ...apiRequest, account });
      throw new Error("Redirecting to re-authenticate");
    }
    throw error;
  }
}
