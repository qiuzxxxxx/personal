<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Camera, CheckCircle2, FileUp, RotateCcw, TriangleAlert } from "lucide-vue-next";
import {
  fetchPhoneSession,
  prepareReceipt,
  uploadReceiptContent,
  type UploadSessionPayload,
} from "@/api/upload";

interface UploadItem {
  id: string;
  name: string;
  size: number;
  file: File;
  status: "pending" | "uploading" | "done" | "failed";
  progress: number;
  error: string;
}

const token = ref("");
const session = ref<UploadSessionPayload | null>(null);
const items = ref<UploadItem[]>([]);
const fatal = ref("");
const busy = ref(false);

const doneCount = computed(() => items.value.filter((item) => item.status === "done").length);
const failedCount = computed(() => items.value.filter((item) => item.status === "failed").length);

const limitLabel = computed(() => {
  if (!session.value) return "";
  const max = session.value.quota.max_file_bytes;
  const maxLabel = max >= 1024 * 1024 * 1024
    ? `${(max / 1024 / 1024 / 1024).toFixed(max % (1024 * 1024 * 1024) ? 1 : 0)} GB`
    : `${Math.round(max / 1024 / 1024)} MB`;
  return `单个文件上限 ${maxLabel}，每个会话最多 ${session.value.quota.max_files} 个文件`;
});

function readCredentials(): { token: string; sessionId: string } | null {
  const hash = window.location.hash.replace(/^#/, "");
  const params = new URLSearchParams(hash);
  const uploadToken = params.get("token") || "";
  const sessionId = params.get("session") || "";
  // The credential leaves the address bar immediately.
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  if (!uploadToken || !sessionId) return null;
  return { token: uploadToken, sessionId };
}

async function loadSession(): Promise<void> {
  try {
    session.value = await fetchPhoneSession(token.value);
  } catch (error) {
    fatal.value = error instanceof Error ? error.message : "会话无效，请重新扫码。";
  }
}

function addFiles(files: FileList | null): void {
  if (!files) return;
  for (const file of Array.from(files)) {
    items.value.push({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: file.name,
      size: file.size,
      file,
      status: "pending",
      progress: 0,
      error: "",
    });
  }
  void startQueue();
}

async function startQueue(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    for (const item of items.value) {
      if (item.status !== "pending") continue;
      item.status = "uploading";
      item.progress = 0;
      try {
        const receipt = await prepareReceipt(token.value, {
          client_upload_id: item.id,
          original_name: item.name,
          declared_size: item.size,
        });
        await uploadReceiptContent(token.value, receipt.id, item.file, (percent) => {
          item.progress = percent;
        });
        item.status = "done";
        item.progress = 100;
      } catch (error) {
        item.status = "failed";
        item.error = error instanceof Error ? error.message : "上传失败。";
      }
    }
  } finally {
    busy.value = false;
  }
}

async function retry(item: UploadItem): Promise<void> {
  item.status = "pending";
  item.error = "";
  item.progress = 0;
  await startQueue();
}

onMounted(async () => {
  const credentials = readCredentials();
  if (!credentials) {
    fatal.value = "缺少上传凭证，请重新扫描电脑上的二维码。";
    return;
  }
  token.value = credentials.token;
  await loadSession();
});
</script>

<template>
  <div class="min-h-screen bg-canvas">
    <div class="mx-auto w-full max-w-lg px-4 py-8">
      <header class="text-center">
        <h1 class="text-[20px] font-semibold text-ink-900">向工作台上传资料</h1>
        <p class="mt-2 text-[12.5px] leading-6 text-ink-500">
          资料会直接进入对方的工作台资料库，仅对方可见。
        </p>
      </header>

      <div
        v-if="fatal"
        class="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-[12.5px] text-rose-700"
      >
        <p class="flex items-center gap-2 font-medium">
          <TriangleAlert :size="15" />
          {{ fatal }}
        </p>
      </div>

      <div
        v-else
        class="mt-6 space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-soft"
      >
        <p v-if="session" class="text-[12px] leading-6 text-ink-500">
          {{ limitLabel }}
          <span v-if="session.destination.task_title"> · 目标：{{ session.destination.task_title }}</span>
          <span v-else-if="session.destination.folder_name"> · 目标：{{ session.destination.folder_name }}</span>
        </p>

        <label
          class="flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-ink-900 px-4 py-3 text-[13px] font-medium text-white transition hover:bg-ink-800"
        >
          <FileUp :size="16" />
          选择文件
          <input
            type="file"
            multiple
            class="hidden"
            @change="addFiles(($event.target as HTMLInputElement).files)"
          />
        </label>

        <label
          class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-[13px] font-medium text-ink-600 transition hover:border-accent-200"
        >
          <Camera :size="16" />
          拍照上传
          <input
            type="file"
            accept="image/*"
            capture="environment"
            class="hidden"
            @change="addFiles(($event.target as HTMLInputElement).files)"
          />
        </label>

        <p class="text-center text-[11.5px] text-ink-400">
          已完成 {{ doneCount }} 个
          <span v-if="failedCount"> · 失败 {{ failedCount }} 个</span>
        </p>
      </div>

      <ul v-if="items.length" class="mt-4 space-y-2">
        <li
          v-for="item in items"
          :key="item.id"
          class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
        >
          <p class="truncate text-[13px] text-ink-800">{{ item.name }}</p>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full transition-all"
              :class="item.status === 'failed' ? 'bg-rose-400' : 'bg-accent-500'"
              :style="{ width: `${item.status === 'done' ? 100 : item.progress}%` }"
            ></div>
          </div>
          <div class="mt-2 flex items-center gap-2 text-[11.5px]">
            <span
              v-if="item.status === 'done'"
              class="inline-flex items-center gap-1 text-emerald-600"
            >
              <CheckCircle2 :size="13" />
              已上传
            </span>
            <span v-else-if="item.status === 'uploading'" class="text-ink-500">
              上传中 {{ item.progress }}%
            </span>
            <span v-else-if="item.status === 'failed'" class="text-rose-600">
              {{ item.error }}
            </span>
            <span v-else class="text-ink-400">等待上传</span>
            <button
              v-if="item.status === 'failed'"
              type="button"
              class="ml-auto inline-flex items-center gap-1 text-accent-600"
              @click="retry(item)"
            >
              <RotateCcw :size="12" />
              重试
            </button>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
