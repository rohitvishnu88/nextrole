"use client";
import { createPortal } from "react-dom";

interface Props {
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

// A real in-app modal, not window.confirm() - browsers silently suppress
// confirm()/alert() after a page has shown several of them (or once the user
// checks "prevent this page from creating additional dialogs"), after which
// every future call resolves to `false` with no visible popup at all. That
// makes any confirm()-gated action look broken with zero feedback.
export function ConfirmDialog({ message, confirmLabel = "delete", onConfirm, onCancel }: Props) {
  return createPortal(
    <div className="fixed inset-0 bg-ink/50 flex items-center justify-center z-[9999]" onClick={onCancel}>
      <div className="bg-surface border-[1.5px] border-ink w-full max-w-sm mx-4 p-5" onClick={e => e.stopPropagation()}>
        <p className="text-sm text-ink mb-4">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="text-sm text-ink border-[1.5px] border-ink px-3 py-1.5 hover:bg-ink hover:text-paper transition-colors"
          >
            cancel
          </button>
          <button
            onClick={onConfirm}
            className="text-sm bg-red text-paper px-3 py-1.5 hover:bg-red/90 transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
