<script setup lang="ts">
import { computed, onMounted } from "vue";
import { BarChart3, Clock, Flame, Target } from "lucide-vue-next";
import EChart from "@/components/EChart.vue";
import type { EChartsOption } from "@/lib/echarts";
import { useFocusStore } from "@/stores/focus";

const focus = useFocusStore();

const series = computed(() => focus.stats?.daily_series ?? []);

// 近 7 日专注时长：柱状图（时长）+ 折线（趋势），由 ECharts 渲染。
const chartOption = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter: (params: unknown) => {
      const items = params as { name?: string; value?: number; seriesName?: string }[];
      const first = items[0];
      if (!first) return "";
      return `${first.name}<br/>${first.seriesName}：${first.value ?? 0} 分钟`;
    },
  },
  grid: { left: 8, right: 8, top: 24, bottom: 0, containLabel: true },
  xAxis: {
    type: "category",
    data: series.value.map((item) => item.day.replace("星期", "周")),
    axisLine: { lineStyle: { color: "#e2e8f0" } },
    axisTick: { show: false },
    axisLabel: { color: "#94a3b8", fontSize: 11 },
  },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#f1f5f9" } },
    axisLabel: { color: "#94a3b8", fontSize: 11, formatter: "{value}分" },
  },
  series: [
    {
      name: "专注时长",
      type: "bar",
      data: series.value.map((item) => item.mins),
      barMaxWidth: 26,
      itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: {
          type: "linear",
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "#d96570" },
            { offset: 0.5, color: "#9b72cb" },
            { offset: 1, color: "#4285f4" },
          ],
        },
      },
    },
    {
      name: "趋势",
      type: "line",
      data: series.value.map((item) => item.mins),
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { color: "#f59e0b", width: 2 },
      itemStyle: { color: "#f59e0b" },
    },
  ],
}));

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

onMounted(() => {
  void focus.loadStats();
});
</script>

<template>
  <div class="space-y-4 p-3 sm:p-5">
    <div>
      <h1 class="text-lg font-semibold text-slate-900">专注与统计</h1>
      <p class="text-xs text-slate-400">本周专注时长、次数与主力方向</p>
    </div>

    <div class="grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-3">
      <div class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <Clock :size="14" />
          本周累计专注
        </div>
        <p class="mt-2 text-2xl font-bold text-slate-900">
          {{ focus.stats?.weekly_total_minutes ?? 0 }}
          <span class="text-xs font-normal text-slate-400">分钟</span>
        </p>
      </div>
      <div class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <Flame :size="14" />
          专注次数
        </div>
        <p class="mt-2 text-2xl font-bold text-slate-900">
          {{ focus.stats?.session_count ?? 0 }}
          <span class="text-xs font-normal text-slate-400">次</span>
        </p>
      </div>
      <div class="col-span-2 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm sm:col-span-1">
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <Target :size="14" />
          主力专注方向
        </div>
        <p class="mt-2 truncate text-lg font-semibold text-slate-900">
          {{ focus.stats?.top_direction || "暂无记录" }}
        </p>
      </div>
    </div>

    <div class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <div class="flex items-center gap-2">
        <BarChart3 :size="15" class="text-blue-600" />
        <h2 class="text-sm font-semibold text-slate-800">近 7 日专注时长分布</h2>
      </div>
      <EChart v-if="series.length" class="mt-3 !h-44 sm:!h-60" :option="chartOption" :height="240" />
      <div v-else class="flex h-56 items-center justify-center text-xs text-slate-400">
        暂无专注记录
      </div>
    </div>

    <div class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <h2 class="text-sm font-semibold text-slate-800">专注记录明细</h2>
      <div class="mt-3 space-y-1.5">
        <div
          v-for="log in focus.stats?.recent_logs ?? []"
          :key="log.id"
          class="flex items-center gap-3 rounded-xl border border-slate-100 px-3 py-2"
        >
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <Clock :size="13" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-xs font-medium text-slate-800">{{ log.target_title }}</p>
            <p class="text-[10px] text-slate-400">{{ formatDateTime(log.created_at) }}</p>
          </div>
          <span class="text-xs font-semibold text-slate-700">{{ log.minutes }} 分钟</span>
        </div>
        <p v-if="!focus.stats?.recent_logs?.length" class="py-6 text-center text-xs text-slate-400">
          还没有专注记录。回到任意页面使用底部专注条，点击「完成记录」即可写入这里。
        </p>
      </div>
    </div>
  </div>
</template>
