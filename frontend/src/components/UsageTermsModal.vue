<script setup lang="ts">
import ModalShell from "@/components/ModalShell.vue";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";
import { TERMS_MARKDOWN, TERMS_TRANSFER_MARKDOWN, TERMS_VERSION } from "@/lib/terms";

withDefaults(
  defineProps<{
    open: boolean;
    acceptMode?: boolean;
    scope?: "full" | "transfer";
  }>(),
  { acceptMode: false, scope: "full" },
);

const emit = defineEmits<{
  close: [];
  accept: [];
}>();
</script>

<template>
  <ModalShell
    :open="open"
    :title="scope === 'transfer' ? '文件中转站使用声明' : 'zixxx 使用声明'"
    :subtitle="`版本 v${TERMS_VERSION} · 含法条引用、禁止信息与注意事项`"
    max-width="max-w-2xl"
    @close="emit('close')"
  >
    <div class="terms-scroll max-h-[58vh] overflow-y-auto rounded-2xl border border-slate-200/70 bg-slate-50/60 px-5 py-4">
      <MarkdownRenderer :content="scope === 'transfer' ? TERMS_TRANSFER_MARKDOWN : TERMS_MARKDOWN" />
    </div>

    <template #footer>
      <span class="mr-auto text-[9.5px] text-ink-300">
        继续使用即视为同意本声明
      </span>
      <button type="button" class="btn-secondary" @click="emit('close')">关闭</button>
      <button
        v-if="acceptMode"
        type="button"
        class="btn-primary"
        @click="emit('accept')"
      >
        我已阅读并同意
      </button>
    </template>
  </ModalShell>
</template>