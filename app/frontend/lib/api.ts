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

export type NudgeMove =
  | {
      type: "torsion";
      delta: { phi?: number; psi?: number };
    }
  | {
      type: "rotamer";
      rotamer_id: number;
    };

export type NudgeResponse = {
  res_idx: number;
  move: NudgeMove;
  expected_delta_score: number;
  term_deltas: ScoreTerms;
  model_used: boolean;
};

export type TorsionMove = {
  type: "torsion";
  delta: {
    phi?: number;
    psi?: number;
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

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body ?? null;
  }
}

export type LevelSummary = {
  id: string;
  name: string;
  difficulty: "easy" | "medium" | "hard";
  length: number;
  preview_img_url?: string;
  tags?: string[];
  short_desc?: string;
};

export type Contact = {
  i: number;
  j: number;
  type?: string;
};

export type Level = {
  id: string;
  name: string;
  difficulty: "easy" | "medium" | "hard";
  length: number;
  sequence: string;
  start_coords_url: string;
  target_ss: string;
  target_contacts?: Contact[];
  tips?: string[];
  preview_img_url?: string;
  version?: number;
};

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

async function handleJsonResponse<T>(
  response: Response,
  errorMessage: string
): Promise<T> {
  if (response.ok) {
    return parseJsonResponse<T>(response);
  }

  let body: unknown = null;
  try {
    body = await parseJsonResponse<unknown>(response);
  } catch (error) {
    body = null;
  }

  throw new ApiError(errorMessage, response.status, body);
}

const LEVELS_ENDPOINT = "/api/levels";

export async function getLevels(): Promise<LevelSummary[]> {
  const response = await fetch(LEVELS_ENDPOINT, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  return handleJsonResponse<LevelSummary[]>(response, "Failed to load levels");
}

export async function getLevel(id: string): Promise<Level> {
  const response = await fetch(`${LEVELS_ENDPOINT}/${id}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  return handleJsonResponse<Level>(
    response,
    `Failed to load level ${id}`
  );
}

const SCORE_ENDPOINT = "/api/score";
const NUDGE_ENDPOINT = "/api/nudge";

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

export async function nudge(): Promise<NudgeResponse> {
  const response = await fetch(NUDGE_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error(`Nudge request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as NudgeResponse;
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
