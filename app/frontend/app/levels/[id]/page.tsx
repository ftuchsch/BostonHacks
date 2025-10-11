"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, Level, getLevel } from "../../../lib/api";
import { PlayScreen } from "../../../components/PlayScreen";

export default function LevelLoaderPage({
  params,
}: {
  params: { id: string };
}) {
  const [level, setLevel] = useState<Level | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coordsStatus, setCoordsStatus] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [coordsError, setCoordsError] = useState<string | null>(null);
  const [coords, setCoords] = useState<number[][] | null>(null);
  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const generateBackbone = useCallback((seq: string) => {
    const points: number[][] = [];
    const step = 4.31;
    const nCa = 1.45;
    const caC = 1.53;
    for (let index = 0; index < seq.length; index += 1) {
      const origin = index * step;
      points.push([origin, 0, 0]);
      points.push([origin + nCa, 0, 0]);
      points.push([origin + nCa + caC, 0, 0]);
    }
    return points;
  }, []);

  const fetchCoords = useCallback(
    async (lvl: Level, isCancelled: () => boolean = () => false) => {
      if (isCancelled() || !isMounted.current) {
        return;
      }

      setCoordsStatus("loading");
      setCoordsError(null);
      setCoords(null);

      try {
        const response = await fetch(lvl.start_coords_url);
        if (isCancelled() || !isMounted.current) {
          return;
        }

        if (!response.ok) {
          throw new Error(
            `Failed to fetch coordinates (status ${response.status})`
          );
        }

        await response.text();
        if (isCancelled() || !isMounted.current) {
          return;
        }

        setCoords(generateBackbone(lvl.sequence));
        setCoordsStatus("ready");
      } catch (err) {
        if (isCancelled() || !isMounted.current) {
          return;
        }

        setCoordsStatus("error");
        setCoordsError(
          err instanceof Error
            ? err.message
            : "Failed to load starting coordinates."
        );
        setCoords(generateBackbone(lvl.sequence));
      }
    },
    [generateBackbone]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setError(null);
    setCoordsStatus("idle");
    setCoordsError(null);

    void (async () => {
      try {
        const lvl = await getLevel(params.id);
        if (cancelled || !isMounted.current) {
          return;
        }

        setLevel(lvl);
        await fetchCoords(lvl, () => cancelled);
      } catch (err) {
        if (cancelled || !isMounted.current) {
          return;
        }

        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
          setLevel(null);
        } else {
          const message =
            err instanceof Error ? err.message : "Failed to load level.";
          setError(message);
        }
      } finally {
        if (!cancelled && isMounted.current) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchCoords, params.id]);

  const handleRetryCoords = useCallback(() => {
    if (level) {
      void fetchCoords(level);
    }
  }, [fetchCoords, level]);

  if (loading) {
    return (
      <main className="level-loader">
        <p>Loading level…</p>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="level-loader">
        <h1>Level not found</h1>
        <p>The requested level could not be located.</p>
        <Link href="/levels" className="level-loader__back">
          Return to Level Select
        </Link>
      </main>
    );
  }

  if (error) {
    return (
      <main className="level-loader">
        <h1>Level failed to load</h1>
        <p>{error}</p>
        <Link href="/levels" className="level-loader__back">
          Return to Level Select
        </Link>
      </main>
    );
  }

  if (!level) {
    return (
      <main className="level-loader">
        <p>Level data unavailable.</p>
        <Link href="/levels" className="level-loader__back">
          Return to Level Select
        </Link>
      </main>
    );
  }

  return (
    <main className="level-loader">
      <header className="level-loader__header">
        <div>
          <p className="level-loader__breadcrumb">
            <Link href="/levels">Levels</Link> / {level.name}
          </p>
          <h1>{level.name}</h1>
          <p className="level-loader__meta">
            <span className="level-loader__badge">{level.difficulty}</span>
            <span aria-hidden="true">•</span>
            <span>{level.length} residues</span>
          </p>
        </div>
      </header>
      {coordsStatus === "loading" && (
        <div className="level-loader__notice">Fetching starting coordinates…</div>
      )}
      {coordsStatus === "error" && (
        <div className="level-loader__notice level-loader__notice--error">
          <p>{coordsError ?? "Failed to load starting coordinates."}</p>
          <button type="button" onClick={handleRetryCoords}>
            Retry download
          </button>
        </div>
      )}
      <section className="level-loader__content">
        <div className="level-loader__play">
          <PlayScreen
            levelId={level.id}
            sequence={level.sequence}
            initialCoords={coords ?? undefined}
          />
        </div>
        <aside className="level-loader__sidebar">
          <h2>Tips</h2>
          {level.tips && level.tips.length > 0 ? (
            <ul>
              {level.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          ) : (
            <p>No tips provided for this level.</p>
          )}
        </aside>
      </section>
    </main>
  );
}
