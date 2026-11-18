<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { LogOut, Megaphone } from "lucide-vue-next";
import ModalShell from "@/components/ModalShell.vue";
import AnnouncementBody from "@/components/AnnouncementBody.vue";
import brandMark from "@/assets/brand/zixxx-mark.png";
import { useAnnouncementStore } from "@/stores/announcements";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";

// 访客（yk）极简顶栏（交接文档修正 N1）：品牌标识 + 公告铃铛 + 退出登录，
// 仅在访客进入工作台外壳之外的中转站等页面时挂载。
const router = useRouter();
const auth = useAuthStore();
const announcements = useAnnouncementStore();
const toast = useToastStore();

const announcementOpen = ref(false);

async function logout(): Promise<void> {
  void auth.logout();
  toast.success("已退出登录");
  await router.replace("/");
}

onMounted(() => {
  void announcements.load(true);
});
</script>

<template>
  <header class="flex h-12 shrink-0 items-center gap-3 border-b border-white/80 bg-white/75 px-4 backdrop-blur-xl">
    <RouterLink to="/transfer" class="flex items-center gap-2">
      <img
        :src="brandMark"
        alt="缺页中断"
        class="h-7 w-7 rounded-lg object-contain drop-shadow-[0_4px_8px_rgba(59,101,246,0.14)]"
      />
      <span class="gemini-text text-[15px] font-bold tracking-tight">缺页中断</span>
      <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">游客模式</span>
    </RouterLink>

    <div class="ml-auto flex items-center gap-1">
      <button
        type="button"
        class="icon-button relative h-9 w-9 !min-h-0 !min-w-0"
        title="公告"
        aria-label="查看公告"
        @click="announcementOpen = true"
      >
        <Megaphone :size="16" />
        <span
          v-if="announcements.hasUnread"
          class="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-blue-600"
        />
      </button>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
        @click="logout"
      >
        <LogOut :size="14" />
        退出登录
      </button>
    </div>

    <ModalShell
      :open="announcementOpen"
      title="公告"
      subtitle="当前公告与历史记录"
      max-width="max-w-lg"
      @close="announcementOpen = false"
    >
      <AnnouncementBody />
      <template #footer>
        <button type="button" class="btn-secondary" @click="announcementOpen = false">
          关闭
        </button>
      </template>
    </ModalShell>
  </header>
</template>
