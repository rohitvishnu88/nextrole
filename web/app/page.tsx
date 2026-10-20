"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Application, TailorHistoryEntry } from "@/lib/types";
import { StatusMarker } from "@/components/ui/StatusMarker";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { Wand2, Briefcase, ArrowRight, Trophy, Search, Download, FileText } from "lucide-react";

export default function Dashboard() {
  const profile = useActiveProfile();
  const [apps, setApps] = useState<Application[]>([]);
  const [tailorHistory, setTailorHistory] = useState<TailorHistoryEntry[]>([]);

  useEffect(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
  }, [profile]);

  useEffect(() => {
    if (!profile) return;
    api.getTailorHistory(profile).then(setTailorHistory).catch(() => {});
  }, [profile]);

  const counts = {
    total:     apps.length,
    interview: apps.filter(a => a.status === "interview").length,
    offer:     apps.filter(a => a.status === "offer").length,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">dashboard</h1>
        <p className="text-sm text-ink-muted mt-1">Your job search, at a glance</p>
      </div>

      {/* Hero gradient card */}
      <div className="relative overflow-hidden bg-ink p-8 text-paper">
        {/* Decorative circles */}
        <div className="absolute -top-16 -right-16 w-64 h-64 bg-ink opacity-20" />
        <div className="absolute -bottom-20 -right-4 w-48 h-48 bg-surface opacity-5" />
        <div className="absolute top-4 right-48 w-24 h-24 bg-ink opacity-10" />

        <div className="relative flex items-center justify-between">
          <div>
            <p className="text-paper/70 text-xs font-bold mb-2">AI-powered</p>
            <h2 className="text-2xl font-bold mb-2">ready to tailor your next resume?</h2>
            <p className="text-paper/70 text-sm max-w-xs leading-relaxed">
              Paste a job URL and Claude tailors your resume in under a minute — cover letter included.
            </p>
          </div>
          <div className="flex flex-col gap-2 shrink-0 ml-8">
            <Link
              href="/tailor"
              className="flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-5 py-2.5 text-sm font-bold transition-colors"
            >
              <Wand2 size={15} />
              tailor a resume
            </Link>
            <Link
              href="/search-brief"
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-paper px-5 py-2.5 text-sm font-medium transition-colors"
            >
              <Search size={14} />
              view search brief
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Applications", value: counts.total,     icon: Briefcase,  color: "bg-blue/10 text-ink" },
          { label: "Interviews",         value: counts.interview, icon: ArrowRight,  color: "bg-yellow/10 text-ink" },
          { label: "Offers",             value: counts.offer,     icon: Trophy,      color: "bg-blue/10 text-ink" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-surface border border-rule-soft p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-3xl font-bold text-ink">{value}</p>
                <p className="text-sm text-ink-muted mt-1">{label}</p>
              </div>
              <span className={`w-10 h-10 flex items-center justify-center ${color}`}>
                <Icon size={18} />
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-surface border border-rule-soft p-6 flex items-center justify-between">
        <div>
          <h2 className="font-bold text-ink">tailor your resume</h2>
          <p className="text-sm text-ink-muted mt-0.5">Paste a job URL or JD and get a tailored PDF + cover letter</p>
        </div>
        <Link
          href="/tailor"
          className="flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-5 py-2.5 text-sm font-bold transition-colors shrink-0 ml-4"
        >
          <Wand2 size={15} />
          tailor a resume
        </Link>
      </div>

      {apps.length > 0 && (
        <div className="bg-surface border border-rule-soft overflow-hidden">
          <div className="px-6 py-4 border-b border-rule-soft flex items-center justify-between">
            <h2 className="font-bold text-ink">recent applications</h2>
            <Link href="/applications" className="text-xs text-ink font-medium hover:underline">view all →</Link>
          </div>
          <div className="divide-y divide-rule-soft">
            {apps.slice(0, 5).map(app => (
              <div key={app.id} className="flex items-center justify-between px-6 py-3.5 hover:bg-paper transition-colors">
                <div>
                  <p className="text-sm font-medium text-ink">{app.job_title}</p>
                  <p className="text-xs text-ink-muted mt-0.5">{app.company}{app.location ? ` · ${app.location}` : ""}</p>
                </div>
                <StatusMarker status={app.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      {profile && apps.length === 0 && (
        <div className="bg-surface border border-rule-soft p-12 text-center">
          <p className="text-ink-muted text-sm">No applications yet.</p>
          <p className="text-ink-muted text-xs mt-1">Tailor a resume or add an application to get started.</p>
        </div>
      )}

      {tailorHistory.length > 0 && (
        <div className="bg-surface border border-rule-soft overflow-hidden">
          <div className="px-6 py-4 border-b border-rule-soft">
            <h2 className="font-bold text-ink">tailored resumes</h2>
          </div>
          <div className="divide-y divide-rule-soft">
            {tailorHistory.slice(0, 5).map(entry => (
              <div key={entry.id} className="flex items-center justify-between px-6 py-3.5 hover:bg-paper transition-colors gap-4">
                <div className="min-w-0">
                  {entry.job_url ? (
                    <a
                      href={entry.job_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-ink hover:underline truncate block"
                    >
                      {entry.job_url}
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-ink">Tailored resume</p>
                  )}
                  <p className="text-xs text-ink-muted mt-0.5">
                    {new Date(entry.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {entry.pdf_available && (
                    <a
                      href={`/api/tailor/history/${profile}/${entry.id}/pdf`}
                      download
                      title="Download PDF"
                      className="flex items-center gap-1 text-xs text-ink border border-rule-soft px-2.5 py-1.5 hover:bg-paper transition-colors"
                    >
                      <Download size={13} />
                      pdf
                    </a>
                  )}
                  {entry.cover_letter_available && (
                    <a
                      href={`/api/tailor/history/${profile}/${entry.id}/cover-letter`}
                      download
                      title="Download Cover Letter"
                      className="flex items-center gap-1 text-xs text-ink border border-rule-soft px-2.5 py-1.5 hover:bg-paper transition-colors"
                    >
                      <FileText size={13} />
                      cover letter
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
