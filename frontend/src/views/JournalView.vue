<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { Eye, PenLine, Save } from "lucide-vue-next";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";
import { extractApiError } from "@/api/client";
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
  loading.value = true;
  try {
    const entry = await store.loadJournal(day);
    if (!entry) return;
    draft.value = entry.content;
    version.value = entry.version;
    saveState.value = "idle";
    lastError.value = "";
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    loading.value = false;
  }
}

let timer: number | undefined;

function scheduleSave(): void {
  window.clearTimeout(timer);
  timer = window.setTimeout(() => void persist(), 800);
}

async function persist(): Promise<void> {
  if (!day.value) return;
  saveState.value = "saving";
  try {
    const entry = await store.saveJournal(
      day.value,
      draft.value,
      version.value || undefined,
    );
    if (!entry) return;
    version.value = entry.version;
    saveState.value = "saved";
    lastError.value = "";
  } catch (error) {
    saveState.value = "failed";
    lastError.value = extractApiError(error);
  }
}

async function saveNow(): Promise<void> {
  window.clearTimeout(timer);
  await persist();
  if (saveState.value === "saved") {
    toast.success("每日记录已保存。");
  }
}

watch(day, (next, previous) => {
  if (previous) {
    window.clearTimeout(timer);
  }
  if (next) void load(next);
});

watch(draft, () => {
  if (loading.value) return;
  scheduleSave();
});

onMounted(() => {
  const query = route.query.date;
  day.value = typeof query === "string" && query ? query : localToday();
  void load(day.value);
});

onUnmounted(() => {
  window.clearTimeout(timer);
});
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-[26px] font-semibold tracking-tight text-ink-900">每日记录</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            记录当天的安排、进展与想法，内容按日期保存。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <input
            v-model="day"
            type="date"
            class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
          />
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

      <p class="mt-3 text-[11.5px] text-ink-400" :class="{ 'text-rose-500': saveState === 'failed' }">
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
