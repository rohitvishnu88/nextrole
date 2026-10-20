import type { ApplicationStatus } from "@/lib/types";

const fill: Record<ApplicationStatus, string> = {
  saved:     "bg-ink",
  applied:   "bg-yellow",
  interview: "bg-blue",
  offer:     "bg-blue",
  rejected:  "bg-red",
};

export function StatusMarker({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`inline-flex items-center gap-2 text-sm ${status === "offer" ? "font-bold" : ""}`}>
      <span aria-hidden className={`w-2.5 h-2.5 shrink-0 ${fill[status]}`} />
      {status}
    </span>
  );
}
