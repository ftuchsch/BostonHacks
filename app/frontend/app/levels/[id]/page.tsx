"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, Level, getLevel } from "../../../lib/api";
import {
  type ResidueCoordinate,
  createLinearBackbone,
  parseResidueCoordinates,
} from "../../../lib/structures";
import { PlayScreen } from "../../../components/PlayScreen";

export default function LevelLoaderPage({
  params,
}: {
  params: { id: string };
}) {
  type LoaderState =
    | { status: "loading" }
    | { status: "not_found" }
    | { status: "error"; message: string }
    | {
        status: "ready";
        level: Level;
        coords: ResidueCoordinate[];
        coordsStatus: "loading" | "ready" | "error";
        coordsError: string | null;
      };

  const [state, setState] = useState<LoaderState>({ status: "loading" });
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const updateCoordsStatus = useCallback(
    (status: "loading" | "ready" | "error", message: string | null = null) => {
      setState((prev) => {
        if (!isMounted.current || prev.status !== "ready") {
          return prev;
        }
        return {
          ...prev,
          coordsStatus: status,
          coordsError: message,
        };
      });
    },
    []
  );

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    void (async () => {
      try {
        const lvl = await getLevel(params.id);
        if (cancelled || !isMounted.current) {
          return;
        }

        const coords = createLinearBackbone(lvl.sequence);
        if (cancelled || !isMounted.current) {
          return;
        }

        setState({
          status: "ready",
          level: lvl,
          coords,
          coordsStatus: "loading",
          coordsError: null,
        });

        void (async () => {
          try {
            const response = await fetch(lvl.start_coords_url, { cache: "no-store" });
            if (cancelled || !isMounted.current) {
              return;
            }

            if (!response.ok) {
              throw new Error(
                `Failed to fetch coordinates (status ${response.status})`
              );
            }

            const payload = await response.json();
            const parsed = parseResidueCoordinates(payload);
            if (parsed && parsed.length > 0 && isMounted.current && !cancelled) {
              setState((prev) => {
                if (prev.status !== "ready") {
                  return prev;
                }
                return {
                  ...prev,
                  coords: parsed,
                };
              });
              updateCoordsStatus("ready");
            } else {
              updateCoordsStatus(
                "error",
                "Starting coordinates were unavailable. Showing a placeholder backbone."
              );
            }
          } catch (err) {
            if (cancelled || !isMounted.current) {
              return;
            }
            const message =
              err instanceof Error
                ? err.message
                : "Failed to load starting coordinates.";
            updateCoordsStatus("error", message);
          }
        })();
      } catch (err) {
        if (cancelled || !isMounted.current) {
          return;
        }

        if (err instanceof ApiError && err.status === 404) {
          setState({ status: "not_found" });
        } else {
          const message =
            err instanceof Error ? err.message : "Failed to load level.";
          setState({ status: "error", message });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.id, updateCoordsStatus]);

  const handleRetryCoords = useCallback(() => {
    if (!isMounted.current) {
      return;
    }
    setState((prev) => {
      if (prev.status !== "ready") {
        return prev;
      }

      updateCoordsStatus("loading");

      void (async () => {
        try {
          const response = await fetch(prev.level.start_coords_url, { cache: "no-store" });
          if (!isMounted.current) {
            return;
          }
          if (!response.ok) {
            throw new Error(
              `Failed to fetch coordinates (status ${response.status})`
            );
          }
          const payload = await response.json();
          const parsed = parseResidueCoordinates(payload);
          if (parsed && parsed.length > 0) {
            setState((prev) => {
              if (!isMounted.current || prev.status !== "ready") {
                return prev;
              }
              return {
                ...prev,
                coords: parsed,
              };
            });
            updateCoordsStatus("ready");
          } else {
            updateCoordsStatus(
              "error",
              "Starting coordinates were unavailable. Showing a placeholder backbone."
            );
          }
        } catch (err) {
          if (!isMounted.current) {
            return;
          }
          const message =
            err instanceof Error
              ? err.message
              : "Failed to load starting coordinates.";
          updateCoordsStatus("error", message);
        }
      })();

      return prev;
    });
  }, [updateCoordsStatus]);

  if (state.status === "loading") {
    return (
      <main className="level-loader">
        <p>Loading level…</p>
      </main>
    );
  }

  if (state.status === "not_found") {
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

  if (state.status === "error") {
    return (
      <main className="level-loader">
        <h1>Level failed to load</h1>
        <p>{state.message}</p>
        <Link href="/levels" className="level-loader__back">
          Return to Level Select
        </Link>
      </main>
    );
  }

  const { level, coords, coordsStatus, coordsError } = state;

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
