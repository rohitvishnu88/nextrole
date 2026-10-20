"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Application, Profile, TailorHistoryEntry } from "@/lib/types";
import { StatusMarker } from "@/components/ui/StatusMarker";
import { PageCircle } from "@/components/ui/PageCircle";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { greeting } from "@/lib/greeting";
import { ArrowRight, Download, FileText, Wand2 } from "lucide-react";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="border-l-[3px] border-ink px-4 py-1">
      <p className="text-4xl font-bold leading-none">{value}</p>
      <p className="text-sm mt-1">{label}</p>
    </div>
  );
}

export default function Dashboard() {
  const profile = useActiveProfile();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [tailorHistory, setTailorHistory] = useState<TailorHistoryEntry[]>([]);

  useEffect(() => {
    api.listProfiles().then(setProfiles).catch(() => {});
  }, []);

  useEffect(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
    api.getTailorHistory(profile).then(setTailorHistory).catch(() => {});
  }, [profile]);

  const name = profiles.find(p => p.slug === profile)?.name;
  const active = apps.filter(a => a.status !== "rejected" && a.status !== "offer").length;
  const recent = [...apps].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);

  return (
    <div className="space-y-12">
      <section className="relative overflow-hidden -mx-6 px-6 -mt-10 pt-10 pb-2 min-h-[260px]">
        <PageCircle colour="blue" />
        <div className="relative space-y-4">
          <h1 className="text-5xl md:text-6xl font-bold leading-none">
            {greeting(new Date())}{name ? <>, {name}</> : null}
          </h1>
          <p className="text-base">
            {active} active application{active !== 1 ? "s" : ""}.
          </p>
          <Link
            href="/tailor"
            className="inline-flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-4 py-2 text-sm font-bold transition-colors"
          >
            <Wand2 size={14} />
            tailor a resume
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-3 gap-0">
        <Stat value={apps.length} label="applications" />
        <Stat value={apps.filter(a => a.status === "interview").length} label="interviews" />
        <Stat value={apps.filter(a => a.status === "offer").length} label="offers" />
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-xl font-bold">recent applications</h2>
          <Link href="/applications" className="flex items-center gap-1 text-sm hover:underline">
            view all <ArrowRight size={13} />
          </Link>
        </div>
        {recent.length === 0 ? (
          <p className="border-t-[1.5px] border-ink py-6 text-sm text-ink-muted">
            Tailor a resume or add an application to get started.
          </p>
        ) : (
          <div>
            {recent.map(app => (
              <div key={app.id} className="grid grid-cols-[2fr_1fr_120px] items-center gap-4 py-3 border-t-[1.5px] border-ink text-sm">
                <span>
                  <span className="font-medium">{app.job_title}</span>
                  <span className="text-ink-muted"> · {app.company}</span>
                </span>
                <span className="text-ink-muted">{formatDate(app.applied_date ?? app.updated_at)}</span>
                <StatusMarker status={app.status} />
              </div>
            ))}
          </div>
        )}
      </section>

      {tailorHistory.length > 0 && (
        <section>
          <h2 className="text-xl font-bold mb-2">tailored resumes</h2>
          {tailorHistory.slice(0, 5).map(entry => (
            <div key={entry.id} className="flex items-center justify-between gap-4 py-3 border-t border-rule-soft">
              <div className="min-w-0">
                {entry.job_url ? (
                  <a href={entry.job_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline truncate block">
                    {entry.job_url}
                  </a>
                ) : (
                  <p className="text-sm font-medium">tailored resume</p>
                )}
                <p className="text-xs text-ink-muted mt-0.5">
                  {new Date(entry.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {entry.pdf_available && (
                  <a
                    href={`/api/tailor/history/${profile}/${entry.id}/pdf`}
                    download
                    className="flex items-center gap-1 text-xs border-[1.5px] border-ink px-2.5 py-1.5 hover:bg-ink hover:text-paper transition-colors"
                  >
                    <Download size={13} />
                    pdf
                  </a>
                )}
                {entry.cover_letter_available && (
                  <a
                    href={`/api/tailor/history/${profile}/${entry.id}/cover-letter`}
                    download
                    className="flex items-center gap-1 text-xs border-[1.5px] border-ink px-2.5 py-1.5 hover:bg-ink hover:text-paper transition-colors"
                  >
                    <FileText size={13} />
                    cover letter
                  </a>
                )}
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
