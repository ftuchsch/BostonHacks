import { parseResidueCoordinates, type ResidueCoordinate } from "./structures";

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
  stats?: ScoreStats;
  structure?: ResidueCoordinate[];
};

export type ScoreStats = {
  term_eval_calls: Record<string, number>;
  full_passes: number;
  incremental_passes: number;
};

export type SubmitRequest = {
  level_id: string;
  sequence: string;
  coords: number[][];
  elapsed_ms?: number;
  player_name?: string;
  client_version?: string;
};

export type SubmitResponse = {
  score: number;
  terms: ScoreTerms;
  rank: number;
  entries: number;
};

export type LeaderboardItem = {
  rank: number;
  player_name: string;
  score: number;
  elapsed_ms?: number;
  ts: string;
};

export type LeaderboardResponse = {
  level_id: string;
  items: LeaderboardItem[];
  total_entries: number;
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
  note?: string;
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
const SUBMIT_ENDPOINT = "/api/submit";
const LEADERBOARD_ENDPOINT = "/api/leaderboard";

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

  const payload = (await response.json()) as Record<string, unknown>;
  return normaliseScoreResponse(payload);
}

const SCORE_TERM_KEYS: Array<keyof ScoreTerms> = [
  "clash",
  "rama",
  "rotamer",
  "ss",
  "compact",
  "hbond",
];

function coerceNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function normaliseTerms(raw: unknown): ScoreTerms {
  const source =
    raw && typeof raw === "object"
      ? (raw as Record<string, unknown>)
      : ({} as Record<string, unknown>);
  return {
    clash: coerceNumber(source.clash),
    rama: coerceNumber(source.rama),
    rotamer: coerceNumber(source.rotamer),
    ss: coerceNumber(source.ss),
    compact: coerceNumber(source.compact),
    hbond: coerceNumber(source.hbond),
  };
}

function normaliseLegacyResidue(entry: unknown, fallbackIdx: number): PerResidueTerm | null {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const payload = entry as Record<string, unknown>;
  const idxCandidate = payload.idx ?? payload.i ?? fallbackIdx;
  const idx = coerceNumber(idxCandidate, fallbackIdx);
  return {
    idx,
    clash: coerceNumber(payload.clash),
    rama: coerceNumber(payload.rama),
    rotamer: coerceNumber(payload.rotamer),
    ss: coerceNumber(payload.ss),
  };
}

function normaliseCacheResidue(idxKey: string, entry: unknown): PerResidueTerm | null {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const idx = Number.parseInt(idxKey, 10);
  const payload = entry as Record<string, unknown>;
  const termsSource =
    payload.terms && typeof payload.terms === "object"
      ? (payload.terms as Record<string, unknown>)
      : payload;
  const resolvedIdx = Number.isNaN(idx)
    ? coerceNumber(payload.idx, 0)
    : idx;
  return {
    idx: resolvedIdx,
    clash: coerceNumber(termsSource.clash),
    rama: coerceNumber(termsSource.rama),
    rotamer: coerceNumber(termsSource.rotamer),
    ss: coerceNumber(termsSource.ss),
  };
}

function normalisePerResidue(raw: unknown): PerResidueTerm[] {
  if (Array.isArray(raw)) {
    return raw
      .map((entry, index) => normaliseLegacyResidue(entry, index))
      .filter((entry): entry is PerResidueTerm => entry !== null)
      .sort((a, b) => a.idx - b.idx);
  }

  if (raw && typeof raw === "object") {
    return Object.entries(raw as Record<string, unknown>)
      .map(([idx, entry]) => normaliseCacheResidue(idx, entry))
      .filter((entry): entry is PerResidueTerm => entry !== null)
      .sort((a, b) => a.idx - b.idx);
  }

  return [];
}

function normaliseStats(raw: unknown): ScoreStats | undefined {
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const payload = raw as Record<string, unknown>;
  const termCallsRaw =
    payload.term_eval_calls && typeof payload.term_eval_calls === "object"
      ? (payload.term_eval_calls as Record<string, unknown>)
      : {};
  const term_eval_calls: Record<string, number> = {};
  SCORE_TERM_KEYS.forEach((key) => {
    if (key in termCallsRaw) {
      term_eval_calls[key] = coerceNumber(termCallsRaw[key]);
    }
  });
  Object.entries(termCallsRaw).forEach(([key, value]) => {
    if (!(key in term_eval_calls)) {
      term_eval_calls[key] = coerceNumber(value);
    }
  });
  return {
    term_eval_calls,
    full_passes: coerceNumber(payload.full_passes),
    incremental_passes: coerceNumber(payload.incremental_passes),
  };
}

function normaliseScoreResponse(raw: Record<string, unknown>): ScoreResponse {
  const perResidue = normalisePerResidue(raw.per_residue);
  const terms = normaliseTerms(raw.terms);
  const stats = normaliseStats(raw.stats);
  const response: ScoreResponse = {
    score: coerceNumber(raw.score),
    terms,
    per_residue: perResidue,
  };
  if (stats) {
    response.stats = stats;
  }
  const structurePayload = parseResidueCoordinates({ residues: raw["structure"] });
  if (structurePayload && structurePayload.length > 0) {
    response.structure = structurePayload;
  }
  return response;
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

export async function submit(payload: SubmitRequest): Promise<SubmitResponse> {
  const response = await fetch(SUBMIT_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleJsonResponse<SubmitResponse>(response, "Submission failed");
}

export async function getLeaderboard(
  levelId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<LeaderboardResponse> {
  const query = new URLSearchParams({ level_id: levelId });
  if (typeof params.limit === "number") {
    query.set("limit", String(params.limit));
  }
  if (typeof params.offset === "number") {
    query.set("offset", String(params.offset));
  }

  const response = await fetch(`${LEADERBOARD_ENDPOINT}?${query.toString()}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  return handleJsonResponse<LeaderboardResponse>(
    response,
    `Failed to load leaderboard for ${levelId}`
  );
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
