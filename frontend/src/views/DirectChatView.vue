<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowLeft,
  Check,
  Loader2,
  LockKeyhole,
  MessagesSquare,
  Paperclip,
  Send,
  ShieldCheck,
  Wifi,
  WifiOff,
  X,
} from "lucide-vue-next";
import ChatFileCard from "@/components/ChatFileCard.vue";
import FileIcon from "@/components/FileIcon.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { getChatMessages, sendChatMessage, uploadChatFile } from "@/api/chat";
import { extractApiError, websocketUrl } from "@/api/client";
import { dayLabel, formatBytes, formatTime, initials, isSameDay } from "@/lib/format";
import type { ChatMessage, User } from "@/types";

const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();

defineOptions({ name: "DirectChatView" });

const messages = ref<ChatMessage[]>([]);
const loading = ref(true);
const loadError = ref("");
const draft = ref("");
const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const scrollRef = ref<HTMLElement | null>(null);
const wsState = ref<"connecting" | "online" | "offline">("connecting");
const partnerTyping = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const sendingText = ref(false);

const maxFileBytes = 80 * 1024 * 1024;
const allowedExtensions = new Set([
  "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv",
  "png", "jpg", "jpeg", "webp", "gif", "zip", "rar", "7z",
]);
const accept = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp,.gif,.zip,.rar,.7z";

let socket: WebSocket | null = null;
let manuallyClosed = false;
let reconnectTimer: number | undefined;
let reconnectAttempts = 0;
let hasConnected = false;
let typingIdleTimer: number | undefined;
let partnerTypingTimer: number | undefined;
let disposed = false;
let localTyping = false;
let scrollFrame = 0;

const partner = computed(() => auth.partnerName);
const currentUser = computed(() => auth.user?.username || "");
const authorized = computed(() => auth.isChatUser);
const wsOnline = computed(() => wsState.value === "online");
const canSend = computed(
  () => Boolean(draft.value.trim() || selectedFile.value) && !uploading.value && !sendingText.value,
);
const statusLabel = computed(() => {
  if (partnerTyping.value) return "正在输入…";
  if (wsState.value === "online") return "实时连接正常";
  if (wsState.value === "connecting") return "正在连接实时通道…";
  return "连接中断，正在重连";
});

const emptyPrompts = ["嗨，在吗？", "今天过得怎么样？", "我有个东西想给你看。"];

function partnerName(): string {
  return partner.value;
}

function scrollToBottom(smooth = false): void {
  nextTick(() => {
    const element = scrollRef.value;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  });
}

function scheduleScroll(): void {
  if (scrollFrame) return;
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0;
    scrollToBottom(false);
  });
}

function sortMessages(): void {
  messages.value.sort((left, right) => {
    return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
  });
}

function appendMessage(message: ChatMessage): void {
  if (!message?.id) return;
  const index = messages.value.findIndex((item) => item.id === message.id);
  if (index >= 0) messages.value[index] = message;
  else messages.value.push(message);
  sortMessages();
  partnerTyping.value = false;
  scheduleScroll();
}

function mergeServerMessages(items: ChatMessage[]): void {
  const map = new Map<string, ChatMessage>();
  for (const item of items) map.set(item.id, item);
  for (const item of messages.value) {
    if (!map.has(item.id)) map.set(item.id, item);
  }
  messages.value = Array.from(map.values()).sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );
  scheduleScroll();
}

async function loadHistory(initial = false): Promise<void> {
  try {
    const items = await getChatMessages();
    if (disposed) return;
    if (initial) messages.value = items;
    else mergeServerMessages(items);
    loadError.value = "";
    if (initial) {
      nextTick(() => window.setTimeout(() => scrollToBottom(false), 60));
    }
  } catch (error) {
    loadError.value = extractApiError(error);
  } finally {
    if (initial) loading.value = false;
  }
}

function wsSend(payload: Record<string, unknown>): boolean {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  try {
    socket.send(JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

function notifyTyping(): void {
  if (wsState.value !== "online") return;
  if (!localTyping) {
    wsSend({ type: "typing", is_typing: true });
    localTyping = true;
  }
  if (typingIdleTimer) window.clearTimeout(typingIdleTimer);
  typingIdleTimer = window.setTimeout(() => {
    wsSend({ type: "typing", is_typing: false });
    localTyping = false;
  }, 1500);
}

function sendTyping(isTyping: boolean): void {
  if (!isTyping && !localTyping) return;
  wsSend({ type: "typing", is_typing: isTyping });
  localTyping = isTyping;
}

function showPartnerTyping(isTyping: boolean): void {
  partnerTyping.value = isTyping;
  if (partnerTypingTimer) window.clearTimeout(partnerTypingTimer);
  if (isTyping) {
    partnerTypingTimer = window.setTimeout(() => {
      partnerTyping.value = false;
    }, 3000);
  }
}

function handleSocketPayload(data: Record<string, unknown>): void {
  if (data.type === "message" && data.message && typeof data.message === "object") {
    appendMessage(data.message as ChatMessage);
    return;
  }
  if (data.type === "typing" && data.username !== currentUser.value) {
    showPartnerTyping(Boolean(data.is_typing));
    return;
  }
  if (data.type === "error" && typeof data.message === "string") {
    toast.error(data.message);
  }
}

function scheduleReconnect(): void {
  if (disposed || manuallyClosed || !authorized.value) return;
  wsState.value = "offline";
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  reconnectAttempts += 1;
  const delay = Math.min(800 * 2 ** Math.min(reconnectAttempts - 1, 4), 12000);
  reconnectTimer = window.setTimeout(connectSocket, delay);
}

function connectSocket(): void {
  if (disposed || manuallyClosed || !authorized.value || !auth.token) return;
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  wsState.value = "connecting";
  try {
    socket = new WebSocket(websocketUrl("/ws/chat/"), ["zixxx.chat", `token.${auth.token}`]);
  } catch {
    scheduleReconnect();
    return;
  }

  socket.onopen = () => {
    if (disposed) return;
    wsState.value = "online";
    reconnectAttempts = 0;
    void loadHistory(false);
    hasConnected = true;
  };

  socket.onmessage = (event) => {
    if (disposed) return;
    try {
      const data = JSON.parse(event.data) as Record<string, unknown>;
      handleSocketPayload(data);
    } catch {
      // Ignore malformed websocket frames.
    }
  };

  socket.onerror = () => {
    wsState.value = "offline";
  };

  socket.onclose = () => {
    socket = null;
    partnerTyping.value = false;
    localTyping = false;
    if (!manuallyClosed && !disposed) scheduleReconnect();
  };
}

function autoResize(): void {
  const element = textareaRef.value;
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight, 150)}px`;
}

watch(draft, (value) => {
  if (value.trim()) notifyTyping();
  else sendTyping(false);
});

function openFilePicker(): void {
  if (uploading.value) return;
  fileInputRef.value?.click();
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
}

function setFile(file: File | null): void {
  if (!file) {
    selectedFile.value = null;
    return;
  }
  if (!allowedExtensions.has(extensionOf(file.name))) {
    toast.error("暂不支持该文件类型");
    return;
  }
  if (file.size <= 0) {
    toast.error("不能发送空文件");
    return;
  }
  if (file.size > maxFileBytes) {
    toast.error("文件超过 80 MB");
    return;
  }
  selectedFile.value = file;
  nextTick(() => textareaRef.value?.focus());
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  setFile(input.files?.[0] || null);
  input.value = "";
}

function removeFile(): void {
  if (uploading.value) return;
  selectedFile.value = null;
}

function usePrompt(text: string): void {
  draft.value = text;
  nextTick(() => {
    autoResize();
    textareaRef.value?.focus();
  });
}

async function sendViaRest(content: string): Promise<void> {
  sendingText.value = true;
  try {
    const message = await sendChatMessage(content);
    appendMessage(message);
    draft.value = "";
    nextTick(autoResize);
  } catch (error) {
    if (!draft.value) draft.value = content;
    toast.error(extractApiError(error));
  } finally {
    sendingText.value = false;
  }
}

async function sendFileMessage(file: File): Promise<void> {
  const caption = draft.value.trim();
  uploading.value = true;
  uploadProgress.value = 0;
  try {
    const message = await uploadChatFile(file, caption, (percent) => {
      uploadProgress.value = percent;
    });
    appendMessage(message);
    selectedFile.value = null;
    draft.value = "";
    nextTick(autoResize);
    sendTyping(false);
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
  }
}

async function send(): Promise<void> {
  if (!canSend.value) return;
  if (selectedFile.value) {
    await sendFileMessage(selectedFile.value);
    return;
  }
  const content = draft.value.trim();
  if (!content) return;
  sendTyping(false);
  draft.value = "";
  nextTick(autoResize);
  if (wsState.value === "online" && wsSend({ type: "message.send", content })) {
    scrollToBottom(true);
    return;
  }
  await sendViaRest(content);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void send();
  }
}

function showDay(index: number): boolean {
  if (index === 0) return true;
  return !isSameDay(messages.value[index - 1].created_at, messages.value[index].created_at);
}

function goToLogin(): void {
  router.push({ path: "/", query: { redirect: "/chat" } });
}

function goAgent(): void {
  router.push({ name: "agent" });
}

function avatarLetter(user: User | null | undefined): string {
  return initials(user?.username || "N");
}

onMounted(async () => {
  document.title = "双人密聊 · zixxx";
  await auth.initialize();
  if (!authorized.value) {
    loading.value = false;
    return;
  }
  await loadHistory(true);
  connectSocket();
});

// Kept alive across section switches: reconnect or tear down the socket when
// the account changes (e.g. logout) instead of relying on unmount.
watch(authorized, (ok) => {
  if (ok) {
    manuallyClosed = false;
    hasConnected = false;
    messages.value = [];
    connectSocket();
    void loadHistory(false);
  } else {
    manuallyClosed = true;
    sendTyping(false);
    socket?.close(1000, "logout");
    socket = null;
    wsState.value = "offline";
    messages.value = [];
    loading.value = false;
  }
});

onActivated(() => {
  scrollToBottom(false);
});

onBeforeUnmount(() => {
  disposed = true;
  manuallyClosed = true;
  sendTyping(false);
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  if (typingIdleTimer) window.clearTimeout(typingIdleTimer);
  if (partnerTypingTimer) window.clearTimeout(partnerTypingTimer);
  if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
  socket?.close(1000, "leave");
  socket = null;
});
</script>

<template>
  <div class="chat-page relative h-full min-h-0 overflow-hidden p-0 sm:p-4 lg:p-5">
    <div class="chat-aura" aria-hidden="true" />

    <div
      v-if="!authorized"
      class="relative z-10 flex h-full items-center justify-center px-4"
    >
      <div class="w-full max-w-[470px] animate-fade-up rounded-[28px] border border-white/80 bg-white/90 p-8 text-center shadow-float backdrop-blur-xl">
        <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-lg">
          <LockKeyhole :size="23" />
        </span>
        <p class="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-400">Private channel</p>
        <h1 class="mt-2 text-[23px] font-medium tracking-tight text-ink-900">这里是双人专属空间</h1>
        <p class="mt-3 text-[12.5px] leading-6 text-ink-500">
          当前账号 <span class="font-medium text-ink-700">{{ auth.user?.username || "访客" }}</span>
          不具备密聊权限。请使用 qzx 或 sqx 登录，与唯一的对方相连。
        </p>
        <div class="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <button type="button" class="btn-primary" @click="goToLogin">
            <ShieldCheck :size="14" />
            切换账号
          </button>
          <button type="button" class="btn-secondary" @click="goAgent">
            <ArrowLeft :size="14" />
            返回 AI 对话
          </button>
        </div>
      </div>
    </div>

    <div
      v-else
      class="relative z-10 mx-auto flex h-full w-full max-w-[1120px] flex-col overflow-hidden bg-white/82 shadow-[0_24px_80px_-40px_rgba(15,23,42,0.32)] backdrop-blur-xl sm:rounded-[28px] sm:border sm:border-white/90"
    >
      <header class="flex h-[76px] shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/70 px-4 backdrop-blur-xl sm:px-6">
        <div class="relative">
          <span class="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-500 text-[12px] font-semibold text-white shadow-sm">
            {{ partner.slice(0, 1).toUpperCase() }}
          </span>
          <span
            class="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white"
            :class="wsOnline ? 'bg-emerald-400' : 'bg-amber-400'"
          />
        </div>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <h1 class="truncate text-[14px] font-semibold tracking-tight text-ink-900">{{ partner }}</h1>
            <span class="rounded-md bg-slate-100 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-ink-400">Private</span>
          </div>
          <p class="mt-0.5 flex items-center gap-1.5 text-[10px] text-ink-400">
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="partnerTyping ? 'bg-accent-400 animate-pulse' : wsOnline ? 'bg-emerald-400' : 'bg-amber-400'"
            />
            {{ statusLabel }}
          </p>
        </div>

        <div class="ml-auto flex items-center gap-2">
          <span class="hidden items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50/70 px-2.5 py-1.5 text-[9.5px] font-medium text-emerald-700 sm:flex">
            <LockKeyhole :size="10" />
            仅你们二人可见
          </span>
          <span class="flex h-8 w-8 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold text-white" :title="currentUser">
            {{ avatarLetter(auth.user) }}
          </span>
        </div>
      </header>

      <div ref="scrollRef" class="chat-canvas relative min-h-0 flex-1 overflow-y-auto">
        <div v-if="loading" class="mx-auto flex h-full max-w-[860px] flex-col justify-end gap-5 px-5 py-8">
          <div class="h-10 w-48 animate-pulse self-start rounded-3xl bg-slate-200/70" />
          <div class="h-12 w-64 animate-pulse self-end rounded-3xl bg-slate-200/60" />
          <div class="h-10 w-56 animate-pulse self-start rounded-3xl bg-slate-200/50" />
        </div>

        <div v-else-if="loadError && !messages.length" class="flex h-full items-center justify-center px-6 py-12">
          <div class="text-center">
            <span class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-500">
              <WifiOff :size="20" />
            </span>
            <p class="mt-4 text-[13px] font-medium text-ink-700">暂时无法读取消息</p>
            <p class="mt-1.5 max-w-[280px] text-[11px] leading-5 text-ink-400">{{ loadError }}</p>
            <button type="button" class="btn-secondary mt-4 h-9 text-[11px]" @click="loadHistory(true)">重新加载</button>
          </div>
        </div>

        <div v-else-if="!messages.length" class="flex h-full min-h-[420px] flex-col items-center justify-center px-6 py-10">
          <div class="relative">
            <div class="absolute inset-0 rounded-full bg-accent-300/30 blur-2xl" />
            <span class="relative flex h-16 w-16 items-center justify-center rounded-[22px] border border-white bg-white/85 text-accent-500 shadow-soft backdrop-blur">
              <MessagesSquare :size="26" :stroke-width="1.5" />
            </span>
          </div>
          <p class="mt-6 text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-300">A quiet room for two</p>
          <h2 class="mt-2 text-[24px] font-medium tracking-[-0.035em] text-ink-900">
            这里只有你和 {{ partner }}
          </h2>
          <p class="mt-2.5 max-w-[360px] text-center text-[12px] leading-6 text-ink-400">
            消息通过自托管服务器实时送达。发送第一条消息，或者传一个文件给对方。
          </p>
          <div class="mt-6 flex flex-wrap justify-center gap-2">
            <button
              v-for="prompt in emptyPrompts"
              :key="prompt"
              type="button"
              class="rounded-full border border-slate-200/80 bg-white/70 px-3.5 py-2 text-[11px] text-ink-500 shadow-sm transition hover:-translate-y-0.5 hover:border-accent-200 hover:bg-white hover:text-ink-800"
              @click="usePrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
        </div>

        <div v-else class="mx-auto max-w-[860px] px-4 py-6 sm:px-7 sm:py-8">
          <div v-for="(message, index) in messages" :key="message.id">
            <div v-if="showDay(index)" class="mb-6 mt-2 flex items-center gap-3 first:mt-0">
              <span class="h-px flex-1 bg-slate-200/60" />
              <span class="rounded-full bg-white/70 px-2.5 py-1 text-[9px] font-medium tracking-wide text-ink-400 ring-1 ring-slate-200/60">
                {{ dayLabel(message.created_at) }}
              </span>
              <span class="h-px flex-1 bg-slate-200/60" />
            </div>

            <article
              class="mb-4 flex animate-fade-up items-end gap-2.5 sm:gap-3"
              :class="message.sender_username === currentUser ? 'justify-end' : 'justify-start'"
            >
              <span
                v-if="message.sender_username !== currentUser"
                class="mb-5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 text-[9px] font-semibold text-white shadow-sm sm:h-8 sm:w-8"
              >
                {{ initials(message.sender_username) }}
              </span>

              <div
                class="max-w-[82%] sm:max-w-[72%]"
                :class="message.sender_username === currentUser ? 'items-end' : 'items-start'"
              >
                <div v-if="message.message_type === 'text'">
                  <div
                    class="whitespace-pre-wrap break-words px-4 py-2.5 text-[13.5px] leading-[1.72] shadow-sm"
                    :class="
                      message.sender_username === currentUser
                        ? 'rounded-[20px] rounded-br-[6px] bg-ink-900 text-white'
                        : 'rounded-[20px] rounded-bl-[6px] border border-slate-200/70 bg-white text-ink-800'
                    "
                  >{{ message.content }}</div>
                </div>

                <div v-else>
                  <ChatFileCard
                    :message="message"
                    :self="message.sender_username === currentUser"
                  />
                  <div
                    v-if="message.content"
                    class="mt-1.5 inline-block whitespace-pre-wrap break-words px-3.5 py-2 text-[12px] leading-5"
                    :class="
                      message.sender_username === currentUser
                        ? 'rounded-2xl rounded-br-[6px] bg-ink-900 text-white'
                        : 'rounded-2xl rounded-bl-[6px] border border-slate-200/70 bg-white text-ink-700'
                    "
                  >{{ message.content }}</div>
                </div>

                <div
                  class="mt-1 flex items-center gap-1 px-1 text-[8.5px] text-ink-300"
                  :class="message.sender_username === currentUser ? 'justify-end' : 'justify-start'"
                >
                  <span>{{ formatTime(message.created_at) }}</span>
                  <Check v-if="message.sender_username === currentUser" :size="9" class="text-emerald-400" />
                </div>
              </div>
            </article>
          </div>

          <Transition name="fade">
            <div v-if="partnerTyping" class="mb-2 flex items-center gap-2 pl-10">
              <span class="flex items-center gap-1 rounded-full border border-slate-200/70 bg-white/90 px-3 py-1.5 shadow-sm">
                <span class="typing-dot" />
                <span class="typing-dot" style="animation-delay: .15s" />
                <span class="typing-dot" style="animation-delay: .3s" />
              </span>
              <span class="text-[9px] text-ink-400">{{ partner }} 正在输入</span>
            </div>
          </Transition>
        </div>
      </div>

      <div class="shrink-0 border-t border-slate-200/60 bg-white/75 px-3 py-3 backdrop-blur-xl sm:px-5 sm:py-4">
        <div class="mx-auto max-w-[830px]">
          <div
            class="composer-shell rounded-[23px] border bg-white/95 p-2 shadow-[0_18px_50px_-30px_rgba(15,23,42,0.32)] transition duration-200 focus-within:border-accent-300"
            :class="wsOnline ? 'border-slate-200' : 'border-amber-200'"
          >
            <div v-if="selectedFile" class="flex items-center gap-2.5 px-1.5 pb-1.5 pt-1">
              <div class="relative flex min-w-0 flex-1 items-center gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50/80 p-2 pr-8">
                <FileIcon :name="selectedFile.name" :mime="selectedFile.type" size="sm" rounded="rounded-lg" />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[11px] font-medium text-ink-700">{{ selectedFile.name }}</p>
                  <p class="text-[9px] text-ink-400">
                    {{ formatBytes(selectedFile.size) }}
                    <template v-if="uploading"> · 上传中 {{ uploadProgress }}%</template>
                  </p>
                </div>
                <button
                  type="button"
                  class="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-ink-400 transition hover:bg-white hover:text-rose-500"
                  :disabled="uploading"
                  aria-label="移除文件"
                  @click="removeFile"
                >
                  <X :size="13" />
                </button>
                <div v-if="uploading" class="absolute bottom-0 left-2 right-2 h-0.5 overflow-hidden rounded-full bg-slate-200">
                  <div class="h-full rounded-full bg-accent-500 transition-all duration-200" :style="{ width: `${uploadProgress}%` }" />
                </div>
              </div>
            </div>

            <div class="flex items-end gap-2 px-1">
              <button
                type="button"
                class="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-500 transition hover:bg-slate-100 hover:text-ink-900 disabled:opacity-40"
                title="发送文件"
                :disabled="uploading"
                @click="openFilePicker"
              >
                <Paperclip :size="18" :stroke-width="1.9" />
              </button>
              <input
                ref="fileInputRef"
                type="file"
                class="hidden"
                :accept="accept"
                @change="onFileChange"
              />

              <textarea
                ref="textareaRef"
                v-model="draft"
                rows="1"
                class="min-h-[38px] max-h-[150px] min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-[13.5px] leading-6 text-ink-900 outline-none placeholder:text-ink-400"
                :placeholder="`给 ${partner} 发消息…`"
                :disabled="uploading"
                @keydown="onKeydown"
                @input="autoResize"
              />

              <button
                type="button"
                class="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-900 text-white shadow-sm transition hover:bg-accent-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
                :disabled="!canSend"
                aria-label="发送消息"
                @click="send"
              >
                <Loader2 v-if="sendingText || uploading" :size="16" class="animate-spin" />
                <Send v-else :size="16" />
              </button>
            </div>
          </div>

          <div class="mt-2 flex items-center justify-between px-1.5 text-[9px] text-ink-300">
            <span class="flex items-center gap-1.5">
              <Wifi v-if="wsOnline" :size="10" class="text-emerald-400" />
              <WifiOff v-else :size="10" class="text-amber-400" />
              {{ wsOnline ? "WebSocket 实时通道已连接" : "实时通道重连中 · 文件传输不受影响" }}
            </span>
            <span class="hidden sm:block">Enter 发送 · Shift + Enter 换行</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  background:
    radial-gradient(800px 440px at 15% 0%, rgba(100, 133, 255, 0.08), transparent 65%),
    radial-gradient(720px 520px at 90% 100%, rgba(20, 184, 166, 0.06), transparent 65%),
    #f6f8fb;
}

.chat-aura {
  position: absolute;
  top: -260px;
  right: 8%;
  width: 620px;
  height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(125, 211, 252, 0.18), transparent 65%);
  filter: blur(45px);
  pointer-events: none;
}

.chat-canvas {
  background:
    radial-gradient(800px 500px at 50% -20%, rgba(226, 237, 255, 0.45), transparent 65%),
    #fbfcfe;
}

.typing-dot {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: #6c98ff;
  animation: thinking 1.1s ease-in-out infinite;
}
</style>
