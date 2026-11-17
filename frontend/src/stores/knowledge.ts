import { defineStore } from "pinia";
import { computed, ref } from "vue";
import * as knowledgeApi from "@/api/knowledge";
import type {
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeSearchResult,
  PersonalMemory,
} from "@/api/knowledge";
import { useAuthStore } from "@/stores/auth";

/**
 * Knowledge state is owner scoped: switching accounts clears every cached
 * list so a previous account's documents or memories can never leak into the
 * next session.
 */
export const useKnowledgeStore = defineStore("knowledge", () => {
  const auth = useAuthStore();

  const collections = ref<KnowledgeCollection[]>([]);
  const documents = ref<KnowledgeDocument[]>([]);
  const memories = ref<PersonalMemory[]>([]);
  const documentCount = ref(0);
  const documentPage = ref(1);
  const documentPages = ref(1);
  const memoryCount = ref(0);
  const memoryPage = ref(1);
  const memoryPages = ref(1);
  const searchResult = ref<KnowledgeSearchResult | null>(null);
  const loading = ref(false);

  let ownerId: number | null = null;
  let sessionEpoch = 0;

  interface OwnerRequest {
    ownerId: number;
    epoch: number;
  }

  const activeCollections = computed(() => collections.value);

  function reset(): void {
    sessionEpoch += 1;
    collections.value = [];
    documents.value = [];
    memories.value = [];
    documentCount.value = 0;
    documentPage.value = 1;
    documentPages.value = 1;
    memoryCount.value = 0;
    memoryPage.value = 1;
    memoryPages.value = 1;
    searchResult.value = null;
    loading.value = false;
  }

  function ensureOwner(): boolean {
    const current = auth.user?.id ?? null;
    if (current !== ownerId) {
      reset();
      ownerId = current;
    }
    return current !== null;
  }

  function beginOwnerRequest(): OwnerRequest | null {
    if (!ensureOwner() || ownerId === null) return null;
    return { ownerId, epoch: sessionEpoch };
  }

  function isCurrentRequest(request: OwnerRequest): boolean {
    return (
      request.epoch === sessionEpoch &&
      request.ownerId === ownerId &&
      request.ownerId === (auth.user?.id ?? null)
    );
  }

  async function loadCollections(): Promise<void> {
    const request = beginOwnerRequest();
    if (!request) return;
    const list = await knowledgeApi.fetchCollections();
    if (!isCurrentRequest(request)) return;
    collections.value = list;
  }

  async function loadDocuments(query: Parameters<typeof knowledgeApi.fetchDocuments>[0] = {}): Promise<void> {
    const request = beginOwnerRequest();
    if (!request) return;
    loading.value = true;
    try {
      const page = await knowledgeApi.fetchDocuments(query);
      if (!isCurrentRequest(request)) return;
      documents.value = page.results;
      documentCount.value = page.count;
      documentPage.value = page.page;
      documentPages.value = page.pages;
    } finally {
      if (isCurrentRequest(request)) loading.value = false;
    }
  }

  async function loadMemories(
    status?: PersonalMemory["status"],
    page = 1,
  ): Promise<void> {
    const request = beginOwnerRequest();
    if (!request) return;
    loading.value = true;
    try {
      const result = await knowledgeApi.fetchMemories({
        ...(status ? { status } : {}),
        page,
      });
      if (!isCurrentRequest(request)) return;
      memories.value = result.results;
      memoryCount.value = result.count;
      memoryPage.value = result.page;
      memoryPages.value = result.pages;
    } finally {
      if (isCurrentRequest(request)) loading.value = false;
    }
  }

  async function runSearch(payload: {
    query: string;
    scope?: "all" | "collections";
    collection_ids?: string[];
  }): Promise<KnowledgeSearchResult | null> {
    const request = beginOwnerRequest();
    if (!request) return null;
    loading.value = true;
    try {
      const result = await knowledgeApi.searchKnowledge(payload);
      if (!isCurrentRequest(request)) return null;
      searchResult.value = result;
      return result;
    } finally {
      if (isCurrentRequest(request)) loading.value = false;
    }
  }

  return {
    collections,
    documents,
    memories,
    documentCount,
    documentPage,
    documentPages,
    memoryCount,
    memoryPage,
    memoryPages,
    searchResult,
    loading,
    activeCollections,
    reset,
    loadCollections,
    loadDocuments,
    loadMemories,
    runSearch,
  };
});
