export type ScoreTerms = {
  clash: number;
  rama: number;
  rotamer: number;
  ss: number;
  compact: number;
  hbond: number;
};

export type PerResidueTerm = {
  idx: number;
  clash: number;
  rama: number;
  rotamer: number;
  ss: number;
};

export type ScoreResponse = {
  score: number;
  terms: ScoreTerms;
  per_residue: PerResidueTerm[];
};

export type TorsionMove = {
  type: "torsion";
  delta: {
    phi: number;
    psi: number;
  };
};

export type RotamerMove = {
  type: "rotamer";
  rotamer_id: number;
};

export type ScoreMove = TorsionMove | RotamerMove;

export type ScoreDiff = {
  res_idx: number;
  move: ScoreMove;
};

export type ScoreRequestBody = {
  diff?: ScoreDiff;
};

const SCORE_ENDPOINT = "/api/score";

export async function score(body: ScoreRequestBody): Promise<ScoreResponse> {
  const response = await fetch(SCORE_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Score request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as ScoreResponse;
  return payload;
}

export type HeatmapPayload = {
  values: number[];
  min: number;
  max: number;
};

export function calculateHeatmap(perResidue: PerResidueTerm[]): HeatmapPayload {
  if (perResidue.length === 0) {
    return { values: [], min: 0, max: 0 };
  }

  const penalties = perResidue.map((r) => Math.max(0, r.clash + r.rama + r.rotamer + r.ss));
  const minPenalty = Math.min(...penalties);
  const maxPenalty = Math.max(...penalties);

  if (maxPenalty === minPenalty) {
    return {
      values: penalties.map(() => 0),
      min: minPenalty,
      max: maxPenalty,
    };
  }

  const normalized = penalties.map((value) => (value - minPenalty) / (maxPenalty - minPenalty));

  return {
    values: normalized,
    min: minPenalty,
    max: maxPenalty,
  };
}
