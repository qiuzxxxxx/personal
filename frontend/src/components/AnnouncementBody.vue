<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useAnnouncementStore } from "@/stores/announcements";
import { formatDate } from "@/lib/format";

const announcements = useAnnouncementStore();

function currentContent(kind: "login" | "transfer"): string {
  return (
    kind === "login" ? announcements.loginContent : announcements.stationContent
  ).trim();
}

/**
 * 历史接口按发布时间倒序返回。当前公告通常就是每种类型的最新一条，
 * 这里跳过它，避免和上方“当前公告”重复。
 */
const pastHistory = computed(() => {
  const skip = new Set<number>();
  for (const kind of ["login", "transfer"] as const) {
    const current = currentContent(kind);
    if (!current) continue;
    const latest = announcements.history.find((item) => item.kind === kind);
    if (latest && latest.content.trim() === current) skip.add(latest.id);
  }
  return announcements.history.filter((item) => !skip.has(item.id));
});

onMounted(() => {
  void announcements.load();
  // 每次打开公告弹窗都拉取最新历史，管理员刚发布的内容无需刷新页面。
  void announcements.loadHistory(true).then(() => announcements.markSeen());
});
</script>

<template>
  <div>
    <section v-if="announcements.hasLogin" aria-label="登录页公告">
      <p
        v-if="announcements.hasStation"
        class="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-400"
      >
        登录页公告
      </p>
      <p class="whitespace-pre-wrap break-words text-[13px] leading-6 text-ink-700">
        {{ announcements.loginContent }}
      </p>
    </section>

    <section
      v-if="announcements.hasStation"
      aria-label="中转站公告"
      :class="announcements.hasLogin ? 'mt-4 border-t pt-4' : ''"
      style="border-color: var(--apple-border)"
    >
      <p
        v-if="announcements.hasLogin"
        class="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-400"
      >
        中转站公告
      </p>
      <p class="whitespace-pre-wrap break-words text-[13px] leading-6 text-ink-700">
        {{ announcements.stationContent }}
      </p>
    </section>

    <p v-if="!announcements.hasAny && !pastHistory.length" class="text-[13px] leading-6 text-ink-400">
      暂无公告。
    </p>

    <section
      v-if="pastHistory.length || announcements.hasAny"
      class="mt-5 border-t pt-4"
      style="border-color: var(--apple-border)"
      aria-label="历史公告"
    >
      <p class="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-400">
        历史公告
      </p>
      <p v-if="!pastHistory.length" class="text-[11px] leading-5 text-ink-300">
        暂无更早的公告。
      </p>
      <ul v-else class="space-y-2.5">
        <li
          v-for="item in pastHistory"
          :key="item.id"
          class="rounded-xl border border-slate-100 bg-white/80 px-3.5 py-3"
        >
          <div class="flex flex-wrap items-center gap-2 text-[9px] text-ink-400">
            <span
              class="rounded-full px-1.5 py-0.5 font-medium"
              :class="
                item.kind === 'login'
                  ? 'bg-blue-50 text-blue-600'
                  : 'bg-accent-50 text-accent-600'
              "
            >
              {{ item.kind === "login" ? "登录页" : "中转站" }}
            </span>
            <span>{{ formatDate(item.created_at) }}</span>
          </div>
          <p class="mt-1.5 whitespace-pre-wrap break-words text-[12px] leading-6 text-ink-600">
            {{ item.content }}
          </p>
        </li>
      </ul>
    </section>
  </div>
</template>
