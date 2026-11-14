<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { Paperclip, Send, SlidersHorizontal, X, Loader2, UploadCloud, Image as ImageIcon } from "lucide-vue-next";
import FileIcon from "@/components/FileIcon.vue";
import { formatBytes } from "@/lib/format";
import { useToastStore } from "@/stores/toast";
import type { LocalUploadFile } from "@/types";

const props = withDefaults(
  defineProps<{
    busy?: boolean;
    disabled?: boolean;
    providerLabel?: string;
    configured?: boolean;
    placeholder?: string;
  }>(),
  {
    busy: false,
    disabled: false,
    providerLabel: "DeepSeek",
    configured: false,
    placeholder: "向 zixxx 提问，或拖入文件…",
  },
);

const emit = defineEmits<{
  send: [payload: { text: string; files: File[] }];
  "open-settings": [];
}>();

const toast = useToastStore();
const draft = ref("");
const files = ref<LocalUploadFile[]>([]);
const dragging = ref(false);
const composing = ref(false);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const dragDepth = ref(0);
const MAX_FILES = 5;
const MAX_BYTES = 25 * 1024 * 1024;
const ALLOWED = new Set(["pdf", "docx", "txt", "md", "markdown", "png", "jpg", "jpeg", "webp"]);

const canSend = computed(() => !props.busy && !props.disabled && Boolean(draft.value.trim() || files.value.length));

function autoResize(): void {
  const element = textareaRef.value;
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight, 190)}px`;
}

watch(draft, () => nextTick(autoResize));

function focus(): void {
  textareaRef.value?.focus();
}

function setDraft(value: string): void {
  draft.value = value;
  nextTick(() => {
    autoResize();
    focus();
  });
}

function openFilePicker(): void {
  if (props.busy || props.disabled) return;
  fileInputRef.value?.click();
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
}

function addFiles(incoming: FileList | File[]): void {
  if (props.busy || props.disabled) return;
  const list = Array.from(incoming);
  for (const file of list) {
    if (files.value.length >= MAX_FILES) {
      toast.error(`最多同时添加 ${MAX_FILES} 个附件`);
      break;
    }
    if (!ALLOWED.has(extensionOf(file.name))) {
      toast.error(`${file.name} 的格式暂不支持`);
      continue;
    }
    if (file.size > MAX_BYTES) {
      toast.error(`${file.name} 超过 25 MB`);
      continue;
    }
    if (file.size === 0) {
      toast.error(`${file.name} 是空文件`);
      continue;
    }
    const duplicate = files.value.some(
      (item) =>
        item.file.name === file.name &&
        item.file.size === file.size &&
        item.file.lastModified === file.lastModified,
    );
    if (duplicate) continue;
    files.value.push({
      file,
      previewUrl: URL.createObjectURL(file),
      id: `${file.name}-${file.size}-${Math.random().toString(36).slice(2)}`,
    });
  }
  if (dragging.value) dragging.value = false;
  if (files.value.length) focus();
}

function removeFile(id: string): void {
  const target = files.value.find((item) => item.id === id);
  if (target) URL.revokeObjectURL(target.previewUrl);
  files.value = files.value.filter((item) => item.id !== id);
}

function clearFiles(): void {
  for (const item of files.value) URL.revokeObjectURL(item.previewUrl);
  files.value = [];
}

function clear(): void {
  draft.value = "";
  clearFiles();
  nextTick(autoResize);
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  if (input.files) addFiles(input.files);
  input.value = "";
}

function onDrop(event: DragEvent): void {
  event.preventDefault();
  dragDepth.value = 0;
  if (event.dataTransfer?.files?.length) addFiles(event.dataTransfer.files);
  dragging.value = false;
}

function onDragEnter(event: DragEvent): void {
  event.preventDefault();
  dragDepth.value += 1;
  if (event.dataTransfer?.types?.includes("Files")) dragging.value = true;
}

function onDragLeave(event: DragEvent): void {
  event.preventDefault();
  dragDepth.value = Math.max(0, dragDepth.value - 1);
  if (dragDepth.value === 0) dragging.value = false;
}

function onPaste(event: ClipboardEvent): void {
  const clipboardFiles = Array.from(event.clipboardData?.files || []);
  if (!clipboardFiles.length) return;
  event.preventDefault();
  addFiles(clipboardFiles);
}

function submit(): void {
  if (!canSend.value) return;
  emit("send", {
    text: draft.value.trim(),
    files: files.value.map((item) => item.file),
  });
  clear();
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey && !composing.value && !event.isComposing) {
    event.preventDefault();
    submit();
  }
}

function onCompositionStart(): void {
  composing.value = true;
}

function onCompositionEnd(): void {
  composing.value = false;
}

onBeforeUnmount(clearFiles);

defineExpose({ setDraft, focus, openFilePicker, addFiles, clear });
</script>

<template>
  <div
    class="composer-shell relative rounded-[27px] border border-slate-200/90 bg-white/95 shadow-composer backdrop-blur-xl transition duration-300 focus-within:border-accent-300/80 focus-within:shadow-[0_28px_80px_-28px_rgba(48,87,223,0.28)]"
    :class="{ 'opacity-90': disabled }"
    @dragenter="onDragEnter"
    @dragover.prevent
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <Transition name="fade">
      <div
        v-if="dragging"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-[27px] border-2 border-dashed border-accent-400 bg-accent-50/95 backdrop-blur-sm"
      >
        <span class="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-accent-600 shadow-sm">
          <UploadCloud :size="22" />
        </span>
        <p class="text-sm font-medium text-accent-700">松开以上传附件</p>
        <p class="text-[11px] text-accent-500">PDF · DOCX · TXT · MD · 图片</p>
      </div>
    </Transition>

    <div v-if="files.length" class="flex flex-wrap gap-2 px-4 pt-4">
      <div
        v-for="item in files"
        :key="item.id"
        class="group relative flex max-w-full items-center gap-2.5 rounded-2xl border border-slate-200/80 bg-slate-50/80 py-1.5 pl-1.5 pr-8"
      >
        <img
          v-if="item.file.type.startsWith('image/')"
          :src="item.previewUrl"
          :alt="item.file.name"
          class="h-9 w-9 rounded-xl object-cover ring-1 ring-black/5"
        />
        <FileIcon
          v-else
          :name="item.file.name"
          :mime="item.file.type"
          size="sm"
          rounded="rounded-xl"
        />
        <span class="min-w-0">
          <span class="block max-w-[190px] truncate text-[11.5px] font-medium text-ink-700">
            {{ item.file.name }}
          </span>
          <span class="block text-[10px] text-ink-400">{{ formatBytes(item.file.size) }}</span>
        </span>
        <button
          type="button"
          class="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-ink-400 transition hover:bg-white hover:text-rose-500 hover:shadow-sm"
          :aria-label="`移除 ${item.file.name}`"
          @click="removeFile(item.id)"
        >
          <X :size="13" />
        </button>
      </div>
    </div>

    <div class="flex items-end gap-2 px-3 py-2.5 sm:px-4 sm:py-3">
      <button
        type="button"
        class="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-500 transition hover:bg-slate-100 hover:text-ink-900 disabled:cursor-not-allowed disabled:opacity-40"
        title="添加附件"
        :disabled="busy || disabled"
        @click="openFilePicker"
      >
        <Paperclip :size="19" :stroke-width="1.9" />
      </button>
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        multiple
        accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
        @change="onFileChange"
      />

      <textarea
        ref="textareaRef"
        v-model="draft"
        rows="1"
        :placeholder="placeholder"
        :disabled="busy || disabled"
        class="composer-textarea min-h-[40px] max-h-[190px] min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-[15px] leading-6 text-ink-900 outline-none placeholder:text-ink-400 disabled:cursor-not-allowed"
        @keydown="onKeydown"
        @compositionstart="onCompositionStart"
        @compositionend="onCompositionEnd"
        @paste="onPaste"
        @input="autoResize"
      />

      <div class="mb-0.5 flex shrink-0 items-center gap-1">
        <button
          type="button"
          class="hidden h-9 items-center gap-1.5 rounded-full px-3 text-[11px] font-medium text-ink-500 transition hover:bg-slate-100 hover:text-ink-800 sm:flex"
          title="API 设置"
          @click="emit('open-settings')"
        >
          <SlidersHorizontal :size="14" />
          <span class="max-w-[96px] truncate">{{ providerLabel }}</span>
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="configured ? 'bg-emerald-400' : 'bg-amber-400'"
          />
        </button>
        <button
          type="button"
          class="flex h-10 w-10 items-center justify-center rounded-full bg-ink-900 text-white shadow-sm transition hover:bg-accent-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          :disabled="!canSend"
          :aria-label="busy ? '正在生成' : '发送'"
          @click="submit"
        >
          <Loader2 v-if="busy" :size="18" class="animate-spin" />
          <Send v-else :size="17" :stroke-width="2" />
        </button>
      </div>
    </div>

    <div class="flex items-center gap-2 border-t border-slate-100/80 px-4 py-2">
      <span class="flex items-center gap-1.5 text-[10px] text-ink-400">
        <ImageIcon :size="11" />
        支持图片、PDF、Word 与文本
      </span>
      <span class="ml-auto hidden text-[10px] text-ink-300 sm:block">
        Enter 发送 · Shift + Enter 换行
      </span>
      <button
        type="button"
        class="flex items-center gap-1 text-[10px] font-medium text-ink-400 transition hover:text-ink-700 sm:hidden"
        @click="emit('open-settings')"
      >
        <SlidersHorizontal :size="11" />
        API
      </button>
    </div>
  </div>
</template>