<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { CircleAlert, Download, Loader2 } from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";
import FileIcon from "@/components/FileIcon.vue";
import { extractApiError, fetchBlob, triggerBlobDownload } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import { formatBytes } from "@/lib/format";
import { PREVIEW_LABEL, previewKind, type PreviewKind } from "@/lib/preview";

const props = defineProps<{
  open: boolean;
  name: string;
  mime?: string;
  size?: number;
  url: string;
}>();

const emit = defineEmits<{ close: [] }>();

const toast = useToastStore();
const kind = ref<PreviewKind>("none");
const objectUrl = ref("");
const textContent = ref("");
const loading = ref(false);
const failed = ref(false);
const errorText = ref("");
const mediaFailed = ref(false);
let alive = true;

const widthClass = computed(() => {
  if (kind.value === "pdf" || kind.value === "video") return "max-w-4xl";
  if (kind.value === "image") return "max-w-3xl";
  return "max-w-2xl";
});

function release(): void {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
  objectUrl.value = "";
  textContent.value = "";
}

function onMediaError(): void {
  mediaFailed.value = true;
}

async function load(): Promise<void> {
  release();
  failed.value = false;
  errorText.value = "";
  mediaFailed.value = false;
  const resolved = previewKind(props.name, props.mime || "", props.size || 0);
  kind.value = resolved;
  if (resolved === "none" || !props.url) return;

  const url = props.url;
  loading.value = true;
  try {
    const blob = await fetchBlob(url, resolved === "image" ? { inline: 1 } : undefined);
    if (!alive || !props.open || props.url !== url) return;
    if (resolved === "text" || resolved === "markdown") {
      const text = await blob.text();
      if (alive && props.open && props.url === url) textContent.value = text;
    } else if (resolved === "pdf") {
      const signature = await blob.slice(0, 5).text();
      if (!alive || !props.open || props.url !== url) return;
      if (signature !== "%PDF-") throw new Error("Invalid PDF signature");
      objectUrl.value = URL.createObjectURL(blob.slice(0, blob.size, "application/pdf"));
    } else {
      const mime = props.mime || blob.type;
      const mediaBlob = mime.startsWith(`${resolved}/`)
        ? blob.slice(0, blob.size, mime)
        : blob;
      objectUrl.value = URL.createObjectURL(mediaBlob);
    }
  } catch (error) {
    if (alive && props.url === url) {
      failed.value = true;
      errorText.value = extractApiError(error);
    }
  } finally {
    if (alive && props.url === url) loading.value = false;
  }
}

watch(() => [props.open, props.url], ([open]) => {
  if (open) void load();
  else release();
});

async function download(): Promise<void> {
  try {
    const blob = await fetchBlob(props.url);
    triggerBlobDownload(blob, props.name);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

onBeforeUnmount(() => {
  alive = false;
  release();
});
</script>

<template>
  <ModalShell
    :open="open"
    :title="name"
    :subtitle="`${PREVIEW_LABEL[kind]} · ${formatBytes(size)}`"
    :max-width="widthClass"
    @close="emit('close')"
  >
    <div class="flex min-h-[220px] items-center justify-center">
      <div v-if="loading" class="flex flex-col items-center gap-3 py-14 text-ink-400">
        <Loader2 :size="22" class="animate-spin" />
        <p class="text-[11px]">正在加载预览…</p>
      </div>

      <div v-else-if="failed" class="flex flex-col items-center gap-3 py-12 text-center">
        <span class="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
          <CircleAlert :size="19" />
        </span>
        <p class="text-[12px] font-medium text-ink-700">预览加载失败</p>
        <p class="max-w-[320px] text-[10.5px] leading-5 text-ink-400">
          {{ errorText || "文件可能已被删除，或当前账号没有下载权限。你可以尝试直接下载。" }}
        </p>
      </div>

      <template v-else>
        <img
          v-if="kind === 'image' && objectUrl && !mediaFailed"
          :src="objectUrl"
          :alt="name"
          class="max-h-[68vh] w-auto max-w-full rounded-2xl border border-slate-200/70 object-contain shadow-sm"
          @error="onMediaError"
        />

        <iframe
          v-else-if="kind === 'pdf' && objectUrl"
          :src="objectUrl"
          class="h-[68vh] w-full rounded-2xl border border-slate-200/70 bg-slate-50"
          title="PDF 预览"
        />

        <video
          v-else-if="kind === 'video' && objectUrl && !mediaFailed"
          :src="objectUrl"
          controls
          class="max-h-[68vh] w-full rounded-2xl bg-ink-950"
          @error="onMediaError"
        />

        <audio
          v-else-if="kind === 'audio' && objectUrl && !mediaFailed"
          :src="objectUrl"
          controls
          class="w-full"
          @error="onMediaError"
        />

        <div
          v-else-if="mediaFailed"
          class="flex flex-col items-center gap-3 py-12 text-center"
        >
          <span class="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-50 text-amber-500">
            <CircleAlert :size="19" />
          </span>
          <p class="text-[12px] font-medium text-ink-700">浏览器无法解码这个文件</p>
          <p class="max-w-[320px] text-[10.5px] leading-5 text-ink-400">
            可能是浏览器不支持的编码（例如 H.265/HEVC 视频、特殊音频编码），或文件已损坏。请下载后使用本地播放器打开。
          </p>
        </div>

        <div
          v-else-if="kind === 'markdown'"
          class="max-h-[62vh] w-full overflow-y-auto rounded-2xl border border-slate-200/70 bg-white px-5 py-4"
        >
          <MarkdownRenderer :content="textContent" />
        </div>

        <pre
          v-else-if="kind === 'text'"
          class="max-h-[62vh] w-full overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-slate-200/70 bg-slate-50 px-5 py-4 font-mono text-[11px] leading-6 text-ink-700"
        >{{ textContent }}</pre>

        <div v-else class="flex flex-col items-center gap-3 py-12 text-center">
          <FileIcon :name="name" :mime="mime" size="lg" />
          <p class="text-[12px] font-medium text-ink-700">该类型暂不支持在线预览</p>
          <p class="max-w-[300px] text-[10.5px] leading-5 text-ink-400">
            出于安全考虑，可执行文件、压缩包与办公文档等仅提供下载，请在本地受信环境中打开。
          </p>
        </div>
      </template>
    </div>

    <template #footer>
      <span class="mr-auto text-[9.5px] text-ink-300">
        预览在本地浏览器内渲染，不会二次上传
      </span>
      <button type="button" class="btn-secondary" @click="emit('close')">关闭</button>
      <button type="button" class="btn-primary" @click="download">
        <Download :size="13" />
        下载文件
      </button>
    </template>
  </ModalShell>
</template>
