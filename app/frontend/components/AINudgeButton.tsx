"use client";

import { useMemo } from "react";
import { AINudgeTooltip, type NudgeSuggestion } from "./AINudgeTooltip";

export type AINudgeButtonProps = {
  disabled: boolean;
  loading: boolean;
  applying: boolean;
  suggestion: NudgeSuggestion | null;
  onRequest: () => void;
  onConfirm: () => void;
  onCancel: () => void;
  anchorRef: React.RefObject<HTMLButtonElement>;
};

export const AINudgeButton = ({
  disabled,
  loading,
  applying,
  suggestion,
  onRequest,
  onConfirm,
  onCancel,
  anchorRef,
}: AINudgeButtonProps) => {
  const label = useMemo(() => {
    if (loading) {
      return "Loading";
    }
    if (applying) {
      return "Applying";
    }
    return "AI Nudge";
  }, [loading, applying]);

  const isDisabled = disabled || loading || applying;

  return (
    <div className="ai-nudge" role="presentation">
      <button
        ref={anchorRef}
        type="button"
        onClick={onRequest}
        disabled={isDisabled}
        className={`ai-nudge__button${isDisabled ? " ai-nudge__button--disabled" : ""}`}
        aria-haspopup="dialog"
        aria-expanded={suggestion ? true : false}
      >
        {(loading || applying) && <span className="ai-nudge__spinner" aria-hidden />}
        <span>{label}</span>
      </button>
      <AINudgeTooltip
        open={Boolean(suggestion)}
        anchorRef={anchorRef}
        suggestion={suggestion}
        onConfirm={onConfirm}
        onCancel={onCancel}
        applying={applying}
      />
      <style jsx>{`
          .ai-nudge {
            position: relative;
          }

          .ai-nudge__button {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.9rem;
            border-radius: 0.75rem;
            border: none;
            background: linear-gradient(135deg, #6366f1, #38bdf8);
            color: #0f172a;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 10px 25px rgba(99, 102, 241, 0.2);
            transition: transform 160ms ease, box-shadow 160ms ease;
          }

          .ai-nudge__button:not(.ai-nudge__button--disabled):hover,
          .ai-nudge__button:not(.ai-nudge__button--disabled):focus-visible {
            transform: translateY(-1px);
            box-shadow: 0 16px 35px rgba(56, 189, 248, 0.25);
            outline: none;
          }

          .ai-nudge__button--disabled {
            opacity: 0.65;
            cursor: not-allowed;
            box-shadow: none;
          }

          .ai-nudge__spinner {
            width: 1rem;
            height: 1rem;
            border-radius: 50%;
            border: 2px solid rgba(15, 23, 42, 0.2);
            border-top-color: #0f172a;
            animation: spin 720ms linear infinite;
          }

          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }

          @media (prefers-reduced-motion: reduce) {
            .ai-nudge__button,
            .ai-nudge__spinner {
              transition: none !important;
              animation: none !important;
            }
          }
        `}</style>
    </div>
  );
};

