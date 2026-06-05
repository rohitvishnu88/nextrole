"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { Wand2, Briefcase, ArrowRight, Trophy, Search } from "lucide-react";

export default function Dashboard() {
  const profile = useActiveProfile();
  const [apps, setApps] = useState<Application[]>([]);

  useEffect(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
  }, [profile]);

  const counts = {
    total:     apps.length,
    interview: apps.filter(a => a.status === "interview").length,
    offer:     apps.filter(a => a.status === "offer").length,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Dashboard</h1>
        <p className="text-sm text-muted mt-1">Your job search, at a glance</p>
      </div>

      {/* Hero gradient card */}
      <div className="relative overflow-hidden bg-navy rounded-3xl p-8 text-white">
        {/* Decorative circles */}
        <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full bg-accent opacity-20" />
        <div className="absolute -bottom-20 -right-4 w-48 h-48 rounded-full bg-white opacity-5" />
        <div className="absolute top-4 right-48 w-24 h-24 rounded-full bg-accent opacity-10" />

        <div className="relative flex items-center justify-between">
          <div>
            <p className="text-white/60 text-xs font-semibold uppercase tracking-widest mb-2">AI-powered</p>
            <h2 className="text-2xl font-bold mb-2">Ready to tailor your next resume?</h2>
            <p className="text-white/70 text-sm max-w-xs leading-relaxed">
              Paste a job URL and Claude tailors your resume in under a minute — cover letter included.
            </p>
          </div>
          <div className="flex flex-col gap-2 shrink-0 ml-8">
            <Link
              href="/tailor"
              className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
            >
              <Wand2 size={15} />
              Tailor a Resume
            </Link>
            <Link
              href="/search-brief"
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
            >
              <Search size={14} />
              View Search Brief
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Applications", value: counts.total,     icon: Briefcase,  color: "bg-accent-light text-accent" },
          { label: "Interviews",         value: counts.interview, icon: ArrowRight,  color: "bg-yellow-50 text-yellow-600" },
          { label: "Offers",             value: counts.offer,     icon: Trophy,      color: "bg-green-soft text-green-text" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-2xl border border-warm-border p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-3xl font-bold text-navy">{value}</p>
                <p className="text-sm text-muted mt-1">{label}</p>
              </div>
              <span className={`w-10 h-10 rounded-full flex items-center justify-center ${color}`}>
                <Icon size={18} />
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-warm-border p-6 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-navy">Tailor your resume</h2>
          <p className="text-sm text-muted mt-0.5">Paste a job URL or JD and get a tailored PDF + cover letter</p>
        </div>
        <Link
          href="/tailor"
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors shrink-0 ml-4"
        >
          <Wand2 size={15} />
          Tailor a Resume
        </Link>
      </div>

      {apps.length > 0 && (
        <div className="bg-white rounded-2xl border border-warm-border overflow-hidden">
          <div className="px-6 py-4 border-b border-warm-border flex items-center justify-between">
            <h2 className="font-semibold text-navy">Recent Applications</h2>
            <Link href="/applications" className="text-xs text-accent font-medium hover:underline">View all →</Link>
          </div>
          <div className="divide-y divide-warm-border">
            {apps.slice(0, 5).map(app => (
              <div key={app.id} className="flex items-center justify-between px-6 py-3.5 hover:bg-cream transition-colors">
                <div>
                  <p className="text-sm font-medium text-navy">{app.job_title}</p>
                  <p className="text-xs text-muted mt-0.5">{app.company}{app.location ? ` · ${app.location}` : ""}</p>
                </div>
                <StatusBadge status={app.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      {profile && apps.length === 0 && (
        <div className="bg-white rounded-2xl border border-warm-border p-12 text-center">
          <p className="text-muted text-sm">No applications yet.</p>
          <p className="text-muted text-xs mt-1">Tailor a resume or add an application to get started.</p>
        </div>
      )}
    </div>
  );
}
