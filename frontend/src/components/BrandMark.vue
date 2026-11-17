<script setup lang="ts">
import brandLogo from "@/assets/brand/zixxx-logo.png";

withDefaults(
  defineProps<{
    size?: number;
  }>(),
  { size: 32 },
);
</script>

<template>
  <img
    class="brand-mark"
    :src="brandLogo"
    alt=""
    :style="{ width: `${size * 1.78}px`, height: `${size}px` }"
    aria-hidden="true"
  />
</template>

<style scoped>
.brand-mark {
  display: block;
  flex-shrink: 0;
  object-fit: contain;
  filter: drop-shadow(0 4px 8px rgba(59, 101, 246, 0.14));
}
</style>
