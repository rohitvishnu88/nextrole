"use client";
import { useState } from "react";

interface Props {
  placeholder: string;
  submitLabel: string;
  onSubmit: (instruction: string) => Promise<void>;
  onCancel: () => void;
}

export function SectionInstructionBox({ placeholder, submitLabel, onSubmit, onCancel }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!instruction.trim()) return;
    setLoading(true);
    setError("");
    try {
      await onSubmit(instruction);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-surface rounded-lg p-3 space-y-2">
      <textarea
        value={instruction}
        onChange={e => setInstruction(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-accent"
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={onCancel}
          className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading || !instruction.trim()}
          className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 disabled:opacity-50 hover:bg-accent/90"
        >
          {loading ? "Drafting..." : submitLabel}
        </button>
      </div>
    </div>
  );
}
