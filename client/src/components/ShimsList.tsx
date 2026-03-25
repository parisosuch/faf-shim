import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Shim, ShimExport } from "../lib/types";

export default function ShimsList() {
  const [shims, setShims] = useState<Shim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create modal
  const createModalRef = useRef<HTMLDialogElement>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({ name: "", slug: "", target_url: "" });

  // Delete modal
  const deleteModalRef = useRef<HTMLDialogElement>(null);
  const [deleteTarget, setDeleteTarget] = useState<Shim | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Import modal
  const importModalRef = useRef<HTMLDialogElement>(null);
  const [importJson, setImportJson] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  async function loadShims() {
    try {
      const data = await api<Shim[]>("/shims/");
      setShims(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shims");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadShims();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api<Shim>("/shims/", { method: "POST", body: createForm });
      await loadShims();
      createModalRef.current?.close();
      setCreateForm({ name: "", slug: "", target_url: "" });
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create shim");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api(`/shims/${deleteTarget.id}`, { method: "DELETE" });
      await loadShims();
      deleteModalRef.current?.close();
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    setImporting(true);
    setImportError(null);
    try {
      const parsed: ShimExport = JSON.parse(importJson);
      await api<Shim>("/shims/import", { method: "POST", body: parsed });
      await loadShims();
      importModalRef.current?.close();
      setImportJson("");
    } catch (e) {
      setImportError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
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
        <h1 className="text-2xl font-bold">Shims</h1>
        <div className="flex gap-2">
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => importModalRef.current?.showModal()}
          >
            Import
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => createModalRef.current?.showModal()}
          >
            New Shim
          </button>
        </div>
      </div>

      {/* Table */}
      {shims.length === 0 ? (
        <div className="text-center py-20 text-base-content/50">
          No shims yet. Create one to get started.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-box border border-base-300">
          <table className="table table-zebra">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
                <th>Target URL</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {shims.map((shim) => (
                <tr key={shim.id}>
                  <td className="font-medium">{shim.name}</td>
                  <td>
                    <code className="text-sm">{shim.slug}</code>
                  </td>
                  <td className="max-w-xs truncate text-sm">{shim.target_url}</td>
                  <td className="text-sm text-base-content/60">
                    {new Date(shim.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex gap-2 justify-end">
                      <a href={`/shims/detail?id=${shim.id}`} className="btn btn-ghost btn-xs">
                        View
                      </a>
                      <button
                        className="btn btn-ghost btn-xs text-error"
                        onClick={() => {
                          setDeleteTarget(shim);
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

      {/* Create modal */}
      <dialog ref={createModalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">New Shim</h3>
          {createError && <div className="alert alert-error mb-4">{createError}</div>}
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Name</span>
              <input
                type="text"
                className="input input-bordered"
                required
                value={createForm.name}
                onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Slug</span>
              <input
                type="text"
                className="input input-bordered"
                required
                pattern="[a-z0-9-]+"
                title="Lowercase letters, numbers, and hyphens only"
                value={createForm.slug}
                onChange={(e) => setCreateForm((f) => ({ ...f, slug: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Target URL</span>
              <input
                type="url"
                className="input input-bordered"
                required
                value={createForm.target_url}
                onChange={(e) => setCreateForm((f) => ({ ...f, target_url: e.target.value }))}
              />
            </div>
            <div className="modal-action mt-2">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => createModalRef.current?.close()}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? <span className="loading loading-spinner loading-sm" /> : "Create"}
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
          <h3 className="font-bold text-lg">Delete Shim</h3>
          <p className="py-4">
            Delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.
          </p>
          <div className="modal-action">
            <button className="btn btn-ghost" onClick={() => deleteModalRef.current?.close()}>
              Cancel
            </button>
            <button className="btn btn-error" disabled={deleting} onClick={handleDelete}>
              {deleting ? <span className="loading loading-spinner loading-sm" /> : "Delete"}
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>

      {/* Import modal */}
      <dialog ref={importModalRef} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">Import Shim</h3>
          {importError && <div className="alert alert-error mb-4">{importError}</div>}
          <form onSubmit={handleImport} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Paste exported JSON</span>
              <textarea
                className="textarea textarea-bordered font-mono text-sm h-48"
                required
                value={importJson}
                onChange={(e) => setImportJson(e.target.value)}
              />
            </div>
            <div className="modal-action mt-2">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => importModalRef.current?.close()}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={importing}>
                {importing ? <span className="loading loading-spinner loading-sm" /> : "Import"}
              </button>
            </div>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </>
  );
}
