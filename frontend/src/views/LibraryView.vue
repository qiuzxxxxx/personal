<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  Download,
  BookPlus,
  FileText,
  Folder,
  FolderPlus,
  Image as ImageIcon,
  Pencil,
  QrCode,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-vue-next";
import api, { extractApiError, requestPath } from "@/api/client";
import { importKnowledge } from "@/api/knowledge";
import PhoneUploadDialog from "@/components/PhoneUploadDialog.vue";
import ModalShell from "@/components/ModalShell.vue";
import {
  createFolder,
  deleteFolder,
  deleteMaterial,
  downloadMaterial,
  fetchFolders,
  fetchMaterials,
  restoreMaterial,
  updateFolder,
  updateMaterial,
  uploadMaterial,
} from "@/api/workspace";
import type { LibraryFolder, LibraryMaterial } from "@/api/workspace";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";

const toast = useToastStore();
const workspace = useWorkspaceStore();
const auth = useAuthStore();

const folders = ref<LibraryFolder[]>([]);
const materials = ref<LibraryMaterial[]>([]);
const count = ref(0);
const page = ref(1);
const pages = ref(1);
const activeFolder = ref("");
const keyword = ref("");
const fileType = ref("");
const showTrash = ref(false);
const loading = ref(false);
const uploading = ref(false);

const newFolderName = ref("");
const showFolderInput = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const uploadFolder = ref("");
const uploadRemark = ref("");
const uploadTask = ref("");
const uploadTags = ref("");

const preview = ref<{ material: LibraryMaterial; url: string; kind: "image" | "pdf" | "text" } | null>(
  null,
);
const previewText = ref("");
const showPhoneUpload = ref(false);
const materialEditOpen = ref(false);
const editingMaterial = ref<LibraryMaterial | null>(null);
const materialEditName = ref("");
const materialEditRemark = ref("");
const materialEditFolder = ref("");
const savingMaterial = ref(false);
const folderEditOpen = ref(false);
const editingFolder = ref<LibraryFolder | null>(null);
const folderEditName = ref("");
const savingFolder = ref(false);
let refreshSequence = 0;

const fileTypes = [
  { value: "", label: "全部类型" },
  { value: "pdf", label: "PDF" },
  { value: "png", label: "PNG" },
  { value: "jpg", label: "JPG" },
  { value: "docx", label: "DOCX" },
  { value: "xlsx", label: "XLSX" },
  { value: "md", label: "Markdown" },
  { value: "txt", label: "文本" },
  { value: "zip", label: "压缩包" },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

async function refresh(): Promise<void> {
  const sequence = ++refreshSequence;
  const ownerId = auth.user?.id ?? null;
  loading.value = true;
  try {
    const [folderList, materialPage] = await Promise.all([
      fetchFolders(),
      fetchMaterials({
        folder: activeFolder.value || undefined,
        q: keyword.value.trim() || undefined,
        type: fileType.value || undefined,
        deleted: showTrash.value,
        page: page.value,
        page_size: 50,
      }),
    ]);
    if (sequence !== refreshSequence || ownerId !== (auth.user?.id ?? null)) return;
    folders.value = folderList;
    materials.value = materialPage.results;
    count.value = materialPage.count;
    pages.value = materialPage.pages;
  } catch (error) {
    if (sequence === refreshSequence && ownerId === (auth.user?.id ?? null)) {
      toast.error(extractApiError(error));
    }
  } finally {
    if (sequence === refreshSequence) loading.value = false;
  }
}

function openMaterialEdit(material: LibraryMaterial): void {
  editingMaterial.value = material;
  materialEditName.value = material.original_name;
  materialEditRemark.value = material.remark;
  materialEditFolder.value = material.folder || "";
  materialEditOpen.value = true;
}

async function saveMaterialEdit(): Promise<void> {
  if (!editingMaterial.value || savingMaterial.value) return;
  if (!materialEditName.value.trim()) {
    toast.error("文件名不能为空。");
    return;
  }
  savingMaterial.value = true;
  try {
    await updateMaterial(editingMaterial.value.id, {
      original_name: materialEditName.value.trim(),
      remark: materialEditRemark.value.trim(),
      folder: materialEditFolder.value || null,
      version: editingMaterial.value.version,
    });
    materialEditOpen.value = false;
    editingMaterial.value = null;
    toast.success("资料信息已更新。");
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingMaterial.value = false;
  }
}

function openFolderEdit(folder: LibraryFolder): void {
  editingFolder.value = folder;
  folderEditName.value = folder.name;
  folderEditOpen.value = true;
}

async function saveFolderEdit(): Promise<void> {
  if (!editingFolder.value || savingFolder.value) return;
  if (!folderEditName.value.trim()) {
    toast.error("资料夹名称不能为空。");
    return;
  }
  savingFolder.value = true;
  try {
    await updateFolder(editingFolder.value.id, {
      name: folderEditName.value.trim(),
      version: editingFolder.value.version,
    });
    folderEditOpen.value = false;
    editingFolder.value = null;
    toast.success("资料夹已重命名。");
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    savingFolder.value = false;
  }
}

async function changePage(next: number): Promise<void> {
  page.value = Math.min(Math.max(1, next), Math.max(1, pages.value));
  await refresh();
}

async function addFolder(): Promise<void> {
  const name = newFolderName.value.trim();
  if (!name) return;
  try {
    await createFolder(name);
    newFolderName.value = "";
    showFolderInput.value = false;
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function removeFolder(folder: LibraryFolder): Promise<void> {
  try {
    await deleteFolder(folder.id);
    if (activeFolder.value === folder.id) activeFolder.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function pickFile(): void {
  fileInput.value?.click();
}

async function onFileSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    await uploadMaterial(file, {
      folder: uploadFolder.value || undefined,
      remark: uploadRemark.value.trim() || undefined,
      tags: uploadTags.value
        .split(/[,，\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
      task: uploadTask.value || undefined,
    });
    toast.success("文件已保存到私人资料库。");
    uploadRemark.value = "";
    uploadTags.value = "";
    uploadTask.value = "";
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    uploading.value = false;
    if (input) input.value = "";
  }
}

async function removeMaterial(material: LibraryMaterial): Promise<void> {
  try {
    await deleteMaterial(material.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function restore(material: LibraryMaterial): Promise<void> {
  try {
    await restoreMaterial(material.id);
    await refresh();
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function download(material: LibraryMaterial): Promise<void> {
  try {
    await downloadMaterial(material);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function addMaterialToKnowledge(material: LibraryMaterial): Promise<void> {
  try {
    await importKnowledge({ material: material.id, ai_enabled: false });
    toast.success(`「${material.original_name}」已加入知识库。`);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

async function openPreview(material: LibraryMaterial): Promise<void> {
  if (!material.is_previewable) {
    await download(material);
    return;
  }
  try {
    const response = await api.get<Blob>(requestPath(`${material.download_url}?inline=1`), {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const extension = material.extension.toLowerCase();
    if (["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(extension)) {
      preview.value = { material, url, kind: "image" };
    } else if (extension === "pdf") {
      preview.value = { material, url, kind: "pdf" };
    } else {
      previewText.value = await response.data.text();
      preview.value = { material, url, kind: "text" };
    }
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function closePreview(): void {
  if (preview.value) {
    URL.revokeObjectURL(preview.value.url);
  }
  preview.value = null;
  previewText.value = "";
}

const groupedByDate = computed(() => {
  const groups = new Map<string, LibraryMaterial[]>();
  for (const material of materials.value) {
    const day = (material.created_at || "").slice(0, 10) || "未知日期";
    const bucket = groups.get(day) || [];
    bucket.push(material);
    groups.set(day, bucket);
  }
  return [...groups.entries()];
});

onMounted(async () => {
  await workspace.loadTasks({});
  await refresh();
});

watch(
  () => auth.user?.id,
  (next, previous) => {
    if (next === previous) return;
    refreshSequence += 1;
    closePreview();
    folders.value = [];
    materials.value = [];
    count.value = 0;
    page.value = 1;
    activeFolder.value = "";
    materialEditOpen.value = false;
    folderEditOpen.value = false;
    if (next) void refresh();
  },
);
</script>

<template>
  <div class="h-full overflow-y-auto bg-canvas">
    <div class="mx-auto w-full max-w-6xl px-3 py-4 sm:px-6 sm:py-6 lg:py-10">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[21px] font-semibold tracking-tight text-ink-900 sm:text-[26px]">私人资料库</h1>
          <p class="mt-1 text-[12.5px] text-ink-400">
            只有你能看到的文件，支持分类、标签、备注与任务关联。
          </p>
        </div>
        <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <button
            type="button"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[12.5px] font-medium text-ink-700 shadow-sm transition hover:border-accent-200"
            @click="showPhoneUpload = true"
          >
            <QrCode :size="15" />
            手机上传
          </button>
          <button
            type="button"
            :disabled="uploading"
            class="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink-900 px-4 text-[13px] font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
            @click="pickFile"
          >
            <Upload :size="15" />
            {{ uploading ? "上传中…" : "上传文件" }}
          </button>
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            @change="onFileSelected"
          />
        </div>
      </header>

      <section class="mt-4 rounded-2xl border border-slate-200 bg-white p-3 shadow-soft sm:mt-6">
        <div class="grid gap-2 sm:grid-cols-3">
          <select
            v-model="uploadFolder"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
          >
            <option value="">未分类</option>
            <option v-for="folder in folders" :key="folder.id" :value="folder.id">
              {{ folder.name }}
            </option>
          </select>
          <select
            v-model="uploadTask"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] text-ink-700 outline-none focus:border-accent-300"
          >
            <option value="">不关联任务</option>
            <option v-for="task in workspace.tasks" :key="task.id" :value="task.id">
              {{ task.title }}
            </option>
          </select>
          <input
            v-model="uploadTags"
            type="text"
            placeholder="标签，用逗号分隔"
            class="w-full rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] outline-none focus:border-accent-300"
          />
        </div>
        <input
          v-model="uploadRemark"
          type="text"
          maxlength="500"
          placeholder="备注（可选）"
          class="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-[12.5px] outline-none focus:border-accent-300"
        />
      </section>

      <div class="mt-6 flex flex-col gap-4 lg:flex-row">
        <aside class="lg:w-56 lg:shrink-0">
          <div class="rounded-2xl border border-slate-200 bg-white p-3 shadow-soft">
            <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.15em] text-ink-400">
              资料夹
            </p>
            <ul class="mt-2 max-h-48 space-y-0.5 overflow-y-auto lg:max-h-none">
              <li>
                <button
                  type="button"
                  class="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12.5px] transition"
                  :class="activeFolder === '' ? 'bg-slate-100 text-ink-900' : 'text-ink-600 hover:bg-slate-50'"
                  @click="activeFolder = ''; page = 1; refresh()"
                >
                  全部文件
                  <span class="text-[11px] text-ink-400">{{ count }}</span>
                </button>
              </li>
              <li v-for="folder in folders" :key="folder.id">
                <div class="flex items-center gap-1">
                  <button
                    type="button"
                    class="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition"
                    :class="activeFolder === folder.id ? 'bg-slate-100 text-ink-900' : 'text-ink-600 hover:bg-slate-50'"
                    @click="activeFolder = folder.id; page = 1; refresh()"
                  >
                    <Folder :size="13" class="shrink-0 text-ink-400" />
                    <span class="truncate">{{ folder.name }}</span>
                    <span class="ml-auto text-[11px] text-ink-400">{{ folder.material_count }}</span>
                  </button>
                  <button
                    type="button"
                    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-300 transition hover:bg-slate-50 hover:text-accent-600"
                    title="重命名资料夹"
                    :aria-label="`重命名资料夹 ${folder.name}`"
                    @click="openFolderEdit(folder)"
                  >
                    <Pencil :size="13" />
                  </button>
                  <button
                    type="button"
                    class="shrink-0 text-ink-300 transition hover:text-rose-500"
                    title="删除资料夹"
                    @click="removeFolder(folder)"
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
                @click="showFolderInput = !showFolderInput"
              >
                <FolderPlus :size="14" />
                新建资料夹
              </button>
              <div v-if="showFolderInput" class="mt-2 flex gap-1.5">
                <input
                  v-model="newFolderName"
                  type="text"
                  maxlength="120"
                  placeholder="名称"
                  class="min-w-0 flex-1 rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] outline-none"
                  @keyup.enter="addFolder"
                />
                <button
                  type="button"
                  class="rounded-lg bg-ink-900 px-2.5 py-1.5 text-[11.5px] font-medium text-white"
                  @click="addFolder"
                >
                  添加
                </button>
              </div>
            </div>
          </div>
        </aside>

        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <div class="flex min-w-0 flex-1 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 sm:flex-none">
              <Search :size="14" class="text-ink-300" />
              <input
                v-model="keyword"
                type="search"
                placeholder="按文件名或备注搜索"
                class="w-full min-w-0 bg-transparent text-[12.5px] outline-none placeholder:text-ink-300 sm:w-44"
                @keyup.enter="page = 1; refresh()"
              />
            </div>
            <select
              v-model="fileType"
              class="w-auto rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-ink-600 outline-none"
              @change="page = 1; refresh()"
            >
              <option v-for="option in fileTypes" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <button
              type="button"
              class="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
              :class="showTrash ? 'bg-rose-600 text-white' : 'bg-white text-ink-500 hover:bg-slate-100'"
              @click="showTrash = !showTrash; page = 1; refresh()"
            >
              回收站
            </button>
            <span class="ml-auto text-[12px] text-ink-400">{{ count }} 个文件</span>
          </div>

          <div
            v-if="!materials.length"
            class="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-12 text-center text-[13px] text-ink-400"
          >
            {{ loading ? "加载中…" : "还没有文件，先上传一份资料吧。" }}
          </div>

          <div v-else class="mt-4 space-y-5">
            <section v-for="[day, items] in groupedByDate" :key="day">
              <h2 class="text-[11.5px] font-semibold uppercase tracking-[0.15em] text-ink-400">
                {{ day }}
              </h2>
              <ul class="mt-2 space-y-2">
                <li
                  v-for="material in items"
                  :key="material.id"
                  class="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft"
                >
                  <span class="shrink-0 text-ink-400">
                    <ImageIcon v-if="material.is_previewable" :size="16" />
                    <FileText v-else :size="16" />
                  </span>
                  <div class="min-w-0 flex-1">
                    <p class="truncate text-[13.5px] text-ink-900">{{ material.original_name }}</p>
                    <p class="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
                      <span>{{ formatSize(material.size_bytes) }}</span>
                      <span v-if="material.folder_name">{{ material.folder_name }}</span>
                      <span v-for="tag in material.tags" :key="tag.id">#{{ tag.name }}</span>
                      <span v-if="material.remark" class="hidden sm:inline">· {{ material.remark }}</span>
                    </p>
                  </div>
                  <div class="flex shrink-0 items-center gap-1 sm:gap-3">
                    <button
                      type="button"
                      class="shrink-0 text-[11.5px] font-medium text-ink-500 hover:text-accent-600"
                      @click="openPreview(material)"
                    >
                      预览
                    </button>
                  <button
                    v-if="!showTrash"
                    type="button"
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-300 transition hover:bg-accent-50 hover:text-accent-600"
                    title="加入知识库"
                    :aria-label="`将 ${material.original_name} 加入知识库`"
                    @click="addMaterialToKnowledge(material)"
                  >
                    <BookPlus :size="15" />
                  </button>
                  <button
                    v-if="!showTrash"
                    type="button"
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-300 transition hover:bg-slate-50 hover:text-ink-700"
                    title="编辑资料信息"
                    :aria-label="`编辑 ${material.original_name}`"
                    @click="openMaterialEdit(material)"
                  >
                    <Pencil :size="15" />
                  </button>
                  <button
                    type="button"
                    class="shrink-0 text-ink-300 transition hover:text-ink-700"
                    title="下载"
                    @click="download(material)"
                  >
                    <Download :size="15" />
                  </button>
                  <button
                    v-if="showTrash"
                    type="button"
                    class="shrink-0 text-ink-300 transition hover:text-accent-600"
                    title="恢复"
                    @click="restore(material)"
                  >
                    <RotateCcw :size="15" />
                  </button>
                  <button
                    v-else
                    type="button"
                    class="shrink-0 text-ink-300 transition hover:text-rose-500"
                    title="删除"
                    @click="removeMaterial(material)"
                  >
                    <Trash2 :size="15" />
                  </button>
                  </div>
                </li>
              </ul>
            </section>
          </div>
          <nav
            v-if="pages > 1"
            class="mt-5 flex items-center justify-center gap-3"
            aria-label="资料分页"
          >
            <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
            <span class="text-[12px] tabular-nums text-ink-500">第 {{ page }} / {{ pages }} 页</span>
            <button type="button" class="btn-secondary !h-9 !min-h-9 !px-3" :disabled="page >= pages" @click="changePage(page + 1)">下一页</button>
          </nav>
        </div>
      </div>
    </div>

    <PhoneUploadDialog
      v-if="showPhoneUpload"
      :folder-id="activeFolder || undefined"
      target-label="私人资料库"
      @close="showPhoneUpload = false"
      @received="refresh"
    />

    <ModalShell
      :open="materialEditOpen"
      title="编辑资料信息"
      subtitle="可修改展示名称、备注和所在资料夹；文件内容不会变化。"
      @close="materialEditOpen = false"
    >
      <div class="space-y-4">
        <div>
          <label class="field-label" for="library-material-name">文件名</label>
          <input id="library-material-name" v-model="materialEditName" maxlength="255" class="field-textarea mt-1.5 h-11 resize-none py-2.5" />
        </div>
        <div>
          <label class="field-label" for="library-material-folder">所在资料夹</label>
          <select id="library-material-folder" v-model="materialEditFolder" class="field-textarea mt-1.5 h-11 resize-none py-2.5">
            <option value="">未分类</option>
            <option v-for="folder in folders" :key="folder.id" :value="folder.id">{{ folder.name }}</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="library-material-remark">备注</label>
          <textarea id="library-material-remark" v-model="materialEditRemark" rows="4" maxlength="500" class="field-textarea mt-1.5" />
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" @click="materialEditOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingMaterial" @click="saveMaterialEdit">保存修改</button>
      </template>
    </ModalShell>

    <ModalShell
      :open="folderEditOpen"
      title="重命名资料夹"
      max-width="max-w-md"
      @close="folderEditOpen = false"
    >
      <label class="field-label" for="library-folder-name">资料夹名称</label>
      <input id="library-folder-name" v-model="folderEditName" maxlength="120" class="field-textarea mt-1.5 h-11 resize-none py-2.5" @keyup.enter="saveFolderEdit" />
      <template #footer>
        <button type="button" class="btn-secondary" @click="folderEditOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="savingFolder" @click="saveFolderEdit">保存</button>
      </template>
    </ModalShell>

    <div
      v-if="preview"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      @click.self="closePreview"
    >
      <div class="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p class="min-w-0 flex-1 truncate text-[13.5px] font-medium text-ink-900">
            {{ preview.material.original_name }}
          </p>
          <button type="button" class="text-ink-400 hover:text-ink-700" @click="closePreview">
            <X :size="17" />
          </button>
        </div>
        <div class="flex-1 overflow-auto bg-slate-50 p-4">
          <img
            v-if="preview.kind === 'image'"
            :src="preview.url"
            :alt="preview.material.original_name"
            class="mx-auto max-h-[70vh] rounded-lg"
          />
          <iframe
            v-else-if="preview.kind === 'pdf'"
            :src="preview.url"
            class="h-[70vh] w-full rounded-lg border border-slate-200"
            title="PDF 预览"
          ></iframe>
          <pre
            v-else
            class="whitespace-pre-wrap break-words text-[12.5px] leading-6 text-ink-700"
          >{{ previewText }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
