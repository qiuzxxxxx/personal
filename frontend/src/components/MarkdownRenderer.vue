<script setup lang="ts">
import { computed } from "vue";
import { copyText, renderMarkdown } from "@/lib/markdown";

const props = defineProps<{
  content: string;
}>();

const html = computed(() => renderMarkdown(props.content));

async function onClick(event: MouseEvent): Promise<void> {
  const target = event.target as HTMLElement | null;
  const button = target?.closest<HTMLButtonElement>(".code-copy");
  if (!button) return;
  const shell = button.closest(".code-shell");
  const code = shell?.querySelector("code");
  if (!code) return;
  const copied = await copyText(code.textContent || "");
  const previous = button.textContent;
  button.textContent = copied ? "已复制" : "复制失败";
  button.classList.toggle("is-copied", copied);
  window.setTimeout(() => {
    button.textContent = previous || "复制";
    button.classList.remove("is-copied");
  }, 1600);
}
</script>

<template>
  <div class="markdown-body min-w-0 max-w-full [&>pre]:overflow-x-auto" @click="onClick" v-html="html" />
</template>