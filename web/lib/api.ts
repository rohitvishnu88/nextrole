import type { Application, ApplicationStatus, Profile, TailorJob, TailoredResume, SearchBrief, Signal } from "./types";

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

export const getTailorData = (jobId: string) =>
  req<TailoredResume>(`/tailor/${jobId}/data`);

export const getTailorCoverLetterText = (jobId: string) =>
  req<{ text: string }>(`/tailor/${jobId}/cover-letter-text`);

export const patchTailorData = (
  jobId: string,
  resume: TailoredResume,
  coverLetter: string,
) =>
  req<{ ok: boolean }>(`/tailor/${jobId}/data`, {
    method: "PATCH",
    body: JSON.stringify({ resume, cover_letter: coverLetter }),
  });

// Search Brief
export const getSearchBrief = (slug: string) =>
  req<SearchBrief>(`/profiles/${slug}/search-brief`);

export const generateSearchBrief = (slug: string) =>
  req<SearchBrief>(`/profiles/${slug}/search-brief/generate`, { method: "POST" });

export const patchSignal = (
  slug: string,
  signalId: string,
  patch: { active?: boolean; label?: string }
) =>
  req<Signal>(`/profiles/${slug}/search-brief/signals/${signalId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const addSignal = (
  slug: string,
  data: { category: string; label: string }
) =>
  req<Signal>(`/profiles/${slug}/search-brief/signals`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const deleteSignal = (slug: string, signalId: string) =>
  req<{ deleted: string }>(`/profiles/${slug}/search-brief/signals/${signalId}`, {
    method: "DELETE",
  });
