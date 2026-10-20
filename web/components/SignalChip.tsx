"use client";
import { useState } from "react";
import { X, Info } from "lucide-react";
import type { Signal, SignalConfidence } from "@/lib/types";

const CONFIDENCE_DOT: Record<SignalConfidence, string> = {
  high:   "bg-blue",
  medium: "bg-yellow",
  low:    "bg-rule-soft",
};

const CONFIDENCE_BG: Record<SignalConfidence, string> = {
  high:   "bg-blue/10 border-blue",
  medium: "bg-yellow/10 border-yellow",
  low:    "bg-paper border-rule-soft",
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

  const bg        = signal.active ? CONFIDENCE_BG[signal.confidence] : "bg-paper border-rule-soft";
  const textColor = signal.active ? "text-ink" : "text-ink-muted line-through";

  return (
    <div className={`relative inline-flex items-center gap-1.5 px-3 py-1.5 border text-sm font-medium transition-all ${bg}`}>

      {/* Confidence dot */}
      <span className={`w-2 h-2 shrink-0 transition-colors ${
        signal.active ? CONFIDENCE_DOT[signal.confidence] : "bg-rule-soft"
      }`} />

      {/* Label */}
      <span className={`transition-colors ${textColor}`}>{signal.label}</span>

      {/* Source info icon */}
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="text-ink-muted hover:text-ink transition-colors ml-0.5"
        aria-label="View source"
      >
        <Info size={11} />
      </button>

      {/* Toggle */}
      <button
        onClick={() => onToggle(signal.id, !signal.active)}
        className={`w-7 h-4 transition-colors ml-0.5 relative shrink-0 ${
          signal.active ? "bg-ink" : "bg-rule-soft"
        }`}
        aria-label={signal.active ? "Disable signal" : "Enable signal"}
      >
        <span className={`absolute top-0.5 w-3 h-3 bg-surface  transition-transform ${
          signal.active ? "translate-x-3.5" : "translate-x-0.5"
        }`} />
      </button>

      {/* Delete */}
      <button
        onClick={() => onDelete(signal.id)}
        className="text-rule-soft hover:text-ink transition-colors"
        aria-label="Remove signal"
      >
        <X size={11} />
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div className="bg-ink text-paper text-xs px-3 py-2 w-52 ">
            <p className="font-bold mb-0.5">{CONFIDENCE_LABEL[signal.confidence]}</p>
            <p className="text-paper/70 leading-relaxed">{signal.source}</p>
          </div>
          <div className="w-2 h-2 bg-ink rotate-45 mx-auto -mt-1" />
        </div>
      )}
    </div>
  );
}
