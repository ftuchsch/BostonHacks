"use client";

import { useCallback, useState } from "react";

import { ApiError, SubmitRequest, SubmitResponse, submit } from "../lib/api";

type SubmitButtonProps = {
  levelId: string;
  sequence: string;
  coords: number[][];
  elapsedMs?: number | (() => number);
  playerName?: string;
  clientVersion?: string;
  disabled?: boolean;
  onSuccess?: (response: SubmitResponse) => void;
  onError?: (message: string, detail?: unknown) => void;
};

export function SubmitButton({
  levelId,
  sequence,
  coords,
  elapsedMs,
  playerName,
  clientVersion,
  disabled,
  onSuccess,
  onError,
}: SubmitButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = useCallback(async () => {
    if (disabled || loading) {
      return;
    }
    setLoading(true);

    const resolvedElapsed =
      typeof elapsedMs === "function" ? elapsedMs() : elapsedMs;

    const payload: SubmitRequest = {
      level_id: levelId,
      sequence,
      coords,
      ...(typeof resolvedElapsed === "number"
        ? { elapsed_ms: Math.max(0, Math.floor(resolvedElapsed)) }
        : {}),
      ...(playerName ? { player_name: playerName } : {}),
      ...(clientVersion ? { client_version: clientVersion } : {}),
    };

    try {
      const response = await submit(payload);
      onSuccess?.(response);
    } catch (error) {
      let message = "Submission failed";
      let detail: unknown = null;
      if (error instanceof ApiError) {
        message = error.message;
        detail = error.body;
      } else if (error instanceof Error) {
        message = error.message;
      }
      onError?.(message, detail);
    } finally {
      setLoading(false);
    }
  }, [clientVersion, coords, disabled, elapsedMs, levelId, loading, onError, onSuccess, playerName, sequence]);

  return (
    <>
      <button
        type="button"
        className="submit-button"
        onClick={handleClick}
        disabled={disabled || loading}
      >
        {loading ? "Submitting…" : "Submit"}
      </button>
      <style jsx>{`
        .submit-button {
          padding: 0.5rem 1.25rem;
          border-radius: 9999px;
          border: none;
          background: linear-gradient(135deg, #38bdf8, #6366f1);
          color: #0f172a;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.15s ease, opacity 0.15s ease;
        }

        .submit-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .submit-button:not(:disabled):hover {
          transform: translateY(-1px);
        }
      `}</style>
    </>
  );
}

