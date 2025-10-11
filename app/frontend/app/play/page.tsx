"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, getLevels } from "../../lib/api";

type LoadState =
  | { status: "loading" }
  | { status: "redirecting" }
  | { status: "error"; message: string };

const DEFAULT_LEVEL_ID = process.env.NEXT_PUBLIC_DEFAULT_LEVEL_ID ?? "level_0001";
const DEFAULT_ERROR = "Quick Play is unavailable right now. Please try again later.";

export default function PlayPage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    void (async () => {
      let targetLevel = DEFAULT_LEVEL_ID;
      try {
        const summaries = await getLevels();
        if (cancelled || !isMounted.current) {
          return;
        }
        if (summaries.length > 0) {
          targetLevel = summaries[0].id;
        } else if (!DEFAULT_LEVEL_ID) {
          throw new Error("No levels available");
        }
      } catch (err) {
        if (cancelled || !isMounted.current) {
          return;
        }
        let message = DEFAULT_ERROR;
        if (err instanceof ApiError && err.status === 404) {
          message = "No Quick Play level available.";
        } else if (err instanceof Error && err.message) {
          message = err.message;
        }
        setState({ status: "error", message });
        return;
      }

      if (cancelled || !isMounted.current) {
        return;
      }

      setState({ status: "redirecting" });
      router.replace(`/levels/${encodeURIComponent(targetLevel)}`);
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (state.status === "error") {
    return (
      <main className="play-loader">
        <h1>Quick Play</h1>
        <p>{state.message ?? DEFAULT_ERROR}</p>
      </main>
    );
  }

  return (
    <main className="play-loader">
      <p>{state.status === "redirecting" ? "Loading Quick Play…" : "Preparing Quick Play…"}</p>
    </main>
  );
}
