import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Shim, ShimRule, ShimVariable } from "../lib/types";

// ---------------------------------------------------------------------------
// Config section
// ---------------------------------------------------------------------------

function ConfigSection({ shim, onSaved }: { shim: Shim; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: shim.name,
    slug: shim.slug,
    target_url: shim.target_url,
    headers: shim.headers,
    secret: shim.secret ?? "",
    signature_header: shim.signature_header ?? "",
    signature_algorithm: shim.signature_algorithm ?? "",
    body_template: shim.body_template ?? "",
    sample_payload: shim.sample_payload ?? "",
    max_body_size_kb: shim.max_body_size_kb?.toString() ?? "",
    log_retention_days: shim.log_retention_days?.toString() ?? "",
    rate_limit_requests: shim.rate_limit_requests?.toString() ?? "",
    rate_limit_window_seconds: shim.rate_limit_window_seconds?.toString() ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function set(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        slug: form.slug,
        target_url: form.target_url,
        headers: form.headers,
        secret: form.secret || null,
        signature_header: form.signature_header || null,
        signature_algorithm: form.signature_algorithm || null,
        body_template: form.body_template || null,
        sample_payload: form.sample_payload || null,
        max_body_size_kb: form.max_body_size_kb ? parseInt(form.max_body_size_kb) : null,
        log_retention_days: form.log_retention_days ? parseInt(form.log_retention_days) : null,
        rate_limit_requests: form.rate_limit_requests ? parseInt(form.rate_limit_requests) : null,
        rate_limit_window_seconds: form.rate_limit_window_seconds
          ? parseInt(form.rate_limit_window_seconds)
          : null,
      };
      await api(`/shims/${shim.id}`, { method: "PATCH", body });
      setSuccess(true);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-2xl">
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">Saved.</div>}

      <div className="grid grid-cols-2 gap-4">
        <label className="form-control col-span-2 sm:col-span-1">
          <div className="label">
            <span className="label-text">Name</span>
          </div>
          <input
            type="text"
            className="input input-bordered"
            required
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
          />
        </label>
        <label className="form-control col-span-2 sm:col-span-1">
          <div className="label">
            <span className="label-text">Slug</span>
          </div>
          <input
            type="text"
            className="input input-bordered"
            required
            value={form.slug}
            onChange={(e) => set("slug", e.target.value)}
          />
        </label>
      </div>

      <label className="form-control">
        <div className="label">
          <span className="label-text">Target URL</span>
        </div>
        <input
          type="url"
          className="input input-bordered"
          required
          value={form.target_url}
          onChange={(e) => set("target_url", e.target.value)}
        />
      </label>

      <label className="form-control">
        <div className="label">
          <span className="label-text">Headers (JSON)</span>
        </div>
        <textarea
          className="textarea textarea-bordered font-mono text-sm"
          rows={3}
          value={form.headers}
          onChange={(e) => set("headers", e.target.value)}
        />
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="form-control">
          <div className="label">
            <span className="label-text">Secret</span>
          </div>
          <input
            type="text"
            className="input input-bordered"
            value={form.secret}
            onChange={(e) => set("secret", e.target.value)}
          />
        </label>
        <label className="form-control">
          <div className="label">
            <span className="label-text">Signature Header</span>
          </div>
          <input
            type="text"
            className="input input-bordered"
            value={form.signature_header}
            onChange={(e) => set("signature_header", e.target.value)}
          />
        </label>
      </div>

      <label className="form-control">
        <div className="label">
          <span className="label-text">Signature Algorithm</span>
        </div>
        <select
          className="select select-bordered"
          value={form.signature_algorithm}
          onChange={(e) => set("signature_algorithm", e.target.value)}
        >
          <option value="">— none —</option>
          <option value="token">token</option>
          <option value="sha256">sha256</option>
        </select>
      </label>

      <label className="form-control">
        <div className="label">
          <span className="label-text">Body Template</span>
        </div>
        <textarea
          className="textarea textarea-bordered font-mono text-sm"
          rows={4}
          value={form.body_template}
          onChange={(e) => set("body_template", e.target.value)}
        />
      </label>

      <label className="form-control">
        <div className="label">
          <span className="label-text">Sample Payload (JSON)</span>
        </div>
        <textarea
          className="textarea textarea-bordered font-mono text-sm"
          rows={3}
          value={form.sample_payload}
          onChange={(e) => set("sample_payload", e.target.value)}
        />
      </label>

      <div className="divider text-sm">Per-shim overrides (leave blank to use global defaults)</div>

      <div className="grid grid-cols-2 gap-4">
        <label className="form-control">
          <div className="label">
            <span className="label-text">Max Body Size (KB)</span>
          </div>
          <input
            type="number"
            className="input input-bordered"
            min={1}
            value={form.max_body_size_kb}
            onChange={(e) => set("max_body_size_kb", e.target.value)}
          />
        </label>
        <label className="form-control">
          <div className="label">
            <span className="label-text">Log Retention (days)</span>
          </div>
          <input
            type="number"
            className="input input-bordered"
            min={0}
            value={form.log_retention_days}
            onChange={(e) => set("log_retention_days", e.target.value)}
          />
        </label>
        <label className="form-control">
          <div className="label">
            <span className="label-text">Rate Limit (requests)</span>
          </div>
          <input
            type="number"
            className="input input-bordered"
            min={1}
            value={form.rate_limit_requests}
            onChange={(e) => set("rate_limit_requests", e.target.value)}
          />
        </label>
        <label className="form-control">
          <div className="label">
            <span className="label-text">Rate Limit Window (seconds)</span>
          </div>
          <input
            type="number"
            className="input input-bordered"
            min={1}
            value={form.rate_limit_window_seconds}
            onChange={(e) => set("rate_limit_window_seconds", e.target.value)}
          />
        </label>
      </div>

      <div className="mt-2">
        <button
          type="submit"
          className={`btn btn-primary${saving ? " loading" : ""}`}
          disabled={saving}
        >
          Save
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Rules section
// ---------------------------------------------------------------------------

const EMPTY_RULE = {
  order: 0,
  field: "",
  operator: "==",
  value: "",
  target_url: "",
  body_template: "",
};

function RulesSection({ shim, onChanged }: { shim: Shim; onChanged: () => void }) {
  const rules = shim.rules;
  const modalRef = useRef<HTMLDialogElement>(null);
  const deleteModalRef = useRef<HTMLDialogElement>(null);
  const [editTarget, setEditTarget] = useState<ShimRule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ShimRule | null>(null);
  const [form, setForm] = useState(EMPTY_RULE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openCreate() {
    setEditTarget(null);
    setForm({ ...EMPTY_RULE, order: rules.length });
    setError(null);
    modalRef.current?.showModal();
  }

  function openEdit(rule: ShimRule) {
    setEditTarget(rule);
    setForm({
      order: rule.order,
      field: rule.field,
      operator: rule.operator,
      value: rule.value,
      target_url: rule.target_url,
      body_template: rule.body_template ?? "",
    });
    setError(null);
    modalRef.current?.showModal();
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = { ...form, body_template: form.body_template || null };
      if (editTarget) {
        await api(`/shims/${shim.id}/rules/${editTarget.id}`, { method: "PATCH", body });
      } else {
        await api(`/shims/${shim.id}/rules`, { method: "POST", body });
      }
      onChanged();
      modalRef.current?.close();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await api(`/shims/${shim.id}/rules/${deleteTarget.id}`, { method: "DELETE" });
    onChanged();
    deleteModalRef.current?.close();
    setDeleteTarget(null);
  }

  async function moveRule(rule: ShimRule, direction: "up" | "down") {
    const sorted = [...rules].sort((a, b) => a.order - b.order);
    const idx = sorted.findIndex((r) => r.id === rule.id);
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    const swap = sorted[swapIdx];
    await Promise.all([
      api(`/shims/${shim.id}/rules/${rule.id}`, { method: "PATCH", body: { order: swap.order } }),
      api(`/shims/${shim.id}/rules/${swap.id}`, { method: "PATCH", body: { order: rule.order } }),
    ]);
    onChanged();
  }

  const sorted = [...rules].sort((a, b) => a.order - b.order);

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Rules</h2>
        <button className="btn btn-primary btn-sm" onClick={openCreate}>
          Add Rule
        </button>
      </div>

      {sorted.length === 0 ? (
        <p className="text-base-content/50 text-sm">
          No rules. Webhooks will always forward to the default target URL.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-box border border-base-300">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Order</th>
                <th>Field</th>
                <th>Op</th>
                <th>Value</th>
                <th>Target URL</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((rule, idx) => (
                <tr key={rule.id}>
                  <td>
                    <div className="flex gap-1">
                      <button
                        className="btn btn-ghost btn-xs"
                        disabled={idx === 0}
                        onClick={() => moveRule(rule, "up")}
                      >
                        ↑
                      </button>
                      <button
                        className="btn btn-ghost btn-xs"
                        disabled={idx === sorted.length - 1}
                        onClick={() => moveRule(rule, "down")}
                      >
                        ↓
                      </button>
                    </div>
                  </td>
                  <td className="font-mono text-sm">{rule.field}</td>
                  <td className="font-mono text-sm">{rule.operator}</td>
                  <td className="font-mono text-sm">{rule.value}</td>
                  <td className="text-sm truncate max-w-xs">{rule.target_url}</td>
                  <td>
                    <div className="flex gap-1 justify-end">
                      <button className="btn btn-ghost btn-xs" onClick={() => openEdit(rule)}>
                        Edit
                      </button>
                      <button
                        className="btn btn-ghost btn-xs text-error"
                        onClick={() => {
                          setDeleteTarget(rule);
                          deleteModalRef.current?.showModal();
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/edit modal */}
      <dialog ref={modalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">{editTarget ? "Edit Rule" : "Add Rule"}</h3>
          {error && <div className="alert alert-error mb-4">{error}</div>}
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="form-control">
                <div className="label">
                  <span className="label-text">Field</span>
                </div>
                <input
                  type="text"
                  className="input input-bordered input-sm"
                  required
                  value={form.field}
                  onChange={(e) => setForm((f) => ({ ...f, field: e.target.value }))}
                />
              </label>
              <label className="form-control">
                <div className="label">
                  <span className="label-text">Operator</span>
                </div>
                <select
                  className="select select-bordered select-sm"
                  value={form.operator}
                  onChange={(e) => setForm((f) => ({ ...f, operator: e.target.value }))}
                >
                  <option value="==">==</option>
                  <option value="!=">!=</option>
                  <option value="contains">contains</option>
                </select>
              </label>
            </div>
            <label className="form-control">
              <div className="label">
                <span className="label-text">Value</span>
              </div>
              <input
                type="text"
                className="input input-bordered input-sm"
                required
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              />
            </label>
            <label className="form-control">
              <div className="label">
                <span className="label-text">Target URL</span>
              </div>
              <input
                type="url"
                className="input input-bordered input-sm"
                required
                value={form.target_url}
                onChange={(e) => setForm((f) => ({ ...f, target_url: e.target.value }))}
              />
            </label>
            <label className="form-control">
              <div className="label">
                <span className="label-text">Body Template (optional)</span>
              </div>
              <textarea
                className="textarea textarea-bordered font-mono text-sm"
                rows={3}
                value={form.body_template}
                onChange={(e) => setForm((f) => ({ ...f, body_template: e.target.value }))}
              />
            </label>
            <label className="form-control">
              <div className="label">
                <span className="label-text">Order</span>
              </div>
              <input
                type="number"
                className="input input-bordered input-sm"
                value={form.order}
                onChange={(e) => setForm((f) => ({ ...f, order: parseInt(e.target.value) }))}
              />
            </label>
            <div className="modal-action">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => modalRef.current?.close()}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`btn btn-primary${saving ? " loading" : ""}`}
                disabled={saving}
              >
                Save
              </button>
            </div>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>

      {/* Delete modal */}
      <dialog ref={deleteModalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg">Delete Rule</h3>
          <p className="py-4">
            Delete rule matching{" "}
            <strong>
              {deleteTarget?.field} {deleteTarget?.operator} {deleteTarget?.value}
            </strong>
            ?
          </p>
          <div className="modal-action">
            <button className="btn btn-ghost" onClick={() => deleteModalRef.current?.close()}>
              Cancel
            </button>
            <button className="btn btn-error" onClick={handleDelete}>
              Delete
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Variables section
// ---------------------------------------------------------------------------

function VariablesSection({ shim, onChanged }: { shim: Shim; onChanged: () => void }) {
  const modalRef = useRef<HTMLDialogElement>(null);
  const deleteModalRef = useRef<HTMLDialogElement>(null);
  const [editTarget, setEditTarget] = useState<ShimVariable | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ShimVariable | null>(null);
  const [form, setForm] = useState({ key: "", value: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openCreate() {
    setEditTarget(null);
    setForm({ key: "", value: "" });
    setError(null);
    modalRef.current?.showModal();
  }

  function openEdit(v: ShimVariable) {
    setEditTarget(v);
    setForm({ key: v.key, value: v.value });
    setError(null);
    modalRef.current?.showModal();
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editTarget) {
        await api(`/shims/${shim.id}/variables/${editTarget.id}`, { method: "PATCH", body: form });
      } else {
        await api(`/shims/${shim.id}/variables`, { method: "POST", body: form });
      }
      onChanged();
      modalRef.current?.close();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await api(`/shims/${shim.id}/variables/${deleteTarget.id}`, { method: "DELETE" });
    onChanged();
    deleteModalRef.current?.close();
    setDeleteTarget(null);
  }

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Variables</h2>
        <button className="btn btn-primary btn-sm" onClick={openCreate}>
          Add Variable
        </button>
      </div>

      {shim.variables.length === 0 ? (
        <p className="text-base-content/50 text-sm">No variables defined.</p>
      ) : (
        <div className="overflow-x-auto rounded-box border border-base-300">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shim.variables.map((v) => (
                <tr key={v.id}>
                  <td className="font-mono text-sm">{v.key}</td>
                  <td className="font-mono text-sm">{v.value}</td>
                  <td>
                    <div className="flex gap-1 justify-end">
                      <button className="btn btn-ghost btn-xs" onClick={() => openEdit(v)}>
                        Edit
                      </button>
                      <button
                        className="btn btn-ghost btn-xs text-error"
                        onClick={() => {
                          setDeleteTarget(v);
                          deleteModalRef.current?.showModal();
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <dialog ref={modalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">
            {editTarget ? "Edit Variable" : "Add Variable"}
          </h3>
          {error && <div className="alert alert-error mb-4">{error}</div>}
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <label className="form-control">
              <div className="label">
                <span className="label-text">Key</span>
              </div>
              <input
                type="text"
                className="input input-bordered"
                required
                value={form.key}
                onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))}
              />
            </label>
            <label className="form-control">
              <div className="label">
                <span className="label-text">Value</span>
              </div>
              <input
                type="text"
                className="input input-bordered"
                required
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              />
            </label>
            <div className="modal-action">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => modalRef.current?.close()}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`btn btn-primary${saving ? " loading" : ""}`}
                disabled={saving}
              >
                Save
              </button>
            </div>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>

      <dialog ref={deleteModalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg">Delete Variable</h3>
          <p className="py-4">
            Delete variable <strong>{deleteTarget?.key}</strong>?
          </p>
          <div className="modal-action">
            <button className="btn btn-ghost" onClick={() => deleteModalRef.current?.close()}>
              Cancel
            </button>
            <button className="btn btn-error" onClick={handleDelete}>
              Delete
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Test section
// ---------------------------------------------------------------------------

interface TestResult {
  matched_rule: ShimRule | null;
  target_url: string;
  rendered_body: string | null;
  rendered_headers: Record<string, string> | null;
}

function TestSection({ shim }: { shim: Shim }) {
  const [payload, setPayload] = useState(shim.sample_payload ?? "{}");
  const [result, setResult] = useState<TestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleTest(e: React.FormEvent) {
    e.preventDefault();
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const parsed = JSON.parse(payload);
      const data = await api<TestResult>(`/shims/${shim.id}/test`, {
        method: "POST",
        body: { payload: parsed },
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Test failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={handleTest} className="flex flex-col gap-3">
        <label className="form-control">
          <div className="label">
            <span className="label-text">Payload (JSON)</span>
          </div>
          <textarea
            className="textarea textarea-bordered font-mono text-sm h-36"
            required
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
          />
        </label>
        <div>
          <button
            type="submit"
            className={`btn btn-primary${running ? " loading" : ""}`}
            disabled={running}
          >
            Run Test
          </button>
        </div>
      </form>

      {result && (
        <div className="flex flex-col gap-3">
          <div className="rounded-box border border-base-300 p-4 flex flex-col gap-2">
            <div className="text-sm font-semibold">Matched Rule</div>
            {result.matched_rule ? (
              <code className="text-sm">
                {result.matched_rule.field} {result.matched_rule.operator}{" "}
                {result.matched_rule.value}
              </code>
            ) : (
              <span className="text-sm text-base-content/50">None (using shim default)</span>
            )}
          </div>
          <div className="rounded-box border border-base-300 p-4 flex flex-col gap-2">
            <div className="text-sm font-semibold">Target URL</div>
            <code className="text-sm">{result.target_url}</code>
          </div>
          {result.rendered_body !== null && (
            <div className="rounded-box border border-base-300 p-4 flex flex-col gap-2">
              <div className="text-sm font-semibold">Rendered Body</div>
              <pre className="text-sm overflow-x-auto">{result.rendered_body}</pre>
            </div>
          )}
          {result.rendered_headers !== null && (
            <div className="rounded-box border border-base-300 p-4 flex flex-col gap-2">
              <div className="text-sm font-semibold">Rendered Headers</div>
              <pre className="text-sm overflow-x-auto">
                {JSON.stringify(result.rendered_headers, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type Tab = "config" | "rules" | "variables" | "test";

export default function ShimDetail() {
  const [shimId, setShimId] = useState<number | null>(null);
  const [shim, setShim] = useState<Shim | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("config");

  async function loadShim(id: number) {
    try {
      const data = await api<Shim>(`/shims/${id}`);
      setShim(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shim");
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
    loadShim(id);
  }, []);

  async function handleExport() {
    if (!shimId) return;
    const data = await api<object>(`/shims/${shimId}/export`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `shim-${shim?.slug ?? shimId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  if (error || !shim) {
    return <div className="alert alert-error">{error ?? "Shim not found"}</div>;
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
            /
          </div>
          <h1 className="text-2xl font-bold">{shim.name}</h1>
          <code className="text-sm text-base-content/60">{shim.slug}</code>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm" onClick={handleExport}>
            Export
          </button>
          <a href={`/shims/logs?id=${shimId}`} className="btn btn-ghost btn-sm">
            Logs
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div role="tablist" className="tabs tabs-bordered mb-6">
        {(["config", "rules", "variables", "test"] as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            className={`tab capitalize${tab === t ? " tab-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "config" && <ConfigSection shim={shim} onSaved={loadShim} />}
      {tab === "rules" && <RulesSection shim={shim} onChanged={loadShim} />}
      {tab === "variables" && <VariablesSection shim={shim} onChanged={loadShim} />}
      {tab === "test" && <TestSection shim={shim} />}
    </>
  );
}
