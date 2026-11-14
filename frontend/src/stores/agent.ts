import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  deleteConversation as deleteConversationRequest,
  getConversation,
  listConversations,
} from "@/api/agent";
import type { AgentMessage, ConversationSummary } from "@/types";

export const useAgentStore = defineStore("agent", () => {
  const conversations = ref<ConversationSummary[]>([]);
  const activeId = ref<string | null>(null);
  const activeTitle = ref("新对话");
  const messages = ref<AgentMessage[]>([]);
  const loadingConversations = ref(false);
  const loadingMessages = ref(false);
  const loaded = ref(false);

  const recentConversations = computed(() => conversations.value.slice(0, 30));

  async function loadConversations(force = false): Promise<void> {
    if (loadingConversations.value) return;
    if (loaded.value && !force) return;
    loadingConversations.value = true;
    try {
      conversations.value = await listConversations();
      loaded.value = true;
    } finally {
      loadingConversations.value = false;
    }
  }

  async function loadConversation(id: string): Promise<void> {
    loadingMessages.value = true;
    try {
      const detail = await getConversation(id);
      activeId.value = detail.id;
      activeTitle.value = detail.title;
      messages.value = detail.messages;
    } finally {
      loadingMessages.value = false;
    }
  }

  function startNew(): void {
    activeId.value = null;
    activeTitle.value = "新对话";
    messages.value = [];
  }

  function applyMeta(conversationId: string, title: string): void {
    activeId.value = conversationId;
    activeTitle.value = title;
    if (!conversations.value.some((item) => item.id === conversationId)) {
      conversations.value.unshift({
        id: conversationId,
        title,
        message_count: 1,
        last_message: "",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    } else {
      const existing = conversations.value.find((item) => item.id === conversationId);
      if (existing) existing.title = title;
    }
  }

  function updateSummary(id: string, patch: Partial<ConversationSummary>): void {
    const target = conversations.value.find((item) => item.id === id);
    if (target) Object.assign(target, patch);
  }

  function syncAfterStream(id: string, title: string, lastMessage: string): void {
    updateSummary(id, {
      title,
      last_message: lastMessage.slice(0, 80),
      updated_at: new Date().toISOString(),
    });
    const target = conversations.value.find((item) => item.id === id);
    if (target) {
      target.message_count = messages.value.filter((item) => !item.streaming).length;
      conversations.value = [
        target,
        ...conversations.value.filter((item) => item.id !== id),
      ];
    }
  }

  async function refreshConversations(): Promise<void> {
    try {
      const items = await listConversations();
      conversations.value = items;
      loaded.value = true;
    } catch {
      // A background refresh must never interrupt the chat experience.
    }
  }

  async function removeConversation(id: string): Promise<void> {
    await deleteConversationRequest(id);
    conversations.value = conversations.value.filter((item) => item.id !== id);
    if (activeId.value === id) startNew();
  }

  function reset(): void {
    conversations.value = [];
    activeId.value = null;
    activeTitle.value = "新对话";
    messages.value = [];
    loaded.value = false;
  }

  return {
    conversations,
    recentConversations,
    activeId,
    activeTitle,
    messages,
    loadingConversations,
    loadingMessages,
    loadConversations,
    loadConversation,
    startNew,
    applyMeta,
    updateSummary,
    syncAfterStream,
    refreshConversations,
    removeConversation,
    reset,
  };
});