import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { getProfile, type Profile } from "../services/api";
import { loginRequest } from "../services/auth";

// The app's view of the signed-in user, derived from the Entra account claims. `id` is the
// stable per-user identifier (localAccountId ≈ the token `sub`/`oid`); display name and
// email come straight from the token.
export type AppUser = {
  id: string;
  name: string;
  email: string;
};

type AuthContextType = {
  user: AppUser | null;
  profile: Profile | null;
  authResolved: boolean;
  profileResolved: boolean;
  hydrating: boolean;
  refreshProfile: () => Promise<void>;
  login: () => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileResolved, setProfileResolved] = useState(false);

  const account = instance.getActiveAccount() ?? accounts[0] ?? null;
  const accountId = account?.localAccountId ?? null;

  const user: AppUser | null = account
    ? {
        id: account.localAccountId,
        name: account.name || account.username?.split("@")[0] || "there",
        email: account.username ?? "",
      }
    : null;

  const refreshProfile = useCallback(async () => {
    if (!accountId) {
      setProfile(null);
      setProfileResolved(true);
      return;
    }
    setProfileResolved(false);
    try {
      setProfile(await getProfile());
    } catch (error) {
      console.error("Error loading profile:", error);
      setProfile(null);
    } finally {
      setProfileResolved(true);
    }
  }, [accountId]);

  useEffect(() => {
    if (inProgress !== "none") return; // wait until MSAL finishes any redirect handling
    if (isAuthenticated && accountId) {
      void refreshProfile();
    } else {
      setProfile(null);
      setProfileResolved(true);
    }
  }, [isAuthenticated, inProgress, accountId, refreshProfile]);

  const login = useCallback(() => {
    void instance.loginRedirect(loginRequest);
  }, [instance]);

  const logout = useCallback(() => {
    void instance.logoutRedirect();
  }, [instance]);

  const authResolved = inProgress === "none";
  const hydrating = inProgress !== "none" || (isAuthenticated && !profileResolved);

  const value: AuthContextType = {
    user,
    profile,
    authResolved,
    profileResolved,
    hydrating,
    refreshProfile,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
