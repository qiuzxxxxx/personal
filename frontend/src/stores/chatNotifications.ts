import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getChatUnreadCount, markChatRead } from "@/api/chat";
import { websocketUrl } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import type { ChatMessage } from "@/types";

export const useChatNotificationsStore = defineStore("chat-notifications", () => {
  const auth = useAuthStore();
  const unreadCount = ref(0);
  const viewingChat = ref(false);
  const connected = ref(false);
  const badgeText = computed(() => (unreadCount.value > 99 ? "99+" : String(unreadCount.value)));

  let socket: WebSocket | null = null;
  let reconnectTimer: number | undefined;
  let reconnectAttempts = 0;
  let activeToken = "";
  let stopped = true;
  let markInFlight = false;
  let markAgain = false;

  async function refresh(): Promise<void> {
    if (!auth.isChatUser || !auth.token) {
      unreadCount.value = 0;
      return;
    }
    try {
      unreadCount.value = await getChatUnreadCount();
    } catch {
      // Keep the last known count until the realtime connection recovers.
    }
  }

  async function markAllRead(): Promise<void> {
    unreadCount.value = 0;
    if (!auth.isChatUser || !auth.token) return;
    if (markInFlight) {
      markAgain = true;
      return;
    }

    markInFlight = true;
    try {
      do {
        markAgain = false;
        await markChatRead();
      } while (markAgain);
    } catch {
      await refresh();
    } finally {
      markInFlight = false;
    }
  }

  function setViewingChat(value: boolean): void {
    viewingChat.value = value;
    if (value) void markAllRead();
  }

  function scheduleReconnect(): void {
    if (stopped || !auth.isChatUser || auth.token !== activeToken) return;
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectAttempts += 1;
    const delay = Math.min(1000 * 2 ** Math.min(reconnectAttempts - 1, 4), 15000);
    reconnectTimer = window.setTimeout(connect, delay);
  }

  function handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(String(event.data)) as Record<string, unknown>;
      if (data.type === "message.deleted" || data.type === "conversation.cleared") {
        void refresh();
        return;
      }
      if (data.type !== "message" || !data.message || typeof data.message !== "object") return;
      const message = data.message as ChatMessage;
      if (message.sender_username === auth.user?.username) return;
      if (viewingChat.value) {
        void markAllRead();
      } else {
        unreadCount.value = Math.min(999, unreadCount.value + 1);
      }
    } catch {
      // Ignore malformed realtime frames and resync after reconnecting.
    }
  }

  function connect(): void {
    if (stopped || !activeToken || !auth.isChatUser || auth.token !== activeToken) return;
    if (socket && socket.readyState <= WebSocket.OPEN) return;

    try {
      const current = new WebSocket(websocketUrl("/ws/chat/"), [
        "zixxx.chat",
        `token.${activeToken}`,
      ]);
      socket = current;
      current.onopen = () => {
        if (socket !== current || stopped) return;
        connected.value = true;
        reconnectAttempts = 0;
        void refresh();
      };
      current.onmessage = handleMessage;
      current.onerror = () => {
        connected.value = false;
      };
      current.onclose = (event) => {
        if (socket !== current) return;
        socket = null;
        connected.value = false;
        if (event.code === 4401) {
          stop();
          return;
        }
        scheduleReconnect();
      };
    } catch {
      scheduleReconnect();
    }
  }

  async function start(): Promise<void> {
    if (!auth.isChatUser || !auth.token) {
      stop();
      return;
    }
    if (!stopped && activeToken === auth.token) {
      await refresh();
      connect();
      return;
    }

    stop();
    stopped = false;
    activeToken = auth.token;
    await refresh();
    if (viewingChat.value) await markAllRead();
    connect();
  }

  function stop(): void {
    stopped = true;
    activeToken = "";
    connected.value = false;
    unreadCount.value = 0;
    reconnectAttempts = 0;
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
    const current = socket;
    socket = null;
    current?.close(1000, "stop notifications");
  }

  return {
    unreadCount,
    viewingChat,
    connected,
    badgeText,
    start,
    stop,
    refresh,
    markAllRead,
    setViewingChat,
  };
});
