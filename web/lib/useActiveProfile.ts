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
