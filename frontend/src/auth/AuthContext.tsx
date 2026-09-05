/**
 * Authentication state for the whole app.
 *
 * On mount it attempts a silent refresh: if the httpOnly refresh cookie is
 * still valid the user lands back in the app without re-entering credentials.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  api,
  refreshSession,
  request,
  setAccessToken,
  setSessionLostHandler,
} from '@/lib/api';
import type { MeResponse, Permission, SessionResponse, User } from '@/lib/types';
import { toPermissionMap, type PermissionMap } from './permissions';

interface AuthState {
  user: User | null;
  permissions: Permission[];
  permissionMap: PermissionMap;
  mustChangePassword: boolean;
  /** True until the initial silent-refresh attempt settles. */
  initialising: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (
    currentPassword: string,
    newPassword: string,
    confirmPassword: string,
  ) => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [initialising, setInitialising] = useState(true);

  const applySession = useCallback((session: SessionResponse) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    setPermissions(session.permissions);
    setMustChangePassword(session.must_change_password);
  }, []);

  const clear = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setPermissions([]);
    setMustChangePassword(false);
  }, []);

  // Restore a session on first load, and again whenever the API tells us the
  // session is gone for good.
  useEffect(() => {
    let cancelled = false;

    setSessionLostHandler(() => {
      if (!cancelled) clear();
    });

    void (async () => {
      const recovered = await refreshSession();
      if (cancelled) return;
      if (recovered) {
        try {
          const me = await api.get<MeResponse>('/auth/me');
          if (cancelled) return;
          setUser(me.user);
          setPermissions(me.permissions);
          setMustChangePassword(me.must_change_password);
        } catch {
          clear();
        }
      }
      if (!cancelled) setInitialising(false);
    })();

    return () => {
      cancelled = true;
      setSessionLostHandler(null);
    };
  }, [clear]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await request<SessionResponse>('/auth/login', {
        method: 'POST',
        body: { email, password },
        skipRetry: true,
      });
      applySession(session);
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    try {
      await request('/auth/logout', { method: 'POST', withCsrf: true, skipRetry: true });
    } catch {
      // Signing out locally must succeed even if the call fails.
    }
    clear();
  }, [clear]);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string, confirmPassword: string) => {
      const session = await request<SessionResponse>('/auth/change-password', {
        method: 'POST',
        body: {
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword,
        },
      });
      // The server rotates the session on a password change and returns the
      // replacement, so the user is never bounced to the sign-in screen.
      applySession(session);
    },
    [applySession],
  );

  const reload = useCallback(async () => {
    const me = await api.get<MeResponse>('/auth/me');
    setUser(me.user);
    setPermissions(me.permissions);
    setMustChangePassword(me.must_change_password);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      permissions,
      permissionMap: toPermissionMap(permissions),
      mustChangePassword,
      initialising,
      isAuthenticated: user !== null,
      login,
      logout,
      changePassword,
      reload,
    }),
    [user, permissions, mustChangePassword, initialising, login, logout, changePassword, reload],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used inside an <AuthProvider>');
  }
  return context;
}
