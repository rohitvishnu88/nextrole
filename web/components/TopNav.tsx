"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, Briefcase, Search, Info } from "lucide-react";
import { ProfileSwitcher } from "./ProfileSwitcher";

const nav = [
  { href: "/",             label: "Dashboard",    icon: LayoutDashboard },
  { href: "/tailor",       label: "Tailor Resume", icon: FileText },
  { href: "/applications", label: "Applications",  icon: Briefcase },
  { href: "/search-brief", label: "Search Brief",  icon: Search },
  { href: "/about",        label: "About",          icon: Info },
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-warm-border">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between gap-6">

        {/* Clickable brand */}
        <Link
          href="/"
          className="font-brand font-bold text-lg text-navy tracking-tight shrink-0 hover:opacity-80 transition-opacity"
        >
          NextRole<span className="text-accent">.</span>
        </Link>

        {/* Nav tabs */}
        <nav className="flex items-center gap-0.5">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  active
                    ? "bg-cream text-navy"
                    : "text-muted hover:text-navy hover:bg-cream"
                }`}
              >
                <Icon size={13} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Profile switcher */}
        <div className="shrink-0">
          <ProfileSwitcher />
        </div>
      </div>
    </header>
  );
}
