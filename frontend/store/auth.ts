import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { api, setToken } from "@/services/api";

interface AuthState {
  user: User | null;
  hydrated: boolean;
  setUser: (user: User | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      hydrated: false,
      setUser: (user) => set({ user }),
      login: async (email, password) => {
        const { access_token } = await api.login(email, password);
        setToken(access_token);
        const user = await api.me();
        set({ user });
      },
      register: async (email, password, fullName) => {
        const { access_token } = await api.register(email, password, fullName);
        setToken(access_token);
        const user = await api.me();
        set({ user });
      },
      logout: () => {
        setToken(null);
        set({ user: null });
      },
      fetchMe: async () => {
        try {
          const user = await api.me();
          set({ user });
        } catch {
          setToken(null);
          set({ user: null });
        }
      },
    }),
    {
      name: "voiceai-auth",
      partialize: (s) => ({ user: s.user }),
      onRehydrateStorage: () => () => {
        useAuthStore.setState({ hydrated: true });
      },
    }
  )
);
