import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { createFocusSession, fetchFocusStats } from "@/api/workspace";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import type { FocusPayload } from "@/types";

const DEFAULT_PLANNED_SECONDS = 25 * 60;
const END_AT_KEY_PREFIX = "nexus.focus.endAtMs";

function storageKeyFor(userId: number | null): string {
  return `${END_AT_KEY_PREFIX}.${userId ?? "anonymous"}`;
}

function readStoredEndAt(key: string): number | null {
  try {
    const value = Number(localStorage.getItem(key));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

function persistEndAt(key: string, endAtMs: number | null): void {
  try {
    if (endAtMs === null) localStorage.removeItem(key);
    else localStorage.setItem(key, String(endAtMs));
  } catch {
    // 禁用 localStorage 时仅影响刷新后恢复，本次会话不受影响。
  }
}

export const useFocusStore = defineStore("focus", () => {
  const auth = useAuthStore();
  const plannedSeconds = ref(DEFAULT_PLANNED_SECONDS);
  const secondsLeft = ref(DEFAULT_PLANNED_SECONDS);
  const running = ref(false);
  const targetTaskId = ref<string | null>(null);
  const stats = ref<FocusPayload | null>(null);
  const loading = ref(false);

  let timer: number | undefined;
  let endAtMs: number | null = null;
  let sessionEpoch = 0;
  // 倒计时按账号隔离存储，避免恢复到其他账号的会话。
  let focusKey = storageKeyFor(auth.user?.id ?? null);

  const formattedTime = computed(() => {
    const minutes = Math.floor(secondsLeft.value / 60);
    const seconds = secondsLeft.value % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  });
  const hasElapsed = computed(() => secondsLeft.value < plannedSeconds.value);
  const targetTitle = computed(() => {
    if (!targetTaskId.value) return "自由专注";
    const workspace = useWorkspaceStore();
    return workspace.tasks.find((task) => task.id === targetTaskId.value)?.title || "自由专注";
  });

  function stopTimer(): void {
    if (timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  }

  // 防后台节流（修正 N5）：不逐秒减 1，而是按 endAtMs 时间戳换算剩余秒数；
  // 后台标签页被节流或切回时都能校准，刷新页面后也能从 localStorage 恢复。
  function syncFromEndAt(): void {
    if (endAtMs === null) return;
    secondsLeft.value = Math.max(0, Math.round((endAtMs - Date.now()) / 1000));
    if (secondsLeft.value <= 0) {
      running.value = false;
      endAtMs = null;
      persistEndAt(focusKey, null);
      stopTimer();
    }
  }

  function tick(): void {
    if (!running.value) return;
    syncFromEndAt();
  }

  function startTimer(): void {
    stopTimer();
    timer = window.setInterval(tick, 500);
  }

  function startOrPause(): void {
    if (running.value) {
      running.value = false;
      endAtMs = null;
      persistEndAt(focusKey, null);
      stopTimer();
      return;
    }
    if (secondsLeft.value <= 0) secondsLeft.value = plannedSeconds.value;
    endAtMs = Date.now() + secondsLeft.value * 1000;
    persistEndAt(focusKey, endAtMs);
    running.value = true;
    startTimer();
  }

  function resetTimer(): void {
    running.value = false;
    endAtMs = null;
    persistEndAt(focusKey, null);
    secondsLeft.value = plannedSeconds.value;
    stopTimer();
  }

  // 刷新页面后恢复未完成的倒计时（还剩时间则继续跑，已过期则停在 0）。
  function restoreFromStorage(): void {
    const stored = readStoredEndAt(focusKey);
    if (stored === null) return;
    const remaining = Math.round((stored - Date.now()) / 1000);
    if (remaining > 0) {
      endAtMs = stored;
      secondsLeft.value = remaining;
      running.value = true;
      startTimer();
    } else {
      persistEndAt(focusKey, null);
      secondsLeft.value = 0;
    }
  }
  restoreFromStorage();

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && running.value) syncFromEndAt();
  });

  async function finishAndLog(): Promise<number> {
    const elapsed = plannedSeconds.value - secondsLeft.value;
    if (elapsed <= 0) return 0;
    const minutes = Math.max(1, Math.round(elapsed / 60));
    await createFocusSession({
      task_id: targetTaskId.value || undefined,
      target_title: targetTitle.value,
      minutes,
    });
    resetTimer();
    await loadStats();
    return minutes;
  }

  async function loadStats(): Promise<void> {
    const epoch = sessionEpoch;
    loading.value = true;
    try {
      const payload = await fetchFocusStats();
      if (epoch !== sessionEpoch) return;
      stats.value = payload;
    } finally {
      if (epoch === sessionEpoch) loading.value = false;
    }
  }

  function reset(): void {
    sessionEpoch += 1;
    stopTimer();
    endAtMs = null;
    // 清理原账号的存储键，再切换到当前账号的键。
    persistEndAt(focusKey, null);
    focusKey = storageKeyFor(auth.user?.id ?? null);
    plannedSeconds.value = DEFAULT_PLANNED_SECONDS;
    secondsLeft.value = DEFAULT_PLANNED_SECONDS;
    running.value = false;
    targetTaskId.value = null;
    stats.value = null;
    loading.value = false;
  }

  return {
    plannedSeconds,
    secondsLeft,
    running,
    targetTaskId,
    stats,
    loading,
    formattedTime,
    hasElapsed,
    targetTitle,
    startOrPause,
    resetTimer,
    finishAndLog,
    loadStats,
    reset,
  };
});
