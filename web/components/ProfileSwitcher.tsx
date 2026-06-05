"use client";
import { useEffect, useState, useCallback } from "react";
import { ChevronDown, Plus, Trash2, User } from "lucide-react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Profile } from "@/lib/types";
import { AddProfileModal } from "./AddProfileModal";

const STORAGE_KEY = "resume_active_profile";

export function ProfileSwitcher() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [active, setActive] = useState<Profile | null>(null);
  const [open, setOpen] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    const list = await api.listProfiles();
    setProfiles(list);
    const savedSlug = localStorage.getItem(STORAGE_KEY);
    const found = list.find(p => p.slug === savedSlug) ?? list[0] ?? null;
    setActive(found);
    if (found) localStorage.setItem(STORAGE_KEY, found.slug);
  }, []);

  useEffect(() => { load(); }, [load]);

  function switchTo(p: Profile) {
    setActive(p);
    localStorage.setItem(STORAGE_KEY, p.slug);
    setOpen(false);
    window.dispatchEvent(new CustomEvent("profile-changed", { detail: p.slug }));
  }

  async function handleDelete(p: Profile, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm(`Delete profile "${p.name}"? This cannot be undone.`)) return;
    setDeleting(p.slug);
    try {
      await api.deleteProfile(p.slug);
      if (active?.slug === p.slug) localStorage.removeItem(STORAGE_KEY);
      await load();
    } finally {
      setDeleting(null);
    }
  }

  const initials = active?.name?.slice(0, 1).toUpperCase() ?? "?";

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 rounded-full border border-warm-border bg-cream px-3 py-1.5 hover:bg-white transition-colors"
        >
          <span className="w-6 h-6 rounded-full bg-accent flex items-center justify-center text-xs font-bold text-white shrink-0">
            {initials}
          </span>
          <span className="text-sm font-medium text-navy max-w-24 truncate">{active?.name ?? "No profile"}</span>
          <ChevronDown size={13} className="text-muted" />
        </button>

        {open && (
          <div className="absolute top-full right-0 mt-2 w-52 bg-white rounded-2xl shadow-lg border border-warm-border py-1.5 z-50">
            {profiles.map(p => (
              <div key={p.slug} className="flex items-center group">
                <button
                  onClick={() => switchTo(p)}
                  className={`flex items-center gap-2 flex-1 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                    active?.slug === p.slug ? "text-accent font-medium" : "text-navy"
                  }`}
                >
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    active?.slug === p.slug ? "bg-accent-light text-accent" : "bg-cream text-muted"
                  }`}>
                    {p.name.slice(0, 1).toUpperCase()}
                  </span>
                  {p.name}
                </button>
                <button
                  onClick={e => handleDelete(p, e)}
                  disabled={deleting === p.slug}
                  className="pr-3 text-warm-border hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-30"
                  title={`Delete ${p.name}`}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}

            <div className="border-t border-warm-border mt-1 pt-1 mx-1">
              {active && (
                <Link
                  href={`/profile/${active.slug}`}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-xs text-muted hover:bg-cream hover:text-navy rounded-xl transition-colors"
                >
                  <User size={12} />
                  View Resume Data
                </Link>
              )}
              <button
                onClick={() => { setShowAdd(true); setOpen(false); }}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-accent font-medium hover:bg-accent-light rounded-xl transition-colors"
              >
                <Plus size={12} />
                Add Profile
              </button>
            </div>
          </div>
        )}
      </div>

      {showAdd && (
        <AddProfileModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); load(); }}
        />
      )}
    </>
  );
}
