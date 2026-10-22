import React from "react";
import ReactDOM from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { EventType, type AuthenticationResult } from "@azure/msal-browser";
import App from "./App";
// Self-hosted Outfit font (bundled, not from Google's CDN) — reliable offline, faster, and
// no third-party request leaking user IPs. Weights match index.html's former <link>.
import "@fontsource/outfit/300.css";
import "@fontsource/outfit/400.css";
import "@fontsource/outfit/500.css";
import "@fontsource/outfit/600.css";
import "@fontsource/outfit/700.css";
import "./index.css";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import { msalInstance } from "./services/auth";

// MSAL v5 must be initialized before use. We process the redirect response here (before
// render); registering the event callback first ensures the account from an interactive
// sign-in is set active. Note: Entra External ID requires single-tenant app registrations
// (signInAudience = AzureADMyOrg) — a multi-tenant API app yields AADSTS500207 here.
msalInstance.initialize().then(async () => {
  msalInstance.addEventCallback((event) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const payload = event.payload as AuthenticationResult;
      if (payload.account) msalInstance.setActiveAccount(payload.account);
    }
  });

  await msalInstance.handleRedirectPromise();

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    msalInstance.setActiveAccount(accounts[0]);
  }

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <AuthProvider>
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </AuthProvider>
      </MsalProvider>
    </React.StrictMode>
  );
});
