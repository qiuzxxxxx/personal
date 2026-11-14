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
  const searchResult = ref<KnowledgeSearchResult | null>(null);
  const loading = ref(false);

  let ownerId: number | null = null;

  const activeCollections = computed(() => collections.value);

  function reset(): void {
    collections.value = [];
    documents.value = [];
    memories.value = [];
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

  async function loadCollections(): Promise<void> {
    if (!ensureOwner()) return;
    const list = await knowledgeApi.fetchCollections();
    if (!ensureOwner()) return;
    collections.value = list;
  }

  async function loadDocuments(query: Parameters<typeof knowledgeApi.fetchDocuments>[0] = {}): Promise<void> {
    if (!ensureOwner()) return;
    loading.value = true;
    try {
      const page = await knowledgeApi.fetchDocuments(query);
      if (!ensureOwner()) return;
      documents.value = page.results;
    } finally {
      loading.value = false;
    }
  }

  async function loadMemories(status?: PersonalMemory["status"]): Promise<void> {
    if (!ensureOwner()) return;
    loading.value = true;
    try {
      const page = await knowledgeApi.fetchMemories(status ? { status } : {});
      if (!ensureOwner()) return;
      memories.value = page.results;
    } finally {
      loading.value = false;
    }
  }

  async function runSearch(payload: {
    query: string;
    scope?: "all" | "collections";
    collection_ids?: string[];
  }): Promise<KnowledgeSearchResult | null> {
    if (!ensureOwner()) return null;
    loading.value = true;
    try {
      const result = await knowledgeApi.searchKnowledge(payload);
      if (!ensureOwner()) return null;
      searchResult.value = result;
      return result;
    } finally {
      loading.value = false;
    }
  }

  return {
    collections,
    documents,
    memories,
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
