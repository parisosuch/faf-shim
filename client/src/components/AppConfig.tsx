import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Config {
  cors_origins: string[];
  log_retention_days: number;
  max_body_size_kb: number;
  cleanup_interval_seconds: number;
}

export default function AppConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // CORS tag input state
  const [corsInput, setCorsInput] = useState("");
  const [corsOrigins, setCorsOrigins] = useState<string[]>([]);

  // Numeric fields stored as strings so the user can freely edit them
  const [logRetention, setLogRetention] = useState("30");
  const [maxBodySize, setMaxBodySize] = useState("1024");
  const [cleanupInterval, setCleanupInterval] = useState("3600");

  useEffect(() => {
    api<Config>("/config/")
      .then((data) => {
        setConfig(data);
        setCorsOrigins(data.cors_origins);
        setLogRetention(String(data.log_retention_days));
        setMaxBodySize(String(data.max_body_size_kb));
        setCleanupInterval(String(data.cleanup_interval_seconds));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load config"))
      .finally(() => setLoading(false));
  }, []);

  function addOrigin() {
    const val = corsInput.trim();
    if (!val || corsOrigins.includes(val)) return;
    setCorsOrigins((prev) => [...prev, val]);
    setCorsInput("");
  }

  function removeOrigin(origin: string) {
    setCorsOrigins((prev) => prev.filter((o) => o !== origin));
  }

  function handleCorsKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addOrigin();
    }
  }

  async function save() {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await api<Config>("/config/", {
        method: "PATCH",
        body: {
          cors_origins: corsOrigins,
          log_retention_days: parseInt(logRetention) || 0,
          max_body_size_kb: parseInt(maxBodySize) || 1,
          cleanup_interval_seconds: parseInt(cleanupInterval) || 60,
        },
      });
      setConfig(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save config");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  if (!config && error) {
    return <div className="alert alert-error">{error}</div>;
  }

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Config</h1>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}
      {success && <div className="alert alert-success mb-4">Settings saved.</div>}

      <div className="card bg-base-100 border border-base-300 max-w-2xl">
        <div className="card-body gap-5">
          {/* CORS Origins */}
          <div className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">CORS Origins</span>
              <span className="text-xs text-base-content/50">Press Enter or , to add</span>
            </div>
            <div className="flex flex-wrap gap-2 p-2 rounded-box border border-base-300 bg-base-200 min-h-10">
              {corsOrigins.map((origin) => (
                <span key={origin} className="badge badge-neutral gap-1">
                  {origin}
                  <button
                    type="button"
                    className="text-base-content/60 hover:text-base-content"
                    onClick={() => removeOrigin(origin)}
                    aria-label={`Remove ${origin}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
              <input
                type="text"
                className="bg-transparent outline-none text-sm flex-1 min-w-24"
                placeholder={corsOrigins.length === 0 ? "e.g. https://example.com" : ""}
                value={corsInput}
                onChange={(e) => setCorsInput(e.target.value)}
                onKeyDown={handleCorsKeyDown}
                onBlur={addOrigin}
              />
            </div>
          </div>

          {/* Log Retention */}
          <div className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">Log Retention (days)</span>
              <span className="text-xs text-base-content/50">0 = keep forever</span>
            </div>
            <input
              type="number"
              className="input input-bordered"
              min={0}
              value={logRetention}
              onChange={(e) => setLogRetention(e.target.value)}
            />
          </div>

          {/* Max Body Size */}
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">Max Body Size (KB)</span>
            <input
              type="number"
              className="input input-bordered"
              min={1}
              value={maxBodySize}
              onChange={(e) => setMaxBodySize(e.target.value)}
            />
          </div>

          {/* Cleanup Interval */}
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">Cleanup Interval (seconds)</span>
            <input
              type="number"
              className="input input-bordered"
              min={60}
              value={cleanupInterval}
              onChange={(e) => setCleanupInterval(e.target.value)}
            />
          </div>

          <div className="card-actions justify-end pt-2">
            <button className="btn btn-primary" disabled={saving} onClick={save}>
              {saving ? <span className="loading loading-spinner loading-sm" /> : "Save"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
