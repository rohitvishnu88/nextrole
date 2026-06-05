"use client";
import { useState } from "react";
import { X, Info } from "lucide-react";
import type { Signal, SignalConfidence } from "@/lib/types";

const CONFIDENCE_DOT: Record<SignalConfidence, string> = {
  high:   "bg-green-500",
  medium: "bg-yellow-400",
  low:    "bg-gray-300",
};

const CONFIDENCE_BG: Record<SignalConfidence, string> = {
  high:   "bg-green-soft border-green-200",
  medium: "bg-yellow-50 border-yellow-100",
  low:    "bg-cream border-warm-border",
};

const CONFIDENCE_LABEL: Record<SignalConfidence, string> = {
  high:   "Directly in resume",
  medium: "Inferred from context",
  low:    "Default assumption",
};

interface Props {
  signal: Signal;
  onToggle: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
}

export function SignalChip({ signal, onToggle, onDelete }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  const bg        = signal.active ? CONFIDENCE_BG[signal.confidence] : "bg-gray-50 border-gray-200";
  const textColor = signal.active ? "text-navy" : "text-muted line-through";

  return (
    <div className={`relative inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium transition-all ${bg}`}>

      {/* Confidence dot */}
      <span className={`w-2 h-2 rounded-full shrink-0 transition-colors ${
        signal.active ? CONFIDENCE_DOT[signal.confidence] : "bg-gray-300"
      }`} />

      {/* Label */}
      <span className={`transition-colors ${textColor}`}>{signal.label}</span>

      {/* Source info icon */}
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="text-muted hover:text-navy transition-colors ml-0.5"
        aria-label="View source"
      >
        <Info size={11} />
      </button>

      {/* Toggle */}
      <button
        onClick={() => onToggle(signal.id, !signal.active)}
        className={`w-7 h-4 rounded-full transition-colors ml-0.5 relative shrink-0 ${
          signal.active ? "bg-accent" : "bg-gray-200"
        }`}
        aria-label={signal.active ? "Disable signal" : "Enable signal"}
      >
        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${
          signal.active ? "translate-x-3.5" : "translate-x-0.5"
        }`} />
      </button>

      {/* Delete */}
      <button
        onClick={() => onDelete(signal.id)}
        className="text-warm-border hover:text-red-400 transition-colors"
        aria-label="Remove signal"
      >
        <X size={11} />
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div className="bg-navy text-white text-xs rounded-xl px-3 py-2 w-52 shadow-lg">
            <p className="font-semibold mb-0.5">{CONFIDENCE_LABEL[signal.confidence]}</p>
            <p className="text-white/80 leading-relaxed">{signal.source}</p>
          </div>
          <div className="w-2 h-2 bg-navy rotate-45 mx-auto -mt-1" />
        </div>
      )}
    </div>
  );
}
