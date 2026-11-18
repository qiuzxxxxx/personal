/**
 * ECharts 按需引入：只注册项目实际用到的图表与组件，
 * 相比整包引入可显著减小打包体积。
 */
import * as echarts from "echarts/core";
import type { ECharts } from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export type EChartsOption = Parameters<ECharts["setOption"]>[0];

export function initChart(el: HTMLElement): ECharts {
  return echarts.init(el);
}

export default echarts;
