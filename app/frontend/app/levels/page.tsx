"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, LevelSummary, getLevels } from "../../lib/api";

const difficultyLabel: Record<LevelSummary["difficulty"], string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

function LevelCard({ level }: { level: LevelSummary }) {
  return (
    <li className="level-card">
      <Link href={`/levels/${level.id}`} className="level-card__link">
        {level.preview_img_url ? (
          <Image
            src={level.preview_img_url}
            alt={level.name}
            width={480}
            height={240}
            className="level-card__preview"
            style={{ width: "100%", height: "auto" }}
          />
        ) : (
          <div className="level-card__preview level-card__preview--placeholder">
            No preview
          </div>
        )}
        <div className="level-card__body">
          <h3 className="level-card__title">{level.name}</h3>
          <p className="level-card__meta">
            <span>{difficultyLabel[level.difficulty]}</span>
            <span aria-hidden="true">•</span>
            <span>{level.length} residues</span>
          </p>
          {level.short_desc && (
            <p className="level-card__description">{level.short_desc}</p>
          )}
          {level.tags && level.tags.length > 0 && (
            <ul className="level-card__tags">
              {level.tags.map((tag) => (
                <li key={tag} className="level-card__tag">
                  {tag}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Link>
    </li>
  );
}

export default function LevelsPage() {
  const [levels, setLevels] = useState<LevelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const payload = await getLevels();
        if (!cancelled) {
          setLevels(payload);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof ApiError
              ? err.message
              : "Failed to load levels.";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="levels-page">
      <header className="levels-page__header">
        <h1>Choose a Level</h1>
        <p>Select a challenge to load the play experience.</p>
      </header>
      {loading && <p>Loading levels…</p>}
      {error && <p className="levels-page__error">{error}</p>}
      {!loading && !error && (
        <ul className="levels-page__grid">
          {levels.map((level) => (
            <LevelCard key={level.id} level={level} />
          ))}
        </ul>
      )}
    </main>
  );
}
