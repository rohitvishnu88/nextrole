"use client";
import { useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { useMe } from "./AuthGate";

export function AccountMenu() {
  const me = useMe();
  const [open, setOpen] = useState(false);
  if (!me) return null;

  async function signOut() {
    await api.logout().catch(() => {});
    window.location.href = "/";
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="account"
        className="w-8 h-8 bg-ink text-paper text-xs font-bold flex items-center justify-center"
      >
        {(me.name || me.email).slice(0, 1).toUpperCase()}
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-2 w-56 bg-surface border-[1.5px] border-ink py-1 z-50">
          <p className="px-3 py-2 text-xs text-ink-muted truncate border-b border-rule-soft">{me.email}</p>
          <Link href="/usage" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm hover:bg-paper">
            usage
          </Link>
          <button onClick={signOut} className="block w-full text-left px-3 py-2 text-sm hover:bg-paper">
            sign out
          </button>
        </div>
      )}
    </div>
  );
}
