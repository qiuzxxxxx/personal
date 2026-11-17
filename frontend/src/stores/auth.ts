import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchMe, loginRequest, logoutRequest } from "@/api/auth";
import {
  getStoredToken,
  getStoredUser,
  setStoredToken,
  setStoredUser,
} from "@/api/client";
import type { User } from "@/types";

function isUser(value: unknown): value is User {
  return Boolean(value && typeof value === "object" && "username" in value);
}

export const useAuthStore = defineStore("auth", () => {
  const initialUser = getStoredUser();
  const token = ref(getStoredToken());
  const user = ref<User | null>(isUser(initialUser) ? initialUser : null);
  const initialized = ref(false);
  const loading = ref(false);
  let initialization: Promise<void> | null = null;

  const isAuthenticated = computed(() => Boolean(token.value && user.value));
  const isQzx = computed(() => user.value?.username === "qzx");
  const isAdmin = computed(() => Boolean(user.value?.is_admin));
  const isSuper = computed(() => Boolean(user.value?.is_super));
  const isGuest = computed(() => Boolean(user.value?.is_guest));
  const isChatUser = computed(() => Boolean(user.value?.is_chat_user));
  const partnerName = computed(() =>
    user.value?.username === "qzx" ? "sqx" : "qzx",
  );

  function persist(): void {
    setStoredToken(token.value);
    setStoredUser(user.value);
  }

  function clear(): void {
    token.value = "";
    user.value = null;
    initialized.value = true;
    setStoredToken("");
    setStoredUser(null);
  }

  async function initialize(force = false): Promise<void> {
    if (initialization) return initialization;
    if (initialized.value && !force) return;
    if (!token.value) {
      initialized.value = true;
      user.value = null;
      return;
    }
    initialization = (async () => {
      const initializingToken = token.value;
      try {
        const fetchedUser = await fetchMe();
        if (token.value !== initializingToken) return;
        user.value = fetchedUser;
        persist();
      } catch {
        if (token.value === initializingToken) clear();
      } finally {
        initialized.value = true;
        initialization = null;
      }
    })();
    return initialization;
  }

  async function login(username: string, password: string): Promise<User> {
    loading.value = true;
    try {
      const response = await loginRequest(username, password);
      token.value = response.token;
      user.value = response.user;
      initialized.value = true;
      persist();
      return response.user;
    } finally {
      loading.value = false;
    }
  }

  async function logout(): Promise<void> {
    const logoutToken = token.value;
    clear();
    try {
      if (logoutToken) await logoutRequest(logoutToken);
    } catch {
      // A local logout must still succeed if the token already expired.
    }
  }

  return {
    token,
    user,
    initialized,
    loading,
    isAuthenticated,
    isQzx,
    isAdmin,
    isSuper,
    isGuest,
    isChatUser,
    partnerName,
    initialize,
    login,
    logout,
    clear,
  };
});
