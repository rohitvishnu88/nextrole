"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { ChevronDown, Plus, Trash2, User } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { Profile } from "@/lib/types";
import { AddProfileModal } from "./AddProfileModal";
import { ConfirmDialog } from "./ConfirmDialog";
import { ACTIVE_PROFILE_STORAGE_KEY, ACTIVE_PROFILE_EVENT, setActiveProfile } from "@/lib/useActiveProfile";

// Matches /profile/{slug} or /profile/{slug}/edit, capturing the /edit suffix if present.
const PROFILE_PATH_RE = /^\/profile\/[^/]+(\/edit)?$/;

export function ProfileSwitcher() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [active, setActive] = useState<Profile | null>(null);
  const [open, setOpen] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<Profile | null>(null);
  const profilesRef = useRef<Profile[]>([]);
  const pathname = usePathname();
  const router = useRouter();

  const load = useCallback(async () => {
    const list = await api.listProfiles();
    profilesRef.current = list;
    setProfiles(list);
    const savedSlug = localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY);
    const found = list.find(p => p.slug === savedSlug) ?? list[0] ?? null;
    setActive(found);
    if (found) localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, found.slug);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    function handleChanged(e: Event) {
      const slug = (e as CustomEvent<string>).detail;
      const found = profilesRef.current.find(p => p.slug === slug) ?? null;
      if (found) setActive(found);
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, handleChanged);
    return () => window.removeEventListener(ACTIVE_PROFILE_EVENT, handleChanged);
  }, []);

  function switchTo(p: Profile) {
    setActive(p);
    setOpen(false);
    setActiveProfile(p.slug);

    // If currently viewing a profile-scoped page, follow the switch to the
    // same page for the newly selected profile instead of leaving the URL
    // pointing at the old one.
    const match = pathname.match(PROFILE_PATH_RE);
    if (match) {
      router.push(`/profile/${p.slug}${match[1] ?? ""}`);
    }
  }

  function handleDelete(p: Profile, e: React.MouseEvent) {
    e.stopPropagation();
    setConfirmingDelete(p);
  }

  async function doDelete(p: Profile) {
    setConfirmingDelete(null);
    setDeleting(p.slug);
    try {
      await api.deleteProfile(p.slug);
      if (active?.slug === p.slug) localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY);
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
          className="flex items-center gap-2 border-[1.5px] border-ink bg-paper px-2 py-1 hover:bg-surface transition-colors"
        >
          <span className="w-6 h-6 bg-ink flex items-center justify-center text-xs font-bold text-paper shrink-0">
            {initials}
          </span>
          <span className="text-sm font-medium text-ink max-w-24 truncate">{active?.name ?? "No profile"}</span>
          <ChevronDown size={13} className="text-ink-muted" />
        </button>

        {open && (
          <div className="absolute top-full right-0 mt-2 w-52 bg-surface border-[1.5px] border-ink py-1.5 z-50">
            {profiles.map(p => (
              <div key={p.slug} className="flex items-center group">
                <button
                  onClick={() => switchTo(p)}
                  className={`flex items-center gap-2 flex-1 px-3 py-2 text-sm transition-colors hover:bg-paper ${
 active?.slug === p.slug ? "text-ink font-bold" : "text-ink"
                  }`}
                >
                  <span className={`w-6 h-6 flex items-center justify-center text-xs font-bold ${
                    active?.slug === p.slug ? "bg-ink text-paper" : "bg-paper text-ink-muted"
                  }`}>
                    {p.name.slice(0, 1).toUpperCase()}
                  </span>
                  {p.name}
                </button>
                <button
                  onClick={e => handleDelete(p, e)}
                  disabled={deleting === p.slug}
                  className="pr-3 text-rule-soft hover:text-ink transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-30"
                  title={`Delete ${p.name}`}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}

            <div className="border-t border-rule-soft mt-1 pt-1 mx-1">
              {active && (
                <Link
                  href={`/profile/${active.slug}`}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-xs text-ink-muted hover:bg-paper hover:text-ink transition-colors"
                >
                  <User size={12} />
                  view resume data
                </Link>
              )}
              <button
                onClick={() => { setShowAdd(true); setOpen(false); }}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-ink font-medium hover:bg-paper transition-colors"
              >
                <Plus size={12} />
                add profile
              </button>
            </div>
          </div>
        )}
      </div>

      {showAdd && (
        <AddProfileModal
          onClose={() => setShowAdd(false)}
          onCreated={(slug) => {
            localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, slug);
            setShowAdd(false);
            load().then(() => {
              setActiveProfile(slug);
            });
          }}
        />
      )}

      {confirmingDelete && (
        <ConfirmDialog
          message={`Delete profile "${confirmingDelete.name}"? This cannot be undone.`}
          onConfirm={() => doDelete(confirmingDelete)}
          onCancel={() => setConfirmingDelete(null)}
        />
      )}
    </>
  );
}
