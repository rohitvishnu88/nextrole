"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { ArrowLeft, Upload, Pencil, Trash2, Plus } from "lucide-react";
import { ReplaceResumeModal } from "@/components/ReplaceResumeModal";
import { SectionInstructionBox } from "@/components/resume-edit/SectionInstructionBox";
import { EditableItemForm } from "@/components/resume-edit/EditableItemForm";
import { HistoryPanel } from "@/components/resume-edit/HistoryPanel";

interface ResumeData {
  name?: string;
  designation?: string;
  work_right?: string;
  email?: string;
  phone?: string;
  website?: string;
  summary?: string;
  experience?: Record<string, unknown>[];
  skills?: Record<string, string[]>;
  education?: Record<string, unknown>[];
  certifications?: Record<string, unknown>[];
  languages?: string[];
  [key: string]: unknown;
}

export default function ResumeEditPage() {
  const { slug } = useParams<{ slug: string }>();
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [error, setError] = useState("");
  const [applyError, setApplyError] = useState("");
  const [showReplace, setShowReplace] = useState(false);
  const [editing, setEditing] = useState<{ section: string; action: "add" | "edit"; itemIndex?: number; group?: string; skill?: string } | null>(null);
  const [drafted, setDrafted] = useState<unknown[] | unknown | null>(null);

  const TITLE_FIELD: Record<string, string> = { experience: "title", education: "degree", certifications: "name" };
  const SECTION_TITLES: Record<string, string> = { experience: "Experience", education: "Education", certifications: "Certifications" };

  // Blank/whitespace-only lines in a string-array field (e.g. an Experience
  // entry's `description` bullets) are filtered once here, at submit time -
  // not on every keystroke. Filtering per-keystroke would strip a trailing
  // blank line the instant the user presses Enter, before they can type the
  // next line, making multi-line entry impossible.
  function stripBlankStringArrays(value: unknown): unknown {
    if (Array.isArray(value)) {
      if (value.every(v => typeof v === "string")) {
        return (value as string[]).filter(s => s.trim() !== "");
      }
      return value.map(stripBlankStringArrays);
    }
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, stripBlankStringArrays(v)])
      );
    }
    return value;
  }

  async function handleDraft(section: string, instruction: string) {
    const target = editing;
    if (!target || !slug) return;
    const res = await api.draftResumeSection(slug, section, {
      action: target.action,
      item_index: target.itemIndex,
      group: target.group,
      skill: target.skill,
      instruction,
    });
    setDrafted(target.action === "add" ? res.items ?? [] : res.item ?? null);
  }

  async function handleConfirm(section: string) {
    if (!editing || !slug || drafted == null) return;
    try {
      await api.applyResumeSection(slug, section, {
        action: editing.action,
        item_index: editing.itemIndex,
        group: editing.group,
        skill: editing.skill,
        item: stripBlankStringArrays(drafted),
      });
      setApplyError("");
      setEditing(null);
      setDrafted(null);
      loadResume();
    } catch (err) {
      setApplyError(`Failed to save: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  async function handleDelete(section: string, itemIndex: number) {
    if (!slug) return;
    if (!confirm("Delete this entry?")) return;
    try {
      await api.applyResumeSection(slug, section, { action: "delete", item_index: itemIndex });
      setApplyError("");
      loadResume();
    } catch (err) {
      setApplyError(`Failed to delete entry: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  function renderListObjectSection(section: "experience" | "education" | "certifications") {
    const items = (resume?.[section] as Record<string, unknown>[] | undefined) ?? [];
    const titleField = TITLE_FIELD[section];
    return (
      <section key={section}>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{SECTION_TITLES[section]}</h2>
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={i} className="bg-surface rounded-lg p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-800">{String(item[titleField] ?? "")}</p>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => { setEditing({ section, action: "edit", itemIndex: i }); setDrafted(null); setApplyError(""); }} className="text-gray-400 hover:text-gray-700">
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => handleDelete(section, i)} className="text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {editing?.section === section && editing.action === "edit" && editing.itemIndex === i && (
                drafted == null ? (
                  <div className="mt-2">
                    <SectionInstructionBox
                      placeholder="Describe the change..."
                      submitLabel="Draft"
                      onSubmit={instruction => handleDraft(section, instruction)}
                      onCancel={() => { setEditing(null); setApplyError(""); }}
                    />
                  </div>
                ) : (
                  <div className="mt-2 space-y-2">
                    <EditableItemForm value={drafted as Record<string, unknown>} onChange={setDrafted} />
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                      <button onClick={() => handleConfirm(section)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
                    </div>
                  </div>
                )
              )}
            </div>
          ))}
        </div>

        {editing?.section === section && editing.action === "add" ? (
          drafted == null ? (
            <div className="mt-3">
              <SectionInstructionBox
                placeholder={`Describe the new ${SECTION_TITLES[section].toLowerCase()} entry...`}
                submitLabel="Draft"
                onSubmit={instruction => handleDraft(section, instruction)}
                onCancel={() => { setEditing(null); setApplyError(""); }}
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              {(drafted as Record<string, unknown>[]).map((draftItem, i) => (
                <div key={i} className="bg-surface rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <div className="flex-1">
                      <EditableItemForm
                        value={draftItem}
                        onChange={next => setDrafted((drafted as Record<string, unknown>[]).map((d, j) => (j === i ? next : d)))}
                      />
                    </div>
                    <button
                      onClick={() => setDrafted((drafted as Record<string, unknown>[]).filter((_, j) => j !== i))}
                      className="text-gray-400 hover:text-red-500 shrink-0"
                      title="Remove this drafted item"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button
                  onClick={() => handleConfirm(section)}
                  disabled={(drafted as Record<string, unknown>[]).length === 0}
                  className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-accent"
                >
                  Confirm
                </button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section, action: "add" }); setDrafted(null); setApplyError(""); }}
            className="mt-3 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
        )}
      </section>
    );
  }

  function renderSkillsSection() {
    const skills = resume?.skills ?? {};
    return (
      <section key="skills">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Skills</h2>
        <div className="space-y-2">
          {Object.entries(skills).map(([group, list]) => (
            <div key={group} className="bg-surface rounded-lg p-3">
              <p className="text-xs font-medium text-gray-500 mb-1">{group}</p>
              <div className="flex flex-wrap gap-1.5">
                {list.map(skill => (
                  <span key={skill} className="flex items-center gap-1 bg-white border border-gray-200 rounded-full px-2 py-0.5 text-xs text-gray-700">
                    {skill}
                    <button onClick={() => { setEditing({ section: "skills", action: "edit", group, skill }); setDrafted(null); setApplyError(""); }} className="text-gray-400 hover:text-gray-700">
                      <Pencil size={11} />
                    </button>
                    <button onClick={() => handleDeleteSkill(group, skill)} className="text-gray-400 hover:text-red-500">
                      <Trash2 size={11} />
                    </button>
                  </span>
                ))}
              </div>
              {editing?.section === "skills" && editing.action === "edit" && editing.group === group && editing.skill && list.includes(editing.skill) && (
                drafted == null ? (
                  <div className="mt-2">
                    <SectionInstructionBox
                      placeholder="Describe the change..."
                      submitLabel="Draft"
                      onSubmit={instruction => handleDraft("skills", instruction)}
                      onCancel={() => { setEditing(null); setApplyError(""); }}
                    />
                  </div>
                ) : (
                  <div className="mt-2 space-y-2">
                    <EditableItemForm value={drafted as Record<string, unknown>} onChange={setDrafted} />
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                      <button onClick={() => handleConfirmSkillEdit()} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
                    </div>
                  </div>
                )
              )}
            </div>
          ))}
        </div>

        {editing?.section === "skills" && editing.action === "add" ? (
          drafted == null ? (
            <div className="mt-3">
              <SectionInstructionBox
                placeholder="Describe the new skill(s), e.g. 'I learned Kafka and improved my Python'"
                submitLabel="Draft"
                onSubmit={instruction => handleDraft("skills", instruction)}
                onCancel={() => { setEditing(null); setApplyError(""); }}
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              {(drafted as { group: string; skill: string }[]).map((draftItem, i) => (
                <div key={i} className="bg-surface rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <div className="flex-1">
                      <EditableItemForm
                        value={draftItem}
                        onChange={next => setDrafted((drafted as Record<string, unknown>[]).map((d, j) => (j === i ? next : d)))}
                      />
                    </div>
                    <button
                      onClick={() => setDrafted((drafted as { group: string; skill: string }[]).filter((_, j) => j !== i))}
                      className="text-gray-400 hover:text-red-500 shrink-0"
                      title="Remove this drafted item"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button
                  onClick={() => handleConfirm("skills")}
                  disabled={(drafted as { group: string; skill: string }[]).length === 0}
                  className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-accent"
                >
                  Confirm
                </button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section: "skills", action: "add" }); setDrafted(null); setApplyError(""); }}
            className="mt-3 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
        )}
      </section>
    );
  }

  async function handleDeleteSkill(group: string, skill: string) {
    if (!slug) return;
    if (!confirm(`Delete "${skill}" from ${group}?`)) return;
    try {
      await api.applyResumeSection(slug, "skills", { action: "delete", group, skill });
      setApplyError("");
      loadResume();
    } catch (err) {
      setApplyError(`Failed to delete entry: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  async function handleConfirmSkillEdit() {
    if (!editing || !slug || drafted == null) return;
    try {
      await api.applyResumeSection(slug, "skills", {
        action: "edit",
        group: editing.group,
        skill: editing.skill,
        item: stripBlankStringArrays(drafted),
      });
      setApplyError("");
      setEditing(null);
      setDrafted(null);
      loadResume();
    } catch (err) {
      setApplyError(`Failed to save: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  function renderLanguagesSection() {
    const items = resume?.languages ?? [];
    return (
      <section key="languages">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Languages</h2>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {items.map((lang, i) => (
            <span key={lang} className="flex items-center gap-1 bg-surface border border-gray-200 rounded-full px-2 py-0.5 text-xs text-gray-700">
              {lang}
              <button onClick={() => { setEditing({ section: "languages", action: "edit", itemIndex: i }); setDrafted(null); setApplyError(""); }} className="text-gray-400 hover:text-gray-700">
                <Pencil size={11} />
              </button>
              <button onClick={() => handleDelete("languages", i)} className="text-gray-400 hover:text-red-500">
                <Trash2 size={11} />
              </button>
            </span>
          ))}
        </div>

        {editing?.section === "languages" && editing.action === "edit" && (
          drafted == null ? (
            <div className="mb-2">
              <SectionInstructionBox
                placeholder="Describe the change..."
                submitLabel="Draft"
                onSubmit={instruction => handleDraft("languages", instruction)}
                onCancel={() => { setEditing(null); setApplyError(""); }}
              />
            </div>
          ) : (
            <div className="mb-2 space-y-2">
              <EditableItemForm value={drafted as string} onChange={setDrafted} />
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleConfirm("languages")} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        )}

        {editing?.section === "languages" && editing.action === "add" ? (
          drafted == null ? (
            <SectionInstructionBox
              placeholder="Describe the new language(s), e.g. 'I learned French and German'"
              submitLabel="Draft"
              onSubmit={instruction => handleDraft("languages", instruction)}
              onCancel={() => { setEditing(null); setApplyError(""); }}
            />
          ) : (
            <div className="space-y-2">
              <EditableItemForm value={(drafted as string[]).join("\n")} onChange={v => setDrafted((v as string).split("\n"))} />
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button
                  onClick={() => handleConfirm("languages")}
                  disabled={(drafted as string[]).filter(s => s.trim() !== "").length === 0}
                  className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-accent"
                >
                  Confirm
                </button>
              </div>
            </div>
          )
        ) : (
          !(editing?.section === "languages" && editing.action === "edit") && (
            <button
              onClick={() => { setEditing({ section: "languages", action: "add" }); setDrafted(null); setApplyError(""); }}
              className="flex items-center gap-1 text-xs text-accent hover:underline"
            >
              <Plus size={13} /> Add new
            </button>
          )
        )}
      </section>
    );
  }

  async function handleScalarConfirm(section: string) {
    if (!slug || drafted == null) return;
    try {
      await api.applyResumeSection(slug, section, { action: "edit", item: stripBlankStringArrays(drafted) });
      setApplyError("");
      setEditing(null);
      setDrafted(null);
      loadResume();
    } catch (err) {
      setApplyError(`Failed to save: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  function renderScalarField(fieldKey: string, label: string) {
    const value = String(resume?.[fieldKey] ?? "");
    const isEditingThis = editing?.section === fieldKey;
    return (
      <section key={fieldKey}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</h2>
          {!isEditingThis && (
            <button onClick={() => { setEditing({ section: fieldKey, action: "edit" }); setDrafted(null); setApplyError(""); }} className="text-gray-400 hover:text-gray-700">
              <Pencil size={13} />
            </button>
          )}
        </div>
        {isEditingThis ? (
          drafted == null ? (
            <SectionInstructionBox
              placeholder={`Describe the change to ${label.toLowerCase()}...`}
              submitLabel="Draft"
              onSubmit={instruction => handleDraft(fieldKey, instruction)}
              onCancel={() => { setEditing(null); setApplyError(""); }}
            />
          ) : (
            <div className="space-y-2">
              <EditableItemForm value={drafted as string} onChange={setDrafted} />
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); setApplyError(""); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleScalarConfirm(fieldKey)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <p className="text-sm text-gray-700">{value || <span className="text-gray-400">(empty)</span>}</p>
        )}
      </section>
    );
  }

  const loadResume = useCallback(() => {
    if (!slug) return;
    api.getResume(slug)
      .then(data => {
        setResume(data as ResumeData);
        setError("");
      })
      .catch(() => setError("No resume data found for this profile."));
  }, [slug]);

  useEffect(() => { loadResume(); }, [loadResume]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!resume) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href={`/profile/${slug}`} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800">
          <ArrowLeft size={14} />
          Back to {resume.name ?? slug}
        </Link>
        <button
          onClick={() => setShowReplace(true)}
          className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
        >
          <Upload size={13} />
          Replace Resume
        </button>
      </div>

      <h1 className="text-xl font-bold text-gray-900">Edit Resume</h1>

      {applyError && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3">
          <p className="text-sm text-red-700">{applyError}</p>
        </div>
      )}

      {renderScalarField("summary", "Summary")}
      {renderListObjectSection("experience")}
      {renderSkillsSection()}
      {renderListObjectSection("education")}
      {renderListObjectSection("certifications")}
      {renderLanguagesSection()}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">Contact</h2>
        <div className="space-y-3">
          {renderScalarField("designation", "Designation")}
          {renderScalarField("work_right", "Work Right")}
          {renderScalarField("email", "Email")}
          {renderScalarField("phone", "Phone")}
          {renderScalarField("website", "Website")}
        </div>
      </section>

      {slug && <HistoryPanel slug={slug} onRestored={loadResume} />}

      {showReplace && slug && (
        <ReplaceResumeModal
          slug={slug}
          onClose={() => setShowReplace(false)}
          onReplaced={loadResume}
        />
      )}
    </div>
  );
}
