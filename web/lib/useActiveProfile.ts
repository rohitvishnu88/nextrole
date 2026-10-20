"use client";
import { useEffect, useState } from "react";

export const ACTIVE_PROFILE_STORAGE_KEY = "resume_active_profile";
export const ACTIVE_PROFILE_EVENT = "profile-changed";

export function setActiveProfile(slug: string): void {
  localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, slug);
  window.dispatchEvent(new CustomEvent(ACTIVE_PROFILE_EVENT, { detail: slug }));
}

export function useActiveProfile(): string {
  const [slug, setSlug] = useState("");
  useEffect(() => {
    setSlug(localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY) ?? "");
    const handler = (e: Event) => setSlug((e as CustomEvent<string>).detail);
    window.addEventListener(ACTIVE_PROFILE_EVENT, handler);
    return () => window.removeEventListener(ACTIVE_PROFILE_EVENT, handler);
  }, []);
  return slug;
}
