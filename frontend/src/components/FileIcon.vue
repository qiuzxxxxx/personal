<script setup lang="ts">
import { computed, type Component } from "vue";
import {
  File,
  FileText,
  FileSpreadsheet,
  FileArchive,
  FileImage,
  Presentation,
  FileCode2,
} from "lucide-vue-next";
import { fileExtension } from "@/lib/format";

const props = withDefaults(
  defineProps<{
    name: string;
    mime?: string;
    size?: "sm" | "md" | "lg";
    rounded?: string;
  }>(),
  { mime: "", size: "md", rounded: "rounded-2xl" },
);

interface FileVisual {
  icon: Component;
  classes: string;
}

const visual = computed<FileVisual>(() => {
  const ext = fileExtension(props.name);
  if (["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(ext) || props.mime.startsWith("image/")) {
    return { icon: FileImage, classes: "bg-rose-50 text-rose-500 ring-rose-100" };
  }
  if (ext === "pdf") {
    return { icon: FileText, classes: "bg-red-50 text-red-500 ring-red-100" };
  }
  if (["doc", "docx", "pages"].includes(ext)) {
    return { icon: FileText, classes: "bg-blue-50 text-blue-500 ring-blue-100" };
  }
  if (["xls", "xlsx", "csv", "numbers"].includes(ext)) {
    return { icon: FileSpreadsheet, classes: "bg-emerald-50 text-emerald-600 ring-emerald-100" };
  }
  if (["ppt", "pptx", "key"].includes(ext)) {
    return { icon: Presentation, classes: "bg-amber-50 text-amber-600 ring-amber-100" };
  }
  if (["zip", "rar", "7z", "tar", "gz"].includes(ext)) {
    return { icon: FileArchive, classes: "bg-orange-50 text-orange-500 ring-orange-100" };
  }
  if (["js", "ts", "json", "py", "html", "css", "vue", "md", "txt"].includes(ext)) {
    return { icon: FileCode2, classes: "bg-violet-50 text-violet-500 ring-violet-100" };
  }
  return { icon: File, classes: "bg-slate-50 text-slate-500 ring-slate-100" };
});

const dimensions = computed(() => {
  if (props.size === "sm") return "h-8 w-8";
  if (props.size === "lg") return "h-14 w-14";
  return "h-11 w-11";
});

const iconSize = computed(() => {
  if (props.size === "sm") return 15;
  if (props.size === "lg") return 25;
  return 20;
});
</script>

<template>
  <span
    class="flex shrink-0 items-center justify-center ring-1 ring-inset"
    :class="[dimensions, rounded, visual.classes]"
  >
    <component :is="visual.icon" :size="iconSize" :stroke-width="1.7" />
  </span>
</template>