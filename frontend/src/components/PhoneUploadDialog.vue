<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import QRCode from "qrcode";
import { RefreshCw, Square, X } from "lucide-vue-next";
import {
  createUploadSession,
  fetchUploadSession,
  revokeUploadSession,
  type UploadReceiptPayload,
  type UploadSessionPayload,
} from "@/api/upload";
import type { LibraryMaterial } from "@/api/workspace";

const props = defineProps<{
  folderId?: string;
  taskId?: string;
  targetLabel?: string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "received", materials: LibraryMaterial[]): void;
}>();

const session = ref<UploadSessionPayload | null>(null);
const qrImage = ref("");
const qrWarning = ref("");
const error = ref("");
const revoking = ref(false);
const revokeUnconfirmed = ref(false);
const now = ref(Date.now());
const receipts = ref<UploadReceiptPayload[]>([]);
const received = ref<LibraryMaterial[]>([]);

let timer: number | undefined;
let pollTimer: number | undefined;

const remainingSeconds = computed(() => {
  if (!session.value) return 0;
  const expires = new Date(session.value.expires_at).getTime();
  return Math.max(0, Math.round((expires - now.value) / 1000));
});

const remainingLabel = computed(() => {
  const total = remainingSeconds.value;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
});

const committedCount = computed(
  () => receipts.value.filter((receipt) => receipt.state === "committed").length,
);

async function createSession(): Promise<void> {
  error.value = "";
  try {
    const created = await createUploadSession({
      folder: props.folderId,
      task: props.taskId,
    });
    session.value = created;
    qrWarning.value = created.qr_warning || "";
    if (created.qr_payload) {
      qrImage.value = await QRCode.toDataURL(created.qr_payload, {
        width: 320,
        margin: 2,
        errorCorrectionLevel: "M",
      });
    } else {
      qrImage.value = "";
    }
    startPolling();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "创建上传会话失败。";
  }
}

function startPolling(): void {
  window.clearInterval(pollTimer);
  pollTimer = window.setInterval(() => {
    if (document.visibilityState !== "visible") return;
    void refreshStatus();
  }, 3000);
}

async function refreshStatus(): Promise<void> {
  if (!session.value) return;
  try {
    const status = await fetchUploadSession(session.value.id);
    session.value = status;
    receipts.value = status.receipts || [];
    const materials = status.materials || [];
    const fresh = materials.filter(
      (material) => !received.value.some((item) => item.id === material.id),
    );
    if (fresh.length) {
      received.value = [...received.value, ...fresh];
      emit("received", fresh);
    }
  } catch {
    // Polling errors are transient; the expiry timestamp remains authoritative.
  }
}

async function regenerate(): Promise<void> {
  if (session.value) {
    try {
      await revokeUploadSession(session.value.id);
    } catch {
      // A failed revoke is reported when the user explicitly stops receiving.
    }
  }
  await createSession();
}

async function stopReceiving(): Promise<void> {
  if (!session.value) {
    emit("close");
    return;
  }
  revoking.value = true;
  try {
    await revokeUploadSession(session.value.id);
    window.clearInterval(pollTimer);
    emit("close");
  } catch {
    revokeUnconfirmed.value = true;
  } finally {
    revoking.value = false;
  }
}

onMounted(async () => {
  await createSession();
  timer = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onUnmounted(() => {
  window.clearInterval(timer);
  window.clearInterval(pollTimer);
});
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4">
    <div class="max-h-[92dvh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-5 shadow-xl" role="dialog" aria-modal="true" aria-labelledby="phone-upload-title">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 id="phone-upload-title" class="text-[15px] font-semibold text-ink-900">手机扫码上传</h2>
          <p class="mt-1 text-[12px] text-ink-400">
            目标：{{ targetLabel || "私人资料库" }} · 剩余 {{ remainingLabel }}
          </p>
        </div>
        <button type="button" class="icon-button h-11 w-11 shrink-0" aria-label="关闭并停止接收" @click="stopReceiving">
          <X :size="17" />
        </button>
      </div>

      <p class="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-[11.5px] leading-5 text-amber-700">
        持有二维码的人可以在有效期内向此处投递文件，上传的资料只进入你的私人资料库。
      </p>

      <div class="mt-4 flex flex-col items-center">
        <div
          class="flex h-[248px] w-[248px] items-center justify-center rounded-2xl border border-slate-200 bg-white p-3"
        >
          <img v-if="qrImage" :src="qrImage" alt="手机上传二维码" class="h-full w-full" />
          <p v-else class="px-3 text-center text-[12px] text-ink-400">
            二维码不可用，请检查 PUBLIC_BASE_URL 配置。
          </p>
        </div>
        <p v-if="qrWarning" class="mt-2 text-[11.5px] text-amber-600">{{ qrWarning }}</p>
        <p v-if="error" class="mt-2 text-[11.5px] text-rose-600">{{ error }}</p>
        <p class="mt-3 text-[12px] text-ink-500">
          已接收 {{ committedCount }} 个文件 · 配额 {{ session?.quota.max_files }} 个 /
          {{ Math.round((session?.quota.max_bytes || 0) / 1024 / 1024) }} MB
        </p>
      </div>

      <ul v-if="received.length" class="mt-3 max-h-32 space-y-1 overflow-y-auto">
        <li
          v-for="material in received"
          :key="material.id"
          class="truncate rounded-lg bg-slate-50 px-2.5 py-1.5 text-[11.5px] text-ink-600"
        >
          {{ material.original_name }}
        </li>
      </ul>

      <p v-if="revokeUnconfirmed" class="mt-3 text-[11.5px] text-rose-600">
        停止接收未确认：网络请求失败，二维码可能仍然有效，请以会话过期时间为准。
      </p>

      <div class="mt-4 flex items-center gap-2">
        <button
          type="button"
          class="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-xl border border-slate-200 text-[12.5px] font-medium text-ink-600 transition hover:border-accent-200"
          @click="regenerate"
        >
          <RefreshCw :size="14" />
          重新生成
        </button>
        <button
          type="button"
          :disabled="revoking"
          class="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-xl bg-ink-900 text-[12.5px] font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
          @click="stopReceiving"
        >
          <Square :size="13" />
          停止接收
        </button>
      </div>
    </div>
  </div>
</template>
