<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";

const props = withDefaults(
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
const panelRef = ref<HTMLElement | null>(null);
let previousFocus: HTMLElement | null = null;

const focusableSelector = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function onBackdrop(): void {
  emit("close");
}

function onClose(): void {
  emit("close");
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
  if (event.key !== "Tab" || !panelRef.value) return;
  const focusable = Array.from(panelRef.value.querySelectorAll<HTMLElement>(focusableSelector));
  if (!focusable.length) {
    event.preventDefault();
    panelRef.value.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      const first = panelRef.value?.querySelector<HTMLElement>(focusableSelector);
      (first ?? panelRef.value)?.focus();
    } else if (previousFocus?.isConnected) {
      previousFocus.focus();
      previousFocus = null;
    }
  },
);

onMounted(() => document.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[90] flex items-end justify-center bg-black/25 p-0 backdrop-blur-sm sm:items-center sm:p-6"
        role="presentation"
        @mousedown.self="onBackdrop"
        @keydown="onKeydown"
      >
        <div
          ref="panelRef"
          class="modal-panel flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-elevated sm:rounded-2xl"
          :class="maxWidth"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          style="border: 1px solid var(--apple-border)"
        >
          <header class="flex items-start gap-4 border-b px-6 py-5" style="border-color: var(--apple-border)">
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
              class="icon-button -mr-2 -mt-1 h-11 w-11 shrink-0 rounded-full bg-black/[0.04] hover:bg-black/[0.08]"
              aria-label="关闭"
              @click="onClose"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            <slot />
          </div>

          <footer
            v-if="$slots.footer"
            class="flex items-center justify-end gap-2 border-t px-6 py-4"
            style="border-color: var(--apple-border); background: #fafafa"
          >
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
