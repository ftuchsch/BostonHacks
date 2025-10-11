"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ApiError, getLeaderboard, type LeaderboardResponse } from "../../lib/api";

type LeaderboardPageProps = {
  params: { levelId: string };
};

const formatElapsed = (elapsed?: number) => {
  if (typeof elapsed !== "number") {
    return "—";
  }
  if (elapsed < 1000) {
    return `${elapsed} ms`;
  }
  return `${(elapsed / 1000).toFixed(1)} s`;
};

const formatTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

export default function LeaderboardPage({ params }: LeaderboardPageProps) {
  const [response, setResponse] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const data = await getLeaderboard(params.levelId, { limit: 50 });
        if (!cancelled) {
          setResponse(data);
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setError("Level not found");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load leaderboard");
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
  }, [params.levelId]);

  const items = useMemo(() => response?.items ?? [], [response]);

  return (
    <main className="leaderboard">
      <header className="leaderboard__header">
        <div>
          <p className="leaderboard__breadcrumb">
            <Link href="/levels">Levels</Link> / {params.levelId}
          </p>
          <h1>Leaderboard</h1>
          <p className="leaderboard__meta">
            {response ? `${response.total_entries} submissions` : "—"}
          </p>
        </div>
        <Link href={`/levels/${params.levelId}`} className="leaderboard__back">
          Back to level
        </Link>
      </header>

      {loading && <p className="leaderboard__status">Loading leaderboard…</p>}
      {error && <p className="leaderboard__status leaderboard__status--error">{error}</p>}

      {!loading && !error ? (
        <section className="leaderboard__panel">
          {items.length === 0 ? (
            <p>No submissions yet. Be the first to submit!</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Player</th>
                  <th>Score</th>
                  <th>Elapsed</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={`${item.rank}-${item.player_name}-${item.ts}`}>
                    <td data-label="Rank">{item.rank}</td>
                    <td data-label="Player">{item.player_name || "Anonymous"}</td>
                    <td data-label="Score">{item.score.toFixed(2)}</td>
                    <td data-label="Elapsed">{formatElapsed(item.elapsed_ms)}</td>
                    <td data-label="Submitted">{formatTimestamp(item.ts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}

      <style jsx>{`
        .leaderboard {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          padding: 2rem;
          background: #0f172a;
          min-height: 100vh;
          color: #e2e8f0;
        }

        .leaderboard__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .leaderboard__breadcrumb {
          margin: 0;
          color: #94a3b8;
        }

        .leaderboard__meta {
          margin: 0.25rem 0 0;
          color: #94a3b8;
        }

        .leaderboard__back {
          padding: 0.5rem 1rem;
          border-radius: 9999px;
          background: rgba(148, 163, 184, 0.2);
          color: #e2e8f0;
        }

        .leaderboard__back:hover {
          background: rgba(148, 163, 184, 0.3);
        }

        .leaderboard__status {
          margin: 0;
          color: #94a3b8;
        }

        .leaderboard__status--error {
          color: #fca5a5;
        }

        .leaderboard__panel {
          background: rgba(15, 23, 42, 0.9);
          border-radius: 1rem;
          padding: 1.5rem;
          box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.1);
        }

        table {
          width: 100%;
          border-collapse: collapse;
          font-variant-numeric: tabular-nums;
        }

        th,
        td {
          padding: 0.75rem 1rem;
          text-align: left;
        }

        thead tr {
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          color: #94a3b8;
        }

        tbody tr:nth-child(odd) {
          background: rgba(30, 41, 59, 0.4);
        }

        tbody tr:hover {
          background: rgba(56, 189, 248, 0.08);
        }

        @media (max-width: 768px) {
          .leaderboard {
            padding: 1.5rem;
          }

          table,
          thead,
          tbody,
          th,
          td,
          tr {
            display: block;
          }

          thead {
            display: none;
          }

          tbody tr {
            margin-bottom: 1rem;
            border-radius: 0.75rem;
            padding: 1rem;
            background: rgba(30, 41, 59, 0.6);
          }

          tbody tr:nth-child(odd) {
            background: rgba(30, 41, 59, 0.6);
          }

          td {
            padding: 0.35rem 0;
            display: flex;
            justify-content: space-between;
          }

          td::before {
            content: attr(data-label);
            color: #94a3b8;
          }
        }
      `}</style>
    </main>
  );
}

