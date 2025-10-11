"use client";

import type { ScoreTerms } from "../lib/api";

const TERM_LABELS: Record<keyof ScoreTerms, string> = {
  clash: "Clash",
  rama: "Ramachandran",
  rotamer: "Rotamer",
  ss: "Secondary Structure",
  compact: "Compact",
  hbond: "Hydrogen Bond",
};

type TermDeltaPillsProps = {
  deltas: ScoreTerms;
};

const ORDER: (keyof ScoreTerms)[] = [
  "clash",
  "rama",
  "rotamer",
  "ss",
  "compact",
  "hbond",
];

const formatDelta = (value: number) => {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const magnitude = Math.abs(value).toFixed(1);
  return `${sign}${magnitude}`;
};

export const TermDeltaPills = ({ deltas }: TermDeltaPillsProps) => {
  return (
    <ul className="term-delta-pills">
      {ORDER.map((key) => {
        const value = deltas[key];
        if (typeof value !== "number") {
          return null;
        }
        const formatted = formatDelta(value);
        const polarity = value === 0 ? "neutral" : value < 0 ? "negative" : "positive";
        return (
          <li key={key} className={`term-delta-pills__item term-delta-pills__item--${polarity}`}>
            <span className="term-delta-pills__label">{TERM_LABELS[key]}</span>
            <span className="term-delta-pills__value">{formatted}</span>
          </li>
        );
      })}
      <style jsx>{`
        .term-delta-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          padding: 0;
          margin: 0;
          list-style: none;
        }

        .term-delta-pills__item {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          padding: 0.35rem 0.6rem;
          border-radius: 9999px;
          font-size: 0.8rem;
          font-variant-numeric: tabular-nums;
          background: rgba(148, 163, 184, 0.16);
          color: #e2e8f0;
        }

        .term-delta-pills__item--positive {
          background: rgba(34, 197, 94, 0.18);
          color: #bbf7d0;
        }

        .term-delta-pills__item--negative {
          background: rgba(248, 113, 113, 0.16);
          color: #fecaca;
        }

        .term-delta-pills__item--neutral {
          background: rgba(148, 163, 184, 0.16);
          color: #e2e8f0;
        }

        .term-delta-pills__label {
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .term-delta-pills__value {
          font-weight: 600;
        }
      `}</style>
    </ul>
  );
};

