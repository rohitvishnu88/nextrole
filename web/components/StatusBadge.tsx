import type { ApplicationStatus } from "@/lib/types";

const colours: Record<ApplicationStatus, string> = {
  saved:     "bg-cream text-muted border border-warm-border",
  applied:   "bg-accent-light text-accent",
  interview: "bg-yellow-50 text-yellow-700",
  offer:     "bg-green-soft text-green-text",
  rejected:  "bg-red-50 text-red-600",
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${colours[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
