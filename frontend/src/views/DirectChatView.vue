<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  Check,
  Loader2,
  MessagesSquare,
  Paperclip,
  Plus,
  Send,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-vue-next";
import ChatFileCard from "@/components/ChatFileCard.vue";
import FileIcon from "@/components/FileIcon.vue";
import ModalShell from "@/components/ModalShell.vue";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";
import {
  addBbsReply,
  createBbsPost,
  deleteBbsPost,
  deleteBbsReply,
  getBbsPosts,
  getBbsPost,
  type BBSPostDetail,
  type BBSPostListItem,
  type BBSReplyItem,
} from "@/api/chat";
import { extractApiError } from "@/api/client";
import { formatBytes, formatTime, initials, isSameDay } from "@/lib/format";
import type { User } from "@/types";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const toast = useToastStore();

defineOptions({ name: "DirectChatView" });

// 帖子列表视图
const posts = ref<BBSPostListItem[]>([]);
const loading = ref(true);
const loadError = ref("");

// 帖子详情视图
const currentPost = ref<BBSPostDetail | null>(null);
const viewingPostId = ref("");
const replyDraft = ref("");
const replyFile = ref<File | null>(null);
const replyFileInputRef = ref<HTMLInputElement | null>(null);
const replying = ref(false);
const replyProgress = ref(0);

// 发帖弹窗
const newPostFileRef = ref<HTMLInputElement | null>(null);
const newPostOpen = ref(false);
const newPostTitle = ref("");
const newPostContent = ref("");
const newPostVisibility = ref<"public" | "private">("public");
const newPostVisibleTo = ref<string[]>([]);
const newPostFile = ref<File | null>(null);
const creatingPost = ref(false);

// 删除确认
const deleteDialogOpen = ref(false);
const deleteTarget = ref<{ type: "post" | "reply"; id: string; postId?: string } | null>(null);
const deleting = ref(false);

// 文件选择
const maxFileBytes = 1024 * 1024 * 1024;
const allowedExtensions = new Set([
  "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv",
  "png", "jpg", "jpeg", "webp", "gif", "zip", "rar", "7z",
]);
const accept = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp,.gif,.zip,.rar,.7z";

const currentUser = computed(() => auth.user?.username || "");
const authorized = computed(() => auth.isChatUser);
const canSend = computed(() => Boolean(replyDraft.value.trim() || replyFile.value) && !replying.value);

const emptyPrompts = ["今天有什么新鲜事？", "分享一个好用的工具。", "求推荐一本书。"];

function scrollToBottom(smooth = false): void {
  nextTick(() => {
    const element = document.querySelector(".bbs-canvas");
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  });
}

async function loadPosts(): Promise<void> {
  loading.value = true;
  try {
    posts.value = await getBbsPosts();
    loadError.value = "";
  } catch (error) {
    loadError.value = extractApiError(error);
  } finally {
    loading.value = false;
  }
}

async function openPost(postId: string): Promise<void> {
  try {
    currentPost.value = await getBbsPost(postId);
    viewingPostId.value = postId;
    replyDraft.value = "";
    replyFile.value = null;
    nextTick(scrollToBottom);
  } catch (error) {
    toast.error(extractApiError(error));
  }
}

function goBack(): void {
  currentPost.value = null;
  viewingPostId.value = "";
}

async function sendReply(): Promise<void> {
  if (!canSend.value || !currentPost.value) return;
  replying.value = true;
  replyProgress.value = 0;
  try {
    const reply = await addBbsReply(
      currentPost.value.id,
      replyDraft.value.trim(),
      replyFile.value || undefined,
    );
    currentPost.value.replies.push(reply);
    currentPost.value.reply_count += 1;
    currentPost.value.last_reply_at = reply.created_at;
    replyDraft.value = "";
    replyFile.value = null;
    nextTick(scrollToBottom);
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    replying.value = false;
    replyProgress.value = 0;
  }
}

function openFilePicker(): void {
  replyFileInputRef.value?.click();
}

function setReplyFile(file: File | null): void {
  if (!file) { replyFile.value = null; return; }
  if (!allowedExtensions.has(file.name.split(".").pop()?.toLowerCase() || "")) {
    toast.error("暂不支持该文件类型");
    return;
  }
  if (file.size <= 0 || file.size > maxFileBytes) {
    toast.error("文件大小无效");
    return;
  }
  replyFile.value = file;
}

async function publishPost(): Promise<void> {
  if (creatingPost.value) return;
  creatingPost.value = true;
  try {
    await createBbsPost(
      {
        title: newPostTitle.value.trim(),
        content: newPostContent.value.trim(),
        visibility: newPostVisibility.value,
        visible_to: newPostVisibleTo.value.length ? newPostVisibleTo.value : undefined,
      },
      newPostFile.value || undefined,
    );
    newPostOpen.value = false;
    newPostTitle.value = "";
    newPostContent.value = "";
    newPostVisibility.value = "public";
    newPostVisibleTo.value = [];
    newPostFile.value = null;
    await loadPosts();
    toast.success("帖子已发布");
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    creatingPost.value = false;
  }
}

function openDeleteDialog(item: { type: "post" | "reply"; id: string; postId?: string }): void {
  deleteTarget.value = item;
  deleteDialogOpen.value = true;
}

function closeDeleteDialog(): void {
  deleteTarget.value = null;
  deleteDialogOpen.value = false;
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target || deleting.value) return;
  deleting.value = true;
  try {
    if (target.type === "post") {
      await deleteBbsPost(target.id);
      toast.success("帖子已删除");
    } else if (target.postId) {
      await deleteBbsReply(target.postId, target.id);
      if (currentPost.value && currentPost.value.id === target.postId) {
        currentPost.value.replies = currentPost.value.replies.filter((r) => r.id !== target.id);
        currentPost.value.reply_count = Math.max(0, currentPost.value.reply_count - 1);
      }
      toast.success("回复已删除");
    }
  } catch (error) {
    toast.error(extractApiError(error));
  } finally {
    deleting.value = false;
    closeDeleteDialog();
  }
}

function showDay(index: number, items: { created_at: string }[]): boolean {
  if (index === 0) return true;
  return !isSameDay(items[index - 1].created_at, items[index].created_at);
}

function goToLogin(): void {
  router.push({ path: "/", query: { redirect: "/chat" } });
}

function goAgent(): void {
  router.push({ name: "agent" });
}

onMounted(async () => {
  document.title = "留言板 · zixxx";
  await auth.initialize();
  if (!authorized.value) {
    loading.value = false;
    return;
  }
  await loadPosts();
});

watch(() => route.query.with, async (value) => {
  if (value && typeof value === "string") {
    await openPost(value);
  }
});

onActivated(() => {
  scrollToBottom(false);
});

onBeforeUnmount(() => {});
</script>

<template>
  <div class="bbs-page relative h-full min-h-0 overflow-hidden p-0 sm:p-4 lg:p-5">
    <div class="bbs-aura" aria-hidden="true" />

    <!-- 无权限 -->
    <div v-if="!authorized" class="relative z-10 flex h-full items-center justify-center px-4">
      <div class="w-full max-w-[470px] animate-fade-up rounded-[28px] border border-white/80 bg-white/90 p-8 text-center shadow-float backdrop-blur-xl">
        <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-lg">
          <MessagesSquare :size="23" />
        </span>
        <p class="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-400">Message board</p>
        <h1 class="mt-2 text-[23px] font-medium tracking-tight text-ink-900">站内留言板</h1>
        <p class="mt-3 text-[12.5px] leading-6 text-ink-500">
          当前账号 <span class="font-medium text-ink-700">{{ auth.user?.username || "访客" }}</span>
          不具备留言权限。请使用成员或管理员账号登录。
        </p>
        <div class="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <button type="button" class="btn-primary" @click="goToLogin">
            <ShieldCheck :size="14" />
            切换账号
          </button>
          <button type="button" class="btn-secondary" @click="goAgent">
            <ArrowLeft :size="14" />
            返回 AI 对话
          </button>
        </div>
      </div>
    </div>

    <!-- 帖子列表 -->
    <div v-else-if="!currentPost" class="relative z-10 mx-auto flex h-full w-full max-w-[900px] flex-col overflow-hidden bg-white/82 shadow-[0_24px_80px_-40px_rgba(15,23,42,0.32)] backdrop-blur-xl sm:rounded-[28px] sm:border sm:border-white/90">
      <header class="flex h-[76px] shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/70 px-4 backdrop-blur-xl sm:px-6">
        <div class="relative">
          <span class="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-500 text-[12px] font-semibold text-white shadow-sm">
            <MessagesSquare :size="18" />
          </span>
        </div>
        <div class="min-w-0">
          <h1 class="text-[14px] font-semibold tracking-tight text-ink-900">留言板</h1>
          <p class="mt-0.5 text-[10px] text-ink-400">所有非访客成员公开可见、可发帖、可回复</p>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <span class="hidden items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50/70 px-2.5 py-1.5 text-[9.5px] font-medium text-emerald-700 sm:flex">
            <ShieldCheck :size="10" />
            记录留存服务器
          </span>
          <span class="flex h-8 w-8 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold text-white" :title="currentUser">
            {{ initials(currentUser || "N") }}
          </span>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-4 sm:p-6">
        <!-- 发帖按钮 -->
        <div class="mb-4">
          <button type="button" class="btn-primary inline-flex items-center gap-2" @click="newPostOpen = true">
            <Plus :size="14" />
            发布新帖
          </button>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="space-y-3">
          <div v-for="i in 3" :key="i" class="h-24 animate-pulse rounded-2xl bg-slate-200/70" />
        </div>

        <!-- 错误 -->
        <div v-else-if="loadError" class="flex h-full items-center justify-center py-12">
          <div class="text-center">
            <p class="mt-4 text-[13px] font-medium text-ink-700">暂时无法读取帖子</p>
            <p class="mt-1.5 max-w-[280px] text-[11px] leading-5 text-ink-400">{{ loadError }}</p>
            <button type="button" class="btn-secondary mt-4 h-9 text-[11px]" @click="loadPosts">重新加载</button>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!posts.length" class="flex h-full min-h-[420px] flex-col items-center justify-center px-6 py-10">
          <div class="relative">
            <div class="absolute inset-0 rounded-full bg-accent-300/30 blur-2xl" />
            <span class="relative flex h-16 w-16 items-center justify-center rounded-[22px] border border-white bg-white/85 text-accent-500 shadow-soft backdrop-blur">
              <MessagesSquare :size="26" :stroke-width="1.5" />
            </span>
          </div>
          <p class="mt-6 text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-300">Message board</p>
          <h2 class="mt-2 text-[24px] font-medium tracking-[-0.035em] text-ink-900">还没有帖子</h2>
          <p class="mt-2.5 max-w-[360px] text-center text-[12px] leading-6 text-ink-400">
            成为第一个发帖的人，和大家分享你的想法或文件。
          </p>
          <div class="mt-6 flex flex-wrap justify-center gap-2">
            <button v-for="prompt in emptyPrompts" :key="prompt" type="button" class="rounded-full border border-slate-200/80 bg-white/70 px-3.5 py-2 text-[11px] text-ink-500 shadow-sm transition hover:-translate-y-0.5 hover:border-accent-200 hover:bg-white hover:text-ink-800" @click="newPostContent = prompt; newPostOpen = true">
              {{ prompt }}
            </button>
          </div>
        </div>

        <!-- 帖子列表 -->
        <div v-else class="space-y-3">
          <article
            v-for="(post, index) in posts"
            :key="post.id"
            class="group rounded-2xl border border-slate-200/80 bg-white/90 p-4 transition hover:border-accent-200 hover:shadow-md cursor-pointer"
            @click="openPost(post.id)"
          >
            <div class="flex items-start gap-3">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 text-[10px] font-semibold text-white shadow-sm">
                {{ initials(post.author_username || "N") }}
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-[11px] font-semibold text-ink-700">{{ post.author_name }}</span>
                  <span v-if="post.visibility === 'private'" class="rounded bg-amber-50 px-1.5 py-0.5 text-[8px] font-medium text-amber-600">私密</span>
                  <span class="text-[9px] text-ink-400">{{ formatTime(post.created_at) }}</span>
                </div>
                <h3 class="mt-1 truncate text-[14px] font-semibold text-ink-900 group-hover:text-accent-600">{{ post.title || "无标题" }}</h3>
                <p class="mt-1 line-clamp-2 text-[12px] leading-5 text-ink-600">{{ post.content || "(仅附件)" }}</p>
                <div class="mt-2 flex items-center gap-3 text-[10px] text-ink-400">
                  <span>{{ post.reply_count }} 条回复</span>
                  <span v-if="post.file_name">📎 {{ post.file_name }}</span>
                  <span v-if="post.last_reply_at">最后回复：{{ formatTime(post.last_reply_at) }}</span>
                </div>
              </div>
              <button
                type="button"
                class="shrink-0 rounded-full p-1.5 text-ink-300 transition hover:bg-rose-50 hover:text-rose-600 opacity-0 group-hover:opacity-100"
                :disabled="deleting"
                @click.stop="openDeleteDialog({ type: 'post', id: post.id })"
              >
                <Trash2 :size="13" />
              </button>
            </div>
          </article>
        </div>
      </div>
    </div>

    <!-- 帖子详情（贴吧式） -->
    <div v-else class="relative z-10 mx-auto flex h-full w-full max-w-[900px] flex-col overflow-hidden bg-white/82 shadow-[0_24px_80px_-40px_rgba(15,23,42,0.32)] backdrop-blur-xl sm:rounded-[28px] sm:border sm:border-white/90">
      <header class="flex h-[76px] shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/70 px-4 backdrop-blur-xl sm:px-6">
        <button type="button" class="icon-button h-9 w-9" @click="goBack">
          <ArrowLeft :size="16" />
        </button>
        <div class="min-w-0 flex-1">
          <h1 class="truncate text-[14px] font-semibold tracking-tight text-ink-900">{{ currentPost.title }}</h1>
          <p class="mt-0.5 text-[10px] text-ink-400">{{ currentPost.author_name }} · {{ formatTime(currentPost.created_at) }} · {{ currentPost.reply_count }} 条回复</p>
        </div>
        <span class="flex h-8 w-8 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold text-white" :title="currentUser">
          {{ initials(currentUser || "N") }}
        </span>
      </header>

      <div ref="scrollRef" class="bbs-canvas relative min-h-0 flex-1 overflow-y-auto">
        <!-- 楼主帖子 -->
        <div class="mx-auto max-w-[860px] px-4 py-6 sm:px-7 sm:py-8">
          <article class="mb-6 rounded-2xl border border-accent-100 bg-gradient-to-br from-accent-50/50 to-white p-5">
            <div class="flex items-center gap-3">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 text-[11px] font-semibold text-white shadow-sm">
                {{ initials(currentPost.author_username || "N") }}
              </span>
              <div>
                <span class="text-[12px] font-semibold text-ink-800">{{ currentPost.author_name }}</span>
                <span class="ml-2 rounded bg-accent-50 px-1.5 py-0.5 text-[8px] font-medium text-accent-600">楼主</span>
                <span class="ml-2 text-[9px] text-ink-400">{{ formatTime(currentPost.created_at) }}</span>
              </div>
            </div>
            <div class="mt-3 pl-13">
              <p v-if="currentPost.content" class="whitespace-pre-wrap break-words text-[13.5px] leading-7 text-ink-800">{{ currentPost.content }}</p>
              <ChatFileCard v-if="currentPost.file_name" :message="{ ...currentPost, sender_username: currentUser || 'N', sender_name: currentPost.author_name, recipient_username: null } as any" :self="false" />
            </div>
          </article>

          <!-- 回复列表 -->
          <div class="space-y-3">
            <div v-for="(reply, index) in currentPost.replies" :key="reply.id">
              <div v-if="showDay(index, currentPost.replies)" class="mb-4 mt-2 flex items-center gap-3">
                <span class="h-px flex-1 bg-slate-200/60" />
                <span class="rounded-full bg-white/70 px-2.5 py-1 text-[9px] font-medium tracking-wide text-ink-400 ring-1 ring-slate-200/60">
                  {{ isSameDay(currentPost.created_at, reply.created_at) ? "同一天" : reply.created_at.slice(0, 10) }}
                </span>
                <span class="h-px flex-1 bg-slate-200/60" />
              </div>
              <article class="rounded-xl border border-slate-200/80 bg-white/90 p-3.5">
                <div class="flex items-center gap-2">
                  <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 text-[8px] font-semibold text-white">
                    {{ initials(reply.author_username || "N") }}
                  </span>
                  <span class="text-[11px] font-semibold text-ink-700">{{ reply.author_name }}</span>
                  <span class="text-[9px] text-ink-400">{{ formatTime(reply.created_at) }}</span>
                  <button
                    type="button"
                    class="ml-auto shrink-0 rounded-full p-1 text-ink-300 transition hover:bg-rose-50 hover:text-rose-600"
                    :disabled="deleting"
                    @click="openDeleteDialog({ type: 'reply', id: reply.id, postId: currentPost.id })"
                  >
                    <Trash2 :size="12" />
                  </button>
                </div>
                <div class="mt-2 pl-9">
                  <p class="whitespace-pre-wrap break-words text-[13px] leading-6 text-ink-700">{{ reply.content }}</p>
                  <ChatFileCard v-if="reply.file_name" :message="{ ...reply, sender_username: reply.author_username, sender_name: reply.author_name, recipient_username: null } as any" :self="reply.author_username === currentUser" />
                </div>
              </article>
            </div>
          </div>

          <!-- 回复框 -->
          <div class="mt-6 shrink-0 border-t border-slate-200/60 bg-white/75 px-3 py-4 backdrop-blur-xl sm:px-5">
            <div class="mx-auto max-w-[830px]">
              <div v-if="replyFile" class="mb-2 flex items-center gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50/80 p-2 pr-8">
                <FileIcon :name="replyFile.name" :mime="replyFile.type" size="sm" rounded="rounded-lg" />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[11px] font-medium text-ink-700">{{ replyFile.name }}</p>
                  <p class="text-[9px] text-ink-400">{{ formatBytes(replyFile.size) }}</p>
                </div>
                <button type="button" class="flex h-6 w-6 items-center justify-center rounded-full text-ink-400 hover:text-rose-500" @click="replyFile = null">
                  <X :size="13" />
                </button>
              </div>
              <div class="flex items-end gap-2 rounded-[23px] border bg-white/95 p-2 shadow-[0_18px_50px_-30px_rgba(15,23,42,0.32)]">
                <button type="button" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-500 hover:bg-slate-100 hover:text-ink-900 disabled:opacity-40" @click="replyFileInputRef?.click()">
                  <Paperclip :size="18" :stroke-width="1.9" />
                </button>
                <input ref="replyFileInputRef" type="file" class="hidden" :accept="accept" @change="setReplyFile(($event.target as HTMLInputElement).files?.[0] || null)" />
                <textarea
                  v-model="replyDraft"
                  rows="1"
                  class="min-h-[38px] max-h-[150px] min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-[13.5px] leading-6 text-ink-900 outline-none placeholder:text-ink-400"
                  placeholder="写回复…"
                  :disabled="replying"
                  @keydown.enter.exact.prevent="sendReply"
                  @input="$nextTick(() => { const el = $event.target as HTMLTextAreaElement; el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 150)}px`; })"
                />
                <button
                  type="button"
                  class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-900 text-white shadow-sm transition hover:bg-accent-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
                  :disabled="!canSend"
                  @click="sendReply"
                >
                  <Loader2 v-if="replying" :size="16" class="animate-spin" />
                  <Send v-else :size="16" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 发帖弹窗 -->
    <ModalShell
      :open="newPostOpen"
      title="发布新帖"
      subtitle="标题和正文至少填一个；可附加文件。"
      max-width="max-w-xl"
      @close="newPostOpen = false"
    >
      <div class="space-y-4">
        <div>
          <label class="field-label">标题</label>
          <input v-model="newPostTitle" type="text" class="field-input mt-1.5" maxlength="120" placeholder="选填，让帖子更容易被搜索到" />
        </div>
        <div>
          <label class="field-label">正文</label>
          <textarea v-model="newPostContent" rows="4" maxlength="5000" class="field-textarea mt-1.5" placeholder="输入内容…" />
        </div>
        <div class="flex items-center gap-4">
          <label class="field-label">可见范围</label>
          <select v-model="newPostVisibility" class="field-input mt-0">
            <option value="public">公开（所有人可见）</option>
            <option value="private">指定可见</option>
          </select>
        </div>
        <div v-if="newPostVisibility === 'private'">
          <label class="field-label">可见用户（逗号分隔用户名）</label>
          <input v-model="newPostVisibleTo" type="text" class="field-input mt-1.5" placeholder="例如：sqx,yjt" />
        </div>
        <div>
          <label class="field-label">附件（可选）</label>
          <div class="mt-1.5 flex items-center gap-2">
            <button type="button" class="btn-secondary h-9 text-[11px]" @click="newPostFileRef?.click()">
              <Paperclip :size="13" />
              选择文件
            </button>
            <input ref="newPostFileRef" type="file" class="hidden" :accept="accept" @change="newPostFile = ($event.target as HTMLInputElement).files?.[0] || null" />
            <span v-if="newPostFile" class="text-[11px] text-ink-500">{{ newPostFile.name }} ({{ formatBytes(newPostFile.size) }})</span>
          </div>
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="creatingPost" @click="newPostOpen = false">取消</button>
        <button type="button" class="btn-primary" :disabled="creatingPost" @click="publishPost">
          <Loader2 v-if="creatingPost" :size="13" class="animate-spin" />
          <Plus v-else :size="13" />
          发布
        </button>
      </template>
    </ModalShell>

    <!-- 删除确认 -->
    <ModalShell
      :open="deleteDialogOpen"
      :title="deleteTarget ? (deleteTarget.type === 'post' ? '删除这条帖子' : '删除这条回复') : ''"
      subtitle="此操作不可撤销。"
      max-width="max-w-md"
      @close="closeDeleteDialog"
    >
      <p class="text-[13px] leading-6 text-ink-700">
        {{ deleteTarget && deleteTarget.type === 'post' ? '你确定要删除这条帖子吗？帖子和所有回复都会消失。' : '你确定要删除这条回复吗？' }}
      </p>
      <template #footer>
        <button type="button" class="btn-secondary" :disabled="deleting" @click="closeDeleteDialog">取消</button>
        <button
          type="button"
          class="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-sm font-semibold text-white transition hover:bg-rose-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 disabled:opacity-50"
          :disabled="deleting"
          @click="confirmDelete"
        >
          <Loader2 v-if="deleting" :size="15" class="animate-spin" />
          删除
        </button>
      </template>
    </ModalShell>
  </div>
</template>

<style scoped>
.bbs-page {
  background:
    radial-gradient(800px 440px at 15% 0%, rgba(100, 133, 255, 0.08), transparent 65%),
    radial-gradient(720px 520px at 90% 100%, rgba(20, 184, 166, 0.06), transparent 65%),
    #f6f8fb;
}

.bbs-aura {
  position: absolute;
  top: -260px;
  right: 8%;
  width: 620px;
  height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(125, 211, 252, 0.18), transparent 65%);
  filter: blur(45px);
  pointer-events: none;
}

.bbs-canvas {
  background:
    radial-gradient(800px 500px at 50% -20%, rgba(226, 237, 255, 0.45), transparent 65%),
    #fbfcfe;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
