"use client";
import { useState } from "react";
import { createPortal } from "react-dom";
import { X, Upload, Check } from "lucide-react";
import * as api from "@/lib/api";

interface Props {
  onClose: () => void;
  onCreated: (slug: string) => void;
}

export function AddProfileModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<Record<string, unknown> | null>(null);
  const [step, setStep] = useState<"form" | "preview" | "done">("form");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  async function handleParse() {
    if (!name || !file) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.parseResume(slug, file);
      setParsed(result);
      setStep("preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to parse resume");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    setLoading(true);
    setError("");
    try {
      await api.createProfile(name, slug);
      await api.confirmResume(slug);
      setStep("done");
      onCreated(slug);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setLoading(false);
    }
  }

  return createPortal(
    <div className="fixed inset-0 bg-ink/50 flex items-center justify-center z-[9999]">
      <div className="bg-surface border-[1.5px] border-ink w-full max-w-xl mx-4 p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-ink-muted hover:text-ink-muted">
          <X size={18} />
        </button>

        <h2 className="text-lg font-bold text-ink mb-4">add profile</h2>

        {step === "form" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink mb-1">name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full border-[1.5px] border-ink px-3 py-2 text-sm text-ink placeholder-ink-muted bg-surface focus:outline-none focus:ring-2 focus:ring-ink"
                placeholder="e.g. Priya"
              />
              {name && <p className="text-xs text-ink-muted mt-1">Slug: {slug}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-ink mb-1">upload resume</label>
              <label className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-rule-soft cursor-pointer hover:border-ink transition-colors">
                <Upload size={20} className="text-ink-muted mb-1" />
                <span className="text-sm text-ink-muted">{file ? file.name : "PDF or DOCX"}</span>
                <input type="file" accept=".pdf,.docx" className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} />
              </label>
            </div>
            {error && <p className="text-sm text-ink border-l-[3px] border-red pl-3">{error}</p>}
            <button
              onClick={handleParse}
              disabled={!name || !file || loading}
              className="w-full bg-ink text-paper py-2 text-sm font-medium disabled:opacity-50 hover:bg-ink/80 transition-colors"
            >
              {loading ? "Parsing..." : "Parse Resume"}
            </button>
          </div>
        )}

        {step === "preview" && parsed && (
          <div className="space-y-4">
            <p className="text-sm text-ink-muted">Review the extracted data before saving:</p>
            <div className="border border-rule-soft divide-y divide-rule-soft max-h-96 overflow-y-auto text-sm text-ink">

              {/* Name */}
              <div className="px-4 py-2.5">
                <span className="text-xs font-bold text-ink-muted block mb-0.5">Name</span>
                <span className="font-medium">{String(parsed.name ?? "—")}</span>
              </div>

              {/* Summary */}
              {typeof parsed.summary === "string" && parsed.summary && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-bold text-ink-muted block mb-0.5">Summary</span>
                  <p className="text-ink leading-relaxed">{parsed.summary}</p>
                </div>
              )}

              {/* Experience */}
              {Array.isArray(parsed.experience) && parsed.experience.length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-bold text-ink-muted block mb-1.5">
                    Experience ({parsed.experience.length} roles)
                  </span>
                  <ul className="space-y-2">
                    {(parsed.experience as Array<Record<string, unknown>>).map((exp, i) => {
                      const bullets = Array.isArray(exp.description) ? exp.description as string[] : [];
                      return (
                        <li key={i} className="text-ink">
                          <span className="font-medium">{typeof exp.title === "string" ? exp.title : "Untitled"}</span>
                          {typeof exp.company === "string" && exp.company && (
                            <span className="text-ink-muted"> · {exp.company}</span>
                          )}
                          {bullets.length > 0 && (
                            <p className="text-xs text-ink-muted mt-0.5">
                              {bullets.length} bullet{bullets.length !== 1 ? "s" : ""} — e.g. {bullets[0].slice(0, 80)}{bullets[0].length > 80 ? "…" : ""}
                            </p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {/* Skills */}
              {typeof parsed.skills === "object" && parsed.skills !== null && Object.keys(parsed.skills).length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-bold text-ink-muted block mb-1.5">Skills</span>
                  <div className="space-y-0.5">
                    {Object.entries(parsed.skills as Record<string, unknown>).map(([group, items]) => (
                      <p key={group} className="text-ink">
                        <span className="font-medium">{group}:</span>{" "}
                        {Array.isArray(items) ? (items as string[]).join(", ") : String(items)}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {Array.isArray(parsed.education) && parsed.education.length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-bold text-ink-muted block mb-1">Education</span>
                  {(parsed.education as Array<Record<string, unknown>>).map((e, i) => (
                    <p key={i} className="text-ink">
                      {typeof e.degree === "string" ? e.degree : ""}
                      {typeof e.school === "string" && e.school ? ` — ${e.school}` : ""}
                    </p>
                  ))}
                </div>
              )}

              {/* Certifications */}
              {Array.isArray(parsed.certifications) && parsed.certifications.length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-bold text-ink-muted block mb-1">Certifications</span>
                  {(parsed.certifications as Array<Record<string, unknown>>).map((c, i) => (
                    <p key={i} className="text-ink">
                      {typeof c.name === "string" ? c.name : ""}
                      {typeof c.issuer === "string" && c.issuer ? ` — ${c.issuer}` : ""}
                    </p>
                  ))}
                </div>
              )}

            </div>
            {error && <p className="text-sm text-ink border-l-[3px] border-red pl-3">{error}</p>}
            <div className="flex gap-3">
              <button onClick={() => setStep("form")} className="flex-1 border-[1.5px] border-ink py-2 text-sm text-ink hover:bg-ink hover:text-paper">
                Re-upload
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading}
                className="flex-1 bg-ink text-paper py-2 text-sm font-medium disabled:opacity-50 hover:bg-ink/80 transition-colors"
              >
                {loading ? "Saving..." : "Confirm & Save"}
              </button>
            </div>
          </div>
        )}

        {step === "done" && (
          <div className="flex flex-col items-center py-6 gap-3">
            <Check size={40} className="text-blue" />
            <p className="text-sm text-ink-muted">Profile created successfully.</p>
            <button onClick={onClose} className="bg-ink text-paper px-6 py-2 text-sm font-medium hover:bg-ink/80">
              done
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
