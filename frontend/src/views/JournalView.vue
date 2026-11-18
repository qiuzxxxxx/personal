<script setup lang="ts">
import { computed, onActivated, onDeactivated, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { BookPlus, Eye, PenLine, Save } from "lucide-vue-next";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";
import { extractApiError } from "@/api/client";
import { importKnowledge } from "@/api/knowledge";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";

const store = useWorkspaceStore();
const toast = useToastStore();
const route = useRoute();

const day = ref("");
const draft = ref("");
const version = ref(0);
const preview = ref(false);
const saveState = ref<"idle" | "saving" | "saved" | "failed">("idle");
const lastError = ref("");
const loading = ref(false);
const revisionByDay = new Map<string, number>();
const draftByDay = new Map<string, { content: string; dirty: boolean }>();
const saveQueues = new Map<string, Promise<void>>();
let loadSequence = 0;
let applyingLoadedDraft = false;

const saveLabel = computed(() => {
  if (saveState.value === "saving") return "保存中…";
  if (saveState.value === "saved") return "已保存";
  if (saveState.value === "failed") return "保存失败";
  return "自动保存";
});

function localToday(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

async function load(day: string): Promise<void> {
  const sequence = ++loadSequence;
  loading.value = true;
  const cached = draftByDay.get(day);
  if (cached) {
    applyingLoadedDraft = true;
    draft.value = cached.content;
    applyingLoadedDraft = false;
  }
  try {
    const entry = await store.loadJournal(day);
    if (!entry || sequence !== loadSequence || day !== JournalViewDay()) return;
    revisionByDay.set(day, entry.version);
    version.value = entry.version;
    const local = draftByDay.get(day);
    if (!local?.dirty) {
      applyingLoadedDraft = true;
      draft.value = entry.content;
      draftByDay.set(day, { content: entry.content, dirty: false });
      applyingLoadedDraft = false;
    }
    saveState.value = "idle";
    lastError.value = "";
  } catch (error) {
    if (sequence === loadSequence && day === JournalViewDay()) {
      toast.error(extractApiError(error));
    }
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

function JournalViewDay(): string {
  return day.value;
}

let timer: number | undefined;

function scheduleSave(): void {
  window.clearTimeout(timer);
  const snapshotDay = day.value;
  const snapshotContent = draft.value;
  timer = window.setTimeout(
    () => void enqueueSave(snapshotDay, snapshotContent, revisionByDay.get(snapshotDay) ?? version.value),
    800,
  );
}

function enqueueSave(snapshotDay: string, content: string, fallbackVersion: number): Promise<void> {
  if (!snapshotDay) return Promise.resolve();
  const previous = saveQueues.get(snapshotDay) ?? Promise.resolve();
  const next = previous
    .catch(() => undefined)
    .then(async () => {
      if (snapshotDay === day.value) saveState.value = "saving";
      try {
        const currentVersion = revisionByDay.get(snapshotDay) ?? fallbackVersion;
        const entry = await store.saveJournal(
          snapshotDay,
          content,
          currentVersion || undefined,
        );
        if (!entry) return;
        revisionByDay.set(snapshotDay, entry.version);
        const cached = draftByDay.get(snapshotDay);
        if (cached?.content === content) {
          draftByDay.set(snapshotDay, { content, dirty: false });
        }
        if (snapshotDay === day.value) {
          version.value = entry.version;
          saveState.value = "saved";
          lastError.value = "";
        }
      } catch (error) {
        if (snapshotDay === day.value) {
          saveState.value = "failed";
          lastError.value = extractApiError(error);
        }
        throw error;
      }
    })
    .finally(() => {
      if (saveQueues.get(snapshotDay) === next) saveQueues.delete(snapshotDay);
    });
  saveQueues.set(snapshotDay, next);
  return next;
}

async function saveNow(): Promise<void> {
  window.clearTimeout(timer);
  await enqueueSave(day.value, draft.value, revisionByDay.get(day.value) ?? version.value).catch(
    () => undefined,
  );
  if (saveState.value === "saved") {
    toast.success("每日记录已保存。");
  }
}

async function addToKnowledge(): Promise<void> {
  window.clearTimeout(timer);
  await enqueueSave(day.value, draft.value, revisionByDay.get(day.value) ?? version.value).catch(
    () => undefined,
  );
  if (saveState.value === "failed") return;
  try {
    const entry = await store.loadJournal(day.value);
    if (!entry?.id) {
      toast.error("请先写下内容并保存，再加入知识库。");
      return;
    }
    await importKnowledge({ entry: entry.id, ai_enabled: false });
    toast.success("这一天的记录已加入知识库。");
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

watch(day, (next, previous) => {
  if (previous) {
    window.clearTimeout(timer);
    const previousDraft = draftByDay.get(previous)?.content ?? draft.value;
    void enqueueSave(previous, previousDraft, revisionByDay.get(previous) ?? version.value).catch(
      () => undefined,
    );
  }
  if (next) {
    const cached = draftByDay.get(next);
    applyingLoadedDraft = true;
    draft.value = cached?.content ?? "";
    version.value = revisionByDay.get(next) ?? 0;
    applyingLoadedDraft = false;
    void load(next);
  }
});

watch(draft, () => {
  if (applyingLoadedDraft || !day.value) return;
  draftByDay.set(day.value, { content: draft.value, dirty: true });
  scheduleSave();
});

watch(
  () => route.query.date,
  (query) => {
    const target = typeof query === "string" && query ? query : localToday();
    if (day.value !== target) day.value = target;
  },
  { immediate: true },
);

onActivated(() => {
  const query = route.query.date;
  const target = typeof query === "string" && query ? query : localToday();
  if (day.value !== target) day.value = target;
});

onDeactivated(() => {
  window.clearTimeout(timer);
  if (day.value && draftByDay.get(day.value)?.dirty) {
    void enqueueSave(day.value, draft.value, revisionByDay.get(day.value) ?? version.value).catch(
      () => undefined,
    );
  }
});

onUnmounted(() => {
  window.clearTimeout(timer);
  loadSequence += 1;
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-3xl px-3 py-5 sm:px-6 sm:py-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div class="min-w-0">
          <h1 class="text-[22px] font-semibold tracking-tight text-ink-900 sm:text-[26px]">每日记录</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            记录当天的安排、进展与想法，内容按日期保存。
          </p>
        </div>
        <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-nowrap">
          <input
            v-model="day"
            type="date"
            class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300 sm:w-auto"
          />
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-[12.5px] font-medium text-ink-600 transition hover:border-accent-200 hover:text-accent-700"
            @click="addToKnowledge"
          >
            <BookPlus :size="15" />
            加入知识库
          </button>
          <button
            type="button"
            class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-ink-500 transition hover:text-accent-600"
            :title="preview ? '编辑' : '预览'"
            @click="preview = !preview"
          >
            <PenLine v-if="preview" :size="16" />
            <Eye v-else :size="16" />
          </button>
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-3.5 text-[12.5px] font-medium text-white transition hover:bg-ink-800"
            @click="saveNow"
          >
            <Save :size="14" />
            保存
          </button>
        </div>
      </header>

      <p class="mt-3 break-words text-[11.5px] text-ink-400" :class="{ 'text-rose-500': saveState === 'failed' }">
        {{ saveLabel }}<span v-if="lastError"> · {{ lastError }}</span>
      </p>

      <div class="mt-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-soft">
        <textarea
          v-if="!preview"
          v-model="draft"
          rows="18"
          maxlength="50000"
          placeholder="今天要做什么？完成了什么？有什么想法？支持 Markdown。"
          class="w-full resize-y bg-transparent text-[13.5px] leading-7 text-ink-800 outline-none placeholder:text-ink-300"
        />
        <div v-else class="min-h-[420px]">
          <MarkdownRenderer :content="draft" />
        </div>
      </div>
    </div>
  </div>
</template>
