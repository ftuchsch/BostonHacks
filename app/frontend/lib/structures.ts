export type ResidueCoordinate = {
  index: number;
  name?: string;
  coords: [number, number, number];
};

export function createLinearBackbone(sequence: string): ResidueCoordinate[] {
  const residues: ResidueCoordinate[] = [];
  const spacing = 3.8;

  for (let idx = 0; idx < sequence.length; idx += 1) {
    const origin = idx * spacing;
    residues.push({
      index: idx,
      name: sequence[idx],
      coords: [origin, 0, 0],
    });
  }

  return residues;
}

export function parseResidueCoordinates(payload: unknown): ResidueCoordinate[] | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const data = payload as { residues?: unknown };
  if (!Array.isArray(data.residues)) {
    return null;
  }

  const residues: ResidueCoordinate[] = [];

  data.residues.forEach((entry, idx) => {
    if (!entry || typeof entry !== "object") {
      return;
    }
    const raw = entry as {
      index?: unknown;
      name?: unknown;
      coords?: unknown;
    };

    if (!Array.isArray(raw.coords) || raw.coords.length < 3) {
      return;
    }

    const coords = raw.coords.slice(0, 3).map((value) => Number(value));
    if (coords.some((value) => Number.isNaN(value) || !Number.isFinite(value))) {
      return;
    }

    const index =
      typeof raw.index === "number" && Number.isFinite(raw.index)
        ? raw.index
        : idx;
    const residueName =
      typeof raw.name === "string" && raw.name.trim().length > 0
        ? raw.name.trim()
        : undefined;

    residues.push({
      index,
      name: residueName,
      coords: [coords[0], coords[1], coords[2]],
    });
  });

  if (residues.length === 0) {
    return null;
  }

  residues.sort((a, b) => a.index - b.index);

  return residues;
}
