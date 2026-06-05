"use client";
import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { SearchBrief, Signal, SignalCategory } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { SignalChip } from "@/components/SignalChip";
import { QueryPreview } from "@/components/QueryPreview";
import { RefreshCw, Plus, Loader2 } from "lucide-react";

const CATEGORY_META: Record<SignalCategory, { label: string; description: string }> = {
  roles:      { label: "Target Roles",   description: "Job titles the agent actively searches for" },
  skills:     { label: "Core Skills",    description: "Technologies included in search queries" },
  location:   { label: "Location",       description: "Where to search — derived from work rights" },
  seniority:  { label: "Seniority",      description: "Career level to target" },
  industries: { label: "Industries",     description: "Preferred sectors (informational — not a hard filter)" },
  exclusions: { label: "Exclusions",     description: "Terms that disqualify a job immediately" },
};

const CATEGORY_ORDER: SignalCategory[] = [
  "roles", "skills", "location", "seniority", "industries", "exclusions",
];

export default function SearchBriefPage() {
  const profile    = useActiveProfile();
  const [brief,    setBrief]    = useState<SearchBrief | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error,    setError]    = useState("");
  const [addingCategory, setAddingCategory] = useState<SignalCategory | null>(null);
  const [newLabel, setNewLabel] = useState("");

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      setBrief(await api.getSearchBrief(profile));
    } catch {
      setBrief(null);
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => { load(); }, [load]);

  async function handleGenerate() {
    if (!profile) return;
    setGenerating(true);
    setError("");
    setBrief(null);
    try {
      await api.generateSearchBrief(profile); // returns {status:"generating"} immediately
      // Poll until the brief file is written by the background task
      let attempts = 0;
      while (attempts < 30) {
        await new Promise(r => setTimeout(r, 2000));
        try {
          const data = await api.getSearchBrief(profile);
          setBrief(data);
          break;
        } catch {
          // still generating — keep polling
        }
        attempts++;
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate");
    } finally {
      setGenerating(false);
    }
  }

  async function handleToggle(id: string, active: boolean) {
    if (!profile || !brief) return;
    const updated = await api.patchSignal(profile, id, { active });
    setBrief(b => b ? { ...b, signals: b.signals.map(s => s.id === id ? { ...s, ...updated } : s) } : b);
  }

  async function handleDelete(id: string) {
    if (!profile || !brief) return;
    await api.deleteSignal(profile, id);
    setBrief(b => b ? { ...b, signals: b.signals.filter(s => s.id !== id) } : b);
  }

  async function handleAdd(category: SignalCategory) {
    if (!profile || !newLabel.trim()) return;
    const signal = await api.addSignal(profile, { category, label: newLabel.trim() });
    setBrief(b => b ? { ...b, signals: [...b.signals, signal] } : b);
    setNewLabel("");
    setAddingCategory(null);
  }

  const signalsByCategory = (cat: SignalCategory): Signal[] =>
    (brief?.signals ?? []).filter(s => s.category === cat);

  if (!profile) {
    return (
      <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
        Select a profile first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Search Brief</h1>
          <p className="text-sm text-muted mt-1">
            {brief ? brief.headline : "Generate a brief to see what parameters the job search agent uses"}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors shrink-0"
        >
          {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {brief ? "Regenerate" : "Generate from Resume"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-3 text-sm text-red-600">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-muted text-sm py-4">
          <Loader2 size={14} className="animate-spin" />
          Loading brief…
        </div>
      )}

      {!loading && !brief && !generating && (
        <div className="bg-white rounded-2xl border border-warm-border p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-accent-light flex items-center justify-center mx-auto mb-4">
            <RefreshCw size={20} className="text-accent" />
          </div>
          <p className="text-navy font-semibold mb-1">No search brief yet</p>
          <p className="text-muted text-sm max-w-xs mx-auto">
            Click "Generate from Resume" — Claude reads your resume and extracts the search parameters automatically.
          </p>
        </div>
      )}

      {generating && (
        <div className="bg-white rounded-2xl border border-warm-border p-12 text-center">
          <Loader2 size={28} className="animate-spin text-accent mx-auto mb-3" />
          <p className="text-navy font-semibold">Analysing your resume…</p>
          <p className="text-muted text-sm mt-1">Claude is extracting search signals. This takes ~10 seconds.</p>
        </div>
      )}

      {brief && !generating && (
        <div className="grid grid-cols-3 gap-6 items-start">

          {/* Signal categories — left 2 cols */}
          <div className="col-span-2 space-y-4">
            {CATEGORY_ORDER.map(cat => {
              const meta  = CATEGORY_META[cat];
              const chips = signalsByCategory(cat);

              return (
                <div key={cat} className="bg-white rounded-2xl border border-warm-border p-5">
                  <div className="flex items-baseline justify-between mb-1">
                    <h2 className="font-semibold text-navy text-sm">{meta.label}</h2>
                    <span className="text-xs text-muted">
                      {chips.filter(s => s.active).length}/{chips.length} active
                    </span>
                  </div>
                  <p className="text-xs text-muted mb-3">{meta.description}</p>

                  <div className="flex flex-wrap gap-2">
                    {chips.map(signal => (
                      <SignalChip
                        key={signal.id}
                        signal={signal}
                        onToggle={handleToggle}
                        onDelete={handleDelete}
                      />
                    ))}

                    {addingCategory === cat ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          autoFocus
                          value={newLabel}
                          onChange={e => setNewLabel(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === "Enter") handleAdd(cat);
                            if (e.key === "Escape") { setAddingCategory(null); setNewLabel(""); }
                          }}
                          placeholder="Label…"
                          className="text-sm border border-warm-border rounded-xl px-3 py-1.5 text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent w-32"
                        />
                        <button
                          onClick={() => handleAdd(cat)}
                          className="text-xs bg-accent text-white rounded-xl px-3 py-1.5 font-medium hover:bg-accent-hover transition-colors"
                        >
                          Add
                        </button>
                        <button
                          onClick={() => { setAddingCategory(null); setNewLabel(""); }}
                          className="text-xs text-muted hover:text-navy transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setAddingCategory(cat)}
                        className="flex items-center gap-1 text-xs text-muted hover:text-accent border border-dashed border-warm-border rounded-full px-3 py-1.5 transition-colors"
                      >
                        <Plus size={11} />
                        Add
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Query preview — right 1 col */}
          <div className="col-span-1">
            <QueryPreview signals={brief.signals} />
          </div>

        </div>
      )}
    </div>
  );
}
