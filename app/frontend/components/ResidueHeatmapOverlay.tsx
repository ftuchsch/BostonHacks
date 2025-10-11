"use client";

import { memo, useMemo } from "react";

export type ResidueHeatmapOverlayProps = {
  values: number[];
  selectedResidue: number | null;
  onSelect: (residueIdx: number) => void;
  residueLabels?: number[];
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const lerp = (start: number, end: number, t: number) => start + (end - start) * t;

const valueToColor = (value: number) => {
  const v = clamp(value, 0, 1);
  const r = Math.round(lerp(37, 236, v));
  const g = Math.round(lerp(99, 72, v));
  const b = Math.round(lerp(235, 28, v));
  return `rgb(${r}, ${g}, ${b})`;
};

const ResidueHeatmapOverlayComponent = ({
  values,
  selectedResidue,
  onSelect,
  residueLabels,
}: ResidueHeatmapOverlayProps) => {
  const labels = useMemo(() => {
    if (residueLabels && residueLabels.length === values.length) {
      return residueLabels;
    }

    return values.map((_, index) => index);
  }, [residueLabels, values]);

  if (values.length === 0) {
    return (
      <div className="heatmap heatmap--empty" role="presentation">
        No per-residue penalties yet.
        <style jsx>{`
          .heatmap--empty {
            padding: 1.25rem;
            border-radius: 0.75rem;
            background: rgba(15, 23, 42, 0.65);
            color: #94a3b8;
            text-align: center;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="heatmap" role="list">
      {values.map((value, index) => {
        const residueIdx = labels[index];
        const isSelected = residueIdx === selectedResidue;
        return (
          <button
            key={residueIdx}
            type="button"
            className={`heatmap__cell${isSelected ? " heatmap__cell--selected" : ""}`}
            style={{ background: valueToColor(value) }}
            onClick={() => onSelect(residueIdx)}
            aria-pressed={isSelected}
            aria-label={`Residue ${residueIdx} penalty ${(value * 100).toFixed(1)}%`}
          >
            <span>{residueIdx}</span>
          </button>
        );
      })}
      <style jsx>{`
        .heatmap {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
          gap: 4px;
        }

        .heatmap__cell {
          position: relative;
          border: none;
          border-radius: 6px;
          padding: 0;
          min-height: 40px;
          color: #0f172a;
          font-weight: 600;
          cursor: pointer;
          transition: transform 120ms ease, box-shadow 120ms ease;
        }

        .heatmap__cell span {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
        }

        .heatmap__cell--selected {
          outline: 2px solid #facc15;
          outline-offset: 2px;
          transform: scale(1.05);
          box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.5);
        }

        .heatmap__cell:hover {
          transform: scale(1.04);
        }
      `}</style>
    </div>
  );
};

export const ResidueHeatmapOverlay = memo(ResidueHeatmapOverlayComponent);
