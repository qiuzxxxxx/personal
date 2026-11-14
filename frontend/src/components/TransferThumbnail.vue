<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { ImageOff, Loader2 } from "lucide-vue-next";
import FileIcon from "@/components/FileIcon.vue";
import { fetchBlob } from "@/api/client";

const props = withDefaults(
  defineProps<{
    url?: string;
    name: string;
    mime?: string;
    isImage?: boolean;
    size?: "sm" | "md" | "lg";
  }>(),
  { url: "", mime: "", isImage: false, size: "md" },
);

const src = ref("");
const loading = ref(false);
const failed = ref(false);
let alive = true;

const dimensions = () => {
  if (props.size === "lg") return "h-14 w-14";
  if (props.size === "sm") return "h-9 w-9";
  return "h-11 w-11";
};

async function load(): Promise<void> {
  if (src.value) URL.revokeObjectURL(src.value);
  src.value = "";
  failed.value = false;
  if (!props.isImage || !props.url) return;
  loading.value = true;
  try {
    const blob = await fetchBlob(props.url);
    if (!alive) return;
    src.value = URL.createObjectURL(blob);
  } catch {
    if (alive) failed.value = true;
  } finally {
    if (alive) loading.value = false;
  }
}

watch(() => [props.url, props.isImage], load, { immediate: true });

onBeforeUnmount(() => {
  alive = false;
  if (src.value) URL.revokeObjectURL(src.value);
});
</script>

<template>
  <span
    class="relative flex shrink-0 items-center justify-center overflow-hidden rounded-2xl ring-1 ring-inset ring-slate-200/70"
    :class="dimensions()"
  >
    <img
      v-if="src"
      :src="src"
      :alt="name"
      class="h-full w-full object-cover"
    />
    <span v-else-if="loading" class="flex h-full w-full items-center justify-center bg-slate-100">
      <Loader2 :size="14" class="animate-spin text-slate-400" />
    </span>
    <span v-else-if="failed" class="flex h-full w-full items-center justify-center bg-slate-50 text-slate-400">
      <ImageOff :size="15" />
    </span>
    <FileIcon
      v-else
      :name="name"
      :mime="mime"
      :size="size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md'"
      rounded="rounded-none"
    />
  </span>
</template>