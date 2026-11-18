<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  Check,
  CircleAlert,
  Download,
  Eye,
  EyeOff,
  Megaphone,
  FolderOpen,
  Globe2,
  Loader2,
  LockKeyhole,
  LogIn,
  Pencil,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import brandLogo from "@/assets/brand/zixxx-logo.png";
import FileIcon from "@/components/FileIcon.vue";
import TransferThumbnail from "@/components/TransferThumbnail.vue";
import FilePreviewModal from "@/components/FilePreviewModal.vue";
import UsageTermsModal from "@/components/UsageTermsModal.vue";
import { useAuthStore } from "@/stores/auth";
import { useAnnouncementStore } from "@/stores/announcements";
import { useToastStore } from "@/stores/toast";
import api, {
  extractApiError,
  requestPath,
  triggerBlobDownload,
} from "@/api/client";
import {
  deleteTransferFile,
  getLoginAnnouncement,
  getTransferAnnouncement,
  listTransferFiles,
  patchTransferFile,
  saveLoginAnnouncement,
  saveTransferAnnouncement,
  uploadTransferFile,
} from "@/api/transfer";
import {
  downloadNameFromDisposition,
  fileExtension,
  formatBytes,
  formatRelative,
} from "@/lib/format";
import { previewKind } from "@/lib/preview";
import { acceptTerms, termsAccepted } from "@/lib/terms";
import type { TransferFile } from "@/types";

const router = useRouter();
const auth = useAuthStore();
const announcements = useAnnouncementStore();
const toast = useToastStore();

defineOptions({ name: "TransferStation" });

const files = ref<TransferFile[]>([]);
const announcement = ref("");
const loginAnnouncement = ref("");
const loading = ref(true);
const loadError = ref("");
const search = ref("");
const filter = ref<"all" | "public" | "private">("all");
const selectedFile = ref<File | null>(null);
const isPublic = ref(true);
const remark = ref("");
const uploaderName = ref("");
const uploading = ref(false);
const uploadProgress = ref(0);
const dragDepth = ref(0);
const dragging = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);
const downloadingId = ref("");
const togglingId = ref("");
const refreshBusy = ref(false);

const editOpen = ref(false);
const editing = ref<TransferFile | null>(null);
const editName = ref("");
const editRemark = ref("");
const editVisibleUntil = ref("");
const savingEdit = ref(false);
const pendingDelete = ref<TransferFile | null>(null);
const deleting = ref(false);
const announcementEditorOpen = ref(false);
const announcementKind = ref<"transfer" | "login">("transfer");
const announcementDraft = ref("");
const savingAnnouncement = ref(false);
const agreed = ref(termsAccepted());
const termsOpen = ref(false);
const termsAcceptMode = ref(false);
const previewTarget = ref<TransferFile | null>(null);
const announcementHistoryOpen = ref(false);

const MAX_BYTES = 1024 * 1024 * 1024;
const isAdmin = computed(() => auth.isSuper);

const publicCount = computed(() => files.value.filter((file) => file.is_public).length);
const privateCount = computed(() => files.value.filter((file) => !file.is_public).length);

const visibleFiles = computed(() => {
  let result = files.value;
  if (isAdmin.value && filter.value !== "all") {
    result = result.filter((file) =>
      filter.value === "public" ? file.is_public : !file.is_public,
    );
  }
  const keyword = search.value.trim().toLowerCase();
  if (keyword) {
    result = result.filter((file) =>
      [file.original_name, file.remark, file.uploader_name]
        .join(" ")
        .toLowerCase()
        .includes(keyword),
    );
  }
  return result;
});

const filterOptions = computed(() => [
  { key: "all" as const, label: "全部", count: files.value.length },
  { key: "public" as const, label: "公开", count: publicCount.value },
  { key: "private" as const, label: "私密", count: privateCount.value },
]);

const uploadActionLabel = computed(() => {
  if (uploading.value) return `上传中 ${uploadProgress.value}%`;
  return isPublic.value ? "上传并公开" : "私密投递给管理员";
});

async function loadFiles(silent = false): Promise<void> {
  if (!silent) loading.value = true;
  try {
    const [fileResult, announcementResult, loginAnnouncementResult] = await Promise.allSettled([
      listTransferFiles(),
      getTransferAnnouncement(),
      getLoginAnnouncement(),
    ]);
    if (fileResult.status === "rejected") throw fileResult.reason;
    files.value = fileResult.value;
    if (announcementResult.status === "fulfilled") {
      announcement.value = announcementResult.value.content;
    }
    if (loginAnnouncementResult.status === "fulfilled") {
      loginAnnouncement.value = loginAnnouncementResult.value.content;
    }
    loadError.value = "";
  } catch (error) {
    loadError.value = extractApiError(error);
    if (!silent) toast.error(loadError.value);
  } finally {
    loading.value = false;
    refreshBusy.value = false;
  }
}

function openAnnouncement(): void {
  announcementHistoryOpen.value = true;
  void announcements.load(true);
  void announcements.loadHistory(true).then(() => announcements.markSeen());
}

function openAnnouncementEditor(kind: "transfer" | "login"): void {
  if (!isAdmin.value) return;
  announcementKind.value = kind;
  announcementDraft.value = kind === "transfer" ? announcement.value : loginAnnouncement.value;
  announcementEditorOpen.value = true;
}

async function saveAnnouncement(): Promise<void> {
  if (!isAdmin.value || savingAnnouncement.value) return;
  savingAnnouncement.value = true;
  try {
    const content = announcementDraft.value.trim();
    const result = announcementKind.value === "transfer"
      ? await saveTransferAnnouncement(content)
      : await saveLoginAnnouncement(content);
    if (announcementKind.value === "transfer") announcement.value = result.content;
    else loginAnnouncement.value = result.content;
    announcementEditorOpen.value = false;
    // 侧边栏“公告”入口与弹窗共用 store，发布后立即同步并标记已读。
    void announcements.load(true);
    void announcements.loadHistory(true).then(() => announcements.markSeen());
    toast.success(content ? "公告已发布" : "公告已撤下");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingAnnouncement.value = false;
  }
}

async function refresh(): Promise<void> {
  refreshBusy.value = true;
  await loadFiles(true);
}

function goToLogin(): void {
  router.push({ path: "/", query: { redirect: "/transfer" } });
}

function openFilePicker(): void {
  if (uploading.value) return;
  if (!ensureAgreed()) return;
  fileInputRef.value?.click();
}

function ensureAgreed(): boolean {
  if (agreed.value) return true;
  termsAcceptMode.value = true;
  termsOpen.value = true;
  toast.info("请先阅读并同意《使用声明》");
  return false;
}

function onAgreeChange(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked;
  if (!checked) return;
  acceptTerms();
  agreed.value = true;
  toast.success("已同意《使用声明》，可以开始上传");
}

function openTerms(acceptMode: boolean): void {
  termsAcceptMode.value = acceptMode;
  termsOpen.value = true;
}

function onAcceptTerms(): void {
  acceptTerms();
  agreed.value = true;
  termsOpen.value = false;
  toast.success("已同意《使用声明》");
}

function previewKindOf(file: TransferFile) {
  return previewKind(file.original_name, file.file_type, file.file_size);
}

function extOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toUpperCase() : "FILE";
}

function selectFile(file: File | null): void {
  if (!file) return;
  if (file.size <= 0) {
    toast.error("不能上传空文件");
    return;
  }
  if (file.size > MAX_BYTES) {
    toast.error("文件超过 1 GB");
    return;
  }
  selectedFile.value = file;
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectFile(input.files?.[0] || null);
  input.value = "";
}

function onDrop(event: DragEvent): void {
  event.preventDefault();
  dragDepth.value = 0;
  dragging.value = false;
  if (uploading.value) return;
  if (!ensureAgreed()) return;
  const file = event.dataTransfer?.files?.[0];
  if (file) selectFile(file);
}

function onDragEnter(event: DragEvent): void {
  event.preventDefault();
  if (uploading.value) return;
  dragDepth.value += 1;
  if (event.dataTransfer?.types?.includes("Files")) dragging.value = true;
}

function onDragLeave(event: DragEvent): void {
  event.preventDefault();
  dragDepth.value = Math.max(0, dragDepth.value - 1);
  if (dragDepth.value === 0) dragging.value = false;
}

function removeSelected(): void {
  if (uploading.value) return;
  selectedFile.value = null;
}

async function upload(): Promise<void> {
  if (!selectedFile.value || uploading.value) return;
  if (!ensureAgreed()) return;
  const target = selectedFile.value;
  uploading.value = true;
  uploadProgress.value = 0;
  try {
    await uploadTransferFile(
      {
        file: target,
        isPublic: isPublic.value,
        remark: remark.value.trim(),
        uploaderName: uploaderName.value.trim(),
      },
      (percent) => {
        uploadProgress.value = percent;
      },
    );
    const wasPublic = isPublic.value;
    selectedFile.value = null;
    remark.value = "";
    await loadFiles(true);
    if (wasPublic) {
      toast.success("已上传，所有人现在都可以下载");
    } else {
      toast.success("已私密投递，只有最高管理员可以看到这个文件");
    }
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
  }
}

function replaceFile(updated: TransferFile): void {
  const index = files.value.findIndex((file) => file.id === updated.id);
  if (index >= 0) files.value[index] = updated;
}

async function togglePublic(file: TransferFile): Promise<void> {
  if (!isAdmin.value || togglingId.value) return;
  togglingId.value = file.id;
  try {
    const updated = await patchTransferFile(file.id, { is_public: !file.is_public });
    replaceFile(updated);
    toast.success(
      updated.is_public
        ? `「${updated.original_name}」已对所有人可见`
        : `「${updated.original_name}」已转为私密，仅你可见`,
    );
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    togglingId.value = "";
  }
}

async function download(file: TransferFile): Promise<void> {
  if (downloadingId.value) return;
  downloadingId.value = file.id;
  try {
    const response = await api.get(requestPath(file.download_url), {
      responseType: "blob",
    });
    const filename = downloadNameFromDisposition(
      response.headers["content-disposition"],
      file.original_name,
    );
    triggerBlobDownload(response.data as Blob, filename);
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    downloadingId.value = "";
  }
}

function openEdit(file: TransferFile): void {
  if (!isAdmin.value) return;
  editing.value = file;
  editName.value = file.original_name;
  editRemark.value = file.remark;
  editVisibleUntil.value = file.visible_until
    ? new Date(new Date(file.visible_until).getTime() - new Date(file.visible_until).getTimezoneOffset() * 60000).toISOString().slice(0, 16)
    : "";
  editOpen.value = true;
}

async function saveEdit(): Promise<void> {
  if (!editing.value || savingEdit.value) return;
  const name = editName.value.trim();
  if (!name) {
    toast.error("文件名不能为空");
    return;
  }
  savingEdit.value = true;
  try {
    const updated = await patchTransferFile(editing.value.id, {
      original_name: name,
      remark: editRemark.value.trim(),
      visible_until: editVisibleUntil.value ? new Date(editVisibleUntil.value).toISOString() : null,
    });
    replaceFile(updated);
    editOpen.value = false;
    editing.value = null;
    toast.success("文件信息已更新");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingEdit.value = false;
  }
}

function askDelete(file: TransferFile): void {
  if (!isAdmin.value) return;
  pendingDelete.value = file;
}

async function confirmDelete(): Promise<void> {
  if (!pendingDelete.value || deleting.value) return;
  deleting.value = true;
  try {
    const target = pendingDelete.value;
    await deleteTransferFile(target.id);
    files.value = files.value.filter((file) => file.id !== target.id);
    pendingDelete.value = null;
    toast.success("文件已删除");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    deleting.value = false;
  }
}

function clearFilters(): void {
  search.value = "";
  filter.value = "all";
}

onMounted(async () => {
  await auth.initialize();
  await loadFiles();
  // 中转站公告改为弹窗：首次加载到公告时自动弹出，页面不再内嵌公告区块。
  void announcements.load(true).then(() => {
    if (announcements.hasStation) openAnnouncement();
  });
});

// Kept alive: silently refresh the list when returning to this section.
onActivated(() => {
  void loadFiles(true);
});

watch(
  () => auth.user?.username,
  async (next, previous) => {
    if (next === previous) return;
    filter.value = "all";
    await loadFiles(true);
  },
);
</script>

<template>
  <div class="transfer-page relative h-full overflow-y-auto">
    <div class="transfer-aura" aria-hidden="true" />
    <div class="relative z-10 mx-auto w-full max-w-[1140px] px-4 pb-14 pt-6 sm:px-7 sm:pt-9">
      <header class="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div class="flex items-start gap-3.5">
          <img
            :src="brandLogo"
            alt="缺页中断 标志"
            class="h-auto w-[108px] shrink-0 object-contain sm:w-[176px]"
          />
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent-600">File relay</span>
              <span class="inline-flex items-center gap-1 rounded-full border border-emerald-100 bg-emerald-50/80 px-2 py-0.5 text-[9px] font-medium text-emerald-700">
                <span class="h-1 w-1 rounded-full bg-emerald-400" />
                免密上传
              </span>
              <span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white/70 px-2 py-0.5 text-[9px] font-medium text-ink-500">
                <Globe2 :size="9" />
                公开可下载
              </span>
            </div>
            <h1 class="mt-2 text-[29px] font-medium tracking-[-0.04em] text-ink-900 sm:text-[36px]">
              文件中转站
            </h1>
            <p class="mt-1.5 max-w-[560px] text-[12.5px] leading-6 text-ink-500">
              打开即传，无需登录。选择公开分享，或只投递给最高管理员。
            </p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 sm:pt-1">
          <button
            v-if="announcement"
            type="button"
            class="flex items-center gap-1.5 rounded-2xl border border-accent-100 bg-white/80 px-3.5 py-2 text-[11px] font-medium text-accent-600 shadow-sm transition hover:border-accent-200 hover:bg-white"
            @click="openAnnouncement"
          >
            <Megaphone :size="14" />
            站点公告
          </button>
          <div
            v-if="isAdmin"
            class="flex items-center gap-2.5 rounded-2xl border border-amber-200/80 bg-amber-50/75 py-2 pl-2.5 pr-3.5 shadow-sm"
          >
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100 text-amber-600">
              <ShieldCheck :size="16" />
            </span>
            <div>
              <p class="text-[11px] font-semibold text-amber-900">{{ auth.user?.username }} · 最高管理员</p>
              <p class="text-[9px] text-amber-700/70">全部文件与私密投递已解锁</p>
            </div>
          </div>
          <button
            v-else-if="auth.isAuthenticated"
            type="button"
            class="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/80 py-2 pl-2.5 pr-3 text-left shadow-sm transition hover:border-slate-300 hover:bg-white"
            @click="goToLogin"
          >
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 text-ink-500">
              <Eye :size="15" />
            </span>
            <span>
              <span class="block text-[11px] font-semibold text-ink-700">{{ auth.user?.username }} · 游客模式</span>
              <span class="block text-[9px] text-ink-400">可上传 / 浏览公开与自己的文件 · 无删除权</span>
            </span>
            <ArrowRight :size="13" class="ml-1 text-ink-300" />
          </button>
          <button
            v-else
            type="button"
            class="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/80 py-2 pl-2.5 pr-3.5 text-left shadow-sm transition hover:border-accent-200 hover:bg-white"
            @click="goToLogin"
          >
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-ink-900 text-white">
              <LogIn :size="15" />
            </span>
            <span>
              <span class="block text-[11px] font-semibold text-ink-700">管理员登录</span>
              <span class="block text-[9px] text-ink-400">仅限授权账号</span>
            </span>
          </button>
        </div>
      </header>

      <div v-if="isAdmin" class="mt-4 flex flex-wrap items-center gap-2" aria-label="公告管理">
        <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3 !text-[11px]" @click="openAnnouncementEditor('transfer')">
          <Megaphone :size="13" />
          中转站公告
        </button>
        <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3 !text-[11px]" @click="openAnnouncementEditor('login')">
          <LogIn :size="13" />
          登录页公告
        </button>
      </div>

      <section class="upload-card mt-6 overflow-hidden rounded-[26px] border border-white/90 bg-white/85 shadow-[0_24px_70px_-42px_rgba(15,23,42,0.35)] backdrop-blur-xl">
        <div class="grid lg:grid-cols-[1.08fr_.92fr]">
          <div class="flex flex-col p-4 sm:p-6">
            <div class="mb-3 flex items-center justify-between">
              <p class="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-ink-400">
                <Sparkles :size="11" class="text-accent-400" />
                免密即传
              </p>
              <span class="text-[9px] text-ink-300">单文件 · 最大 1 GB</span>
            </div>

            <div
              v-if="!agreed"
              class="mb-3 rounded-2xl border border-amber-200/80 bg-amber-50/70 p-3.5"
            >
              <label class="flex cursor-pointer items-start gap-2.5 text-[11px] leading-5 text-amber-900">
                <input
                  type="checkbox"
                  class="mt-0.5 h-3.5 w-3.5 shrink-0 accent-amber-500"
                  @change="onAgreeChange"
                />
                <span>
                  我已阅读并同意
                  <button
                    type="button"
                    class="font-medium underline underline-offset-2"
                    @click.prevent="openTerms(false)"
                  >《文件中转站使用声明》</button>，承诺不上传、不传播法律法规禁止的信息（含危害国家安全、淫秽色情、侵权与侵犯隐私等内容）。
                </span>
              </label>
            </div>

            <div
              class="upload-zone relative flex min-h-[216px] flex-1 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[20px] border border-dashed px-5 py-7 text-center transition duration-300"
              :class="
                dragging
                  ? 'border-accent-400 bg-accent-50/80'
                  : selectedFile
                    ? 'border-slate-200 bg-slate-50/55'
                    : 'border-slate-300/80 bg-[#fbfcfe] hover:border-accent-300 hover:bg-accent-50/25'
              "
              role="button"
              tabindex="0"
              @click="openFilePicker"
              @keydown.enter="openFilePicker"
              @dragenter="onDragEnter"
              @dragover.prevent
              @dragleave="onDragLeave"
              @drop="onDrop"
            >
              <input ref="fileInputRef" type="file" class="hidden" @change="onFileChange" />

              <Transition name="fade">
                <div
                  v-if="dragging"
                  class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-[20px] bg-accent-50/90 backdrop-blur-sm"
                >
                  <span class="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-accent-600 shadow-sm">
                    <UploadCloud :size="22" />
                  </span>
                  <p class="text-[12px] font-medium text-accent-700">松开即可添加文件</p>
                </div>
              </Transition>

              <template v-if="!selectedFile">
                <div class="upload-orbit">
                  <span class="flex h-12 w-12 items-center justify-center rounded-2xl border border-white bg-white text-ink-700 shadow-soft">
                    <UploadCloud :size="21" :stroke-width="1.7" />
                  </span>
                </div>
                <h2 class="mt-5 text-[16px] font-semibold tracking-tight text-ink-900">
                  把文件放在这里
                </h2>
                <p class="mt-1.5 text-[11px] leading-5 text-ink-400">
                  拖拽文件，或点击选择 · 无需账号
                </p>
                <span class="mt-4 inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[9.5px] font-medium text-ink-500 shadow-sm">
                  <Globe2 :size="10" />
                  上传时可选择公开 / 私密
                </span>
              </template>

              <template v-else>
                <div class="flex w-full max-w-[360px] flex-col items-center">
                  <div class="relative">
                    <FileIcon :name="selectedFile.name" :mime="selectedFile.type" size="lg" />
                    <span class="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-emerald-400 text-white">
                      <Check :size="10" :stroke-width="3" />
                    </span>
                  </div>
                  <p class="mt-3 max-w-full truncate text-[13px] font-semibold text-ink-800">
                    {{ selectedFile.name }}
                  </p>
                  <p class="mt-0.5 text-[10px] text-ink-400">
                    {{ extOf(selectedFile.name) }} · {{ formatBytes(selectedFile.size) }}
                  </p>
                  <div class="mt-4 flex items-center gap-2">
                    <button
                      type="button"
                      class="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-medium text-ink-600 transition hover:border-slate-300 hover:text-ink-900"
                      :disabled="uploading"
                      @click.stop="openFilePicker"
                    >
                      更换文件
                    </button>
                    <button
                      type="button"
                      class="flex h-7 w-7 items-center justify-center rounded-full text-ink-400 transition hover:bg-rose-50 hover:text-rose-500"
                      :disabled="uploading"
                      aria-label="移除文件"
                      @click.stop="removeSelected"
                    >
                      <X :size="14" />
                    </button>
                  </div>

                  <div v-if="uploading" class="mt-5 w-full">
                    <div class="h-1.5 overflow-hidden rounded-full bg-slate-200">
                      <div
                        class="h-full rounded-full bg-gradient-to-r from-accent-500 to-cyan-400 transition-all duration-200"
                        :style="{ width: `${uploadProgress}%` }"
                      />
                    </div>
                    <p class="mt-2 text-[9px] text-ink-400">正在上传 {{ uploadProgress }}%</p>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <div class="border-t border-slate-100 bg-[#fbfcfe]/85 p-4 sm:p-6 lg:border-l lg:border-t-0">
            <p class="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-ink-400">可见范围</p>
            <div class="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                class="visibility-card text-left"
                :class="isPublic ? 'is-selected' : ''"
                :disabled="uploading"
                @click="isPublic = true"
              >
                <span class="flex items-center justify-between">
                  <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                    <Globe2 :size="14" />
                  </span>
                  <Check v-if="isPublic" :size="13" class="text-accent-500" />
                </span>
                <span class="mt-2 block text-[11.5px] font-semibold text-ink-800">所有人可见</span>
                <span class="mt-0.5 block text-[9px] leading-4 text-ink-400">公开列出，免登录下载</span>
              </button>

              <button
                type="button"
                class="visibility-card text-left"
                :class="!isPublic ? 'is-selected-private' : ''"
                :disabled="uploading"
                @click="isPublic = false"
              >
                <span class="flex items-center justify-between">
                  <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                    <LockKeyhole :size="14" />
                  </span>
                  <Check v-if="!isPublic" :size="13" class="text-amber-500" />
                </span>
                <span class="mt-2 block text-[11.5px] font-semibold text-ink-800">最高管理员</span>
                <span class="mt-0.5 block text-[9px] leading-4 text-ink-400">私密投递，访客不可见</span>
              </button>
            </div>

            <div class="mt-4">
              <label class="field-label" for="transfer-remark">备注（可选）</label>
              <input
                id="transfer-remark"
                v-model="remark"
                maxlength="120"
                class="mt-1.5 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-[11px] text-ink-700 outline-none transition placeholder:text-ink-300 focus:border-accent-300 focus:ring-4 focus:ring-accent-500/10"
                placeholder="给这个文件加一句说明"
                :disabled="uploading"
              />
            </div>

            <div v-if="!auth.isAuthenticated" class="mt-3">
              <label class="field-label" for="transfer-uploader">署名（可选）</label>
              <input
                id="transfer-uploader"
                v-model="uploaderName"
                maxlength="64"
                class="mt-1.5 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-[11px] text-ink-700 outline-none transition placeholder:text-ink-300 focus:border-accent-300 focus:ring-4 focus:ring-accent-500/10"
                placeholder="留空则显示「免密访客」"
                :disabled="uploading"
              />
            </div>

            <button
              type="button"
              class="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-ink-900 text-[11.5px] font-semibold text-white shadow-[0_12px_24px_-16px_rgba(15,23,42,.8)] transition hover:bg-accent-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-white/80"
              :disabled="!selectedFile || uploading"
              @click="upload"
            >
              <Loader2 v-if="uploading" :size="14" class="animate-spin" />
              <UploadCloud v-else :size="14" />
              {{ uploadActionLabel }}
            </button>
            <p class="mt-2 text-center text-[9px] leading-4 text-ink-300">
              {{ isPublic ? "上传后所有访客都能在列表中找到它" : "文件只对最高管理员可见，上传后立即从访客列表隐藏" }}
            </p>
          </div>
        </div>
      </section>

      <section class="mt-7 overflow-hidden rounded-[26px] border border-white/90 bg-white/70 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.35)] backdrop-blur-xl">
        <div class="flex flex-col gap-3 border-b border-slate-200/60 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div class="flex items-center gap-2.5">
            <h2 class="text-[14px] font-semibold tracking-tight text-ink-900">站内文件</h2>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-medium tabular-nums text-ink-500">
              {{ files.length }}
            </span>
            <span v-if="isAdmin" class="hidden items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[8.5px] font-medium text-amber-700 sm:inline-flex">
              <ShieldCheck :size="9" />
              含私密投递 {{ privateCount }}
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <div v-if="auth.isAuthenticated" class="flex rounded-full bg-slate-100/80 p-0.5">
              <button
                v-for="option in filterOptions"
                :key="option.key"
                type="button"
                class="rounded-full px-2.5 py-1 text-[9.5px] font-medium transition"
                :class="filter === option.key ? 'bg-white text-ink-800 shadow-sm' : 'text-ink-400 hover:text-ink-700'"
                @click="filter = option.key"
              >
                {{ option.label }}
                <span class="ml-0.5 tabular-nums text-ink-300">{{ option.count }}</span>
              </button>
            </div>

            <div class="relative">
              <Search :size="13" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-300" />
              <input
                v-model="search"
                type="search"
                placeholder="搜索文件名或备注"
                class="h-8 w-[160px] rounded-full border border-slate-200 bg-white/80 pl-7 pr-3 text-[10px] text-ink-600 outline-none transition placeholder:text-ink-300 focus:border-accent-300 focus:ring-4 focus:ring-accent-500/10 sm:w-[190px]"
              />
            </div>

            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-ink-400 transition hover:text-ink-700"
              title="刷新列表"
              :disabled="refreshBusy"
              @click="refresh"
            >
              <RefreshCw :size="12" :class="{ 'animate-spin': refreshBusy }" />
            </button>
          </div>
        </div>

        <div class="p-2.5 sm:p-3">
          <div v-if="loading" class="space-y-2">
            <div v-for="index in 3" :key="index" class="flex items-center gap-3 rounded-2xl px-3 py-3">
              <div class="h-11 w-11 animate-pulse rounded-2xl bg-slate-200/70" />
              <div class="flex-1 space-y-2">
                <div class="h-2.5 w-1/3 animate-pulse rounded-full bg-slate-200/80" />
                <div class="h-2 w-1/2 animate-pulse rounded-full bg-slate-200/60" />
              </div>
            </div>
          </div>

          <div v-else-if="loadError && !files.length" class="flex flex-col items-center justify-center px-5 py-14 text-center">
            <span class="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-500">
              <CircleAlert :size="19" />
            </span>
            <p class="mt-3 text-[12px] font-medium text-ink-700">无法加载文件列表</p>
            <p class="mt-1 max-w-[320px] text-[10px] leading-5 text-ink-400">{{ loadError }}</p>
            <button type="button" class="btn-secondary mt-4 h-9 text-[10px]" @click="loadFiles()">重试</button>
          </div>

          <div v-else-if="!visibleFiles.length" class="flex flex-col items-center justify-center px-5 py-14 text-center">
            <span class="flex h-12 w-12 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 text-ink-300">
              <FolderOpen :size="21" />
            </span>
            <p class="mt-3 text-[12px] font-medium text-ink-600">
              {{ files.length ? "没有匹配的文件" : isAdmin ? "中转站还是空的" : "还没有公开文件" }}
            </p>
            <p class="mt-1 max-w-[320px] text-[10px] leading-5 text-ink-400">
              {{ files.length ? "试试清空搜索或切换筛选条件。" : "上传第一个文件，让这里开始运转。" }}
            </p>
            <button
              v-if="files.length && (search || filter !== 'all')"
              type="button"
              class="mt-3 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] text-ink-500 transition hover:text-ink-800"
              @click="clearFilters"
            >
              清空筛选
            </button>
          </div>

          <div v-else class="space-y-0.5">
            <div
              v-for="file in visibleFiles"
              :key="file.id"
              class="file-row group flex flex-col gap-2.5 rounded-2xl px-3 py-3 transition sm:flex-row sm:items-center"
            >
              <div class="flex min-w-0 flex-1 items-center gap-3">
                <div
                  class="shrink-0"
                  :class="previewKindOf(file) !== 'none' ? 'cursor-zoom-in' : ''"
                  :title="previewKindOf(file) !== 'none' ? '点击在线预览' : ''"
                  @click="previewKindOf(file) !== 'none' && (previewTarget = file)"
                >
                  <TransferThumbnail
                    :url="file.preview_url"
                    :name="file.original_name"
                    :mime="file.file_type"
                    :is-image="file.is_image"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                    <p class="max-w-full truncate text-[12px] font-semibold text-ink-800 sm:max-w-[320px]" :title="file.original_name">
                      {{ file.original_name }}
                    </p>
                    <span
                      v-if="isAdmin"
                      class="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[8px] font-medium"
                      :class="file.is_public ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'"
                    >
                      <Globe2 v-if="file.is_public" :size="8" />
                      <LockKeyhole v-else :size="8" />
                      {{ file.is_public ? "公开" : "私密" }}
                    </span>
                    <span
                      v-else-if="file.is_public"
                      class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[8px] font-medium text-emerald-600"
                    >
                      <Globe2 :size="8" />
                      公开
                    </span>
                    <span
                      v-else
                      class="inline-flex items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[8px] font-medium text-amber-600"
                      title="你的私密投递，仅你与最高管理员可见"
                    >
                      <LockKeyhole :size="8" />
                      私密 · 我的投递
                    </span>
                  </div>
                  <p v-if="file.remark" class="mt-0.5 max-w-[560px] truncate text-[10px] text-ink-500" :title="file.remark">
                    {{ file.remark }}
                  </p>
                  <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[8.5px] text-ink-400">
                    <span class="font-mono">{{ file.extension ? file.extension.toUpperCase() : "FILE" }}</span>
                    <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
                    <span>{{ formatBytes(file.file_size) }}</span>
                    <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
                    <span>{{ file.uploader_name }}</span>
                    <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
                    <span>{{ formatRelative(file.created_at) }}</span>
                    <template v-if="file.visible_until">
                      <span class="h-0.5 w-0.5 rounded-full bg-slate-300" />
                      <span :class="new Date(file.visible_until) <= new Date() ? 'text-rose-500' : ''">
                        {{ new Date(file.visible_until) <= new Date() ? "已过期" : `可见至 ${formatRelative(file.visible_until)}` }}
                      </span>
                    </template>
                  </div>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-1 self-end sm:self-center">
                <button
                  v-if="previewKindOf(file) !== 'none'"
                  type="button"
                  class="file-action"
                  title="在线预览"
                  @click="previewTarget = file"
                >
                  <Eye :size="13" />
                </button>
                <template v-if="isAdmin">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[9px] font-medium transition"
                    :class="
                      file.is_public
                        ? 'border-emerald-200 bg-emerald-50/70 text-emerald-700 hover:bg-emerald-100'
                        : 'border-amber-200 bg-amber-50/70 text-amber-700 hover:bg-amber-100'
                    "
                    :disabled="togglingId === file.id"
                    :title="file.is_public ? '点击切换为最高管理员可见' : '点击切换为所有人可见'"
                    @click="togglePublic(file)"
                  >
                    <Loader2 v-if="togglingId === file.id" :size="11" class="animate-spin" />
                    <Eye v-else-if="file.is_public" :size="11" />
                    <EyeOff v-else :size="11" />
                    {{ file.is_public ? "所有人可见" : "最高管理员" }}
                  </button>
                  <button
                    type="button"
                    class="file-action"
                    title="重命名 / 编辑备注"
                    @click="openEdit(file)"
                  >
                    <Pencil :size="13" />
                  </button>
                  <button
                    type="button"
                    class="file-action hover:!text-rose-500"
                    title="删除文件"
                    @click="askDelete(file)"
                  >
                    <Trash2 :size="13" />
                  </button>
                </template>

                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 rounded-full bg-ink-900 px-3 py-1.5 text-[9px] font-medium text-white shadow-sm transition hover:bg-accent-600 disabled:opacity-60"
                  :disabled="downloadingId === file.id"
                  @click="download(file)"
                >
                  <Loader2 v-if="downloadingId === file.id" :size="11" class="animate-spin" />
                  <Download v-else :size="11" />
                  下载
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>

    <FilePreviewModal
      :open="Boolean(previewTarget)"
      :name="previewTarget?.original_name || ''"
      :mime="previewTarget?.file_type || ''"
      :size="previewTarget?.file_size || 0"
      :url="previewTarget ? previewTarget.download_url : ''"
      @close="previewTarget = null"
    />

    <ModalShell
      :open="announcementHistoryOpen"
      title="公告"
      subtitle="当前公告与历史记录"
      max-width="max-w-xl"
      @close="announcementHistoryOpen = false"
    >
      <AnnouncementBody />
      <template #footer>
        <button type="button" class="btn-secondary" @click="announcementHistoryOpen = false">
          关闭
        </button>
      </template>
    </ModalShell>

    <UsageTermsModal
      :open="termsOpen"
      :accept-mode="termsAcceptMode"
      scope="transfer"
      @close="termsOpen = false"
      @accept="onAcceptTerms"
    />

    <ModalShell
      :open="announcementEditorOpen"
      :title="announcementKind === 'transfer' ? '管理中转站公告' : '管理登录页公告'"
      subtitle="公告按纯文本展示。清空内容并保存即可撤下。"
      max-width="max-w-xl"
      @close="announcementEditorOpen = false"
    >
      <label class="field-label" for="announcement-content">公告内容</label>
      <textarea
        id="announcement-content"
        v-model="announcementDraft"
        rows="10"
        maxlength="5000"
        class="field-textarea mt-2"
        placeholder="输入要向用户展示的公告；留空保存表示撤下。"
      />
      <p class="mt-2 text-right text-[11px] tabular-nums text-ink-400">
        {{ announcementDraft.length }} / 5000
      </p>
      <template #footer>
        <button type="button" class="btn-secondary" @click="announcementEditorOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingAnnouncement" @click="saveAnnouncement">
          <Loader2 v-if="savingAnnouncement" :size="14" class="animate-spin" />
          {{ announcementDraft.trim() ? "发布公告" : "撤下公告" }}
        </button>
      </template>
    </ModalShell>

    <ModalShell
      :open="editOpen"
      title="编辑文件信息"
      subtitle="重命名只改变站内展示名称与下载文件名，不会影响文件内容。"
      @close="editOpen = false"
    >
      <div v-if="editing" class="space-y-4">
        <div class="flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3">
          <FileIcon :name="editing.original_name" :mime="editing.file_type" />
          <div class="min-w-0">
            <p class="truncate text-[11.5px] font-medium text-ink-700">{{ editing.original_name }}</p>
            <p class="mt-0.5 text-[9px] text-ink-400">
              {{ formatBytes(editing.file_size) }} · {{ editing.uploader_name }}
            </p>
          </div>
        </div>

        <div>
          <label class="field-label" for="edit-transfer-name">文件名</label>
          <input
            id="edit-transfer-name"
            v-model="editName"
            maxlength="255"
            class="field-textarea mt-1.5 h-10 resize-none py-2.5"
          />
        </div>
        <div>
          <label class="field-label" for="edit-transfer-remark">备注</label>
          <textarea
            id="edit-transfer-remark"
            v-model="editRemark"
            rows="3"
            maxlength="255"
            class="field-textarea mt-1.5"
            placeholder="补充这个文件的用途或说明"
          />
        </div>
        <div>
          <label class="field-label" for="edit-transfer-expiry">可见截止时间</label>
          <input id="edit-transfer-expiry" v-model="editVisibleUntil" type="datetime-local" class="field-textarea mt-1.5 h-10 resize-none py-2.5" />
          <p class="mt-1 text-[10px] text-ink-400">留空表示长期可见；到期后文件会从普通用户列表隐藏，下载和预览链接也会失效。</p>
        </div>
        <div class="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-[9.5px] text-ink-400">
          <Eye :size="12" />
          可见性当前为「{{ editing.is_public ? "所有人可见" : "最高管理员" }}」，可在列表中一键切换。
        </div>
      </div>

      <template #footer>
        <button type="button" class="btn-secondary" @click="editOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingEdit" @click="saveEdit">
          <Loader2 v-if="savingEdit" :size="13" class="animate-spin" />
          保存修改
        </button>
      </template>
    </ModalShell>

    <ModalShell
      :open="Boolean(pendingDelete)"
      title="删除这个文件？"
      subtitle="此操作会从服务器磁盘物理删除文件，无法撤销。"
      max-width="max-w-md"
      @close="pendingDelete = null"
    >
      <div v-if="pendingDelete" class="rounded-2xl border border-rose-100 bg-rose-50/70 p-4">
        <div class="flex items-center gap-3">
          <FileIcon :name="pendingDelete.original_name" :mime="pendingDelete.file_type" />
          <div class="min-w-0">
            <p class="truncate text-[12px] font-medium text-ink-800">{{ pendingDelete.original_name }}</p>
            <p class="mt-0.5 text-[9px] text-ink-400">{{ formatBytes(pendingDelete.file_size) }}</p>
          </div>
        </div>
      </div>
      <p class="mt-3 text-[11px] leading-5 text-ink-500">
        删除后，所有公开链接与私密访问都会立即失效。建议先确认文件已经完成交接。
      </p>

      <template #footer>
        <button type="button" class="btn-secondary" @click="pendingDelete = null">取消</button>
        <button
          type="button"
          class="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-[12px] font-semibold text-white shadow-sm transition hover:bg-rose-700 disabled:opacity-60"
          :disabled="deleting"
          @click="confirmDelete"
        >
          <Loader2 v-if="deleting" :size="13" class="animate-spin" />
          <Trash2 v-else :size="13" />
          永久删除
        </button>
      </template>
    </ModalShell>
  </div>
</template>

<style scoped>
.transfer-page {
  background:
    radial-gradient(950px 520px at 85% -8%, rgba(66, 133, 244, 0.14), transparent 65%),
    radial-gradient(820px 480px at 18% 12%, rgba(155, 114, 203, 0.13), transparent 65%),
    radial-gradient(760px 500px at 12% 102%, rgba(217, 101, 112, 0.1), transparent 65%),
    transparent;
}

.transfer-aura {
  position: absolute;
  top: -240px;
  left: 14%;
  width: 760px;
  height: 480px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 50%, rgba(66, 133, 244, 0.22), transparent 60%),
    radial-gradient(circle at 65% 45%, rgba(155, 114, 203, 0.2), transparent 62%),
    radial-gradient(circle at 82% 65%, rgba(217, 101, 112, 0.16), transparent 64%);
  filter: blur(60px);
  pointer-events: none;
}

.upload-zone {
  background-image: radial-gradient(rgba(148, 163, 184, 0.15) 0.6px, transparent 0.6px);
  background-size: 18px 18px;
}

.upload-orbit {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.upload-orbit::before,
.upload-orbit::after {
  content: "";
  position: absolute;
  inset: -9px;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  border-radius: 50%;
}

.upload-orbit::after {
  inset: -18px;
  border-color: rgba(148, 163, 184, 0.16);
}

.visibility-card {
  border: 1px solid #e8edf4;
  border-radius: 14px;
  background: white;
  padding: 10px;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.visibility-card:hover {
  border-color: #cbd5e1;
}

.visibility-card.is-selected {
  border-color: rgba(68, 115, 246, 0.45);
  background: #f5f8ff;
  box-shadow: 0 0 0 3px rgba(68, 115, 246, 0.07);
}

.visibility-card.is-selected-private {
  border-color: rgba(245, 158, 11, 0.4);
  background: #fffbeb;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.06);
}

.file-row:hover {
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 30px -26px rgba(15, 23, 42, 0.45);
}

.file-action {
  display: inline-flex;
  height: 30px;
  width: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid transparent;
  color: #94a3b8;
  transition:
    color 0.2s ease,
    background 0.2s ease,
    border-color 0.2s ease;
}

.file-action:hover {
  border-color: #e2e8f0;
  background: white;
  color: #334155;
}
</style>
