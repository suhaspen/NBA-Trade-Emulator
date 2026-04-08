import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
} from "chart.js";
import { Bar, Radar } from "react-chartjs-2";
import type { AnalysisResult, RadarSeries } from "./api";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
);

const axisColor = "#94a3b8";
const gridColor = "rgba(148, 163, 184, 0.14)";
const legendColor = "#cbd5e1";
const tooltipBg = "rgba(15, 17, 24, 0.94)";
const tooltipBorder = "rgba(255,255,255,0.1)";

function hexToRgba(hex: string, a: number) {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${a})`;
}

const chartCard =
  "rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm";
const chartTitle = "text-sm font-semibold uppercase tracking-wide text-muted";
const chartSub = "mt-1 text-sm text-muted";

export function ChartsBlock({ data }: { data: AnalysisResult }) {
  const bc = data.charts.bar;
  const metrics = Object.keys(bc.metrics);
  const barData = {
    labels: metrics,
    datasets: bc.labels.map((label, i) => ({
      label,
      backgroundColor: bc.colors[i],
      borderColor: bc.colors[i],
      data: metrics.map((m) => {
        const v = bc.metrics[m]![i];
        return v == null ? 0 : v;
      }),
    })),
  };

  const rd = data.charts.radar;
  const radarData = {
    labels: rd.labels,
    datasets: rd.series.map((s: RadarSeries) => ({
      label: s.label,
      data: s.data,
      borderColor: s.color,
      backgroundColor: hexToRgba(s.color, s.dashed ? 0.06 : 0.18),
      borderWidth: 2,
      borderDash: s.dashed ? [6, 4] : [],
      pointBackgroundColor: s.color,
    })),
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className={chartCard}>
        <h3 className={chartTitle}>Metric comparison</h3>
        <p className={chartSub}>Players only; picks affect totals above.</p>
        <div className="mt-5 h-80">
          <Bar
            data={barData}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { labels: { color: legendColor, font: { size: 11 } } },
                tooltip: {
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  borderWidth: 1,
                  titleColor: legendColor,
                  bodyColor: "#e8ecf4",
                  padding: 12,
                  cornerRadius: 8,
                },
              },
              scales: {
                x: { ticks: { color: axisColor }, grid: { color: gridColor } },
                y: { ticks: { color: axisColor }, grid: { color: gridColor }, beginAtZero: true },
              },
            }}
          />
        </div>
      </section>
      <section className={chartCard}>
        <h3 className={chartTitle}>Six-dimension radar</h3>
        <p className={chartSub}>Normalized to the current player pool.</p>
        <div className="mt-5 h-96">
          <Radar
            data={radarData}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { labels: { color: legendColor, font: { size: 11 } } },
                tooltip: {
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  borderWidth: 1,
                  titleColor: legendColor,
                  bodyColor: "#e8ecf4",
                  padding: 12,
                  cornerRadius: 8,
                },
              },
              scales: {
                r: {
                  angleLines: { color: gridColor },
                  grid: { color: gridColor },
                  suggestedMin: 0,
                  suggestedMax: 100,
                  ticks: { color: axisColor, backdropColor: "transparent" },
                  pointLabels: { color: legendColor, font: { size: 11 } },
                },
              },
            }}
          />
        </div>
      </section>
    </div>
  );
}
