/// <reference lib="webworker" />

import { calculateHeatmap, score, ScoreDiff, ScoreResponse } from "../lib/api";

type ScoreWorkerRequest = {
  requestId: number;
  diff?: ScoreDiff;
};

type ScoreWorkerSuccess = {
  requestId: number;
  status: "success";
  response: ScoreResponse;
  heatmap: number[];
};

type ScoreWorkerError = {
  requestId: number;
  status: "error";
  message: string;
};

type ScoreWorkerMessage = ScoreWorkerSuccess | ScoreWorkerError;

const ctx = self as unknown as DedicatedWorkerGlobalScope;

ctx.onmessage = async (event: MessageEvent<ScoreWorkerRequest>) => {
  const { requestId, diff } = event.data;

  try {
    const response = await score(diff ? { diff } : {});
    const { values } = calculateHeatmap(response.per_residue);

    const payload: ScoreWorkerSuccess = {
      requestId,
      status: "success",
      response,
      heatmap: values,
    };

    ctx.postMessage(payload satisfies ScoreWorkerMessage);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error while scoring";

    const payload: ScoreWorkerError = {
      requestId,
      status: "error",
      message,
    };

    ctx.postMessage(payload satisfies ScoreWorkerMessage);
  }
};
