"use client";
import { useState } from "react";
import { X, Upload, Check } from "lucide-react";
import * as api from "@/lib/api";

interface Props {
  onClose: () => void;
  onCreated: () => void;
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
      onCreated();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-xl p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600">
          <X size={18} />
        </button>

        <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Profile</h2>

        {step === "form" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="e.g. Priya"
              />
              {name && <p className="text-xs text-gray-400 mt-1">Slug: {slug}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Upload Resume</label>
              <label className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-accent transition-colors">
                <Upload size={20} className="text-gray-400 mb-1" />
                <span className="text-sm text-gray-500">{file ? file.name : "PDF or DOCX"}</span>
                <input type="file" accept=".pdf,.docx" className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} />
              </label>
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              onClick={handleParse}
              disabled={!name || !file || loading}
              className="w-full bg-accent text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50 hover:bg-accent/90 transition-colors"
            >
              {loading ? "Parsing..." : "Parse Resume"}
            </button>
          </div>
        )}

        {step === "preview" && parsed && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">Review the extracted data before saving:</p>
            <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-96 overflow-y-auto text-sm text-gray-800">

              {/* Name */}
              <div className="px-4 py-2.5">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-0.5">Name</span>
                <span className="font-medium">{String(parsed.name ?? "—")}</span>
              </div>

              {/* Summary */}
              {typeof parsed.summary === "string" && parsed.summary && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-0.5">Summary</span>
                  <p className="text-gray-700 leading-relaxed">{parsed.summary}</p>
                </div>
              )}

              {/* Experience */}
              {Array.isArray(parsed.experience) && parsed.experience.length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                    Experience ({parsed.experience.length} roles)
                  </span>
                  <ul className="space-y-2">
                    {(parsed.experience as Array<Record<string, unknown>>).map((exp, i) => {
                      const bullets = Array.isArray(exp.description) ? exp.description as string[] : [];
                      return (
                        <li key={i} className="text-gray-700">
                          <span className="font-medium">{typeof exp.title === "string" ? exp.title : "Untitled"}</span>
                          {typeof exp.company === "string" && exp.company && (
                            <span className="text-gray-400"> · {exp.company}</span>
                          )}
                          {bullets.length > 0 && (
                            <p className="text-xs text-gray-500 mt-0.5">
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
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">Skills</span>
                  <div className="space-y-0.5">
                    {Object.entries(parsed.skills as Record<string, unknown>).map(([group, items]) => (
                      <p key={group} className="text-gray-700">
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
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1">Education</span>
                  {(parsed.education as Array<Record<string, unknown>>).map((e, i) => (
                    <p key={i} className="text-gray-700">
                      {typeof e.degree === "string" ? e.degree : ""}
                      {typeof e.school === "string" && e.school ? ` — ${e.school}` : ""}
                    </p>
                  ))}
                </div>
              )}

              {/* Certifications */}
              {Array.isArray(parsed.certifications) && parsed.certifications.length > 0 && (
                <div className="px-4 py-2.5">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1">Certifications</span>
                  {(parsed.certifications as Array<Record<string, unknown>>).map((c, i) => (
                    <p key={i} className="text-gray-700">
                      {typeof c.name === "string" ? c.name : ""}
                      {typeof c.issuer === "string" && c.issuer ? ` — ${c.issuer}` : ""}
                    </p>
                  ))}
                </div>
              )}

            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <div className="flex gap-3">
              <button onClick={() => setStep("form")} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50">
                Re-upload
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading}
                className="flex-1 bg-accent text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50 hover:bg-accent/90 transition-colors"
              >
                {loading ? "Saving..." : "Confirm & Save"}
              </button>
            </div>
          </div>
        )}

        {step === "done" && (
          <div className="flex flex-col items-center py-6 gap-3">
            <Check size={40} className="text-green-500" />
            <p className="text-sm text-gray-600">Profile created successfully.</p>
            <button onClick={onClose} className="bg-accent text-white rounded-lg px-6 py-2 text-sm font-medium hover:bg-accent/90">
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
