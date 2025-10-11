"use client";

import { memo, useMemo } from "react";
import type { PerResidueTerm } from "../lib/api";

type ResidueTermKey = "clash" | "rama" | "rotamer" | "ss";

export type ResiduePanelProps = {
  residue: PerResidueTerm | null;
  isScoring: boolean;
  angles: { phi: number; psi: number } | null;
  rotamerId: number | null;
  errorMessage: string | null;
  highlight: { resIdx: number; terms: ResidueTermKey[] } | null;
};

const ResiduePanelComponent = ({
  residue,
  isScoring,
  angles,
  rotamerId,
  errorMessage,
  highlight,
}: ResiduePanelProps) => {
  const penaltyFormatter = useMemo(
    () =>
      new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
        signDisplay: "always",
      }),
    []
  );

  const penalties = useMemo(() => {
    if (!residue) {
      return [];
    }

    return (
      [
        { key: "clash" as const, label: "Clash", value: residue.clash },
        { key: "rama" as const, label: "Ramachandran", value: residue.rama },
        { key: "rotamer" as const, label: "Rotamer", value: residue.rotamer },
        { key: "ss" as const, label: "Secondary Structure", value: residue.ss },
      ]
        .filter((entry) => typeof entry.value === "number")
        .sort((a, b) => b.value - a.value)
    );
  }, [residue]);

  const highlightedTerms =
    residue && highlight && highlight.resIdx === residue.idx
      ? new Set<ResidueTermKey>(highlight.terms)
      : null;

  return (
    <aside className="residue-panel">
      <header className="residue-panel__header">
        <h2>Residue Penalties</h2>
        {isScoring ? <span className="residue-panel__status">Scoring…</span> : null}
      </header>
      {residue ? (
        <div className="residue-panel__content">
          <div className="residue-panel__meta">
            <div>
              <span className="residue-panel__meta-label">Residue</span>
              <span className="residue-panel__meta-value">{residue.idx}</span>
            </div>
            {angles ? (
              <div>
                <span className="residue-panel__meta-label">φ / ψ</span>
                <span className="residue-panel__meta-value">
                  {angles.phi.toFixed(1)}° / {angles.psi.toFixed(1)}°
                </span>
              </div>
            ) : null}
            {rotamerId !== null ? (
              <div>
                <span className="residue-panel__meta-label">Rotamer</span>
                <span className="residue-panel__meta-value">#{rotamerId}</span>
              </div>
            ) : null}
          </div>
          <dl className="residue-panel__penalties">
            {penalties.map((entry) => {
              const isHighlighted = highlightedTerms?.has(entry.key) ?? false;
              const rowClass = isHighlighted
                ? "residue-panel__penalty residue-panel__penalty--highlight"
                : "residue-panel__penalty";
              const labelClass = isHighlighted
                ? "residue-panel__penalty-label residue-panel__penalty-label--highlight"
                : "residue-panel__penalty-label";
              const valueClass = isHighlighted
                ? "residue-panel__penalty-value residue-panel__penalty-value--highlight"
                : "residue-panel__penalty-value";
              return (
                <div key={entry.key} className={rowClass}>
                  <dt className={labelClass}>{entry.label}</dt>
                  <dd className={valueClass}>{penaltyFormatter.format(entry.value)}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : (
        <p className="residue-panel__empty">Select a residue to inspect penalties.</p>
      )}
      {errorMessage ? <p className="residue-panel__error">{errorMessage}</p> : null}
      <style jsx>{`
        .residue-panel {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1rem;
          border-radius: 0.75rem;
          background: rgba(15, 23, 42, 0.8);
          color: #e2e8f0;
          min-height: 0;
        }

        .residue-panel__header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .residue-panel__header h2 {
          margin: 0;
          font-size: 1.1rem;
        }

        .residue-panel__status {
          margin-left: auto;
          font-size: 0.875rem;
          color: #94a3b8;
        }

        .residue-panel__meta {
          display: flex;
          gap: 1rem;
          flex-wrap: wrap;
        }

        .residue-panel__meta-label {
          display: block;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #94a3b8;
        }

        .residue-panel__meta-value {
          font-size: 1rem;
          font-weight: 600;
          font-variant-numeric: tabular-nums;
        }

        .residue-panel__penalties {
          display: grid;
          gap: 0.75rem;
          margin: 0;
        }

        .residue-panel__penalty {
          display: flex;
          justify-content: space-between;
          font-size: 0.95rem;
          border-radius: 0.5rem;
          padding: 0.25rem 0.5rem;
        }

        .residue-panel__penalty--highlight {
          animation: residue-penalty-highlight 650ms ease-out;
          background: rgba(34, 197, 94, 0.16);
        }

        .residue-panel__penalty-label,
        .residue-panel__penalty-value {
          margin: 0;
        }

        .residue-panel__penalty-value {
          font-variant-numeric: tabular-nums;
        }

        .residue-panel__penalty-label--highlight,
        .residue-panel__penalty-value--highlight {
          color: #bbf7d0;
        }

        .residue-panel__penalty-value--highlight {
          font-weight: 600;
        }

        @keyframes residue-penalty-highlight {
          0% {
            background: rgba(34, 197, 94, 0.32);
          }
          100% {
            background: rgba(34, 197, 94, 0);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .residue-panel__penalty--highlight {
            animation: none;
          }
        }

        .residue-panel__empty {
          margin: 0;
          color: #94a3b8;
        }

        .residue-panel__error {
          margin: 0;
          padding: 0.75rem;
          border-radius: 0.5rem;
          background: rgba(248, 113, 113, 0.16);
          color: #fca5a5;
          font-size: 0.9rem;
        }
      `}</style>
    </aside>
  );
};

export const ResiduePanel = memo(ResiduePanelComponent);
