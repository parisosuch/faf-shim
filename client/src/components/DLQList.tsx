import { useEffect, useState } from "react";
import { api, parseUTC } from "../lib/api";

interface DeadLetter {
  id: number;
  shim_id: number;
  webhook_log_id: number | null;
  payload: string;
  target_url: string;
  headers: string;
  failed_at: string | null;
  status: number | null;
  error: string | null;
  replayed_at: string | null;
  replay_status: number | null;
  replay_error: string | null;
}

interface Shim {
  id: number;
  name: string;
  slug: string;
}

const PAGE_SIZE = 50;

function statusBadge(status: number | null, fallback = "—") {
  if (status === null) return <span className="badge badge-ghost badge-sm">{fallback}</span>;
  if (status >= 200 && status < 300)
    return <span className="badge badge-success badge-sm">{status}</span>;
  if (status >= 400) return <span className="badge badge-error badge-sm">{status}</span>;
  return <span className="badge badge-warning badge-sm">{status}</span>;
}

export default function DLQList() {
  const [entries, setEntries] = useState<DeadLetter[]>([]);
  const [shims, setShims] = useState<Map<number, Shim>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [replayingId, setReplayingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [clearing, setClearing] = useState(false);

  async function loadData(off: number) {
    setLoading(true);
    setError(null);
    try {
      const [dlqData, shimsData] = await Promise.all([
        api<DeadLetter[]>(`/dlq/?limit=${PAGE_SIZE}&offset=${off}`),
        api<Shim[]>("/shims/"),
      ]);
      setEntries(dlqData);
      setShims(new Map(shimsData.map((s) => [s.id, s])));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load DLQ");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData(0);
  }, []);

  function changePage(newOffset: number) {
    setOffset(newOffset);
    setExpandedId(null);
    loadData(newOffset);
  }

  async function deleteEntry(id: number) {
    setDeletingId(id);
    try {
      await api(`/dlq/${id}`, { method: "DELETE" });
      setEntries((prev) => prev.filter((e) => e.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  async function clearAll() {
    if (!confirm("Delete all dead letter entries? This cannot be undone.")) return;
    setClearing(true);
    try {
      await api("/dlq/", { method: "DELETE" });
      setEntries([]);
      setExpandedId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Clear failed");
    } finally {
      setClearing(false);
    }
  }

  async function replay(id: number) {
    setReplayingId(id);
    try {
      const updated = await api<DeadLetter>(`/dlq/${id}/replay`, { method: "POST" });
      setEntries((prev) => prev.map((e) => (e.id === id ? updated : e)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay failed");
    } finally {
      setReplayingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dead Letter Queue</h1>
        <div className="flex gap-2">
          {entries.length > 0 && (
            <button
              className="btn btn-error btn-sm btn-outline"
              onClick={clearAll}
              disabled={clearing}
            >
              {clearing ? <span className="loading loading-spinner loading-xs" /> : "Clear All"}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => loadData(offset)}>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {entries.length === 0 ? (
        <div className="text-center py-20 text-base-content/50">No dead letters. Nice.</div>
      ) : (
        <div className="overflow-x-auto rounded-box border border-base-300">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Failed At</th>
                <th>Shim</th>
                <th>Target URL</th>
                <th>Status</th>
                <th>Error</th>
                <th>Replayed At</th>
                <th>Replay Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <>
                  <tr
                    key={entry.id}
                    className="cursor-pointer hover"
                    onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                  >
                    <td className="text-sm whitespace-nowrap">
                      {entry.failed_at ? parseUTC(entry.failed_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      {shims.get(entry.shim_id) ? (
                        <a
                          href={`/shims/detail?id=${entry.shim_id}`}
                          className="hover:underline font-medium"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {shims.get(entry.shim_id)!.name}
                        </a>
                      ) : (
                        <span className="text-base-content/40">#{entry.shim_id}</span>
                      )}
                    </td>
                    <td className="text-sm truncate max-w-xs">{entry.target_url}</td>
                    <td>{statusBadge(entry.status)}</td>
                    <td className="text-sm text-error truncate max-w-xs">{entry.error ?? "—"}</td>
                    <td className="text-sm whitespace-nowrap">
                      {entry.replayed_at ? parseUTC(entry.replayed_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      {entry.replayed_at ? (
                        statusBadge(entry.replay_status)
                      ) : (
                        <span className="text-base-content/30 text-xs">—</span>
                      )}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1">
                        <button
                          className="btn btn-xs btn-outline"
                          disabled={replayingId === entry.id}
                          onClick={() => replay(entry.id)}
                        >
                          {replayingId === entry.id ? (
                            <span className="loading loading-spinner loading-xs" />
                          ) : (
                            "Replay"
                          )}
                        </button>
                        <button
                          className="btn btn-xs btn-error btn-outline"
                          disabled={deletingId === entry.id}
                          onClick={() => deleteEntry(entry.id)}
                        >
                          {deletingId === entry.id ? (
                            <span className="loading loading-spinner loading-xs" />
                          ) : (
                            "Delete"
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedId === entry.id && (
                    <tr key={`${entry.id}-expanded`} className="bg-base-200">
                      <td colSpan={8} className="p-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <div className="text-xs font-semibold mb-2 text-base-content/60">
                              Payload
                            </div>
                            <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                              {(() => {
                                try {
                                  return JSON.stringify(JSON.parse(entry.payload), null, 2);
                                } catch {
                                  return entry.payload;
                                }
                              })()}
                            </pre>
                          </div>
                          <div>
                            <div className="text-xs font-semibold mb-2 text-base-content/60">
                              Headers
                            </div>
                            <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                              {(() => {
                                try {
                                  return JSON.stringify(JSON.parse(entry.headers), null, 2);
                                } catch {
                                  return entry.headers;
                                }
                              })()}
                            </pre>
                          </div>
                          {entry.replay_error && (
                            <div className="md:col-span-2">
                              <div className="text-xs font-semibold mb-2 text-error">
                                Replay Error
                              </div>
                              <p className="text-xs text-error">{entry.replay_error}</p>
                            </div>
                          )}
                        </div>
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
          Showing {offset + 1}–{offset + entries.length}
        </span>
        <button
          className="btn btn-ghost btn-sm"
          disabled={entries.length < PAGE_SIZE}
          onClick={() => changePage(offset + PAGE_SIZE)}
        >
          Next →
        </button>
      </div>
    </>
  );
}
