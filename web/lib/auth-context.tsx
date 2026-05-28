'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import { api, setToken, getToken, User } from './api';

const GUEST_ID_KEY = 'xyq_guest_id';

function isGuestEmail(email: string | null | undefined): boolean {
  return !!email && email.startsWith('guest-') && email.endsWith('@xyq.local');
}

function decorateUser(u: User): User {
  return { ...u, is_guest: u.is_guest ?? isGuestEmail(u.email) };
}

function readGuestId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(GUEST_ID_KEY);
  } catch {
    return null;
  }
}

function writeGuestId(id: string | null) {
  if (typeof window === 'undefined') return;
  try {
    if (id) localStorage.setItem(GUEST_ID_KEY, id);
    else localStorage.removeItem(GUEST_ID_KEY);
  } catch {
    /* ignore */
  }
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isGuest: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
  ensureGuest: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const acquireGuest = useCallback(async () => {
    const existingId = readGuestId();
    const resp = await api.guest(existingId);
    setToken(resp.token);
    writeGuestId(resp.guest_id);
    setUser(decorateUser(resp.user));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    const token = getToken();
    if (!token) {
      try {
        await acquireGuest();
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
      return;
    }
    try {
      const u = await api.me();
      setUser(decorateUser(u));
    } catch {
      setToken(null);
      try {
        await acquireGuest();
      } catch {
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, [acquireGuest]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const ensureGuest = useCallback(async () => {
    if (user) return;
    try {
      await acquireGuest();
    } catch {
      /* swallow; caller decides UX */
    }
  }, [user, acquireGuest]);

  const signIn = async (email: string, password: string) => {
    const { token, user } = await api.login(email, password);
    setToken(token);
    writeGuestId(null);
    setUser(decorateUser(user));
  };

  const signUp = async (email: string, password: string) => {
    const { token, user } = await api.signup(email, password);
    setToken(token);
    writeGuestId(null);
    setUser(decorateUser(user));
  };

  const signOut = () => {
    setToken(null);
    writeGuestId(null);
    setUser(null);
    refresh();
  };

  const isGuest = !!user && (user.is_guest ?? isGuestEmail(user.email));

  return (
    <AuthContext.Provider
      value={{ user, loading, isGuest, signIn, signUp, signOut, refresh, ensureGuest }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
