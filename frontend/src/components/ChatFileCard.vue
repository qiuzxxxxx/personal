<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Download, Loader2, Maximize2, AlertCircle, Eye } from "lucide-vue-next";
import FileIcon from "@/components/FileIcon.vue";
import FilePreviewModal from "@/components/FilePreviewModal.vue";
import { fetchBlob, triggerBlobDownload } from "@/api/client";
import { formatBytes } from "@/lib/format";
import { previewKind } from "@/lib/preview";
import { useToastStore } from "@/stores/toast";
import type { ChatMessage } from "@/types";

const props = defineProps<{
  message: ChatMessage;
  self?: boolean;
}>();

const toast = useToastStore();
const previewUrl = ref("");
const previewLoading = ref(false);
const previewFailed = ref(false);
const downloading = ref(false);
const previewOpen = ref(false);
let alive = true;

const kind = computed(() =>
  previewKind(props.message.file_name, props.message.file_type, props.message.file_size),
);

const extension = computed(() => {
  const name = props.message.file_name || "";
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toUpperCase() : "FILE";
});

async function loadPreview(): Promise<void> {
  if (!props.message.is_image || !props.message.file_url) return;
  previewLoading.value = true;
  previewFailed.value = false;
  try {
    const blob = await fetchBlob(props.message.file_url, { inline: 1 });
    if (!alive) return;
    previewUrl.value = URL.createObjectURL(blob);
  } catch {
    if (alive) previewFailed.value = true;
  } finally {
    if (alive) previewLoading.value = false;
  }
}

function openPreview(): void {
  if (kind.value === "none") return;
  previewOpen.value = true;
}

async function download(): Promise<void> {
  if (downloading.value) return;
  downloading.value = true;
  try {
    const blob = await fetchBlob(props.message.file_url);
    triggerBlobDownload(blob, props.message.file_name || "文件");
  } catch {
    toast.error("文件下载失败，请稍后重试");
  } finally {
    downloading.value = false;
  }
}

onMounted(loadPreview);

onBeforeUnmount(() => {
  alive = false;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});
</script>

<template>
  <div
    class="group overflow-hidden rounded-[20px] border bg-white/92 shadow-[0_10px_30px_-24px_rgba(15,23,42,0.35)] backdrop-blur"
    :class="self ? 'border-accent-100' : 'border-slate-200/80'"
  >
    <template v-if="message.is_image && !previewFailed">
      <div
        class="relative w-[250px] max-w-full cursor-zoom-in overflow-hidden bg-slate-100 sm:w-[300px]"
        role="button"
        tabindex="0"
        :aria-label="`预览 ${message.file_name}`"
        @click="openPreview"
        @keydown.enter="openPreview"
      >
        <div v-if="previewLoading" class="flex h-[190px] items-center justify-center bg-slate-100">
          <Loader2 :size="20" class="animate-spin text-slate-400" />
        </div>
        <img
          v-else-if="previewUrl"
          :src="previewUrl"
          :alt="message.file_name"
          class="max-h-[330px] w-full object-cover"
        />
        <div
          v-if="previewUrl"
          class="pointer-events-none absolute inset-0 bg-gradient-to-t from-ink-950/40 via-transparent to-transparent opacity-0 transition group-hover:opacity-100"
        />
        <span
          v-if="previewUrl"
          class="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-ink-950/45 text-white opacity-0 backdrop-blur transition hover:opacity-100"
        >
          <Maximize2 :size="13" />
        </span>
      </div>
    </template>

    <div class="flex items-center gap-2.5 p-2.5">
      <FileIcon
        v-if="!message.is_image || previewFailed"
        :name="message.file_name"
        :mime="message.file_type"
        size="sm"
        rounded="rounded-xl"
      />
      <span v-else class="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-[8px] font-semibold text-rose-400">
        IMG
      </span>
      <div class="min-w-0 flex-1">
        <p class="truncate text-[11.5px] font-medium text-ink-700" :title="message.file_name">
          {{ message.file_name }}
        </p>
        <p class="mt-0.5 flex items-center gap-1.5 text-[9px] text-ink-400">
          <span class="font-mono">{{ extension }}</span>
          <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
          {{ formatBytes(message.file_size) }}
          <template v-if="previewFailed">
            <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
            <span class="flex items-center gap-0.5 text-amber-500">
              <AlertCircle :size="8" /> 预览不可用
            </span>
          </template>
        </p>
      </div>
      <button
        v-if="kind !== 'none'"
        type="button"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-400 transition hover:bg-slate-100 hover:text-ink-800"
        aria-label="在线预览"
        title="在线预览"
        @click="previewOpen = true"
      >
        <Eye :size="14" />
      </button>
      <button
        type="button"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-400 transition hover:bg-slate-100 hover:text-ink-800 disabled:opacity-50"
        aria-label="下载文件"
        :disabled="downloading"
        @click="download"
      >
        <Loader2 v-if="downloading" :size="14" class="animate-spin" />
        <Download v-else :size="14" />
      </button>
    </div>

    <FilePreviewModal
      :open="previewOpen"
      :name="message.file_name"
      :mime="message.file_type"
      :size="message.file_size"
      :url="message.file_url"
      @close="previewOpen = false"
    />
  </div>
</template>
