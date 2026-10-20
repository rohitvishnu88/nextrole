"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ProfileSwitcher } from "./ProfileSwitcher";

const nav = [
  { href: "/",             label: "dashboard" },
  { href: "/tailor",       label: "tailor" },
  { href: "/jobs",         label: "jobs" },
  { href: "/applications", label: "applications" },
  { href: "/search-brief", label: "search brief" },
  { href: "/about",        label: "about" },
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 bg-paper border-b-[1.5px] border-ink">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between gap-6">
        <Link href="/" className="font-bold text-lg text-ink shrink-0">
          nextrole.
        </Link>

        <nav className="flex items-center gap-5">
          {nav.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`text-sm py-1 border-b-2 transition-colors ${
                  active ? "border-ink text-ink font-bold" : "border-transparent text-ink-muted hover:text-ink"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="shrink-0">
          <ProfileSwitcher />
        </div>
      </div>
    </header>
  );
}
