import { create } from "zustand";
import Cookies from "js-cookie";
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getUser,
  type UserProfile,
} from "./api";

const TOKEN_KEY = "mw_token";

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  loading: boolean;
  error: string | null;

  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, phone?: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuth = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  loading: true,
  error: null,

  init: async () => {
    const token = Cookies.get(TOKEN_KEY) ?? null;
    if (!token) {
      set({ loading: false, token: null, user: null });
      return;
    }
    try {
      const user = await getUser(token);
      set({ token, user, loading: false });
    } catch {
      Cookies.remove(TOKEN_KEY);
      set({ token: null, user: null, loading: false });
    }
  },

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const res = await apiLogin({ email, password });
      Cookies.set(TOKEN_KEY, res.token, { expires: 30 });
      const user = await getUser(res.token);
      set({ token: res.token, user, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Login failed";
      set({ loading: false, error: msg });
      throw e;
    }
  },

  register: async (email, password, phone) => {
    set({ loading: true, error: null });
    try {
      const res = await apiRegister({ email, password, phone, account_type: "free" });
      Cookies.set(TOKEN_KEY, res.token, { expires: 30 });
      const user = await getUser(res.token);
      set({ token: res.token, user, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Registration failed";
      set({ loading: false, error: msg });
      throw e;
    }
  },

  logout: async () => {
    const { token } = get();
    if (token) {
      try {
        await apiLogout(token);
      } catch {
        // ignore
      }
    }
    Cookies.remove(TOKEN_KEY);
    set({ token: null, user: null, loading: false, error: null });
  },

  clearError: () => set({ error: null }),
}));
