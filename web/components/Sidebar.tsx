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
