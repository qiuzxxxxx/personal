<script setup lang="ts">
import { onBeforeUnmount, onMounted, useId } from "vue";

withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    subtitle?: string;
    maxWidth?: string;
    hideClose?: boolean;
  }>(),
  {
    subtitle: "",
    maxWidth: "max-w-lg",
    hideClose: false,
  },
);

const emit = defineEmits<{
  close: [];
}>();

const titleId = useId();

function onBackdrop(): void {
  emit("close");
}

function onClose(): void {
  emit("close");
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[90] flex items-end justify-center bg-ink-950/35 p-0 backdrop-blur-[3px] sm:items-center sm:p-6"
        role="presentation"
        @mousedown.self="onBackdrop"
        @keydown="onKeydown"
      >
        <div
          class="modal-panel flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-[28px] border border-white/70 bg-white shadow-[0_30px_100px_-30px_rgba(15,23,42,0.45)] sm:rounded-[28px]"
          :class="maxWidth"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
        >
          <header class="flex items-start gap-4 border-b border-slate-100 px-6 py-5">
            <div class="min-w-0 flex-1">
              <h2 :id="titleId" class="text-[17px] font-semibold tracking-tight text-ink-900">
                {{ title }}
              </h2>
              <p v-if="subtitle" class="mt-1 text-[13px] leading-5 text-ink-500">
                {{ subtitle }}
              </p>
            </div>
            <button
              v-if="!hideClose"
              type="button"
              class="icon-button -mr-2 -mt-1 h-9 w-9 shrink-0"
              aria-label="关闭"
              @click="onClose"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            <slot />
          </div>

          <footer
            v-if="$slots.footer"
            class="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/70 px-6 py-4"
          >
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>