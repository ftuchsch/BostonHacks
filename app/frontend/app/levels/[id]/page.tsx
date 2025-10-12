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
  const backendHelpMessage =
    "Unable to reach the backend API. Start the Python server with `make dev-back` (http://127.0.0.1:8000) and try again.";

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
        if (cancelled || !isMounted.current) return;

        // Start with a placeholder backbone so the UI shows something immediately
        const placeholderCoords = createLinearBackbone(lvl.sequence);

        setState({
          status: "ready",
          level: lvl,
          coords: placeholderCoords,
          coordsStatus: "loading",
          coordsError: null,
        });

        // Try to fetch the real coordinates
        void (async () => {
          try {
            const response = await fetch(lvl.start_coords_url, {
              cache: "no-store",
            });
            if (cancelled || !isMounted.current) return;

            if (!response.ok) {
              throw new Error(
                `Failed to fetch coordinates (status ${response.status})`
              );
            }

            const payload: unknown = await response.json();
            const parsed = parseResidueCoordinates(payload);

            if (parsed && parsed.length > 0 && isMounted.current && !cancelled) {
              setState((prev) => {
                if (prev.status !== "ready") return prev;
                return { ...prev, coords: parsed };
              });
              updateCoordsStatus("ready");
            } else {
              updateCoordsStatus(
                "error",
                "Starting coordinates were unavailable. Showing a placeholder backbone."
              );
            }
          } catch (err) {
            if (cancelled || !isMounted.current) return;

            const message =
              err instanceof TypeError
                ? backendHelpMessage
                : err instanceof Error
                ? err.message
                : "Failed to load starting coordinates.";
            updateCoordsStatus("error", message);
          }
        })();
      } catch (err) {
        if (cancelled || !isMounted.current) return;

        if (err instanceof ApiError) {
          if (err.status === 404) {
            setState({ status: "not_found" });
            return;
          }

          const detail =
            err.body &&
            typeof err.body === "object" &&
            "detail" in err.body &&
            typeof (err.body as { detail?: unknown }).detail === "string"
              ? (err.body as { detail: string }).detail
              : null;

          const message =
            detail ?? err.message ?? `Server responded with status ${err.status} while loading the level.`;

          setState({ status: "error", message });
          return;
        }

        const message =
          err instanceof TypeError
            ? backendHelpMessage
            : err instanceof Error
            ? err.message
            : "Failed to load level.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.id, updateCoordsStatus]);

  const handleRetryCoords = useCallback(() => {
    if (!isMounted.current) return;
    setState((prev) => {
      if (prev.status !== "ready") return prev;

      updateCoordsStatus("loading");

      void (async () => {
        try {
          const response = await fetch(prev.level.start_coords_url, {
            cache: "no-store",
          });
          if (!isMounted.current) return;
          if (!response.ok) {
            throw new Error(
              `Failed to fetch coordinates (status ${response.status})`
            );
          }

          const payload: unknown = await response.json();
          const parsed = parseResidueCoordinates(payload);

          if (parsed && parsed.length > 0) {
            setState((innerPrev) => {
              if (!isMounted.current || innerPrev.status !== "ready") {
                return innerPrev;
              }
              return { ...innerPrev, coords: parsed };
            });
            updateCoordsStatus("ready");
          } else {
            updateCoordsStatus(
              "error",
              "Starting coordinates were unavailable. Showing a placeholder backbone."
            );
          }
        } catch (err) {
          if (!isMounted.current) return;
          const message =
            err instanceof TypeError
              ? backendHelpMessage
              : err instanceof Error
              ? err.message
              : "Failed to load starting coordinates.";
          updateCoordsStatus("error", message);
        }
      })();

      return prev;
    });
  }, [updateCoordsStatus]);

  // --- Render states ---
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
        <h1>Failed to load level</h1>
        <p>{state.message}</p>
        <Link href="/levels" className="level-loader__back">
          Return to Level Select
        </Link>
      </main>
    );
  }

  if (state.status === "ready") {
    return (
      <PlayScreen
        levelId={state.level.id}
        sequence={state.level.sequence}
        initialCoords={state.coords}
        coordsStatus={state.coordsStatus}
        coordsError={state.coordsError}
        onRetryCoords={handleRetryCoords}
      />
    );
  }

  return null;
}
