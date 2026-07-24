"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { ArrowLeft, Upload, Pencil, Trash2, Plus } from "lucide-react";
import { ReplaceResumeModal } from "@/components/ReplaceResumeModal";
import { SectionInstructionBox } from "@/components/resume-edit/SectionInstructionBox";
import { EditableItemForm } from "@/components/resume-edit/EditableItemForm";

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
  const [showReplace, setShowReplace] = useState(false);
  const [editing, setEditing] = useState<{ section: string; action: "add" | "edit"; itemIndex?: number; group?: string; skill?: string } | null>(null);
  const [drafted, setDrafted] = useState<unknown[] | unknown | null>(null);

  const TITLE_FIELD: Record<string, string> = { experience: "title", education: "degree", certifications: "name" };
  const SECTION_TITLES: Record<string, string> = { experience: "Experience", education: "Education", certifications: "Certifications" };

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
    await api.applyResumeSection(slug, section, {
      action: editing.action,
      item_index: editing.itemIndex,
      group: editing.group,
      skill: editing.skill,
      item: drafted,
    });
    setEditing(null);
    setDrafted(null);
    loadResume();
  }

  async function handleDelete(section: string, itemIndex: number) {
    if (!slug) return;
    if (!confirm("Delete this entry?")) return;
    await api.applyResumeSection(slug, section, { action: "delete", item_index: itemIndex });
    loadResume();
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
                  <button onClick={() => { setEditing({ section, action: "edit", itemIndex: i }); setDrafted(null); }} className="text-gray-400 hover:text-gray-700">
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
                      onCancel={() => setEditing(null)}
                    />
                  </div>
                ) : (
                  <div className="mt-2 space-y-2">
                    <EditableItemForm value={drafted as Record<string, unknown>} onChange={setDrafted} />
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
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
                onCancel={() => setEditing(null)}
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              {(drafted as Record<string, unknown>[]).map((draftItem, i) => (
                <div key={i} className="bg-surface rounded-lg p-3">
                  <EditableItemForm
                    value={draftItem}
                    onChange={next => setDrafted((drafted as Record<string, unknown>[]).map((d, j) => (j === i ? next : d)))}
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleConfirm(section)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section, action: "add" }); setDrafted(null); }}
            className="mt-3 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
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

      {renderListObjectSection("experience")}
      {renderListObjectSection("education")}
      {renderListObjectSection("certifications")}

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
