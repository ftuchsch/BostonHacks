"use client";

import { useEffect, useMemo, useRef } from "react";
import type { ScoreTerms } from "../lib/api";
import { TermDeltaPills } from "./TermDeltaPills";

export type NudgeSuggestion = {
  resIdx: number;
  move:
    | { type: "torsion"; delta?: { phi?: number; psi?: number } }
    | { type: "rotamer"; rotamer_id: number };
  expectedDelta: number;
  termDeltas: ScoreTerms;
  modelUsed: boolean;
};

type AINudgeTooltipProps = {
  open: boolean;
  anchorRef: React.RefObject<HTMLButtonElement>;
  suggestion: NudgeSuggestion | null;
  onConfirm: () => void;
  onCancel: () => void;
  applying: boolean;
};

const formatDegrees = (value?: number) => {
  if (typeof value !== "number") {
    return null;
  }
  const formatter = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  });
  const signed = `${value >= 0 ? "+" : "−"}${formatter.format(Math.abs(value))}°`;
  return signed;
};

export const AINudgeTooltip = ({
  open,
  anchorRef,
  suggestion,
  onConfirm,
  onCancel,
  applying,
}: AINudgeTooltipProps) => {
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);

  const moveDescription = useMemo(() => {
    if (!suggestion) {
      return "";
    }
    if (suggestion.move.type === "torsion") {
      const phi = formatDegrees(suggestion.move.delta?.phi);
      const psi = formatDegrees(suggestion.move.delta?.psi);
      const parts: string[] = [];
      if (phi) {
        parts.push(`φ ${phi}`);
      }
      if (psi) {
        parts.push(`ψ ${psi}`);
      }
      const angles = parts.join(" • ");
      return `res ${suggestion.resIdx}, ${angles || "torsion"}`;
    }
    return `res ${suggestion.resIdx}, rotamer #${suggestion.move.rotamer_id}`;
  }, [suggestion]);

  const expectedDeltaText = useMemo(() => {
    if (!suggestion) {
      return "";
    }
    const formatter = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
    const sign = suggestion.expectedDelta >= 0 ? "+" : "−";
    const magnitude = formatter.format(Math.abs(suggestion.expectedDelta));
    return `Expected ${sign}${magnitude}`;
  }, [suggestion]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const anchorElement = anchorRef.current;

    const focusFirst = () => {
      if (confirmButtonRef.current) {
        confirmButtonRef.current.focus();
      }
    };

    focusFirst();

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key === "Tab") {
        if (!confirmButtonRef.current || !cancelButtonRef.current) {
          return;
        }
        const focusable = [confirmButtonRef.current, cancelButtonRef.current];
        const currentIndex = focusable.indexOf(document.activeElement as HTMLButtonElement);
        if (event.shiftKey) {
          event.preventDefault();
          const nextIndex = (currentIndex - 1 + focusable.length) % focusable.length;
          focusable[nextIndex].focus();
        } else {
          event.preventDefault();
          const nextIndex = (currentIndex + 1) % focusable.length;
          focusable[nextIndex].focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeydown);

    return () => {
      document.removeEventListener("keydown", handleKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      } else if (anchorElement) {
        anchorElement.focus();
      }
    };
  }, [open, onCancel, anchorRef]);

  if (!open || !suggestion) {
    return null;
  }

  return (
    <div className="ai-nudge-tooltip" role="dialog" aria-modal="true">
      <header className="ai-nudge-tooltip__header">
        <h3>{moveDescription}</h3>
        <p>{expectedDeltaText}</p>
        {suggestion.expectedDelta <= 0 ? (
          <p className="ai-nudge-tooltip__note">No guaranteed improvement</p>
        ) : null}
      </header>
      <div className="ai-nudge-tooltip__body">
        <TermDeltaPills deltas={suggestion.termDeltas} />
      </div>
      <footer className="ai-nudge-tooltip__footer">
        <span className={`ai-nudge-tooltip__badge ai-nudge-tooltip__badge--${suggestion.modelUsed ? "model" : "heuristic"}`}>
          {suggestion.modelUsed ? "Model" : "Heuristic"}
        </span>
        <div className="ai-nudge-tooltip__actions">
          <button
            ref={cancelButtonRef}
            type="button"
            onClick={onCancel}
            className="ai-nudge-tooltip__button ai-nudge-tooltip__button--secondary"
          >
            Cancel
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            onClick={onConfirm}
            disabled={applying}
            className="ai-nudge-tooltip__button ai-nudge-tooltip__button--primary"
          >
            {applying ? "Applying…" : "Confirm"}
          </button>
        </div>
      </footer>
      <style jsx>{`
        .ai-nudge-tooltip {
          position: absolute;
          top: 100%;
          right: 0;
          margin-top: 0.75rem;
          width: min(320px, 90vw);
          padding: 1rem;
          border-radius: 0.75rem;
          background: rgba(15, 23, 42, 0.97);
          color: #f8fafc;
          box-shadow: 0 20px 35px rgba(15, 23, 42, 0.35);
          z-index: 20;
        }

        .ai-nudge-tooltip__header {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          margin-bottom: 0.75rem;
        }

        .ai-nudge-tooltip__header h3 {
          margin: 0;
          font-size: 1rem;
        }

        .ai-nudge-tooltip__header p {
          margin: 0;
          font-size: 0.85rem;
          color: #cbd5f5;
        }

        .ai-nudge-tooltip__note {
          font-style: italic;
          color: #facc15;
        }

        .ai-nudge-tooltip__body {
          margin-bottom: 0.75rem;
        }

        .ai-nudge-tooltip__footer {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          flex-wrap: wrap;
        }

        .ai-nudge-tooltip__badge {
          padding: 0.25rem 0.6rem;
          border-radius: 9999px;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .ai-nudge-tooltip__badge--model {
          background: rgba(59, 130, 246, 0.18);
          color: #bfdbfe;
        }

        .ai-nudge-tooltip__badge--heuristic {
          background: rgba(148, 163, 184, 0.18);
          color: #cbd5f5;
        }

        .ai-nudge-tooltip__actions {
          margin-left: auto;
          display: flex;
          gap: 0.5rem;
        }

        .ai-nudge-tooltip__button {
          min-width: 90px;
          padding: 0.45rem 0.75rem;
          border-radius: 0.5rem;
          border: none;
          font-size: 0.9rem;
          cursor: pointer;
        }

        .ai-nudge-tooltip__button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .ai-nudge-tooltip__button--secondary {
          background: rgba(148, 163, 184, 0.25);
          color: #e2e8f0;
        }

        .ai-nudge-tooltip__button--primary {
          background: #38bdf8;
          color: #0f172a;
          font-weight: 600;
        }

        @media (prefers-reduced-motion: reduce) {
          .ai-nudge-tooltip {
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
};

