import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface WebhookLog {
  id: number;
  shim_id: number;
  received_at: string;
  payload: string;
  forwarded_payload: string | null;
  target_url: string | null;
  status: number | null;
  duration_ms: number | null;
  error: string | null;
}

interface Shim {
  id: number;
  name: string;
  slug: string;
}

const PAGE_SIZE = 50;

export default function ShimLogs() {
  const [shimId, setShimId] = useState<number | null>(null);
  const [shim, setShim] = useState<Shim | null>(null);
  const [logs, setLogs] = useState<WebhookLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  async function loadData(id: number, off: number) {
    setLoading(true);
    try {
      const [shimData, logsData] = await Promise.all([
        api<Shim>(`/shims/${id}`),
        api<WebhookLog[]>(`/shims/${id}/logs?limit=${PAGE_SIZE}&offset=${off}`),
      ]);
      setShim(shimData);
      setLogs(logsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const id = Number(new URLSearchParams(window.location.search).get("id"));
    if (!id) {
      setError("No shim ID provided");
      setLoading(false);
      return;
    }
    setShimId(id);
    loadData(id, 0);
  }, []);

  function changePage(newOffset: number) {
    setOffset(newOffset);
    setExpandedId(null);
    if (shimId) loadData(shimId, newOffset);
  }

  function statusBadge(status: number | null) {
    if (status === null) return <span className="badge badge-ghost badge-sm">—</span>;
    if (status >= 200 && status < 300)
      return <span className="badge badge-success badge-sm">{status}</span>;
    if (status >= 400) return <span className="badge badge-error badge-sm">{status}</span>;
    return <span className="badge badge-warning badge-sm">{status}</span>;
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>;
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-sm text-base-content/50 mb-1">
            <a href="/shims" className="hover:underline">
              Shims
            </a>{" "}
            /{" "}
            <a href={`/shims/detail?id=${shimId}`} className="hover:underline">
              {shim?.name ?? shimId}
            </a>{" "}
            /
          </div>
          <h1 className="text-2xl font-bold">Logs</h1>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => shimId && loadData(shimId, offset)}>
          Refresh
        </button>
      </div>

      {/* Table */}
      {logs.length === 0 ? (
        <div className="text-center py-20 text-base-content/50">No logs yet.</div>
      ) : (
        <div className="overflow-x-auto rounded-box border border-base-300">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Received</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Target URL</th>
                <th>Error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <>
                  <tr
                    key={log.id}
                    className="cursor-pointer hover"
                    onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                  >
                    <td className="text-sm whitespace-nowrap">
                      {new Date(log.received_at).toLocaleString()}
                    </td>
                    <td>{statusBadge(log.status)}</td>
                    <td className="text-sm">
                      {log.duration_ms !== null ? `${log.duration_ms}ms` : "—"}
                    </td>
                    <td className="text-sm truncate max-w-xs">{log.target_url ?? "—"}</td>
                    <td className="text-sm text-error truncate max-w-xs">{log.error ?? "—"}</td>
                    <td>
                      <span className="text-base-content/40 text-xs">
                        {expandedId === log.id ? "▲" : "▼"}
                      </span>
                    </td>
                  </tr>
                  {expandedId === log.id && (
                    <tr key={`${log.id}-expanded`} className="bg-base-200">
                      <td colSpan={6} className="p-4 space-y-4">
                        <div>
                          <div className="text-xs font-semibold mb-2 text-base-content/60">
                            Incoming Payload
                          </div>
                          <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                            {(() => {
                              try {
                                return JSON.stringify(JSON.parse(log.payload), null, 2);
                              } catch {
                                return log.payload;
                              }
                            })()}
                          </pre>
                        </div>
                        {log.forwarded_payload && (
                          <div>
                            <div className="text-xs font-semibold mb-2 text-base-content/60">
                              Outgoing Payload
                            </div>
                            <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                              {(() => {
                                try {
                                  return JSON.stringify(JSON.parse(log.forwarded_payload), null, 2);
                                } catch {
                                  return log.forwarded_payload;
                                }
                              })()}
                            </pre>
                          </div>
                        )}
                        {log.error && (
                          <div>
                            <div className="text-xs font-semibold mb-2 text-error/70">Error</div>
                            <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all text-error">
                              {log.error}
                            </pre>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <button
          className="btn btn-ghost btn-sm"
          disabled={offset === 0}
          onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}
        >
          ← Previous
        </button>
        <span className="text-sm text-base-content/50">
          Showing {offset + 1}–{offset + logs.length}
        </span>
        <button
          className="btn btn-ghost btn-sm"
          disabled={logs.length < PAGE_SIZE}
          onClick={() => changePage(offset + PAGE_SIZE)}
        >
          Next →
        </button>
      </div>
    </>
  );
}
