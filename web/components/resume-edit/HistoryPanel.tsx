"use client";
import { useEffect, useState } from "react";
import { History, Eye, RotateCcw } from "lucide-react";
import * as api from "@/lib/api";
import type { ResumeVersionSummary, ResumeVersion } from "@/lib/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";

interface Props {
  slug: string;
  onRestored: () => void;
}

export function HistoryPanel({ slug, onRestored }: Props) {
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<ResumeVersionSummary[]>([]);
  const [viewing, setViewing] = useState<ResumeVersion | null>(null);
  const [error, setError] = useState("");
  const [confirmingRestoreId, setConfirmingRestoreId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api.getResumeHistory(slug)
      .then(v => {
        setVersions(v);
        setError("");
      })
      .catch(err => {
        setVersions([]);
        setError(`Failed to load history: ${err instanceof Error ? err.message : "unknown error"}`);
      });
  }, [open, slug]);

  async function handleView(versionId: string) {
    try {
      const version = await api.getResumeVersion(slug, versionId);
      setViewing(version);
      setError("");
    } catch (err) {
      setError(`Failed to load version: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  async function doRestore(versionId: string) {
    setConfirmingRestoreId(null);
    try {
      await api.restoreResumeVersion(slug, versionId);
      setError("");
      setViewing(null);
      setOpen(false);
      onRestored();
    } catch (err) {
      setError(`Failed to restore version: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <button onClick={() => setOpen(o => !o)} className="flex items-center gap-1.5 text-sm font-medium text-gray-700 hover:text-gray-900">
        <History size={15} />
        History {open ? "▲" : "▼"}
      </button>

      {error && (
        <div className="mt-2 rounded-lg bg-red-50 border border-red-200 p-3">
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}

      {open && (
        <div className="mt-3 space-y-2">
          {versions.length === 0 && !error && <p className="text-xs text-gray-400">No past versions yet.</p>}
          {[...versions].reverse().map(v => (
            <div key={v.id} className="flex items-center justify-between bg-surface rounded-lg px-3 py-2">
              <div>
                <p className="text-xs font-medium text-gray-800">{v.change_summary}</p>
                <p className="text-xs text-gray-400">{new Date(v.timestamp).toLocaleString()}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => handleView(v.id)} className="text-gray-400 hover:text-gray-700">
                  <Eye size={14} />
                </button>
                <button onClick={() => setConfirmingRestoreId(v.id)} className="text-gray-400 hover:text-accent">
                  <RotateCcw size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {viewing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={() => setViewing(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-xl mx-4 p-6 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-gray-800">{viewing.change_summary}</p>
              <button onClick={() => setConfirmingRestoreId(viewing.id)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">
                Restore this version
              </button>
            </div>
            {error && (
              <div className="mb-3 rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-xs text-red-700">{error}</p>
              </div>
            )}
            <pre className="bg-gray-950 text-green-400 text-xs rounded-lg p-4 overflow-x-auto leading-relaxed">
              {JSON.stringify(viewing.data, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {confirmingRestoreId && (
        <ConfirmDialog
          message="Restore this version? The current resume will be saved to history first."
          confirmLabel="Restore"
          onConfirm={() => doRestore(confirmingRestoreId)}
          onCancel={() => setConfirmingRestoreId(null)}
        />
      )}
    </div>
  );
}
