<script setup lang="ts">
import { useId } from "vue";

withDefaults(
  defineProps<{
    size?: number;
  }>(),
  { size: 32 },
);

const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
const orbId = `zixxx-orb-${uid}`;
const shineId = `zixxx-shine-${uid}`;
</script>

<template>
  <span
    class="brand-mark"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient :id="orbId" x1="6" y1="5" x2="43" y2="44" gradientUnits="userSpaceOnUse">
          <stop stop-color="#818CF8" />
          <stop offset="0.48" stop-color="#4F7CFF" />
          <stop offset="1" stop-color="#22D3EE" />
        </linearGradient>
        <linearGradient :id="shineId" x1="15" y1="12" x2="31" y2="33" gradientUnits="userSpaceOnUse">
          <stop stop-color="white" />
          <stop offset="1" stop-color="white" stop-opacity="0.65" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="15" :fill="`url(#${orbId})`" />
      <circle cx="24" cy="24" r="14.5" stroke="white" stroke-opacity="0.22" />
      <path
        d="M24 11.5c.72 7.28 4.22 10.78 11.5 11.5-7.28.72-10.78 4.22-11.5 11.5-.72-7.28-4.22-10.78-11.5-11.5 7.28-.72 10.78-4.22 11.5-11.5Z"
        :fill="`url(#${shineId})`"
      />
      <circle cx="35.5" cy="13.5" r="2.1" fill="white" fill-opacity="0.9" />
    </svg>
  </span>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  flex-shrink: 0;
  filter: drop-shadow(0 7px 14px rgba(59, 101, 246, 0.27));
}
.brand-mark svg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>