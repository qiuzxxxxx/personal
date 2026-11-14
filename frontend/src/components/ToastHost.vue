<script setup lang="ts">
import { CircleCheck, CircleAlert, Info, X } from "lucide-vue-next";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed inset-x-0 top-4 z-[120] flex flex-col items-center gap-2 px-4">
      <TransitionGroup name="toast">
        <div
          v-for="item in toast.items"
          :key="item.id"
          class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border bg-white/95 px-4 py-3 shadow-[0_18px_50px_-20px_rgba(15,23,42,0.35)] backdrop-blur-xl"
          :class="{
            'border-emerald-200/80': item.kind === 'success',
            'border-rose-200/80': item.kind === 'error',
            'border-slate-200/80': item.kind === 'info',
          }"
          role="status"
        >
          <span
            class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
            :class="{
              'bg-emerald-50 text-emerald-600': item.kind === 'success',
              'bg-rose-50 text-rose-600': item.kind === 'error',
              'bg-sky-50 text-sky-600': item.kind === 'info',
            }"
          >
            <CircleCheck v-if="item.kind === 'success'" :size="15" />
            <CircleAlert v-else-if="item.kind === 'error'" :size="15" />
            <Info v-else :size="15" />
          </span>
          <p class="min-w-0 flex-1 pt-0.5 text-[13px] leading-5 text-ink-700">{{ item.message }}</p>
          <button
            type="button"
            class="mt-0.5 rounded-md p-1 text-ink-400 transition hover:bg-slate-100 hover:text-ink-700"
            aria-label="关闭通知"
            @click="toast.dismiss(item.id)"
          >
            <X :size="14" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>