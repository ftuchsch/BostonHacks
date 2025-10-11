"use client";

import { memo, useMemo } from "react";
import type { ScoreTerms } from "../lib/api";

export type ScoreBarsProps = {
  totalScore: number;
  terms: ScoreTerms | null;
  isScoring: boolean;
  highlightedTerms?: (keyof ScoreTerms)[];
};

const formatTermLabel = (term: keyof ScoreTerms) => {
  switch (term) {
    case "clash":
      return "Clash";
    case "rama":
      return "Ramachandran";
    case "rotamer":
      return "Rotamer";
    case "ss":
      return "Secondary Structure";
    case "compact":
      return "Compact";
    case "hbond":
      return "Hydrogen Bond";
    default:
      return term;
  }
};

const ScoreBarsComponent = ({ totalScore, terms, isScoring, highlightedTerms = [] }: ScoreBarsProps) => {
  const totalFormatter = useMemo(
    () =>
      new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }),
    []
  );

  const termFormatter = useMemo(
    () =>
      new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
        signDisplay: "always",
      }),
    []
  );

  const barData = useMemo(() => {
    if (!terms) {
      return [];
    }

    const entries = (Object.entries(terms) as [keyof ScoreTerms, number][]).map(
      ([key, value]) => ({
        key,
        value,
      })
    );

    const maxMagnitude = entries.reduce((acc, { value }) => {
      const magnitude = Math.abs(value);
      return magnitude > acc ? magnitude : acc;
    }, 0);

    const highlightSet = new Set(highlightedTerms);

    return entries.map((entry) => ({
      ...entry,
      percent: maxMagnitude === 0 ? 0 : Math.abs(entry.value) / maxMagnitude,
      highlighted: highlightSet.has(entry.key),
    }));
  }, [terms, highlightedTerms]);

  return (
    <section className="score-bars" aria-label="Score summary">
      <header className="score-bars__header">
        <h2>Total Score</h2>
        <span className="score-bars__value">{totalFormatter.format(totalScore)}</span>
        {isScoring ? <span className="score-bars__status">Scoring…</span> : null}
      </header>
      <div className="score-bars__list">
        {barData.map(({ key, value, percent, highlighted }) => (
          <div
            key={key}
            className={`score-bars__row${highlighted ? " score-bars__row--highlight" : ""}`}
          >
            <span className="score-bars__label">{formatTermLabel(key)}</span>
            <div className="score-bars__bar">
              <div
                className="score-bars__bar-fill"
                style={{
                  width: `${Math.min(100, percent * 100)}%`,
                  backgroundColor: value >= 0 ? "#22c55e" : "#ef4444",
                }}
              />
            </div>
            <span className="score-bars__value">{termFormatter.format(value)}</span>
          </div>
        ))}
        {barData.length === 0 ? (
          <p className="score-bars__empty">Awaiting score…</p>
        ) : null}
      </div>
      <style jsx>{`
        .score-bars {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          padding: 1rem;
          border-radius: 0.75rem;
          background: #101827;
          color: #f8fafc;
        }

        .score-bars__header {
          display: flex;
          align-items: baseline;
          gap: 0.75rem;
        }

        .score-bars__header h2 {
          font-size: 1.25rem;
          margin: 0;
        }

        .score-bars__value {
          font-variant-numeric: tabular-nums;
        }

        .score-bars__status {
          margin-left: auto;
          font-size: 0.875rem;
          color: #94a3b8;
        }

        .score-bars__list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .score-bars__row {
          display: grid;
          grid-template-columns: 1.75fr 3fr auto;
          align-items: center;
          gap: 0.75rem;
          border-radius: 0.5rem;
          padding: 0.15rem 0.35rem;
        }

        .score-bars__row--highlight {
          animation: score-bars-highlight 650ms ease-out;
          background: rgba(34, 197, 94, 0.16);
        }

        @keyframes score-bars-highlight {
          0% {
            background: rgba(34, 197, 94, 0.32);
          }
          100% {
            background: rgba(34, 197, 94, 0.0);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .score-bars__row--highlight {
            animation: none;
          }
        }

        .score-bars__label {
          font-size: 0.9rem;
        }

        .score-bars__bar {
          width: 100%;
          height: 0.625rem;
          background: rgba(148, 163, 184, 0.2);
          border-radius: 9999px;
          overflow: hidden;
        }

        .score-bars__bar-fill {
          height: 100%;
          transition: width 120ms ease;
        }

        .score-bars__empty {
          margin: 0;
          color: #94a3b8;
          font-size: 0.9rem;
        }
      `}</style>
    </section>
  );
};

export const ScoreBars = memo(ScoreBarsComponent);
