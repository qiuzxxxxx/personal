<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  BookOpen,
  Check,
  Database,
  FileText,
  FolderPlus,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
} from "lucide-vue-next";
import { extractApiError } from "@/api/client";
import {
  createCollection,
  createDocument,
  deleteCollection,
  deleteDocument,
  importKnowledge,
  purgeDocument,
  reindexDocument,
  restoreDocument,
  updateDocument,
} from "@/api/knowledge";
import type { KnowledgeCollection, KnowledgeDocument } from "@/api/knowledge";
import { useToastStore } from "@/stores/toast";
import { useKnowledgeStore } from "@/stores/knowledge";
import { useWorkspaceStore } from "@/stores/workspace";

const router = useRouter();
const toast = useToastStore();
const knowledge = useKnowledgeStore();
const workspace = useWorkspaceStore();

const activeCollection = ref("");
const keyword = ref("");
const showTrash = ref(false);
const showNewCollection = ref(false);
const newCollectionName = ref("");
const showEditor = ref(false);
const editing = ref<KnowledgeDocument | null>(null);
const draftTitle = ref("");
const draftBody = ref("");
const draftCollection = ref("");
const draftAiEnabled = ref(false);
const saving = ref(false);
const busyId = ref("");

const statusLabels: Record<string, string> = {
  pending: "排队中",
  processing: "解析中",
  ready: "可检索",
  failed: "失败",
  needs_ocr: "需要 OCR",
  stale: "来源已更新",
};

const statusClasses: Record<string, string> = {
  pending: "bg-slate-100 text-ink-500",
  processing: "bg-amber-50 text-amber-600",
  ready: "bg-emerald-50 text-emerald-600",
  failed: "bg-rose-50 text-rose-600",
  needs_ocr: "bg-orange-50 text-orange-600",
  stale: "bg-sky-50 text-sky-600",
};

const visibleDocuments = computed(() => knowledge.documents);

async function refresh(): Promise<void> {
  await knowledge.loadCollections();
  await knowledge.loadDocuments({
    collection: activeCollection.value || undefined,
    q: keyword.value.trim() || undefined,
    deleted: showTrash.value,
  });
}

async function addCollection(): Promise<void> {
  const name = newCollectionName.value.trim();
  if (!name) return;
  try {
    await createCollection({ name });
    newCollectionName.value = "";
    showNewCollection.value = false;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function removeCollection(collection: KnowledgeCollection): Promise<void> {
  try {
    await deleteCollection(collection.id);
    if (activeCollection.value === collection.id) activeCollection.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function openNewDocument(): void {
  editing.value = null;
  draftTitle.value = "";
  draftBody.value = "";
  draftCollection.value = activeCollection.value;
  draftAiEnabled.value = false;
  showEditor.value = true;
}

function openDocument(document: KnowledgeDocument): void {
  editing.value = document;
  draftTitle.value = document.title;
  draftBody.value = document.manual_body;
  draftCollection.value = document.collection ?? "";
  draftAiEnabled.value = document.ai_enabled;
  showEditor.value = true;
}

async function saveDocument(): Promise<void> {
  const title = draftTitle.value.trim();
  if (!title) {
    toast.error("标题不能为空。");
    return;
  }
  saving.value = true;
  try {
    if (editing.value) {
      await updateDocument(editing.value.id, {
        title,
        collection: draftCollection.value || null,
        manual_body: draftBody.value,
        ai_enabled: draftAiEnabled.value,
        version: editing.value.version,
      });
      toast.success("知识条目已更新。");
    } else {
      await createDocument({
        title,
        collection: draftCollection.value || null,
        manual_body: draftBody.value,
        ai_enabled: draftAiEnabled.value,
      });
      toast.success("知识条目已创建，正在建立索引。");
    }
    showEditor.value = false;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    saving.value = false;
  }
}

async function toggleAi(document: KnowledgeDocument): Promise<void> {
  busyId.value = document.id;
  try {
    await updateDocument(document.id, {
      ai_enabled: !document.ai_enabled,
      version: document.version,
    });
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyId.value = "";
  }
}

async function removeDocument(document: KnowledgeDocument): Promise<void> {
  try {
    await deleteDocument(document.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function restoreDocumentItem(document: KnowledgeDocument): Promise<void> {
  try {
    await restoreDocument(document.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function purgeDocumentItem(document: KnowledgeDocument): Promise<void> {
  try {
    await purgeDocument(document.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function rebuild(document: KnowledgeDocument): Promise<void> {
  busyId.value = document.id;
  try {
    await reindexDocument(document.id);
    toast.success("已重新排队建立索引。");
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    busyId.value = "";
  }
}

async function importJournal(): Promise<void> {
  try {
    await workspace.loadJournal(new Date().toISOString().slice(0, 10));
  } catch {
    // A missing journal is not an error for the import action.
  }
  const entry = workspace.journal;
  if (!entry?.id) {
    toast.error("今天的每日记录还没有内容。");
    return;
  }
  try {
    await importKnowledge({
      entry: entry.id,
      collection: activeCollection.value || null,
      ai_enabled: false,
    });
    toast.success("已把今天的每日记录加入知识库。");
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function runSearch(): Promise<void> {
  const query = keyword.value.trim();
  if (!query) return;
  try {
    const result = await knowledge.runSearch({
      query,
      scope: activeCollection.value ? "collections" : "all",
      collection_ids: activeCollection.value ? [activeCollection.value] : [],
    });
    if (result && !result.count) {
      toast.info("没有检索到匹配的资料片段。");
    }
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

onMounted(async () => {
  await refresh();
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[26px] font-semibold tracking-tight text-ink-900">个人知识库</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            笔记、私人资料与每日记录都可以加入这里，AI 只在你允许的范围内检索。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
            @click="router.push('/knowledge/memories')"
          >
            <Sparkles :size="15" />
            个人记忆
          </button>
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
            @click="importJournal"
          >
            <BookOpen :size="15" />
            导入今日记录
          </button>
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800"
            @click="openNewDocument"
          >
            新建笔记
          </button>
        </div>
      </header>

      <div class="mt-6 flex flex-col gap-4 lg:flex-row">
        <aside class="lg:w-56 lg:shrink-0">
          <div class="rounded-2xl border border-slate-200 bg-white p-3 shadow-soft">
            <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.15em] text-ink-400">
              知识集合
            </p>
            <ul class="mt-2 space-y-0.5">
              <li>
                <button
                  type="button"
                  class="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12.5px] transition"
                  :class="activeCollection === '' ? 'bg-slate-100 text-ink-900' : 'text-ink-600 hover:bg-slate-50'"
                  @click="activeCollection = ''; refresh()"
                >
                  全部集合
                  <span class="text-[11px] text-ink-400">
                    {{ knowledge.documents.length }}
                  </span>
                </button>
              </li>
              <li v-for="collection in knowledge.collections" :key="collection.id">
                <div class="flex items-center gap-1">
                  <button
                    type="button"
                    class="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition"
                    :class="activeCollection === collection.id ? 'bg-slate-100 text-ink-900' : 'text-ink-600 hover:bg-slate-50'"
                    @click="activeCollection = collection.id; refresh()"
                  >
                    <Database :size="13" class="shrink-0 text-ink-400" />
                    <span class="truncate">{{ collection.name }}</span>
                    <span class="ml-auto text-[11px] text-ink-400">
                      {{ collection.document_count }}
                    </span>
                  </button>
                  <button
                    type="button"
                    class="shrink-0 text-ink-300 transition hover:text-rose-500"
                    title="删除集合"
                    @click="removeCollection(collection)"
                  >
                    <Trash2 :size="13" />
                  </button>
                </div>
              </li>
            </ul>
            <div class="mt-2 border-t border-slate-100 pt-2">
              <button
                type="button"
                class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12.5px] text-ink-500 transition hover:bg-slate-50 hover:text-ink-800"
                @click="showNewCollection = !showNewCollection"
              >
                <FolderPlus :size="14" />
                新建集合
              </button>
              <div v-if="showNewCollection" class="mt-2 flex gap-1.5">
                <input
                  v-model="newCollectionName"
                  type="text"
                  maxlength="120"
                  placeholder="名称"
                  class="min-w-0 flex-1 rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
                  @keyup.enter="addCollection"
                />
                <button
                  type="button"
                  class="rounded-lg bg-ink-900 px-2.5 py-1.5 text-[11.5px] font-medium text-white"
                  @click="addCollection"
                >
                  添加
                </button>
              </div>
            </div>
          </div>
        </aside>

        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <div class="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5">
              <Search :size="14" class="text-ink-300" />
              <input
                v-model="keyword"
                type="search"
                placeholder="搜索标题或正文"
                class="w-44 bg-transparent text-[12.5px] outline-none placeholder:text-ink-300"
                @keyup.enter="runSearch"
              />
            </div>
            <button
              type="button"
              class="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-ink-600 transition hover:border-accent-200"
              @click="runSearch"
            >
              检索
            </button>
            <button
              type="button"
              class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
              :class="showTrash ? 'bg-rose-600 text-white' : 'bg-white text-ink-500 hover:bg-slate-100'"
              @click="showTrash = !showTrash; refresh()"
            >
              回收站
            </button>
            <span class="ml-auto text-[12px] text-ink-400">
              {{ visibleDocuments.length }} 个条目
            </span>
          </div>

          <section
            v-if="knowledge.searchResult && knowledge.searchResult.count"
            class="mt-4 rounded-2xl border border-accent-200 bg-accent-50/40 p-4"
          >
            <p class="text-[12px] font-semibold uppercase tracking-[0.15em] text-accent-600">
              检索结果
            </p>
            <ul class="mt-2 space-y-2">
              <li
                v-for="match in knowledge.searchResult.matches"
                :key="match.source_id"
                class="rounded-xl border border-white bg-white/80 px-3 py-2"
              >
                <p class="flex flex-wrap items-center gap-2 text-[12.5px] font-medium text-ink-900">
                  <span class="rounded-md bg-accent-100 px-1.5 py-0.5 font-mono text-[10.5px] text-accent-700">
                    {{ match.source_id }}
                  </span>
                  {{ match.title }}
                  <span class="text-[11px] font-normal text-ink-400">
                    {{ match.reason }} · 得分 {{ match.score }}
                  </span>
                </p>
                <p class="mt-1 whitespace-pre-wrap break-words text-[12px] leading-5 text-ink-600">
                  {{ match.text.slice(0, 220) }}
                </p>
              </li>
            </ul>
          </section>

          <div
            v-if="!visibleDocuments.length"
            class="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-12 text-center text-[13px] text-ink-400"
          >
            {{ knowledge.loading ? "加载中…" : "还没有知识条目，新建一条笔记或导入资料吧。" }}
          </div>

          <ul v-else class="mt-4 space-y-2">
            <li
              v-for="document in visibleDocuments"
              :key="document.id"
              class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
            >
              <div class="flex flex-wrap items-start gap-3">
                <span class="mt-0.5 shrink-0 text-ink-400">
                  <FileText :size="16" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[13.5px] font-medium text-ink-900">
                    {{ document.title }}
                  </p>
                  <p class="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
                    <span
                      class="rounded-md px-1.5 py-0.5"
                      :class="statusClasses[document.index_status] || 'bg-slate-100 text-ink-500'"
                    >
                      {{ statusLabels[document.index_status] || document.index_status }}
                    </span>
                    <span>{{ document.source_label }}</span>
                    <span v-if="document.collection_name">#{{ document.collection_name }}</span>
                    <span>{{ document.chunk_count }} 个片段</span>
                  </p>
                </div>
                <div class="flex shrink-0 items-center gap-1.5">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11.5px] font-medium transition"
                    :class="
                      document.ai_enabled
                        ? 'bg-accent-50 text-accent-600'
                        : 'bg-slate-100 text-ink-400 hover:text-ink-700'
                    "
                    :disabled="busyId === document.id"
                    :title="document.ai_enabled ? 'AI 可检索' : 'AI 不可检索'"
                    @click="toggleAi(document)"
                  >
                    <Check v-if="document.ai_enabled" :size="12" />
                    <Sparkles v-else :size="12" />
                    AI
                  </button>
                  <button
                    type="button"
                    class="text-ink-300 transition hover:text-accent-600"
                    title="重新建立索引"
                    :disabled="busyId === document.id"
                    @click="rebuild(document)"
                  >
                    <RefreshCw :size="15" />
                  </button>
                  <button
                    type="button"
                    class="text-[11.5px] font-medium text-ink-500 transition hover:text-accent-600"
                    @click="openDocument(document)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="showTrash"
                    type="button"
                    class="text-ink-300 transition hover:text-accent-600"
                    title="恢复"
                    @click="restoreDocumentItem(document)"
                  >
                    <RotateCcw :size="15" />
                  </button>
                  <button
                    v-else
                    type="button"
                    class="text-ink-300 transition hover:text-rose-500"
                    title="移入回收站"
                    @click="removeDocument(document)"
                  >
                    <Trash2 :size="15" />
                  </button>
                  <button
                    v-if="showTrash"
                    type="button"
                    class="text-ink-300 transition hover:text-rose-600"
                    title="永久删除"
                    @click="purgeDocumentItem(document)"
                  >
                    永久
                  </button>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div
      v-if="showEditor"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      @click.self="showEditor = false"
    >
      <div class="flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p class="text-[13.5px] font-medium text-ink-900">
            {{ editing ? "编辑知识条目" : "新建知识条目" }}
          </p>
          <button type="button" class="text-ink-400 hover:text-ink-700" @click="showEditor = false">
            关闭
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-4">
          <input
            v-model="draftTitle"
            type="text"
            maxlength="200"
            placeholder="标题"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-accent-300"
          />
          <textarea
            v-model="draftBody"
            rows="12"
            placeholder="正文内容，支持 Markdown。"
            class="mt-3 w-full resize-y rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] leading-6 outline-none focus:border-accent-300"
          ></textarea>
          <div class="mt-3 flex flex-wrap items-center gap-3">
            <select
              v-model="draftCollection"
              class="rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
            >
              <option value="">不归入集合</option>
              <option v-for="collection in knowledge.collections" :key="collection.id" :value="collection.id">
                {{ collection.name }}
              </option>
            </select>
            <label class="flex items-center gap-1.5 text-[12.5px] text-ink-600">
              <input v-model="draftAiEnabled" type="checkbox" class="accent-ink-900" />
              允许 AI 检索这条资料
            </label>
          </div>
        </div>
        <div class="flex justify-end gap-2 border-t border-slate-100 px-4 py-3">
          <button
            type="button"
            class="rounded-xl border border-slate-200 px-3.5 py-2 text-[12.5px] font-medium text-ink-600"
            @click="showEditor = false"
          >
            取消
          </button>
          <button
            type="button"
            :disabled="saving"
            class="rounded-xl bg-ink-900 px-4 py-2 text-[12.5px] font-medium text-white disabled:opacity-50"
            @click="saveDocument"
          >
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
