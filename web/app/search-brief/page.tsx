"use client";
import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { SearchBrief, Signal, SignalCategory } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { SignalChip } from "@/components/SignalChip";
import { QueryPreview } from "@/components/QueryPreview";
import { PageCircle } from "@/components/ui/PageCircle";
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
      <div className="bg-yellow/10 border-l-[3px] border-yellow px-4 py-3 text-sm text-ink">
        Select a profile first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden -mx-6 px-6 -mt-10 pt-10 pb-6 flex items-start justify-between">
        <PageCircle colour="yellow" />
        <div className="relative">
          <h1 className="text-5xl font-bold text-ink leading-none">search brief</h1>
          <p className="text-sm text-ink-muted mt-3">
            {brief ? brief.headline : "Generate a brief to see what parameters the job search agent uses"}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 bg-ink hover:bg-ink/80 disabled:opacity-50 text-paper px-4 py-2 text-sm font-bold transition-colors shrink-0 relative"
        >
          {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {brief ? "regenerate" : "generate from resume"}
        </button>
      </div>

      {error && (
        <div className="bg-red/10 border-l-[3px] border-red px-3 py-2 text-sm text-ink">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-ink-muted text-sm py-4">
          <Loader2 size={14} className="animate-spin" />
          Loading brief…
        </div>
      )}

      {!loading && !brief && !generating && (
        <div className="border-t-[1.5px] border-ink pt-5 text-center">
          <div className="w-12 h-12 bg-ink text-paper flex items-center justify-center mx-auto mb-4">
            <RefreshCw size={20} className="text-ink" />
          </div>
          <p className="text-ink font-bold mb-1">No search brief yet</p>
          <p className="text-ink-muted text-sm max-w-xs mx-auto">
            Click "Generate from Resume" — Claude reads your resume and extracts the search parameters automatically.
          </p>
        </div>
      )}

      {generating && (
        <div className="border-t-[1.5px] border-ink pt-5 text-center">
          <Loader2 size={28} className="animate-spin text-ink mx-auto mb-3" />
          <p className="text-ink font-bold">Analysing your resume…</p>
          <p className="text-ink-muted text-sm mt-1">Claude is extracting search signals. This takes ~10 seconds.</p>
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
                <div key={cat} className="border-t-[1.5px] border-ink pt-5">
                  <div className="flex items-baseline justify-between mb-1">
                    <h2 className="font-bold text-ink text-sm">{meta.label}</h2>
                    <span className="text-xs text-ink-muted">
                      {chips.filter(s => s.active).length}/{chips.length} active
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted mb-3">{meta.description}</p>

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
                          className="text-sm border border-rule-soft px-3 py-1.5 text-ink placeholder-muted bg-paper focus:outline-none focus:ring-2 focus:ring-ink focus:border-ink w-32"
                        />
                        <button
                          onClick={() => handleAdd(cat)}
                          className="text-xs bg-ink text-paper px-3 py-1.5 font-medium hover:bg-ink/80 transition-colors"
                        >
                          Add
                        </button>
                        <button
                          onClick={() => { setAddingCategory(null); setNewLabel(""); }}
                          className="text-xs text-ink-muted hover:text-ink transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setAddingCategory(cat)}
                        className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink border border-dashed border-rule-soft px-3 py-1.5 transition-colors"
                      >
                        <Plus size={11} />
                        add
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
