<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { initChart } from "@/lib/echarts";
import type { EChartsOption } from "@/lib/echarts";
import type { ECharts } from "echarts/core";

const props = withDefaults(
  defineProps<{
    option: EChartsOption;
    height?: number;
  }>(),
  { height: 260 },
);

const chartEl = ref<HTMLElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function render(): void {
  if (chart && props.option) chart.setOption(props.option, true);
}

onMounted(() => {
  if (!chartEl.value) return;
  chart = initChart(chartEl.value);
  render();
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartEl.value);
});

watch(() => props.option, render, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartEl" class="w-full" :style="{ height: `${height}px` }" />
</template>
