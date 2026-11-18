<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Settings2,
  Sparkles,
  FileText,
  Image as ImageIcon,
  Code2,
  BrainCircuit,
  Copy,
  Check,
  Loader2,
  Square,
  CircleAlert,
  ArrowUpRight,
  Plus,
  ShieldCheck,
  HardDriveUpload,
  LogIn,
  BookPlus,
  History,
  Trash2,
} from "lucide-vue-next";
import BrandMark from "@/components/BrandMark.vue";
import ModalShell from "@/components/ModalShell.vue";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";
import MultimodalInput from "@/components/MultimodalInput.vue";
import ApiConfigModal from "@/components/ApiConfigModal.vue";
import KnowledgeScopeBar from "@/components/KnowledgeScopeBar.vue";
import { useAgentStore } from "@/stores/agent";
import { useAuthStore } from "@/stores/auth";
import { useConfigStore } from "@/stores/config";
import { useToastStore } from "@/stores/toast";
import { useKnowledgeStore } from "@/stores/knowledge";
import { uploadAgentAttachment, streamAgentChat } from "@/api/agent";
import { importKnowledge } from "@/api/knowledge";
import { extractApiError } from "@/api/client";
import { copyText } from "@/lib/markdown";
import { formatTime } from "@/lib/format";
import { providerLabel } from "@/lib/providers";
import type { AgentMessage, AgentStreamEvent, ConversationSummary, KnowledgeScope, KnowledgeSourceRef } from "@/types";

interface Suggestion {
  icon: Component;
  title: string;
  description: string;
  prompt?: string;
  attach?: boolean;
}

interface ComposerExpose {
  setDraft: (value: string) => void;
  focus: () => void;
  openFilePicker: () => void;
  clear: () => void;
}

defineOptions({ name: "AgentChatView" });

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const agent = useAgentStore();
const configStore = useConfigStore();
const toast = useToastStore();
const knowledge = useKnowledgeStore();

const scrollRef = ref<HTMLElement | null>(null);
const composerRef = ref<ComposerExpose | null>(null);
const configOpen = ref(false);
const sending = ref(false);
const uploadingLabel = ref("");
const copiedId = ref("");
const streamController = ref<AbortController | null>(null);
const disposed = ref(false);
const importingMessageId = ref("");

// 知识范围开关：知识库、个人记忆、当前工作台。默认全部关闭，状态保存在会话上。
const knowledgeScope = computed({
  get: () => agent.knowledgeScope,
  set: (value: KnowledgeScope) => {
    agent.knowledgeScope = value;
  },
});
const lastSources = ref<KnowledgeSourceRef[]>([]);

async function addMessageToKnowledge(message: AgentMessage): Promise<void> {
  if (message.streaming || !message.id || importingMessageId.value) return;
  importingMessageId.value = message.id;
  try {
    await importKnowledge({ message: message.id, ai_enabled: false });
    toast.success("这条回答已加入知识库。");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    importingMessageId.value = "";
  }
}
const lastWarnings = ref<string[]>([]);
let cancelRequested = false;
let scrollFrame = 0;

const suggestions: Suggestion[] = [
  {
    icon: FileText,
    title: "读懂一份文档",
    description: "提炼 PDF / Word 的核心信息",
    attach: true,
  },
  {
    icon: ImageIcon,
    title: "看看这张图片",
    description: "识别画面、文字与隐藏细节",
    attach: true,
  },
  {
    icon: Code2,
    title: "写一段代码",
    description: "从思路到可运行的实现",
    prompt: "请帮我实现一个功能，并解释关键代码：\n",
  },
  {
    icon: BrainCircuit,
    title: "弄懂一个概念",
    description: "把复杂问题拆开、讲透",
    prompt: "请用由浅入深的方式，向我解释这个概念：\n",
  },
];

const greetingName = computed(() => auth.user?.username || "朋友");
const provider = computed(() => providerLabel(configStore.config.provider));
const configReady = computed(
  () => Boolean(configStore.config.base_url.trim() && configStore.config.model.trim()),
);
// deepseek 与 custom 由服务端内置 Key 兜底，无需用户自备。
const needsKey = computed(
  () =>
    !["custom", "deepseek"].includes(configStore.config.provider) &&
    !configStore.hasKey,
);
const canUseAgent = computed(() => auth.isAuthenticated && !auth.isGuest);
const hasMessages = computed(() => agent.messages.length > 0);
const showEmpty = computed(() => !hasMessages.value && !agent.loadingMessages);
const streamingMessage = computed(() =>
  agent.messages.find((message) => message.streaming) || null,
);
const pageTitle = computed(() =>
  agent.activeId ? agent.activeTitle : "新的探索",
);

function scrollToBottom(smooth = false): void {
  nextTick(() => {
    const element = scrollRef.value;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  });
}

function scheduleScroll(): void {
  if (!agent.messages.length) return;
  if (scrollFrame) return;
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0;
    scrollToBottom(false);
  });
}

watch(
  () => agent.messages.length,
  (length) => {
    if (!length) {
      nextTick(() => scrollRef.value?.scrollTo({ top: 0, behavior: "auto" }));
    }
  },
);

watch(
  () =>
    agent.messages
      .map((message) => `${message.id}:${message.content.length}:${message.streaming ? 1 : 0}`)
      .join("|"),
  scheduleScroll,
);

watch(
  () => route.query.c,
  async (value) => {
    if (!canUseAgent.value) return;
    const id = typeof value === "string" ? value : "";
    if (!id) return;
    if (id === agent.activeId && agent.messages.length) {
      scrollToBottom(false);
      return;
    }
    if (sending.value) cancelStream();
    try {
      await agent.loadConversation(id);
      scrollToBottom(false);
    } catch (error) {
      toast.error(extractApiError(error));
      agent.startNew();
      if (route.query.c) router.replace({ name: "agent" });
    }
  },
  { immediate: true },
);

onMounted(async () => {
  await auth.initialize();
  if (!canUseAgent.value) return;
  await configStore.load();
  try {
    await agent.loadConversations(true);
  } catch {
    // History is optional; the composer remains usable.
  }
  try {
    await knowledge.loadCollections();
  } catch {
    // The knowledge panel stays usable without the collection list.
  }
  if (agent.activeId && !route.query.c) {
    router.replace({ name: "agent", query: { c: agent.activeId } });
  }
  if (agent.messages.length) {
    window.setTimeout(() => scrollToBottom(false), 80);
  }
});

onActivated(() => {
  if (agent.messages.length) scrollToBottom(false);
});

onDeactivated(() => {
  // KeepAlive only deactivates the view, it does not unmount it.  A running
  // stream has to be stopped here, otherwise it keeps writing into a hidden
  // view and the composer stays locked.
  cancelStreamSilently();
});

onBeforeUnmount(() => {
  disposed.value = true;
  cancelRequested = true;
  streamController.value?.abort();
  if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
});

function openSettings(): void {
  configOpen.value = true;
}

function goLogin(): void {
  router.push({ path: "/", query: { redirect: "/agent" } });
}

function goTransfer(): void {
  router.push({ name: "transfer" });
}

function applySuggestion(suggestion: Suggestion): void {
  if (suggestion.attach) {
    composerRef.value?.openFilePicker();
    return;
  }
  if (suggestion.prompt) composerRef.value?.setDraft(suggestion.prompt);
}

function startNew(): void {
  if (sending.value) cancelStream();
  agent.startNew();
  router.push({ name: "agent" });
  nextTick(() => composerRef.value?.focus());
}

// ---- 会话历史（恢复旧侧栏的会话列表与删除能力） ----
const historyOpen = ref(false);
const pendingDelete = ref<ConversationSummary | null>(null);
const deletingConversation = ref(false);

async function openHistory(): Promise<void> {
  historyOpen.value = true;
  try {
    await agent.loadConversations(true);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function openConversation(id: string): Promise<void> {
  if (sending.value) cancelStream();
  try {
    await agent.loadConversation(id);
    historyOpen.value = false;
    if (route.query.c !== id) {
      await router.replace({ name: "agent", query: { c: id } });
    }
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function confirmRemoveConversation(): Promise<void> {
  const target = pendingDelete.value;
  if (!target || deletingConversation.value) return;
  deletingConversation.value = true;
  try {
    await agent.removeConversation(target.id);
    pendingDelete.value = null;
    toast.success("会话已删除");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    deletingConversation.value = false;
  }
}

function handleStreamEvent(event: AgentStreamEvent, assistant: AgentMessage, user: AgentMessage): void {
  if (event.type === "meta") {
    user.id = event.user_message.id;
    user.attachments = event.user_message.attachments;
    agent.applyMeta(event.conversation_id, event.title);
    if (route.query.c !== event.conversation_id) {
      router.replace({ name: "agent", query: { c: event.conversation_id } });
    }
    return;
  }
  if (event.type === "sources") {
    lastSources.value = event.sources;
    lastWarnings.value = event.warnings;
    return;
  }
  if (event.type === "delta") {
    assistant.content += event.content;
    assistant.error = "";
    return;
  }
  if (event.type === "done") {
    Object.assign(assistant, event.message);
    assistant.streaming = false;
    assistant.error = "";
    agent.syncAfterStream(agent.activeId || event.message.id, agent.activeTitle, event.message.content);
    window.setTimeout(() => {
      if (!disposed.value) agent.refreshConversations();
    }, 600);
    return;
  }
  if (event.type === "error") {
    assistant.streaming = false;
    assistant.error = event.message;
    if (event.partial_message) {
      assistant.id = event.partial_message.id;
      assistant.content = event.partial_message.content;
    }
    toast.error(event.message);
    if (agent.activeId) {
      window.setTimeout(() => {
        if (!disposed.value) agent.refreshConversations();
      }, 300);
    }
  }
}

async function handleSend(payload: { text: string; files: File[] }): Promise<void> {
  if (!canUseAgent.value || sending.value || agent.loadingMessages) return;
  if (!payload.text && !payload.files.length) return;
  if (!configReady.value) {
    configOpen.value = true;
    toast.info("先连接一个模型接口，就可以开始对话了");
    return;
  }
  if (needsKey.value) {
    configOpen.value = true;
    toast.info("请填写 API Key（本地免密网关请选择「自定义」）");
    return;
  }

  cancelRequested = false;
  sending.value = true;
  uploadingLabel.value = "";
  const now = new Date().toISOString();
  const tempUserId = `temp-user-${Date.now()}`;
  const userMessage: AgentMessage = {
    id: tempUserId,
    role: "user",
    content: payload.text,
    attachments: payload.files.map((file, index) => ({
      id: `local-${index}`,
      name: file.name,
      mime: file.type,
      size: file.size,
      is_image: file.type.startsWith("image/"),
    })),
    created_at: now,
  };
  const assistant: AgentMessage = {
    id: `stream-${Date.now()}`,
    role: "assistant",
    content: "",
    attachments: [],
    created_at: now,
    streaming: true,
  };
  agent.messages.push(userMessage, assistant);
  scrollToBottom(true);

  try {
    const uploaded = [];
    for (let index = 0; index < payload.files.length; index += 1) {
      if (cancelRequested) throw new DOMException("Aborted", "AbortError");
      uploadingLabel.value = `正在解析附件 ${index + 1}/${payload.files.length}`;
      uploaded.push(await uploadAgentAttachment(payload.files[index]));
    }
    if (cancelRequested) throw new DOMException("Aborted", "AbortError");
    uploadingLabel.value = "";
    if (uploaded.length) {
      userMessage.attachments = uploaded.map((item) => ({
        id: item.id,
        name: item.original_name,
        mime: item.mime_type,
        size: item.file_size,
        is_image: item.is_image,
      }));
    }

    const controller = new AbortController();
    streamController.value = controller;
    await streamAgentChat(
      {
        conversation_id: agent.activeId,
        message: payload.text || "请阅读并分析我上传的附件。",
        attachment_ids: uploaded.map((item) => item.id),
        api_config: {
          provider: configStore.config.provider,
          base_url: configStore.config.base_url,
          model: configStore.config.model,
          system_prompt: configStore.config.system_prompt,
          use_saved: true,
        },
        knowledge: {
          enabled: knowledgeScope.value.enabled,
          scope: knowledgeScope.value.scope,
          collection_ids: knowledgeScope.value.collection_ids,
          use_personal_memory: knowledgeScope.value.use_personal_memory,
          project_id: knowledgeScope.value.project_id,
          use_workspace: knowledgeScope.value.use_workspace,
          strict_sources: knowledgeScope.value.strict_sources,
        },
      },
      {
        signal: controller.signal,
        onEvent: (event) => {
          if (disposed.value) return;
          handleStreamEvent(event, assistant, userMessage);
        },
      },
    );

    if (assistant.streaming) {
      assistant.streaming = false;
      if (!assistant.content) assistant.error = "连接意外中断，请稍后重试。";
    }
  } catch (error) {
    assistant.streaming = false;
    if (cancelRequested) {
      if (!assistant.content && !assistant.error) assistant.error = "已停止生成。";
    } else if (error instanceof DOMException && error.name === "AbortError") {
      // Navigation / unmount aborts are not user-facing errors.
    } else {
      const message = extractApiError(error);
      assistant.error = message;
      toast.error(message);
    }
    if (agent.activeId && !disposed.value) {
      agent.refreshConversations();
    }
  } finally {
    if (!disposed.value) {
      sending.value = false;
      uploadingLabel.value = "";
      streamController.value = null;
      scheduleScroll();
      nextTick(() => composerRef.value?.focus());
    }
  }
}

function cancelStream(): void {
  cancelRequested = true;
  streamController.value?.abort();
  const active = streamingMessage.value;
  if (active) {
    active.streaming = false;
    if (!active.content && !active.error) active.error = "已停止生成。";
  }
  sending.value = false;
  uploadingLabel.value = "";
  toast.info("已停止生成");
}

function cancelStreamSilently(): void {
  cancelRequested = true;
  streamController.value?.abort();
  const active = streamingMessage.value;
  if (active) active.streaming = false;
  sending.value = false;
}

async function copyAssistant(message: AgentMessage): Promise<void> {
  if (!message.content) return;
  const ok = await copyText(message.content);
  if (!ok) {
    toast.error("复制失败，请手动选择文本");
    return;
  }
  copiedId.value = message.id;
  window.setTimeout(() => {
    if (copiedId.value === message.id) copiedId.value = "";
  }, 1600);
}

function formatMessageTime(value: string): string {
  return formatTime(value);
}
</script>

<template>
  <div class="agent-view relative flex h-full min-h-0 flex-col overflow-hidden">
    <div class="agent-aura" aria-hidden="true" />

    <div
      v-if="!canUseAgent"
      class="relative z-10 flex h-full items-center justify-center px-4"
    >
      <div class="w-full max-w-[480px] animate-fade-up rounded-[28px] border border-white/80 bg-white/90 p-8 text-center shadow-float backdrop-blur-xl">
        <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-lg">
          <Sparkles :size="23" />
        </span>
        <p class="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-400">
          Login required
        </p>
        <h1 class="mt-2 text-[23px] font-medium tracking-tight text-ink-900">
          AI 对话需要登录
        </h1>
        <p class="mt-3 text-[12.5px] leading-6 text-ink-500">
          请使用非访客账号登录后开始多模态对话。公开文件中转站仍然无需账号。
        </p>
        <div class="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <button type="button" class="btn-primary" @click="goLogin">
            <LogIn :size="14" />
            去登录
          </button>
          <button type="button" class="btn-secondary" @click="goTransfer">
            <HardDriveUpload :size="14" />
            免密中转站
          </button>
        </div>
      </div>
    </div>

    <template v-else>
    <header class="relative z-10 flex h-[62px] shrink-0 items-center gap-3 px-4 sm:px-7">
      <div class="flex min-w-0 items-center gap-2.5">
        <span class="hidden h-5 w-5 items-center justify-center rounded-lg bg-ink-900 text-white sm:flex">
          <Sparkles :size="11" />
        </span>
        <p class="hidden text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-400 sm:block">
          缺页中断
        </p>
        <span class="hidden h-3 w-px bg-slate-200 sm:block" />
        <p class="truncate text-[12.5px] font-medium text-ink-600">{{ pageTitle }}</p>
      </div>

      <div class="ml-auto flex items-center gap-1.5">
        <button
          type="button"
          class="hidden items-center gap-2 rounded-full border border-white/80 bg-white/70 py-1.5 pl-2.5 pr-3 text-[11px] font-medium text-ink-600 shadow-sm backdrop-blur transition hover:border-slate-200 hover:bg-white sm:flex"
          :aria-label="`API 设置 · ${provider}`"
          @click="openSettings"
        >
          <span class="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-ink-500">
            <Settings2 :size="11" />
          </span>
          {{ provider }}
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="configReady && !needsKey ? 'bg-emerald-400' : 'bg-amber-400'"
          />
        </button>
        <button
          type="button"
          class="icon-button h-9 w-9 bg-white/60 backdrop-blur sm:hidden"
          aria-label="API 设置"
          @click="openSettings"
        >
          <Settings2 :size="17" />
        </button>
        <button
          type="button"
          class="icon-button h-9 w-9 bg-white/60 backdrop-blur"
          title="历史会话"
          @click="openHistory"
        >
          <History :size="17" />
        </button>
        <button
          type="button"
          class="icon-button h-9 w-9 bg-white/60 backdrop-blur"
          title="新对话"
          @click="startNew"
        >
          <Plus :size="18" />
        </button>
      </div>
    </header>

    <div ref="scrollRef" class="relative z-10 min-h-0 flex-1 overflow-y-auto scroll-smooth">
      <div v-if="agent.loadingMessages" class="mx-auto flex max-w-[880px] flex-col gap-5 px-5 py-12 sm:px-8">
        <div class="h-3 w-24 animate-pulse rounded-full bg-slate-200/80" />
        <div class="h-4 w-3/4 animate-pulse rounded-full bg-slate-200/60" />
        <div class="h-4 w-2/3 animate-pulse rounded-full bg-slate-200/50" />
        <div class="mt-8 ml-auto h-16 w-1/2 animate-pulse rounded-3xl bg-slate-200/50" />
      </div>

      <div v-else-if="showEmpty" class="mx-auto flex w-full max-w-[940px] flex-col px-4 pb-8 pt-[4vh] sm:px-8 sm:pt-[8vh]">
        <div class="relative max-w-[780px]">
          <div class="hero-orb" aria-hidden="true" />
          <div class="animate-fade-up">
            <div class="mb-5 flex items-center gap-2">
              <span class="inline-flex items-center gap-1.5 rounded-full border border-white bg-white/75 py-1.5 pl-2 pr-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-500 shadow-sm backdrop-blur">
                <span class="flex h-4 w-4 items-center justify-center rounded-full bg-accent-500 text-white">
                  <Sparkles :size="9" />
                </span>
                Multimodal Agent
              </span>
              <span class="inline-flex items-center gap-1 rounded-full border border-white/70 bg-white/45 px-2.5 py-1.5 text-[10px] font-medium text-ink-400 backdrop-blur">
                <ShieldCheck :size="11" />
                自托管 · 数据留在本地
              </span>
            </div>

            <h1 class="text-[32px] font-medium leading-[1.22] tracking-[-0.04em] text-ink-900 sm:text-[44px]">
              你好，<span class="hero-name">{{ greetingName }}</span>
              <br class="hidden sm:block" />
              今天想一起完成什么？
            </h1>
            <p class="mt-4 max-w-[520px] text-[13.5px] leading-6 text-ink-500 sm:text-[14px]">
              阅读文档、理解图片，或者把一个模糊的想法变成清晰的答案。缺页中断 会陪你把问题想透。
            </p>
          </div>

          <button
            v-if="needsKey"
            type="button"
            class="mt-5 inline-flex animate-fade-up items-center gap-2 rounded-full border border-amber-200/80 bg-amber-50/80 px-3.5 py-2 text-[11px] font-medium text-amber-800 shadow-sm transition hover:bg-amber-50"
            @click="openSettings"
          >
            <span class="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-600">
              <Sparkles :size="11" />
            </span>
            连接你的模型 API
            <ArrowUpRight :size="12" />
          </button>
        </div>

        <div class="mt-8 grid max-w-[780px] grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          <button
            v-for="(suggestion, index) in suggestions"
            :key="suggestion.title"
            type="button"
            class="suggestion-card group animate-fade-up"
            :style="{ animationDelay: `${80 + index * 55}ms` }"
            @click="applySuggestion(suggestion)"
          >
            <span class="flex items-center justify-between">
              <span class="flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-ink-500 shadow-sm transition group-hover:border-accent-200 group-hover:text-accent-600">
                <component :is="suggestion.icon" :size="15" />
              </span>
              <ArrowUpRight :size="13" class="text-ink-300 opacity-0 transition duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:opacity-100" />
            </span>
            <span class="mt-3 block text-[12.5px] font-semibold text-ink-800">{{ suggestion.title }}</span>
            <span class="mt-1 block text-[10.5px] leading-4 text-ink-400">{{ suggestion.description }}</span>
          </button>
        </div>
      </div>

      <div v-else class="mx-auto w-full max-w-[860px] px-4 pb-10 pt-7 sm:px-7 sm:pt-10">
        <div class="space-y-9">
          <template v-for="message in agent.messages" :key="message.id">
            <article v-if="message.role === 'assistant'" class="group animate-fade-up">
              <div class="flex items-start gap-3 sm:gap-4">
                <BrandMark :size="30" class="mt-0.5" />
                <div class="min-w-0 flex-1">
                  <div class="mb-2 flex items-center gap-2">
                    <p class="text-[12px] font-semibold text-ink-800">缺页中断</p>
                    <span class="rounded-md bg-slate-100 px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-[0.08em] text-ink-400">AI</span>
                    <span v-if="message.streaming" class="flex items-center gap-1 text-[10px] font-medium text-accent-500">
                      <span class="thinking-dot" />
                      {{ uploadingLabel || "正在生成" }}
                    </span>
                  </div>

                  <div v-if="!message.content && message.streaming" class="flex items-center gap-2 py-2">
                    <span class="thinking-orb" />
                    <span class="thinking-orb" style="animation-delay: .15s" />
                    <span class="thinking-orb" style="animation-delay: .3s" />
                    <span class="ml-1 text-[12px] text-ink-400">
                      {{ uploadingLabel || "正在思考" }}
                    </span>
                  </div>

                  <MarkdownRenderer v-if="message.content" :content="message.content" />

                  <div
                    v-if="message.error"
                    class="mt-3 flex items-start gap-2.5 rounded-2xl border border-rose-100 bg-rose-50/70 px-3.5 py-3 text-[11.5px] leading-[1.7] text-rose-700"
                  >
                    <CircleAlert :size="15" class="mt-0.5 shrink-0 text-rose-500" />
                    <div class="min-w-0">
                      <p class="font-medium">这次回答没有完成</p>
                      <p class="mt-0.5 text-rose-600/90">{{ message.error }}</p>
                    </div>
                  </div>

                  <div
                    v-if="message.knowledge_sources?.length"
                    class="mt-2.5 flex flex-wrap items-center gap-1.5"
                  >
                    <span
                      v-for="source in message.knowledge_sources"
                      :key="source.source_id"
                      class="inline-flex max-w-[260px] items-center gap-1 rounded-lg border border-slate-200/80 bg-white/80 px-2 py-1 text-[10.5px] text-ink-500"
                      :title="source.text"
                    >
                      <span class="font-mono text-accent-600">{{ source.source_id }}</span>
                      <span class="truncate">{{ source.title }}</span>
                      <span v-if="source.page_start" class="shrink-0 text-ink-300">
                        第 {{ source.page_start }} 页
                      </span>
                    </span>
                  </div>

                  <div v-if="!message.streaming && message.content" class="mt-2.5 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
                    <button
                      type="button"
                      class="message-action"
                      @click="copyAssistant(message)"
                    >
                      <Check v-if="copiedId === message.id" :size="12" />
                      <Copy v-else :size="12" />
                      {{ copiedId === message.id ? "已复制" : "复制" }}
                    </button>
                    <button
                      type="button"
                      class="message-action"
                      :disabled="Boolean(importingMessageId)"
                      @click="addMessageToKnowledge(message)"
                    >
                      <Loader2 v-if="importingMessageId === message.id" :size="12" class="animate-spin" />
                      <BookPlus v-else :size="12" />
                      加入知识库
                    </button>
                    <span class="text-[9px] text-ink-300">{{ formatMessageTime(message.created_at) }}</span>
                  </div>

                  <div v-if="message.streaming" class="mt-3 flex items-center">
                    <button
                      type="button"
                      class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-2.5 py-1 text-[10px] font-medium text-ink-500 transition hover:border-slate-300 hover:text-ink-800"
                      @click="cancelStream"
                    >
                      <Square :size="9" fill="currentColor" />
                      停止生成
                    </button>
                  </div>
                </div>
              </div>
            </article>

            <article v-else class="flex animate-fade-up justify-end">
              <div class="flex max-w-[90%] items-start gap-2.5 sm:max-w-[78%]">
                <div class="min-w-0">
                  <div
                    v-if="message.content"
                    class="whitespace-pre-wrap break-words rounded-[22px] rounded-br-[7px] bg-[#edf0f6] px-4 py-3 text-[14px] leading-[1.7] text-ink-900 sm:text-[14.5px]"
                  >{{ message.content }}</div>

                  <div
                    v-if="message.attachments?.length"
                    class="mt-2 flex flex-wrap justify-end gap-1.5"
                  >
                    <span
                      v-for="attachment in message.attachments"
                      :key="attachment.id"
                      class="inline-flex max-w-[210px] items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white/80 px-2 py-1.5 text-[10px] text-ink-500"
                    >
                      <ImageIcon v-if="attachment.is_image" :size="12" class="text-rose-400" />
                      <FileText v-else :size="12" class="text-slate-400" />
                      <span class="truncate">{{ attachment.name }}</span>
                    </span>
                  </div>

                  <p class="mt-1.5 pr-1 text-right text-[9px] text-ink-300">
                    {{ formatMessageTime(message.created_at) }}
                  </p>
                </div>
                <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold text-white">
                  {{ (auth.user?.username || "你").slice(0, 1).toUpperCase() }}
                </span>
              </div>
            </article>
          </template>
        </div>

        <div class="h-4" />
      </div>
    </div>

    <div class="composer-area relative z-20 shrink-0">
      <div class="mx-auto w-full max-w-[860px] px-3 pb-3 sm:px-7 sm:pb-5">
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <KnowledgeScopeBar :scope="knowledgeScope" @change="knowledgeScope = $event" />
          <div
            v-if="lastWarnings.length"
            class="text-[11px] text-amber-600"
          >
            {{ lastWarnings.join(" ") }}
          </div>
        </div>
        <MultimodalInput
          ref="composerRef"
          :busy="sending"
          :disabled="agent.loadingMessages"
          :provider-label="provider"
          :configured="configReady && !needsKey"
          @send="handleSend"
          @open-settings="openSettings"
        />
        <p class="mt-2.5 text-center text-[9.5px] leading-4 text-ink-300">
          缺页中断 可能会犯错，请核查重要信息 · 内容将发送至你配置的模型接口
        </p>
      </div>
    </div>
    </template>

    <ApiConfigModal :open="configOpen" @close="configOpen = false" />

    <ModalShell
      :open="historyOpen"
      title="历史会话"
      subtitle="点击会话继续对话，或删除不再需要的记录"
      max-width="max-w-lg"
      @close="historyOpen = false"
    >
      <div v-if="agent.recentConversations.length === 0" class="py-8 text-center text-sm text-slate-500">
        还没有历史会话
      </div>
      <ul v-else class="flex max-h-[46vh] flex-col gap-1.5 overflow-y-auto pr-1">
        <li
          v-for="conversation in agent.recentConversations"
          :key="conversation.id"
          class="group flex items-center gap-2 rounded-xl border border-transparent px-3 py-2.5 transition hover:border-slate-200 hover:bg-slate-50"
        >
          <button
            type="button"
            class="min-w-0 flex-1 text-left"
            @click="openConversation(conversation.id)"
          >
            <p class="truncate text-sm font-medium text-slate-800">
              {{ conversation.title || "未命名会话" }}
            </p>
            <p class="mt-0.5 text-xs text-slate-400">
              {{ formatTime(conversation.updated_at) }}
            </p>
          </button>
          <button
            type="button"
            class="icon-button h-8 w-8 !min-h-0 !min-w-0 text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-red-600"
            title="删除会话"
            aria-label="删除会话"
            @click="pendingDelete = conversation"
          >
            <Trash2 :size="15" />
          </button>
        </li>
      </ul>
      <template #footer>
        <button type="button" class="btn-secondary" @click="historyOpen = false">关闭</button>
      </template>
    </ModalShell>

    <ModalShell
      :open="pendingDelete !== null"
      title="删除会话"
      max-width="max-w-sm"
      @close="pendingDelete = null"
    >
      <p class="text-sm leading-6 text-slate-600">
        确定删除「{{ pendingDelete?.title || "未命名会话" }}」吗？删除后该会话与消息将不可恢复。
      </p>
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="deletingConversation" @click="pendingDelete = null">
          取消
        </button>
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-60"
          :disabled="deletingConversation"
          @click="confirmRemoveConversation"
        >
          <Loader2 v-if="deletingConversation" :size="15" class="animate-spin" />
          删除
        </button>
      </template>
    </ModalShell>
  </div>
</template>
