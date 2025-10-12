"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import {
  calculateHeatmap,
  nudge,
  score,
  type PerResidueTerm,
  type ScoreDiff,
  type ScoreResponse,
  type ScoreTerms,
  type SubmitResponse,
} from "../lib/api";
import type { ResidueCoordinate } from "../lib/structures";
import { ResidueHeatmapOverlay } from "./ResidueHeatmapOverlay";
import { ResiduePanel } from "./ResiduePanel";
import { ScoreBars } from "./ScoreBars";
import { AINudgeButton } from "./AINudgeButton";
import type { NudgeSuggestion } from "./AINudgeTooltip";
import { ProteinViewer } from "./ProteinViewer";
import { SubmitButton } from "./SubmitButton";

type WorkerMessage =
  | {
      requestId: number;
      status: "success";
      response: ScoreResponse;
      heatmap: number[];
    }
  | {
      requestId: number;
      status: "error";
      message: string;
    };

type Angles = {
  phi: number;
  psi: number;
};

type ResidueTermKey = "clash" | "rama" | "rotamer" | "ss";

const INITIAL_ANGLES: Angles = { phi: 0, psi: 0 };

const useDebouncedCallback = <Args extends unknown[]>(
  callback: (...args: Args) => void,
  delay: number
) => {
  const timerRef = useRef<number | null>(null);

  const debounced = useCallback(
    (...args: Args) => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }

      timerRef.current = window.setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay]
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  return debounced;
};

const fallbackHeatmap = (response: ScoreResponse) =>
  calculateHeatmap(response.per_residue).values;

type PlayScreenProps = {
  levelId?: string;
  sequence?: string;
  initialCoords?: ResidueCoordinate[];
  playerName?: string;
  coordsStatus?: "loading" | "ready" | "error";
  coordsError?: string | null;
  onRetryCoords?: () => void;
};

export const PlayScreen = ({
  levelId,
  sequence,
  initialCoords,
  playerName,
  coordsStatus,
  coordsError,
  onRetryCoords,
}: PlayScreenProps) => {
  const router = useRouter();
  const [selectedResidue, setSelectedResidue] = useState<number | null>(null);
  const [angles, setAngles] = useState<Angles>(INITIAL_ANGLES);
  const [rotamerId, setRotamerId] = useState<number | null>(null);
  const [isScoring, setIsScoring] = useState(false);
  const [totalScore, setTotalScore] = useState(0);
  const [termTotals, setTermTotals] = useState<ScoreTerms | null>(null);
  const [perResidue, setPerResidue] = useState<PerResidueTerm[]>([]);
  const [heatmapValues, setHeatmapValues] = useState<number[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [highlightedTerms, setHighlightedTerms] = useState<(keyof ScoreTerms)[]>([]);
  const [highlightedResidue, setHighlightedResidue] = useState<{
    resIdx: number;
    terms: ResidueTermKey[];
  } | null>(null);
  const [nudgeState, setNudgeState] = useState<{
    loading: boolean;
    suggestion: NudgeSuggestion | null;
    applying: boolean;
    error: string | null;
  }>({
    loading: false,
    suggestion: null,
    applying: false,
    error: null,
  });

  const requestIdRef = useRef(0);
  const latestAppliedRequestRef = useRef(0);
  const lastDiffRef = useRef<ScoreDiff | null>(null);
  const retryTokenRef = useRef<number | null>(null);
  const hasRetriedRef = useRef(false);
  const queueScoreRequestRef = useRef<((diff: ScoreDiff) => void) | null>(null);
  const interactingRef = useRef(false);
  const interactingTimerRef = useRef<number | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const previousTermsRef = useRef<ScoreTerms | null>(null);
  const previousResiduesRef = useRef<PerResidueTerm[]>([]);
  const highlightTimeoutRef = useRef<number | null>(null);
  const residueHighlightTimeoutRef = useRef<number | null>(null);
  const pendingHighlightResidueRef = useRef<number | null>(null);
  const nudgeButtonRef = useRef<HTMLButtonElement | null>(null);
  const levelStartRef = useRef<number>(Date.now());
  const [submissionResult, setSubmissionResult] = useState<SubmitResponse | null>(
    null
  );
  const [submitModalOpen, setSubmitModalOpen] = useState(false);
  const structureResidues = useMemo(
    () => initialCoords ?? null,
    [initialCoords]
  );
  const submitCoords = useMemo(() => {
    if (!structureResidues) {
      const fallbackCount = sequence?.length ?? 0;
      if (fallbackCount === 0) {
        return [];
      }
      return Array.from({ length: fallbackCount }, (_, idx) => idx).flatMap((idx) => [
        [idx * 3 - 1.46, 0, 0],
        [idx * 3, 0, 0],
        [idx * 3 + 1.53, 0, 0],
      ]);
    }

    const CA_LENGTH = 1.46;
    const C_LENGTH = 1.53;

    const toTuple = (coords: number[] | [number, number, number]): [number, number, number] => [
      Number(coords[0]),
      Number(coords[1]),
      Number(coords[2]),
    ];

    const magnitude = (vector: [number, number, number]): number =>
      Math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);

    const normalize = (vector: [number, number, number]): [number, number, number] => {
      const length = magnitude(vector);
      if (length < 1e-8) {
        return [1, 0, 0];
      }
      return [vector[0] / length, vector[1] / length, vector[2] / length];
    };

    const diff = (
      a: [number, number, number],
      b: [number, number, number]
    ): [number, number, number] => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

    const add = (
      a: [number, number, number],
      b: [number, number, number]
    ): [number, number, number] => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];

    const scale = (
      vector: [number, number, number],
      length: number
    ): [number, number, number] => [
      vector[0] * length,
      vector[1] * length,
      vector[2] * length,
    ];

    const caPositions = structureResidues.map((residue) => {
      const caAtom = residue.atoms?.find((atom) => atom.name.toUpperCase() === "CA");
      return toTuple(caAtom?.coords ?? residue.coords);
    });

    const backbone: [number, number, number][] = [];

    structureResidues.forEach((residue, index) => {
      const atoms = residue.atoms ?? [];
      const findAtom = (name: string) =>
        atoms.find((atom) => atom.name.toUpperCase() === name)?.coords;

      let n = findAtom("N");
      let ca = findAtom("CA") ?? residue.coords;
      let c = findAtom("C");

      const caTuple = toTuple(ca);
      const prevCA = caPositions[index - 1] ?? add(caTuple, [-CA_LENGTH, 0, 0]);
      const nextCA = caPositions[index + 1] ?? add(caTuple, [CA_LENGTH, 0, 0]);

      if (!n) {
        const backward = normalize(diff(prevCA, caTuple));
        n = add(caTuple, scale(backward, CA_LENGTH));
      }

      if (!c) {
        const forward = normalize(diff(nextCA, caTuple));
        c = add(caTuple, scale(forward, C_LENGTH));
      }

      backbone.push(toTuple(n), caTuple, toTuple(c));
    });

    return backbone;
  }, [structureResidues, sequence?.length]);
  const coordsNotice = useMemo(() => {
    if (!coordsStatus) {
      return null;
    }
    if (coordsStatus === "loading") {
      return { tone: "info" as const, message: "Fetching detailed starting coordinates…" };
    }
    if (coordsStatus === "error") {
      return {
        tone: "error" as const,
        message: coordsError ?? "Starting coordinates are unavailable. Showing a placeholder backbone.",
      };
    }
    return null;
  }, [coordsError, coordsStatus]);
  const structureLoaded = Boolean(
    levelId && sequence && structureResidues && structureResidues.length > 0
  );
  const computeElapsedMs = useCallback(
    () => Date.now() - levelStartRef.current,
    []
  );

  const handleSubmitSuccess = useCallback((response: SubmitResponse) => {
    setSubmissionResult(response);
    setSubmitModalOpen(true);
    setToastMessage(null);
  }, []);

  const handleSubmitError = useCallback(
    (message: string, detail?: unknown) => {
      let display = message;
      if (detail && typeof detail === "object" && detail !== null) {
        const payload = detail as { detail?: unknown };
        if (payload.detail && typeof payload.detail === "object") {
          const inner = payload.detail as Record<string, unknown>;
          if (Array.isArray(inner.errors) && inner.errors.length > 0) {
            display = inner.errors.slice(0, 3).join("; ");
          } else if (typeof inner.message === "string") {
            display = inner.message;
          }
        }
      }
      setToastMessage(display);
    },
    []
  );

  const handleModalClose = useCallback(() => {
    setSubmitModalOpen(false);
  }, []);

  const handleInteractionPulse = useCallback(() => {
    interactingRef.current = true;
    if (interactingTimerRef.current) {
      window.clearTimeout(interactingTimerRef.current);
    }
    interactingTimerRef.current = window.setTimeout(() => {
      interactingRef.current = false;
    }, 400);
  }, []);

  useEffect(() => {
    return () => {
      if (retryTokenRef.current) {
        window.clearTimeout(retryTokenRef.current);
      }
      if (interactingTimerRef.current) {
        window.clearTimeout(interactingTimerRef.current);
      }
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
      if (residueHighlightTimeoutRef.current) {
        window.clearTimeout(residueHighlightTimeoutRef.current);
      }
    };
  }, []);

  const applyScorePayload = useCallback(
    (
      requestId: number,
      response: ScoreResponse,
      meta?: { highlightResidue?: number; heatmap?: number[] }
    ) => {
      if (requestId !== latestAppliedRequestRef.current) {
        return;
      }
      const previousTerms = previousTermsRef.current;
      const nextTerms = response.terms;
      const improvedTerms: (keyof ScoreTerms)[] = [];
      if (previousTerms) {
        (Object.keys(nextTerms) as (keyof ScoreTerms)[]).forEach((key) => {
          if (nextTerms[key] < previousTerms[key] - 1e-6) {
            improvedTerms.push(key);
          }
        });
      }

      if (improvedTerms.length > 0) {
        setHighlightedTerms(improvedTerms);
        if (highlightTimeoutRef.current) {
          window.clearTimeout(highlightTimeoutRef.current);
        }
        highlightTimeoutRef.current = window.setTimeout(() => {
          setHighlightedTerms([]);
          highlightTimeoutRef.current = null;
        }, 700);
      } else {
        setHighlightedTerms([]);
      }

      const candidateResidue =
        meta?.highlightResidue ?? pendingHighlightResidueRef.current;
      if (candidateResidue !== null) {
        const previousResidueEntry = previousResiduesRef.current.find(
          (entry) => entry.idx === candidateResidue
        );
        const nextResidueEntry = response.per_residue.find(
          (entry) => entry.idx === candidateResidue
        );
        if (previousResidueEntry && nextResidueEntry) {
          const residueImproved: ResidueTermKey[] = [];
          (['clash', 'rama', 'rotamer', 'ss'] as const).forEach((key) => {
            if (nextResidueEntry[key] < previousResidueEntry[key] - 1e-6) {
              residueImproved.push(key);
            }
          });
          if (residueImproved.length > 0) {
            setHighlightedResidue({ resIdx: candidateResidue, terms: residueImproved });
            if (residueHighlightTimeoutRef.current) {
              window.clearTimeout(residueHighlightTimeoutRef.current);
            }
            residueHighlightTimeoutRef.current = window.setTimeout(() => {
              setHighlightedResidue(null);
              residueHighlightTimeoutRef.current = null;
            }, 700);
          } else {
            setHighlightedResidue(null);
          }
        } else {
          setHighlightedResidue(null);
        }
      } else {
        setHighlightedResidue(null);
      }

      pendingHighlightResidueRef.current = null;
      setTotalScore(response.score);
      setTermTotals(response.terms);
      setPerResidue(response.per_residue);
      setHeatmapValues(meta?.heatmap ?? fallbackHeatmap(response));
      if (selectedResidue === null && response.per_residue.length > 0) {
        setSelectedResidue(response.per_residue[0].idx);
      }
      setIsScoring(false);
      setToastMessage(null);
      hasRetriedRef.current = false;
      previousTermsRef.current = response.terms;
      previousResiduesRef.current = response.per_residue;
    },
    [selectedResidue]
  );

  const handleRequestError = useCallback(() => {
    setIsScoring(false);
    setToastMessage("Score update failed; retrying…");
    if (!hasRetriedRef.current && interactingRef.current) {
      hasRetriedRef.current = true;
      if (retryTokenRef.current) {
        window.clearTimeout(retryTokenRef.current);
      }
      retryTokenRef.current = window.setTimeout(() => {
        const queue = queueScoreRequestRef.current;
        if (queue && lastDiffRef.current) {
          queue(lastDiffRef.current);
        }
      }, 250);
    }
  }, []);

  const directRequest = useCallback(
    async (requestId: number, diff?: ScoreDiff) => {
      try {
        const response = await score(diff ? { diff } : {});
        applyScorePayload(requestId, response);
      } catch (error) {
        console.error("Score request failed", error);
        handleRequestError();
      }
    },
    [applyScorePayload, handleRequestError]
  );

  const queueScoreRequest = useCallback(
    (diff: ScoreDiff) => {
      const nextRequestId = requestIdRef.current + 1;
      requestIdRef.current = nextRequestId;
      latestAppliedRequestRef.current = nextRequestId;
      setIsScoring(true);
      lastDiffRef.current = diff;
      pendingHighlightResidueRef.current = diff.res_idx;

      const worker = workerRef.current;
      if (worker) {
        worker.postMessage({ requestId: nextRequestId, diff });
      } else {
        void directRequest(nextRequestId, diff);
      }
    },
    [directRequest, workerRef]
  );
  queueScoreRequestRef.current = queueScoreRequest;

  const handleWorkerMessage = useCallback(
    (message: WorkerMessage) => {
      if (message.requestId !== latestAppliedRequestRef.current) {
        if (message.requestId > latestAppliedRequestRef.current) {
          latestAppliedRequestRef.current = message.requestId;
        }
        return;
      }

      if (message.status === "success") {
        applyScorePayload(message.requestId, message.response, {
          heatmap: message.heatmap,
        });
      } else {
        setIsScoring(false);
        setToastMessage("Score update failed; retrying…");
        if (!hasRetriedRef.current && interactingRef.current) {
          hasRetriedRef.current = true;
          if (retryTokenRef.current) {
            window.clearTimeout(retryTokenRef.current);
          }
          retryTokenRef.current = window.setTimeout(() => {
            const queue = queueScoreRequestRef.current;
            if (queue && lastDiffRef.current) {
              queue(lastDiffRef.current);
            }
          }, 250);
        }
      }
    },
    [applyScorePayload]
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const worker = new Worker(new URL("../workers/scoreWorker.ts", import.meta.url), {
      type: "module",
    });

    workerRef.current = worker;

    const listener = (event: MessageEvent<WorkerMessage>) => {
      handleWorkerMessage(event.data);
    };

    worker.addEventListener("message", listener);

    return () => {
      worker.removeEventListener("message", listener);
      worker.terminate();
      workerRef.current = null;
    };
  }, [handleWorkerMessage]);

  const debouncedScore = useDebouncedCallback((diff: ScoreDiff) => {
    queueScoreRequest(diff);
  }, 150);

  const ensureInitialScore = useCallback(() => {
    if (perResidue.length === 0 && !isScoring) {
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      latestAppliedRequestRef.current = requestId;
      setIsScoring(true);
      const worker = workerRef.current;
      if (worker) {
        worker.postMessage({ requestId });
      } else {
        void directRequest(requestId);
      }
    }
  }, [directRequest, isScoring, perResidue.length, workerRef]);

  useEffect(() => {
    ensureInitialScore();
  }, [ensureInitialScore]);

  const handleResidueSelect = useCallback((resIdx: number) => {
    setSelectedResidue(resIdx);
  }, []);

  const handleAngleChange = useCallback(
    (key: keyof Angles) =>
      (event: ChangeEvent<HTMLInputElement>) => {
        const value = Number(event.target.value);
        setAngles((prev) => {
          const nextAngles = { ...prev, [key]: value };
          const deltaPhi = key === "phi" ? value - prev.phi : 0;
          const deltaPsi = key === "psi" ? value - prev.psi : 0;
          const residueIdx =
            selectedResidue ?? perResidue[0]?.idx ?? 0;
          setSelectedResidue((current) => current ?? residueIdx);
          const diff: ScoreDiff = {
            res_idx: residueIdx,
            move: {
              type: "torsion",
              delta: {
                phi: deltaPhi,
                psi: deltaPsi,
              },
            },
          };
          handleInteractionPulse();
          debouncedScore(diff);
          return nextAngles;
        });
      },
    [debouncedScore, handleInteractionPulse, perResidue, selectedResidue]
  );

  const handleRotamerChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const rawValue = event.target.value;
      const value = rawValue === "" ? null : Number(rawValue);
      setRotamerId(value);
      if (value === null || Number.isNaN(value)) {
        return;
      }
      const residueIdx = selectedResidue ?? perResidue[0]?.idx ?? 0;
      if (selectedResidue === null) {
        setSelectedResidue(residueIdx);
      }
      const diff: ScoreDiff = {
        res_idx: residueIdx,
        move: {
          type: "rotamer",
          rotamer_id: value,
        },
      };
      handleInteractionPulse();
      debouncedScore(diff);
    },
    [debouncedScore, handleInteractionPulse, perResidue, selectedResidue]
  );

  const handleNudgeRequest = useCallback(async () => {
    setNudgeState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const response = await nudge();
      const suggestion: NudgeSuggestion = {
        resIdx: response.res_idx,
        move: response.move,
        expectedDelta: response.expected_delta_score,
        termDeltas: response.term_deltas,
        modelUsed: response.model_used,
      };
      setNudgeState({
        loading: false,
        suggestion,
        applying: false,
        error: null,
      });
    } catch (error) {
      console.error("Nudge request failed", error);
      setToastMessage("Couldn't fetch nudge. Try again.");
      setNudgeState((prev) => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  }, []);

  const handleNudgeCancel = useCallback(() => {
    setNudgeState((prev) => ({
      ...prev,
      suggestion: null,
      applying: false,
    }));
  }, []);

  const handleNudgeConfirm = useCallback(async () => {
    if (!nudgeState.suggestion) {
      return;
    }
    const suggestion = nudgeState.suggestion;
    setNudgeState((prev) => ({ ...prev, applying: true, error: null }));

    const move = suggestion.move;
    let diff: ScoreDiff;
    if (move.type === "torsion") {
      const delta = move.delta ?? {};
      diff = {
        res_idx: suggestion.resIdx,
        move: {
          type: "torsion",
          delta: {
            ...(typeof delta.phi === "number" ? { phi: delta.phi } : {}),
            ...(typeof delta.psi === "number" ? { psi: delta.psi } : {}),
          },
        },
      };
    } else {
      diff = {
        res_idx: suggestion.resIdx,
        move: {
          type: "rotamer",
          rotamer_id: move.rotamer_id,
        },
      };
    }

    const nextRequestId = requestIdRef.current + 1;
    requestIdRef.current = nextRequestId;
    latestAppliedRequestRef.current = nextRequestId;
    setIsScoring(true);
    lastDiffRef.current = diff;
    pendingHighlightResidueRef.current = diff.res_idx;
    try {
      const response = await score({ diff });
      applyScorePayload(nextRequestId, response, { highlightResidue: diff.res_idx });
    } catch (error) {
      console.error("Apply nudge failed", error);
      setToastMessage("Apply failed.");
      setIsScoring(false);
      pendingHighlightResidueRef.current = null;
    } finally {
      setNudgeState({
        loading: false,
        suggestion: null,
        applying: false,
        error: null,
      });
    }
  }, [applyScorePayload, nudgeState.suggestion]);

  const selectedResidueTerms = useMemo(() => {
    if (selectedResidue === null) {
      return null;
    }
    return perResidue.find((res) => res.idx === selectedResidue) ?? null;
  }, [perResidue, selectedResidue]);

  const rotamerOptions = useMemo(() => Array.from({ length: 6 }, (_, index) => index + 1), []);

  return (
    <div className="play-screen">
      <div className="play-screen__grid">
        <section className="play-screen__viewer" aria-label="3D Viewer">
          <header className="play-screen__viewer-header">
            <div className="play-screen__viewer-title">
              <h1>Folding Workspace</h1>
              {isScoring ? <span className="play-screen__badge">Scoring…</span> : null}
            </div>
            <div className="play-screen__viewer-actions">
              <AINudgeButton
                anchorRef={nudgeButtonRef}
                disabled={isScoring || Boolean(nudgeState.suggestion)}
                loading={nudgeState.loading}
                applying={nudgeState.applying}
                suggestion={nudgeState.suggestion}
                onRequest={handleNudgeRequest}
                onConfirm={handleNudgeConfirm}
                onCancel={handleNudgeCancel}
              />
              <SubmitButton
                levelId={levelId ?? ""}
                sequence={sequence ?? ""}
                coords={submitCoords}
                elapsedMs={computeElapsedMs}
                playerName={playerName}
                disabled={!structureLoaded || isScoring}
                onSuccess={handleSubmitSuccess}
                onError={handleSubmitError}
              />
            </div>
          </header>
          {coordsNotice ? (
            <div
              className={
                coordsNotice.tone === "error"
                  ? "play-screen__coords-alert play-screen__coords-alert--error"
                  : "play-screen__coords-alert"
              }
            >
              <span>{coordsNotice.message}</span>
              {coordsNotice.tone === "error" && onRetryCoords ? (
                <button type="button" onClick={onRetryCoords}>
                  Retry download
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="play-screen__scene">
            <ProteinViewer
              residues={structureResidues ?? []}
              selectedResidue={selectedResidue}
              onSelectResidue={handleResidueSelect}
            />
          </div>
          <div className="play-screen__controls">
            <label className="play-screen__control">
              <span>φ (Phi)</span>
              <input
                type="range"
                min={-180}
                max={180}
                step={1}
                value={angles.phi}
                onChange={handleAngleChange("phi")}
              />
              <output>{angles.phi.toFixed(1)}°</output>
            </label>
            <label className="play-screen__control">
              <span>ψ (Psi)</span>
              <input
                type="range"
                min={-180}
                max={180}
                step={1}
                value={angles.psi}
                onChange={handleAngleChange("psi")}
              />
              <output>{angles.psi.toFixed(1)}°</output>
            </label>
            <label className="play-screen__control">
              <span>Rotamer</span>
              <select value={rotamerId ?? ""} onChange={handleRotamerChange}>
                <option value="" disabled>
                  Select rotamer
                </option>
                {rotamerOptions.map((option) => (
                  <option key={option} value={option}>
                    Rotamer {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="play-screen__heatmap">
            <ResidueHeatmapOverlay
              values={heatmapValues}
              selectedResidue={selectedResidue}
              onSelect={handleResidueSelect}
              residueLabels={perResidue.map((res) => res.idx)}
            />
          </div>
        </section>
        <div className="play-screen__sidebar">
          <ScoreBars
            totalScore={totalScore}
            terms={termTotals}
            isScoring={isScoring}
            highlightedTerms={highlightedTerms}
          />
          <ResiduePanel
            residue={selectedResidueTerms}
            isScoring={isScoring}
            angles={selectedResidue !== null ? angles : null}
            rotamerId={rotamerId}
            errorMessage={toastMessage}
            highlight={highlightedResidue}
          />
        </div>
      </div>
      {submitModalOpen && submissionResult ? (
        <div className="submit-modal" role="dialog" aria-modal="true">
          <div className="submit-modal__backdrop" onClick={handleModalClose} />
          <div className="submit-modal__card">
            <h2>Submitted!</h2>
            <p>
              Score {submissionResult.score.toFixed(2)} (rank #{submissionResult.rank} of
              {" "}
              {submissionResult.entries})
            </p>
            <div className="submit-modal__actions">
              <button type="button" onClick={handleModalClose}>
                Close
              </button>
              {levelId ? (
                <button
                  type="button"
                  className="submit-modal__primary"
                  onClick={() => {
                    setSubmitModalOpen(false);
                    router.push(`/leaderboard/${levelId}`);
                  }}
                >
                  View Leaderboard
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
      {toastMessage ? <div className="play-screen__toast">{toastMessage}</div> : null}
      <style jsx>{`
        .play-screen {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1.5rem;
          color: #e2e8f0;
          background: #0f172a;
          min-height: 100vh;
        }

        .play-screen__grid {
          display: grid;
          grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
          gap: 1.5rem;
          flex: 1;
        }

        .play-screen__viewer {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1.25rem;
          border-radius: 1rem;
          background: rgba(15, 23, 42, 0.9);
          box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.1);
        }

        .play-screen__viewer-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }

        .play-screen__viewer-title {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .play-screen__viewer-actions {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .play-screen__coords-alert {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.6rem 0.9rem;
          border-radius: 0.75rem;
          background: rgba(59, 130, 246, 0.12);
          color: #bfdbfe;
          font-size: 0.95rem;
        }

        .play-screen__coords-alert button {
          margin-left: auto;
          padding: 0.25rem 0.75rem;
          border-radius: 9999px;
          background: rgba(14, 165, 233, 0.2);
          color: #bae6fd;
          border: 1px solid rgba(125, 211, 252, 0.4);
          cursor: pointer;
        }

        .play-screen__coords-alert button:hover {
          background: rgba(14, 165, 233, 0.32);
        }

        .play-screen__coords-alert--error {
          background: rgba(248, 113, 113, 0.14);
          color: #fecaca;
          border: 1px solid rgba(248, 113, 113, 0.3);
        }

        .play-screen__coords-alert--error button {
          background: rgba(248, 113, 113, 0.18);
          color: #fecaca;
          border-color: rgba(252, 165, 165, 0.4);
        }

        .play-screen__scene {
          width: 100%;
          aspect-ratio: 16 / 10;
          min-height: 18rem;
        }


        .play-screen__viewer-header h1 {
          margin: 0;
          font-size: 1.5rem;
        }

        .play-screen__badge {
          padding: 0.25rem 0.75rem;
          border-radius: 9999px;
          background: rgba(59, 130, 246, 0.2);
          color: #93c5fd;
          font-size: 0.85rem;
        }

        .play-screen__controls {
          display: grid;
          gap: 1rem;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        }

        .play-screen__control {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          font-size: 0.95rem;
        }

        .play-screen__control input[type="range"] {
          width: 100%;
        }

        .play-screen__control output {
          font-variant-numeric: tabular-nums;
          color: #93c5fd;
        }

        .play-screen__heatmap {
          flex: 1;
          min-height: 200px;
        }

        .play-screen__sidebar {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .play-screen__toast {
          align-self: center;
          padding: 0.5rem 1rem;
          border-radius: 9999px;
          background: rgba(248, 113, 113, 0.16);
          color: #fca5a5;
          font-size: 0.95rem;
        }

        .submit-modal {
          position: fixed;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 20;
        }

        .submit-modal__backdrop {
          position: absolute;
          inset: 0;
          background: rgba(15, 23, 42, 0.8);
        }

        .submit-modal__card {
          position: relative;
          background: rgba(15, 23, 42, 0.95);
          border-radius: 1rem;
          padding: 1.5rem;
          box-shadow: 0 20px 45px rgba(15, 23, 42, 0.5);
          border: 1px solid rgba(148, 163, 184, 0.2);
          min-width: 320px;
          max-width: 90vw;
        }

        .submit-modal__card h2 {
          margin-top: 0;
          margin-bottom: 0.5rem;
        }

        .submit-modal__card p {
          margin: 0 0 1rem;
          font-variant-numeric: tabular-nums;
        }

        .submit-modal__actions {
          display: flex;
          justify-content: flex-end;
          gap: 0.75rem;
        }

        .submit-modal__actions button {
          padding: 0.5rem 1rem;
          border-radius: 9999px;
          border: none;
          background: rgba(148, 163, 184, 0.2);
          color: #e2e8f0;
          cursor: pointer;
        }

        .submit-modal__actions button:hover {
          background: rgba(148, 163, 184, 0.3);
        }

        .submit-modal__primary {
          background: linear-gradient(135deg, #38bdf8, #6366f1);
          color: #0f172a;
          font-weight: 600;
        }

        @media (max-width: 1024px) {
          .play-screen__grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};
