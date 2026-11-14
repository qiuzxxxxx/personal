<script setup lang="ts">
const friendLinks = [
  { label: "qzx 的博客", href: "https://blog.qzx1028.space" },
  { label: "GitHub @qiuzxxxxx", href: "https://github.com/qiuzxxxxx" },
];

const contactEmail = "zixuanqiu72@gmail.com";

const icp = {
  label: "豫ICP备2026020102号",
  href: "https://beian.miit.gov.cn/",
};
</script>

<template>
  <footer class="shrink-0 border-t border-slate-200/60 bg-white/55 backdrop-blur-xl">
    <div
      class="mx-auto flex w-full max-w-[1140px] flex-wrap items-center justify-center gap-x-4 gap-y-1 px-4 py-2.5 text-[9.5px] text-ink-400 sm:justify-between"
    >
      <p>
        © 2026 zixxx · 自托管个人空间 ·
        <a
          :href="`mailto:${contactEmail}`"
          class="transition hover:text-ink-700 hover:underline hover:underline-offset-2"
        >联系：{{ contactEmail }}</a>
      </p>
      <nav class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1" aria-label="友情链接">
        <span class="text-ink-300">友链</span>
        <a
          v-for="link in friendLinks"
          :key="link.href"
          :href="link.href"
          target="_blank"
          rel="noopener noreferrer"
          class="transition hover:text-ink-700 hover:underline hover:underline-offset-2"
        >
          {{ link.label }}
        </a>
        <span class="h-2.5 w-px bg-slate-200" aria-hidden="true" />
        <a
          :href="icp.href"
          target="_blank"
          rel="noopener noreferrer"
          class="transition hover:text-ink-700 hover:underline hover:underline-offset-2"
          title="工业和信息化部政务服务平台"
        >
          {{ icp.label }}
        </a>
      </nav>
    </div>
  </footer>
</template>