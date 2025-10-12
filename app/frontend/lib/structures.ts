export type AtomCoordinate = {
  name: string;
  element?: string;
  coords: [number, number, number];
};

export type ResidueCoordinate = {
  index: number;
  name?: string;
  coords: [number, number, number];
  atoms?: AtomCoordinate[];
};

export function createLinearBackbone(sequence: string): ResidueCoordinate[] {
  const residues: ResidueCoordinate[] = [];
  if (!sequence || sequence.length === 0) {
    return residues;
  }

  const helixRadius = 2.3;
  const risePerResidue = 1.5;
  const turnAngle = (Math.PI * 2) / 3.6; // ~100° per residue

  const caPositions: [number, number, number][] = [];

  for (let idx = 0; idx < sequence.length; idx += 1) {
    const theta = idx * turnAngle;
    const x = helixRadius * Math.cos(theta);
    const y = helixRadius * Math.sin(theta);
    const z = idx * risePerResidue;
    caPositions.push([x, y, z]);
  }

  const addVec = (
    base: [number, number, number],
    dx: number,
    dy: number,
    dz: number
  ): [number, number, number] =>
    [
      Math.round((base[0] + dx) * 1e3) / 1e3,
      Math.round((base[1] + dy) * 1e3) / 1e3,
      Math.round((base[2] + dz) * 1e3) / 1e3,
    ] as [number, number, number];

  const normalise = (
    vector: [number, number, number],
    fallback: [number, number, number]
  ): [number, number, number] => {
    const [vx, vy, vz] = vector;
    const length = Math.sqrt(vx * vx + vy * vy + vz * vz);
    if (length < 1e-6) {
      return fallback;
    }
    return [vx / length, vy / length, vz / length];
  };

  for (let idx = 0; idx < sequence.length; idx += 1) {
    const residueName = sequence[idx];
    const ca = caPositions[idx];
    const prev = caPositions[Math.max(0, idx - 1)];
    const next = caPositions[Math.min(sequence.length - 1, idx + 1)];

    const tangent = normalise(
      [next[0] - prev[0], next[1] - prev[1], next[2] - prev[2]],
      [0, 0, 1]
    );
    const radial = normalise([ca[0], ca[1], 0], [1, 0, 0]);
    const binormal = normalise(
      [
        tangent[1] * radial[2] - tangent[2] * radial[1],
        tangent[2] * radial[0] - tangent[0] * radial[2],
        tangent[0] * radial[1] - tangent[1] * radial[0],
      ],
      [0, 0, 1]
    );

    const nLength = 1.46;
    const cLength = 1.53;
    const cbLength = 1.53;

    const caRounded: [number, number, number] = [
      Math.round(ca[0] * 1e3) / 1e3,
      Math.round(ca[1] * 1e3) / 1e3,
      Math.round(ca[2] * 1e3) / 1e3,
    ];

    const n = addVec(
      ca,
      -tangent[0] * nLength + binormal[0] * 0.12,
      -tangent[1] * nLength + binormal[1] * 0.12,
      -tangent[2] * nLength + binormal[2] * 0.12
    );
    const c = addVec(
      ca,
      tangent[0] * cLength,
      tangent[1] * cLength,
      tangent[2] * cLength
    );
    const o = addVec(
      c,
      -tangent[0] * 0.34 - radial[0] * 0.6,
      -tangent[1] * 0.34 - radial[1] * 0.6,
      -tangent[2] * 0.34 - radial[2] * 0.6
    );
    const cb = addVec(
      ca,
      radial[0] * cbLength + binormal[0] * 0.5,
      radial[1] * cbLength + binormal[1] * 0.5,
      radial[2] * cbLength + binormal[2] * 0.5
    );

    residues.push({
      index: idx,
      name: residueName,
      coords: caRounded,
      atoms: [
        { name: "N", element: "N", coords: n },
        { name: "CA", element: "C", coords: caRounded },
        { name: "C", element: "C", coords: c },
        { name: "O", element: "O", coords: o },
        { name: "CB", element: "C", coords: cb },
      ],
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

  data.residues.forEach((entry: unknown, idx: number) => {
    if (!entry || typeof entry !== "object") {
      return;
    }
    const raw = entry as {
      index?: unknown;
      name?: unknown;
      coords?: unknown;
      atoms?: unknown;
    };

    if (!Array.isArray(raw.coords) || raw.coords.length < 3) {
      return;
    }

    const coordsArray = raw.coords.slice(0, 3).map((value) => Number(value));
    if (coordsArray.some((value) => Number.isNaN(value) || !Number.isFinite(value))) {
      return;
    }
    const coords: [number, number, number] = [
      coordsArray[0],
      coordsArray[1],
      coordsArray[2],
    ];

    const index =
      typeof raw.index === "number" && Number.isFinite(raw.index)
        ? raw.index
        : idx;
    const residueName =
      typeof raw.name === "string" && raw.name.trim().length > 0
        ? raw.name.trim()
        : undefined;

    let atoms: AtomCoordinate[] | undefined;

    if (Array.isArray(raw.atoms)) {
      const parsedAtoms: AtomCoordinate[] = [];
      raw.atoms.forEach((atomEntry: unknown) => {
        if (!atomEntry || typeof atomEntry !== "object") {
          return;
        }
        const atom = atomEntry as {
          name?: unknown;
          element?: unknown;
          coords?: unknown;
        };

        if (typeof atom.name !== "string") {
          return;
        }
        if (!Array.isArray(atom.coords) || atom.coords.length < 3) {
          return;
        }

        const atomCoordsArray = atom.coords
          .slice(0, 3)
          .map((value) => Number(value));
        if (atomCoordsArray.some((value) => Number.isNaN(value) || !Number.isFinite(value))) {
          return;
        }
        const atomCoords: [number, number, number] = [
          atomCoordsArray[0],
          atomCoordsArray[1],
          atomCoordsArray[2],
        ];

        parsedAtoms.push({
          name: atom.name,
          element:
            typeof atom.element === "string" && atom.element.trim().length > 0
              ? atom.element.trim()
              : undefined,
          coords: atomCoords,
        });
      });

      if (parsedAtoms.length > 0) {
        atoms = parsedAtoms;
      }
    }

    residues.push({
      index,
      name: residueName,
      coords,
      atoms,
    });
  });

  if (residues.length === 0) {
    return null;
  }

  residues.sort((a, b) => a.index - b.index);

  return residues;
}
