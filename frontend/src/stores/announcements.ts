import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  getAnnouncementHistory,
  getLoginAnnouncement,
  getTransferAnnouncement,
} from "@/api/transfer";
import type { AnnouncementHistoryItem } from "@/types";

/**
 * 站点公告是公开数据：登录页弹窗与登录后的侧边栏入口共用同一份缓存，
 * 避免两个页面各自请求、内容不一致。
 */
const SEEN_STORAGE_KEY = "nexus.announcements.seen";

function readSeenId(): number {
  try {
    return Number(localStorage.getItem(SEEN_STORAGE_KEY)) || 0;
  } catch {
    return 0;
  }
}

export const useAnnouncementStore = defineStore("announcements", () => {
  const loginContent = ref("");
  const stationContent = ref("");
  const loginUpdatedAt = ref<string | null>(null);
  const stationUpdatedAt = ref<string | null>(null);
  const loaded = ref(false);
  const history = ref<AnnouncementHistoryItem[]>([]);
  const historyLoaded = ref(false);
  const lastSeenId = ref(readSeenId());
  let loading: Promise<void> | null = null;
  let historyLoading: Promise<void> | null = null;

  const hasLogin = computed(() => Boolean(loginContent.value.trim()));
  const hasStation = computed(() => Boolean(stationContent.value.trim()));
  const hasAny = computed(() => hasLogin.value || hasStation.value);
  const hasHistory = computed(() => history.value.length > 0);

  const latestHistoryItem = computed(() => history.value[0] ?? null);
  const hasUnread = computed(
    () =>
      Boolean(latestHistoryItem.value) &&
      (latestHistoryItem.value?.id ?? 0) > lastSeenId.value,
  );

  /** Header shows the newest currently published announcement. */
  const latestCurrent = computed(() => {
    const login = hasLogin.value
      ? { kind: "login" as const, content: loginContent.value, updatedAt: loginUpdatedAt.value || "" }
      : null;
    const station = hasStation.value
      ? { kind: "transfer" as const, content: stationContent.value, updatedAt: stationUpdatedAt.value || "" }
      : null;
    if (login && station) {
      return login.updatedAt >= station.updatedAt ? login : station;
    }
    return login || station;
  });

  function markSeen(): void {
    const latest = latestHistoryItem.value;
    if (!latest || latest.id <= lastSeenId.value) return;
    lastSeenId.value = latest.id;
    try {
      localStorage.setItem(SEEN_STORAGE_KEY, String(latest.id));
    } catch {
      // 浏览器禁用本地存储时，本次会话仍会通过内存状态记住已读。
    }
  }

  async function load(force = false): Promise<void> {
    if (loading) return loading;
    if (loaded.value && !force) return;
    loading = (async () => {
      const [loginResult, stationResult] = await Promise.allSettled([
        getLoginAnnouncement(),
        getTransferAnnouncement(),
      ]);
      let succeeded = false;
      if (loginResult.status === "fulfilled") {
        loginContent.value = loginResult.value.content ?? "";
        loginUpdatedAt.value = loginResult.value.updated_at ?? null;
        succeeded = true;
      }
      if (stationResult.status === "fulfilled") {
        stationContent.value = stationResult.value.content ?? "";
        stationUpdatedAt.value = stationResult.value.updated_at ?? null;
        succeeded = true;
      }
      // 两个接口都失败时不标记已加载，下次挂载或手动打开还能重试。
      loaded.value = succeeded;
    })().finally(() => {
      loading = null;
    });
    return loading;
  }

  async function loadHistory(force = false): Promise<void> {
    if (historyLoading) return historyLoading;
    if (historyLoaded.value && !force) return;
    historyLoading = (async () => {
      try {
        history.value = await getAnnouncementHistory();
        historyLoaded.value = true;
      } catch {
        // 历史公告读取失败时保留已有缓存，下次打开再重试。
      }
    })().finally(() => {
      historyLoading = null;
    });
    return historyLoading;
  }

  function reset(): void {
    loginContent.value = "";
    stationContent.value = "";
    loginUpdatedAt.value = null;
    stationUpdatedAt.value = null;
    loaded.value = false;
    history.value = [];
    historyLoaded.value = false;
  }

  return {
    loginContent,
    stationContent,
    loginUpdatedAt,
    stationUpdatedAt,
    loaded,
    history,
    historyLoaded,
    lastSeenId,
    hasLogin,
    hasStation,
    hasAny,
    hasHistory,
    hasUnread,
    latestHistoryItem,
    latestCurrent,
    load,
    loadHistory,
    markSeen,
    reset,
  };
});
