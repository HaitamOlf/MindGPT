# frontend/ — React + TypeScript + Vite (Microsoft Entra External ID)

The MindGPT web client. Sign-in is **Microsoft Entra External ID (MSAL)** and all data
access is **API-only** — the browser never talks to a database directly, and never handles
credentials itself.

## Auth & data model

- **Sign-in:** MSAL (`@azure/msal-browser` + `@azure/msal-react`) redirects to the CIAM
  hosted sign-in flow. The app never handles credentials itself (no password fields). See
  [`../docs/ENTRA_SETUP.md`](../docs/ENTRA_SETUP.md) for the tenant/app config.
- **API calls:** every request carries an Entra **access token** scoped to the MindGPT API
  (`services/auth.ts` → `acquireApiToken`), which the backend validates. All data —
  conversations, profile, memory, wellness — goes through the FastAPI backend
  (`services/api.ts`); there is no client-side database SDK.
- **Identity in the UI:** display name/email come from the token claims; the profile
  (name/DOB/country) is stored via `PUT /profile`.

## Key files

```
src/
├─ services/
│  ├─ auth.ts     # MSAL config + acquireApiToken (access token for the API)
│  └─ api.ts      # typed backend client; attaches the bearer token per call
├─ context/
│  └─ AuthContext.tsx  # wraps MSAL; exposes user (from claims), profile, login/logout
├─ components/
│  ├─ Auth.tsx           # single "Sign in" button → MSAL redirect
│  ├─ ProfileSetup.tsx   # first-run profile → PUT /profile
│  ├─ Chat.tsx           # chat UI (text + image upload, with preview/zoom)
│  ├─ Sidebar.tsx        # conversation list (GET/DELETE /conversations)
│  ├─ TopBar.tsx         # display name + dashboard entry
│  └─ AccountDashboard.tsx  # profile, memory bank, wellness trend (all API-backed)
└─ main.tsx       # initializes MSAL, wraps the app in MsalProvider
```

## Running locally

```bash
cd frontend
npm install
cp .env.example .env    # already contains the real public CIAM identifiers + API scope
npm run dev             # http://localhost:5173 (the registered redirect URI)
```

`.env` needs `VITE_API_BASE_URL` pointing at a running backend (e.g. `http://localhost:8000`).
A real end-to-end sign-in needs the CIAM config in `../docs/ENTRA_SETUP.md` completed
(admin consent granted) and the backend reachable.

## Notes

- **No guest/anonymous sessions.** Every request to the backend requires a valid Entra
  JWT, so there is no anonymous mode — sign-in (or sign-up) is required. Social providers
  (e.g. Google) can be enabled as federated identity providers on the CIAM user flow
  without any app-code change (see `../docs/ENTRA_SETUP.md`).
- **The Outfit font is self-hosted** (`@fontsource/outfit`), not loaded from a third-party
  CDN — reliable offline and no user IPs leaked to a font host.

## Build

```bash
npm run build    # tsc -b && vite build — type-checks the whole app
```
