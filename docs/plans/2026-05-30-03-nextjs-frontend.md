# Next.js Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app with a profile switcher, resume tailoring UI, and a job application tracker (table + kanban views) that communicates with the FastAPI backend.

**Architecture:** Next.js 14 App Router with TypeScript and Tailwind CSS. A single `lib/api.ts` client handles all backend calls. Pages: Dashboard (`/`), Tailor (`/tailor`), Applications (`/applications`), Profile view (`/profile/[slug]`). A sidebar layout wraps all pages and houses the profile switcher. Drag-and-drop on the kanban board via `dnd-kit`.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, dnd-kit (`@dnd-kit/core`, `@dnd-kit/sortable`), lucide-react (icons).

**Prerequisite:** Plan 02 (Backend API) must be complete and the FastAPI server must be running.

**Note on testing:** This plan uses TypeScript type checks (`tsc --noEmit`) as the primary correctness gate for each task. Visual correctness is verified by running the dev server and checking the UI in a browser. There are no browser-based automated tests.

---

## Colour Tokens (referenced throughout)

| Token | Value | Usage |
|---|---|---|
| `navy` | `#1a2744` | Sidebar background, header |
| `accent` | `#5b6ef5` | CTAs, active states, links |
| `surface` | `#f5f6fa` | Card backgrounds |
| `text-main` | `#111827` | Body text |
| `text-muted` | `#6b7280` | Secondary text |

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| CREATE | `web/` | Next.js app root |
| CREATE | `web/package.json` | Dependencies |
| CREATE | `web/tsconfig.json` | TypeScript config |
| CREATE | `web/tailwind.config.ts` | Tailwind with custom colours |
| CREATE | `web/next.config.ts` | API proxy to FastAPI |
| CREATE | `web/app/globals.css` | Base styles + Tailwind directives |
| CREATE | `web/app/layout.tsx` | Root layout with sidebar |
| CREATE | `web/app/page.tsx` | Dashboard |
| CREATE | `web/app/tailor/page.tsx` | Tailor a resume |
| CREATE | `web/app/applications/page.tsx` | Application tracker (table + kanban) |
| CREATE | `web/app/profile/[slug]/page.tsx` | Profile resume data view |
| CREATE | `web/lib/api.ts` | Typed API client |
| CREATE | `web/lib/types.ts` | Shared TypeScript types |
| CREATE | `web/components/Sidebar.tsx` | Left nav + profile switcher |
| CREATE | `web/components/ProfileSwitcher.tsx` | Profile dropdown + Add Profile modal |
| CREATE | `web/components/AddProfileModal.tsx` | Upload resume, parse, confirm |
| CREATE | `web/components/ApplicationTable.tsx` | Sortable table view |
| CREATE | `web/components/ApplicationKanban.tsx` | Drag-and-drop kanban board |
| CREATE | `web/components/StatusBadge.tsx` | Coloured status pill |
| CREATE | `web/components/AddApplicationModal.tsx` | New application form |

---

### Task 1: Scaffold the Next.js app

**Files:**
- Create all `web/` config files

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "resume-builder-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18",
    "react-dom": "^18",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "lucide-react": "^0.378.0"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10",
    "postcss": "^8",
    "tailwindcss": "^3.4",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "es2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `web/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#1a2744",
        accent: "#5b6ef5",
        surface: "#f5f6fa",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: Create `web/postcss.config.js`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Create `web/next.config.ts`**

This proxies `/api/*` requests to FastAPI so the frontend never has CORS issues in dev:

```typescript
import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default config;
```

- [ ] **Step 6: Create `web/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-white text-gray-900;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

- [ ] **Step 7: Install dependencies**

```bash
cd /Users/rohit/resume-builder/web
npm install
```

Expected: `node_modules/` populated, no errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/
git commit -m "chore: scaffold Next.js app with Tailwind, dnd-kit, TypeScript config"
```

---

### Task 2: Define shared types and API client

**Files:**
- Create: `web/lib/types.ts`
- Create: `web/lib/api.ts`

- [ ] **Step 1: Create `web/lib/types.ts`**

```typescript
export interface Profile {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "interview"
  | "offer"
  | "rejected";

export interface Application {
  id: string;
  profile_id: string;
  job_title: string;
  company: string;
  location: string | null;
  url: string | null;
  status: ApplicationStatus;
  applied_date: string | null;
  notes: string | null;
  resume_file: string | null;
  cover_letter_file: string | null;
  created_at: string;
  updated_at: string;
}

export interface TailorJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  message: string;
  pdf_file?: string;
  cover_letter_file?: string;
  url?: string;
}
```

- [ ] **Step 2: Create `web/lib/api.ts`**

```typescript
import type { Application, ApplicationStatus, Profile, TailorJob } from "./types";

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

// Profiles
export const listProfiles = () => req<Profile[]>("/profiles");
export const createProfile = (name: string, slug: string) =>
  req<Profile>("/profiles", {
    method: "POST",
    body: JSON.stringify({ name, slug }),
  });
export const deleteProfile = (slug: string) =>
  req<{ deleted: string }>(`/profiles/${slug}`, { method: "DELETE" });

export async function parseResume(slug: string, file: File): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/profiles/${slug}/resume/parse`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Parse failed: ${res.statusText}`);
  return res.json();
}

export const confirmResume = (slug: string) =>
  req<{ saved: boolean; profile: string }>(`/profiles/${slug}/resume/confirm`, {
    method: "POST",
  });

export const getResume = (slug: string) =>
  req<Record<string, unknown>>(`/profiles/${slug}/resume`);

// Applications
export const listApplications = (profile: string) =>
  req<Application[]>(`/applications?profile=${profile}`);

export const createApplication = (data: {
  profile_id: string;
  job_title: string;
  company: string;
  location?: string;
  url?: string;
  status?: ApplicationStatus;
  applied_date?: string;
  notes?: string;
  resume_file?: string;
  cover_letter_file?: string;
}) => req<Application>("/applications", { method: "POST", body: JSON.stringify(data) });

export const updateApplication = (id: string, fields: Partial<Application>) =>
  req<{ updated: boolean }>(`/applications/${id}`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });

export const deleteApplication = (id: string) =>
  req<{ deleted: string }>(`/applications/${id}`, { method: "DELETE" });

// Tailor
export const startTailor = (profileSlug: string, url?: string, jdText?: string) =>
  req<{ job_id: string }>("/tailor", {
    method: "POST",
    body: JSON.stringify({ profile_slug: profileSlug, url, jd_text: jdText }),
  });

export const getTailorStatus = (jobId: string) =>
  req<TailorJob>(`/tailor/${jobId}`);
```

- [ ] **Step 3: Create `web/lib/useActiveProfile.ts`**

```typescript
"use client";
import { useEffect, useState } from "react";

export function useActiveProfile(): string {
  const [slug, setSlug] = useState("");
  useEffect(() => {
    setSlug(localStorage.getItem("resume_active_profile") ?? "");
    const handler = (e: Event) => setSlug((e as CustomEvent<string>).detail);
    window.addEventListener("profile-changed", handler);
    return () => window.removeEventListener("profile-changed", handler);
  }, []);
  return slug;
}
```

- [ ] **Step 4: Type check**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/lib/
git commit -m "feat: add shared TypeScript types, API client, and useActiveProfile hook"
```

---

### Task 3: Sidebar layout and root structure

**Files:**
- Create: `web/components/StatusBadge.tsx`
- Create: `web/components/Sidebar.tsx`
- Create: `web/app/layout.tsx`

- [ ] **Step 1: Create `web/components/StatusBadge.tsx`**

```tsx
import type { ApplicationStatus } from "@/lib/types";

const colours: Record<ApplicationStatus, string> = {
  saved: "bg-gray-100 text-gray-600",
  applied: "bg-blue-100 text-blue-700",
  interview: "bg-yellow-100 text-yellow-700",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-600",
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colours[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
```

- [ ] **Step 2: Create `web/components/Sidebar.tsx`**

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, Briefcase } from "lucide-react";
import { ProfileSwitcher } from "./ProfileSwitcher";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tailor", label: "Tailor Resume", icon: FileText },
  { href: "/applications", label: "Applications", icon: Briefcase },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 min-h-screen bg-navy text-white flex flex-col">
      <div className="px-4 py-5 border-b border-white/10">
        <ProfileSwitcher />
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === href
                ? "bg-accent text-white"
                : "text-white/70 hover:bg-white/10 hover:text-white"
            }`}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: Create placeholder `web/components/ProfileSwitcher.tsx`** (full version in Task 4)

```tsx
"use client";
export function ProfileSwitcher() {
  return <div className="text-white text-sm font-medium">Profile</div>;
}
```

- [ ] **Step 4: Create `web/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Resume Builder",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-white">
        <Sidebar />
        <main className="flex-1 p-8 overflow-y-auto">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Create placeholder `web/app/page.tsx`**

```tsx
export default function Dashboard() {
  return <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>;
}
```

- [ ] **Step 6: Type check and start dev server**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
npm run dev
```

Open `http://localhost:3000`. Expected: Navy sidebar on left, "Dashboard" heading on right.

Stop with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/app/ web/components/
git commit -m "feat: add Next.js layout, sidebar, and placeholder pages"
```

---

### Task 4: Profile Switcher and Add Profile modal

**Files:**
- Create (replace): `web/components/ProfileSwitcher.tsx`
- Create: `web/components/AddProfileModal.tsx`

- [ ] **Step 1: Create `web/components/AddProfileModal.tsx`**

```tsx
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
      await api.createProfile(name, slug);
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
      await api.confirmResume(slug);
      setStep("done");
      onCreated();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save resume");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 relative">
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
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
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
            <div className="bg-surface rounded-lg p-4 max-h-72 overflow-y-auto text-xs space-y-2">
              <p><span className="font-medium">Name:</span> {String(parsed.name ?? "")}</p>
              <p><span className="font-medium">Summary:</span> {String(parsed.summary ?? "").slice(0, 120)}...</p>
              <p><span className="font-medium">Experience entries:</span> {Array.isArray(parsed.experience) ? parsed.experience.length : 0}</p>
              <p><span className="font-medium">Skills categories:</span> {typeof parsed.skills === "object" && parsed.skills ? Object.keys(parsed.skills).join(", ") : ""}</p>
              <p><span className="font-medium">Education entries:</span> {Array.isArray(parsed.education) ? parsed.education.length : 0}</p>
              <p><span className="font-medium">Certifications:</span> {Array.isArray(parsed.certifications) ? parsed.certifications.length : 0}</p>
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
```

- [ ] **Step 2: Replace `web/components/ProfileSwitcher.tsx` with the full version**

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import { ChevronDown, Plus, User } from "lucide-react";
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

  const initials = active?.name?.slice(0, 1).toUpperCase() ?? "?";

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 w-full rounded-lg px-2 py-1.5 hover:bg-white/10 transition-colors"
        >
          <span className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-xs font-bold text-white shrink-0">
            {initials}
          </span>
          <span className="flex-1 text-left text-sm font-medium truncate">{active?.name ?? "No profile"}</span>
          <ChevronDown size={14} className="text-white/50" />
        </button>

        {open && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-lg py-1 z-50">
            {profiles.map(p => (
              <button
                key={p.slug}
                onClick={() => switchTo(p)}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-surface transition-colors ${active?.slug === p.slug ? "text-accent font-medium" : "text-gray-700"}`}
              >
                <User size={14} />
                {p.name}
              </button>
            ))}
            <div className="border-t border-gray-100 mt-1 pt-1">
              {active && (
                <Link
                  href={`/profile/${active.slug}`}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 w-full px-3 py-2 text-xs text-gray-500 hover:bg-surface"
                >
                  View Resume Data
                </Link>
              )}
              <button
                onClick={() => { setShowAdd(true); setOpen(false); }}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-accent hover:bg-surface"
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
```

- [ ] **Step 3: Type check**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
```

Expected: No errors.

- [ ] **Step 4: Start dev server and verify**

```bash
npm run dev
```

Open `http://localhost:3000`. Click the profile area in the sidebar — dropdown should open with "Add Profile". The Add Profile modal should open when clicked.

Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/components/
git commit -m "feat: add ProfileSwitcher and AddProfileModal with parse/confirm flow"
```

---

### Task 5: Dashboard page

**Files:**
- Create (replace): `web/app/page.tsx`

- [ ] **Step 1: Replace `web/app/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { Wand2 } from "lucide-react";

export default function Dashboard() {
  const profile = useActiveProfile();
  const [apps, setApps] = useState<Application[]>([]);

  useEffect(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
  }, [profile]);

  const counts = {
    total: apps.length,
    interview: apps.filter(a => a.status === "interview").length,
    offer: apps.filter(a => a.status === "offer").length,
  };

  const recent = apps.slice(0, 5);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "Total Applications", value: counts.total },
          { label: "Interviews", value: counts.interview },
          { label: "Offers", value: counts.offer },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface rounded-xl p-5">
            <p className="text-3xl font-bold text-navy">{value}</p>
            <p className="text-sm text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      <Link
        href="/tailor"
        className="inline-flex items-center gap-2 bg-accent text-white rounded-lg px-5 py-2.5 text-sm font-medium hover:bg-accent/90 transition-colors mb-8"
      >
        <Wand2 size={16} />
        Tailor a Resume
      </Link>

      {recent.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-gray-800 mb-3">Recent Applications</h2>
          <div className="space-y-2">
            {recent.map(app => (
              <div key={app.id} className="flex items-center justify-between bg-surface rounded-lg px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{app.job_title}</p>
                  <p className="text-xs text-gray-500">{app.company}{app.location ? ` · ${app.location}` : ""}</p>
                </div>
                <StatusBadge status={app.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      {profile && apps.length === 0 && (
        <p className="text-sm text-gray-400">No applications yet. Tailor a resume or add one manually.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type check and verify**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
npm run dev
```

Open `http://localhost:3000`. Expected: Stats bar (0/0/0 until you add applications), "Tailor a Resume" CTA button.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/app/page.tsx
git commit -m "feat: add Dashboard page with stats and recent applications"
```

---

### Task 6: Tailor page

**Files:**
- Create: `web/app/tailor/page.tsx`

- [ ] **Step 1: Create `web/app/tailor/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { TailorJob } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { AddApplicationModal } from "@/components/AddApplicationModal";

export default function TailorPage() {
  const profile = useActiveProfile();
  const [mode, setMode] = useState<"url" | "jd">("url");
  const [input, setInput] = useState("");
  const [job, setJob] = useState<TailorJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [showAddToTracker, setShowAddToTracker] = useState(false);

  async function handleSubmit() {
    if (!input.trim() || !profile) return;
    setError("");
    setJob(null);
    try {
      const res = await api.startTailor(
        profile,
        mode === "url" ? input.trim() : undefined,
        mode === "jd" ? input.trim() : undefined,
      );
      setJob({ job_id: res.job_id, status: "running", message: "Starting..." });
      setPolling(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start");
    }
  }

  useEffect(() => {
    if (!polling || !job) return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getTailorStatus(job.job_id);
        setJob(status);
        if (status.status !== "running") {
          setPolling(false);
        }
      } catch {
        setPolling(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, job]);

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Tailor a Resume</h1>

      {!profile && (
        <p className="text-sm text-yellow-600 bg-yellow-50 rounded-lg px-4 py-3 mb-4">
          Select or create a profile first.
        </p>
      )}

      <div className="bg-surface rounded-xl p-6 mb-6">
        <div className="flex gap-2 mb-4">
          {(["url", "jd"] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setInput(""); }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${mode === m ? "bg-accent text-white" : "bg-white text-gray-600 border border-gray-200 hover:border-accent"}`}
            >
              {m === "url" ? "Job URL" : "Paste JD"}
            </button>
          ))}
        </div>

        {mode === "url" ? (
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="https://linkedin.com/jobs/view/..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
        ) : (
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-none"
          />
        )}

        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={!input.trim() || !profile || polling}
          className="mt-4 bg-accent text-white rounded-lg px-5 py-2 text-sm font-medium disabled:opacity-50 hover:bg-accent/90 transition-colors"
        >
          {polling ? "Working..." : "Tailor Resume"}
        </button>
      </div>

      {job && (
        <div className="bg-surface rounded-xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <span className={`w-2 h-2 rounded-full ${job.status === "running" ? "bg-yellow-400 animate-pulse" : job.status === "completed" ? "bg-green-500" : "bg-red-400"}`} />
            <p className="text-sm font-medium text-gray-700">{job.message}</p>
          </div>

          {job.status === "completed" && (
            <div className="flex flex-wrap gap-2">
              <a
                href={`/api/tailor/${job.job_id}/pdf`}
                download
                className="inline-flex items-center gap-2 bg-navy text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-navy/90 transition-colors"
              >
                Download PDF
              </a>
              <a
                href={`/api/tailor/${job.job_id}/cover-letter`}
                download
                className="inline-flex items-center gap-2 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Download Cover Letter
              </a>
              <button
                onClick={() => setShowAddToTracker(true)}
                className="inline-flex items-center gap-2 border border-accent text-accent rounded-lg px-4 py-2 text-sm font-medium hover:bg-accent/5 transition-colors"
              >
                + Add to Tracker
              </button>
            </div>
          )}
      </div>
      )}

      {showAddToTracker && profile && (
        <AddApplicationModal
          profileId={profile}
          prefillUrl={job?.url}
          onClose={() => setShowAddToTracker(false)}
          onCreated={() => setShowAddToTracker(false)}
        />
      )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type check and verify**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
npm run dev
```

Open `http://localhost:3000/tailor`. Switch between "Job URL" and "Paste JD" tabs. Make sure the FastAPI server is running (`uvicorn a2a.server:app --port 8000`) and paste a job URL to test the full flow.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/app/tailor/
git commit -m "feat: add Tailor page with URL/JD modes and progress polling"
```

---

### Task 7: Application Tracker — table and kanban

**Files:**
- Create: `web/components/StatusBadge.tsx` (already done in Task 3)
- Create: `web/components/ApplicationTable.tsx`
- Create: `web/components/ApplicationKanban.tsx`
- Create: `web/components/AddApplicationModal.tsx`
- Create: `web/app/applications/page.tsx`

- [ ] **Step 1: Create `web/components/AddApplicationModal.tsx`**

```tsx
"use client";
import { useState } from "react";
import { X } from "lucide-react";
import type { ApplicationStatus } from "@/lib/types";
import * as api from "@/lib/api";

interface Props {
  profileId: string;
  prefillUrl?: string;
  onClose: () => void;
  onCreated: () => void;
}

const STATUSES: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"];

export function AddApplicationModal({ profileId, prefillUrl, onClose, onCreated }: Props) {
  const [form, setForm] = useState({
    job_title: "", company: "", location: "", url: prefillUrl ?? "", status: "applied" as ApplicationStatus, notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!form.job_title || !form.company) return;
    setLoading(true);
    setError("");
    try {
      await api.createApplication({ ...form, profile_id: profileId, location: form.location || undefined, url: form.url || undefined, notes: form.notes || undefined });
      onCreated();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Application</h2>
        <div className="space-y-3">
          {(["job_title", "company", "location", "url"] as const).map(field => (
            <input key={field} value={form[field]} onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
              placeholder={field === "job_title" ? "Job Title *" : field.charAt(0).toUpperCase() + field.slice(1)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          ))}
          <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value as ApplicationStatus }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
            {STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select>
          <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            placeholder="Notes (optional)" rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-none" />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button onClick={handleSubmit} disabled={!form.job_title || !form.company || loading}
            className="w-full bg-accent text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50 hover:bg-accent/90 transition-colors">
            {loading ? "Saving..." : "Add Application"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `web/components/ApplicationTable.tsx`**

```tsx
"use client";
import { useState } from "react";
import type { Application } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { Trash2 } from "lucide-react";
import * as api from "@/lib/api";

interface Props {
  apps: Application[];
  onRefresh: () => void;
}

type SortKey = "company" | "job_title" | "status" | "applied_date";

export function ApplicationTable({ apps, onRefresh }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("applied_date");
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(true); }
  }

  const sorted = [...apps].sort((a, b) => {
    const av = a[sortKey] ?? "";
    const bv = b[sortKey] ?? "";
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const Th = ({ label, k }: { label: string; k: SortKey }) => (
    <th onClick={() => toggleSort(k)} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-800 select-none">
      {label} {sortKey === k ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  async function handleDelete(id: string) {
    await api.deleteApplication(id);
    onRefresh();
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead className="bg-surface">
          <tr>
            <Th label="Company" k="company" />
            <Th label="Role" k="job_title" />
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Location</th>
            <Th label="Status" k="status" />
            <Th label="Applied" k="applied_date" />
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.map(app => (
            <tr key={app.id} className="hover:bg-surface/50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{app.company}</td>
              <td className="px-4 py-3 text-gray-700">{app.job_title}</td>
              <td className="px-4 py-3 text-gray-500">{app.location ?? "—"}</td>
              <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
              <td className="px-4 py-3 text-gray-500">{app.applied_date ?? "—"}</td>
              <td className="px-4 py-3 text-right">
                <button onClick={() => handleDelete(app.id)} className="text-gray-300 hover:text-red-400 transition-colors">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">No applications yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Create `web/components/ApplicationKanban.tsx`**

```tsx
"use client";
import { useState } from "react";
import {
  DndContext, DragEndEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Application, ApplicationStatus } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import * as api from "@/lib/api";

const COLUMNS: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"];
const COL_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved", applied: "Applied", interview: "Interview", offer: "Offer", rejected: "Rejected",
};

function KanbanCard({ app, isDragging }: { app: Application; isDragging?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: app.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}
      className="bg-white rounded-lg px-3 py-2.5 shadow-sm border border-gray-100 cursor-grab active:cursor-grabbing">
      <p className="text-sm font-medium text-gray-900 truncate">{app.company}</p>
      <p className="text-xs text-gray-500 truncate mb-1.5">{app.job_title}</p>
      {app.applied_date && <p className="text-xs text-gray-400">{app.applied_date}</p>}
    </div>
  );
}

interface Props { apps: Application[]; onRefresh: () => void; }

export function ApplicationKanban({ apps, onRefresh }: Props) {
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const byStatus = (status: ApplicationStatus) => apps.filter(a => a.status === status);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveApp(null);
    if (!over) return;
    const newStatus = over.id as ApplicationStatus;
    if (!COLUMNS.includes(newStatus)) return;
    const app = apps.find(a => a.id === active.id);
    if (!app || app.status === newStatus) return;
    await api.updateApplication(app.id, { status: newStatus });
    onRefresh();
  }

  function handleDragStart(event: DragStartEvent) {
    const app = apps.find(a => a.id === event.active.id);
    setActiveApp(app ?? null);
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map(col => {
          const colApps = byStatus(col);
          return (
            <div key={col} className="flex-shrink-0 w-52">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">{COL_LABELS[col]}</span>
                <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">{colApps.length}</span>
              </div>
              <SortableContext id={col} items={colApps.map(a => a.id)} strategy={verticalListSortingStrategy}>
                <div className="min-h-24 bg-surface rounded-xl p-2 space-y-2" data-droppable-id={col}
                  id={col}>
                  {colApps.map(app => (
                    <KanbanCard key={app.id} app={app} isDragging={activeApp?.id === app.id} />
                  ))}
                </div>
              </SortableContext>
            </div>
          );
        })}
      </div>
      <DragOverlay>
        {activeApp && (
          <div className="bg-white rounded-lg px-3 py-2.5 shadow-lg border border-accent/30 w-52">
            <p className="text-sm font-medium text-gray-900">{activeApp.company}</p>
            <p className="text-xs text-gray-500">{activeApp.job_title}</p>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
```

- [ ] **Step 4: Create `web/app/applications/page.tsx`**

```tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";
import { ApplicationTable } from "@/components/ApplicationTable";
import { ApplicationKanban } from "@/components/ApplicationKanban";
import { AddApplicationModal } from "@/components/AddApplicationModal";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { LayoutGrid, List, Plus } from "lucide-react";

export default function ApplicationsPage() {
  const profile = useActiveProfile();
  const [apps, setApps] = useState<Application[]>([]);
  const [view, setView] = useState<"table" | "kanban">("table");
  const [showAdd, setShowAdd] = useState(false);

  const refresh = useCallback(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
  }, [profile]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
        <div className="flex items-center gap-2">
          <div className="flex bg-surface rounded-lg p-1 gap-1">
            <button onClick={() => setView("table")} className={`p-1.5 rounded ${view === "table" ? "bg-white shadow-sm" : "text-gray-400"}`}>
              <List size={16} />
            </button>
            <button onClick={() => setView("kanban")} className={`p-1.5 rounded ${view === "kanban" ? "bg-white shadow-sm" : "text-gray-400"}`}>
              <LayoutGrid size={16} />
            </button>
          </div>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 bg-accent text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-accent/90 transition-colors">
            <Plus size={14} />
            Add Application
          </button>
        </div>
      </div>

      {!profile && (
        <p className="text-sm text-yellow-600 bg-yellow-50 rounded-lg px-4 py-3">Select a profile first.</p>
      )}

      {profile && view === "table" && <ApplicationTable apps={apps} onRefresh={refresh} />}
      {profile && view === "kanban" && <ApplicationKanban apps={apps} onRefresh={refresh} />}

      {showAdd && profile && (
        <AddApplicationModal profileId={profile} onClose={() => setShowAdd(false)} onCreated={() => { setShowAdd(false); refresh(); }} />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Type check**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
```

Expected: No errors.

- [ ] **Step 6: Start dev server and verify**

```bash
npm run dev
```

Open `http://localhost:3000/applications`. Toggle between table and kanban. Add an application via the modal. Verify it appears in both views. Drag a card between columns in kanban view — it should persist (requires FastAPI running).

- [ ] **Step 7: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/
git commit -m "feat: add Applications page with sortable table and drag-and-drop kanban"
```

---

### Task 8: Profile view page

**Files:**
- Create: `web/app/profile/[slug]/page.tsx`

- [ ] **Step 1: Create `web/app/profile/[slug]/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import * as api from "@/lib/api";

interface Experience {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  description: string[];
}

interface ResumeData {
  name?: string;
  summary?: string;
  experience?: Experience[];
  skills?: Record<string, string[]>;
  education?: Array<{ degree?: string; school?: string }>;
  certifications?: Array<{ name?: string; issuer?: string }>;
}

export default function ProfilePage() {
  const { slug } = useParams<{ slug: string }>();
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!slug) return;
    api.getResume(slug)
      .then(data => setResume(data as ResumeData))
      .catch(() => setError("No resume data found for this profile."));
  }, [slug]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!resume) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{resume.name ?? slug} — Resume Data</h1>

      {resume.summary && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Summary</h2>
          <p className="text-sm text-gray-700 leading-relaxed">{resume.summary}</p>
        </section>
      )}

      {resume.experience && resume.experience.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Experience</h2>
          <div className="space-y-4">
            {resume.experience.map((exp, i) => (
              <div key={i} className="bg-surface rounded-lg p-4">
                <p className="text-sm font-semibold text-gray-900">{exp.title}</p>
                <p className="text-xs text-gray-500 mb-2">{exp.company} · {exp.start_date} – {exp.end_date}</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {(exp.description ?? []).slice(0, 3).map((b, j) => (
                    <li key={j} className="text-xs text-gray-600">{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {resume.skills && Object.keys(resume.skills).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Skills</h2>
          <div className="space-y-1">
            {Object.entries(resume.skills).map(([group, items]) => (
              <p key={group} className="text-sm text-gray-700">
                <span className="font-medium">{group}:</span> {items.join(", ")}
              </p>
            ))}
          </div>
        </section>
      )}

      {resume.education && resume.education.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Education</h2>
          {resume.education.map((e, i) => (
            <p key={i} className="text-sm text-gray-700">{e.degree} — {e.school}</p>
          ))}
        </section>
      )}

      {resume.certifications && resume.certifications.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Certifications</h2>
          {resume.certifications.map((c, i) => (
            <p key={i} className="text-sm text-gray-700">{c.name} — {c.issuer}</p>
          ))}
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type check and verify**

```bash
cd /Users/rohit/resume-builder/web
npm run typecheck
npm run dev
```

Open the profile switcher, click "View Resume Data" — it should navigate to `/profile/{slug}` and show the parsed resume in a clean card layout.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/app/profile/
git commit -m "feat: add Profile view page showing parsed resume_data.json"
```

---

## Final Verification Checklist

Run both services:

```bash
# Terminal 1 — FastAPI
uvicorn a2a.server:app --reload --port 8000

# Terminal 2 — Next.js
cd web && npm run dev
```

- [ ] `http://localhost:3000` — Dashboard loads with stats
- [ ] Profile switcher shows profiles from the API
- [ ] "Add Profile" modal: upload a PDF, see parsed preview, confirm → profile appears in switcher
- [ ] `/tailor` — paste a job URL, trigger tailoring, download PDF and cover letter
- [ ] `/applications` — add an application, see it in table and kanban
- [ ] Drag a kanban card to a new column — status updates persist
- [ ] Click "View Resume Data" from profile switcher — shows resume fields
- [ ] `npm run typecheck` in `web/` — no TypeScript errors
