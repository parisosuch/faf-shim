import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, parseUTC } from "../lib/api";

interface BucketEntry {
  bucket: string;
  requests: number;
  successful_forwards: number;
  failed_forwards: number;
  avg_duration_ms: number | null;
}

interface ShimMetric {
  shim_id: number;
  slug: string;
  name: string;
  total_requests: number;
  successful_forwards: number;
  failed_forwards: number;
  avg_duration_ms: number | null;
  last_triggered_at: string | null;
  buckets: BucketEntry[];
}

interface MetricsResponse {
  global: {
    total_requests: number;
    successful_forwards: number;
    failed_forwards: number;
    avg_duration_ms: number | null;
    cache_hits: number;
    cache_misses: number;
    buckets: BucketEntry[];
  };
  shims: ShimMetric[];
}

// ---------------------------------------------------------------------------
// Fill in missing buckets so the chart always shows a full timeline
// ---------------------------------------------------------------------------

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function formatBucketKey(date: Date, bucketType: Bucket): string {
  const y = date.getUTCFullYear();
  const m = pad2(date.getUTCMonth() + 1);
  const d = pad2(date.getUTCDate());
  const h = pad2(date.getUTCHours());
  if (bucketType === "hour") return `${y}-${m}-${d} ${h}:00`;
  if (bucketType === "day") return `${y}-${m}-${d}`;
  if (bucketType === "month") return `${y}-${m}`;
  // week: Python's %Y-%W (Monday-based, week 0 = days before first Monday)
  const jan1 = new Date(Date.UTC(y, 0, 1));
  const weekNum = Math.floor(
    (date.getTime() - jan1.getTime()) / (7 * 24 * 60 * 60 * 1000) +
      (jan1.getUTCDay() === 0 ? 0 : (7 - jan1.getUTCDay()) / 7),
  );
  return `${y}-${pad2(weekNum)}`;
}

function normalizeBuckets(raw: BucketEntry[], bucketType: Bucket, range: number): BucketEntry[] {
  const map = new Map(raw.map((b) => [b.bucket, b]));

  const now = new Date();
  const buckets: BucketEntry[] = [];

  for (let i = range - 1; i >= 0; i--) {
    const d = new Date(now);
    if (bucketType === "hour") d.setUTCHours(d.getUTCHours() - i, 0, 0, 0);
    else if (bucketType === "day") d.setUTCDate(d.getUTCDate() - i);
    else if (bucketType === "week") d.setUTCDate(d.getUTCDate() - i * 7);
    else d.setUTCMonth(d.getUTCMonth() - i);

    const key = formatBucketKey(d, bucketType);
    buckets.push(
      map.get(key) ?? {
        bucket: key,
        requests: 0,
        successful_forwards: 0,
        failed_forwards: 0,
        avg_duration_ms: null,
      },
    );
  }

  return buckets;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="stat bg-base-100 rounded-box border border-base-300">
      <div className="stat-title">{label}</div>
      <div className="stat-value text-xl">{value}</div>
      {sub && <div className="stat-desc">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

type Bucket = "hour" | "day" | "week" | "month";

export default function MetricsDashboard() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bucket, setBucket] = useState<Bucket>("day");
  const [range, setRange] = useState(30);

  async function load(b: Bucket, r: number) {
    setLoading(true);
    setError(null);
    try {
      const res = await api<MetricsResponse>(`/metrics/?bucket=${b}&range=${r}`);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(bucket, range);
  }, []);

  function handleBucket(b: Bucket) {
    setBucket(b);
    load(b, range);
  }

  function handleRange(r: number) {
    setRange(r);
    load(bucket, r);
  }

  const g = data?.global;

  // Resolve DaisyUI theme colors via Tailwind's compiled classes so we get
  // actual color values that work as SVG fill attributes (not CSS var refs).
  const [colors, setColors] = useState({
    success: "#22c55e",
    error: "#ef4444",
    b2: "#1a1a1a",
    b3: "#333",
  });
  useEffect(() => {
    function resolveColor(cls: string) {
      const el = document.createElement("div");
      el.className = cls;
      el.style.cssText = "position:absolute;visibility:hidden";
      document.body.appendChild(el);
      const color = getComputedStyle(el).backgroundColor;
      document.body.removeChild(el);
      return color || undefined;
    }
    setColors({
      success: resolveColor("bg-success") ?? "#22c55e",
      error: resolveColor("bg-error") ?? "#ef4444",
      b2: resolveColor("bg-base-200") ?? "#1a1a1a",
      b3: resolveColor("bg-base-300") ?? "#333",
    });
  }, []);
  const chartData = useMemo(
    () => (g ? normalizeBuckets(g.buckets, bucket, range) : []),
    [g, bucket, range],
  );

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Metrics</h1>
        <button className="btn btn-ghost btn-sm" onClick={() => load(bucket, range)}>
          Refresh
        </button>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {/* Global stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <StatCard label="Total Requests" value={g?.total_requests ?? "—"} />
        <StatCard
          label="Successful"
          value={g?.successful_forwards ?? "—"}
          sub={
            g && g.total_requests > 0
              ? `${Math.round((g.successful_forwards / g.total_requests) * 100)}%`
              : undefined
          }
        />
        <StatCard label="Failed" value={g?.failed_forwards ?? "—"} />
        <StatCard
          label="Avg Duration"
          value={g?.avg_duration_ms != null ? `${g.avg_duration_ms}ms` : "—"}
        />
        <StatCard
          label="Cache Hits"
          value={g?.cache_hits ?? "—"}
          sub={
            g && g.cache_hits + g.cache_misses > 0
              ? `${Math.round((g.cache_hits / (g.cache_hits + g.cache_misses)) * 100)}% hit rate`
              : undefined
          }
        />
        <StatCard label="Cache Misses" value={g?.cache_misses ?? "—"} />
      </div>

      {/* Chart controls + chart */}
      <div className="card bg-base-100 border border-base-300 mb-6">
        <div className="card-body p-4">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h2 className="font-semibold">Requests over time</h2>
            <div className="flex gap-2">
              <select
                className="select select-bordered select-sm w-32"
                value={range}
                onChange={(e) => handleRange(Number(e.target.value))}
              >
                <option value={7}>Last 7</option>
                <option value={30}>Last 30</option>
                <option value={90}>Last 90</option>
              </select>
              <select
                className="select select-bordered select-sm"
                value={bucket}
                onChange={(e) => handleBucket(e.target.value as Bucket)}
              >
                <option value="hour">Hours</option>
                <option value="day">Days</option>
                <option value="week">Weeks</option>
                <option value="month">Months</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center py-10">
              <span className="loading loading-spinner" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.15} />
                <XAxis
                  dataKey="bucket"
                  tick={{ fontSize: 11, fillOpacity: 0.5 }}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 11, fillOpacity: 0.5 }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  width={32}
                />
                <Tooltip
                  contentStyle={{
                    background: colors.b2,
                    border: `1px solid ${colors.b3}`,
                    borderRadius: "var(--rounded-box, 0.5rem)",
                    fontSize: 12,
                  }}
                  cursor={{ fill: colors.b3, opacity: 0.4 }}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <Bar
                  dataKey="successful_forwards"
                  name="Success"
                  stackId="a"
                  fill={colors.success}
                  opacity={0.85}
                  radius={[0, 0, 0, 0]}
                />
                <Bar
                  dataKey="failed_forwards"
                  name="Failed"
                  stackId="a"
                  fill={colors.error}
                  opacity={0.85}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Per-shim table */}
      <div className="card bg-base-100 border border-base-300">
        <div className="card-body p-4">
          <h2 className="font-semibold mb-3">Per-shim totals</h2>
          {!data || data.shims.length === 0 ? (
            <p className="text-sm text-base-content/50">No shims yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Shim</th>
                    <th>Total</th>
                    <th>Success</th>
                    <th>Failed</th>
                    <th>Avg Duration</th>
                    <th>Last Triggered</th>
                  </tr>
                </thead>
                <tbody>
                  {data.shims.map((s) => (
                    <tr key={s.shim_id}>
                      <td>
                        <a
                          href={`/shims/detail?id=${s.shim_id}`}
                          className="hover:underline font-medium"
                        >
                          {s.name}
                        </a>
                        <div className="text-xs text-base-content/50">{s.slug}</div>
                      </td>
                      <td>{s.total_requests}</td>
                      <td>
                        <span className="text-success">{s.successful_forwards}</span>
                      </td>
                      <td>
                        <span className={s.failed_forwards > 0 ? "text-error" : ""}>
                          {s.failed_forwards}
                        </span>
                      </td>
                      <td>{s.avg_duration_ms != null ? `${s.avg_duration_ms}ms` : "—"}</td>
                      <td className="text-sm text-base-content/60">
                        {s.last_triggered_at ? parseUTC(s.last_triggered_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
