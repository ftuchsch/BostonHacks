"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";

import type { ResidueCoordinate } from "../lib/structures";

type ProteinViewerProps = {
  residues: ResidueCoordinate[];
  selectedResidue?: number | null;
  onSelectResidue?: (index: number) => void;
};

type Rotation = {
  yaw: number;
  pitch: number;
};

type AtomInfo = {
  id: number;
  residueIndex: number;
  name: string;
  element: string;
  coords: [number, number, number];
};

type BondType = "backbone" | "sidechain" | "carbonyl";

type BondInfo = {
  startId: number;
  endId: number;
  type: BondType;
};

type ProjectedCA = {
  residueIndex: number;
  x: number;
  y: number;
  z: number;
};

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const ZOOM_RANGE: [number, number] = [0.6, 2.8];
const INITIAL_ROTATION: Rotation = { yaw: Math.PI / 6, pitch: -Math.PI / 8 };

const ATOM_RADII: Record<string, number> = {
  C: 0.6,
  N: 0.58,
  O: 0.55,
  S: 0.75,
  H: 0.4,
};

const ATOM_COLORS: Record<string, [number, number, number]> = {
  C: [203, 213, 225],
  N: [56, 189, 248],
  O: [248, 113, 113],
  S: [250, 204, 21],
  H: [241, 245, 249],
};

const BOND_COLORS: Record<BondType, [number, number, number]> = {
  backbone: [148, 163, 184],
  sidechain: [165, 180, 203],
  carbonyl: [244, 114, 182],
};

const BOND_WIDTH: Record<BondType, number> = {
  backbone: 7,
  sidechain: 5.5,
  carbonyl: 4,
};

const clampChannel = (value: number): number => Math.max(0, Math.min(255, value));

const scaleColour = (
  colour: [number, number, number],
  factor: number
): [number, number, number] => [
  clampChannel(colour[0] * factor),
  clampChannel(colour[1] * factor),
  clampChannel(colour[2] * factor),
];

const offsetColour = (
  colour: [number, number, number],
  offset: number
): [number, number, number] => [
  clampChannel(colour[0] + offset),
  clampChannel(colour[1] + offset),
  clampChannel(colour[2] + offset),
];

const getResidueAtoms = (residue: ResidueCoordinate) => {
  if (Array.isArray(residue.atoms) && residue.atoms.length > 0) {
    return residue.atoms;
  }
  return [
    {
      name: "CA",
      element: "C",
      coords: residue.coords,
    },
  ];
};

const colourString = ([r, g, b]: [number, number, number], alpha = 1) =>
  `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;

export function ProteinViewer({
  residues,
  selectedResidue = null,
  onSelectResidue,
}: ProteinViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const draggingRef = useRef(false);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
  const projectedCARef = useRef<ProjectedCA[]>([]);
  const frameRef = useRef<number | null>(null);

  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [rotation, setRotation] = useState<Rotation>(INITIAL_ROTATION);
  const [zoom, setZoom] = useState(1);

  const residueData = useMemo(() => residues ?? [], [residues]);

  const structure = useMemo(() => {
    const atoms: AtomInfo[] = [];
    const bonds: BondInfo[] = [];
    const residueAtomMap = new Map<number, Map<string, AtomInfo>>();

    let nextId = 0;
    residueData.forEach((residue) => {
      const atomMap = new Map<string, AtomInfo>();
      const atomsForResidue = getResidueAtoms(residue);
      atomsForResidue.forEach((atom) => {
        const element = (atom.element ?? atom.name[0] ?? "C").toUpperCase();
        const coords: [number, number, number] = [
          Number(atom.coords[0]),
          Number(atom.coords[1]),
          Number(atom.coords[2]),
        ];
        const info: AtomInfo = {
          id: nextId,
          residueIndex: residue.index,
          name: atom.name,
          element,
          coords,
        };
        nextId += 1;
        atoms.push(info);
        atomMap.set(atom.name, info);
      });
      residueAtomMap.set(residue.index, atomMap);
    });

    const connect = (
      residueIdxA: number,
      atomA: string,
      residueIdxB: number,
      atomB: string,
      type: BondType
    ) => {
      const entryA = residueAtomMap.get(residueIdxA)?.get(atomA);
      const entryB = residueAtomMap.get(residueIdxB)?.get(atomB);
      if (entryA && entryB) {
        bonds.push({ startId: entryA.id, endId: entryB.id, type });
      }
    };

    residueData.forEach((residue, idx) => {
      connect(residue.index, "N", residue.index, "CA", "backbone");
      connect(residue.index, "CA", residue.index, "C", "backbone");
      connect(residue.index, "C", residue.index, "O", "carbonyl");
      connect(residue.index, "CA", residue.index, "CB", "sidechain");
      const nextResidue = residueData[idx + 1];
      if (nextResidue) {
        connect(residue.index, "C", nextResidue.index, "N", "backbone");
      }
    });

    return { atoms, bonds };
  }, [residueData]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return () => undefined;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      const { width, height } = entry.contentRect;
      setDimensions((prev) => {
        if (
          Math.abs(prev.width - width) < 0.5 &&
          Math.abs(prev.height - height) < 0.5
        ) {
          return prev;
        }
        return { width, height };
      });
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
    };
  }, []);

  const renderScene = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const { width, height } = dimensions;
    const dpr = window.devicePixelRatio || 1;
    const scaledWidth = Math.max(1, Math.floor(width * dpr));
    const scaledHeight = Math.max(1, Math.floor(height * dpr));
    if (canvas.width !== scaledWidth || canvas.height !== scaledHeight) {
      canvas.width = scaledWidth;
      canvas.height = scaledHeight;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }

    context.save();
    context.scale(dpr, dpr);
    context.clearRect(0, 0, width, height);

    const { atoms, bonds } = structure;
    if (atoms.length === 0) {
      context.restore();
      return;
    }

    const centre = atoms.reduce(
      (acc, atom) => {
        return {
          x: acc.x + atom.coords[0],
          y: acc.y + atom.coords[1],
          z: acc.z + atom.coords[2],
        };
      },
      { x: 0, y: 0, z: 0 }
    );

    centre.x /= atoms.length;
    centre.y /= atoms.length;
    centre.z /= atoms.length;

    let maxRadius = 1;
    atoms.forEach((atom) => {
      const dx = atom.coords[0] - centre.x;
      const dy = atom.coords[1] - centre.y;
      const dz = atom.coords[2] - centre.z;
      const radius = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (radius > maxRadius) {
        maxRadius = radius;
      }
    });

    const yaw = rotation.yaw;
    const pitch = clamp(rotation.pitch, -Math.PI / 2 + 0.01, Math.PI / 2 - 0.01);
    const sinYaw = Math.sin(yaw);
    const cosYaw = Math.cos(yaw);
    const sinPitch = Math.sin(pitch);
    const cosPitch = Math.cos(pitch);

    const scale = ((Math.min(width, height) * 0.42) / maxRadius) * zoom;

    type ProjectedAtom = AtomInfo & {
      screenX: number;
      screenY: number;
      screenZ: number;
      radius: number;
    };

    const projectedAtoms: ProjectedAtom[] = atoms.map((atom) => {
      const dx = atom.coords[0] - centre.x;
      const dy = atom.coords[1] - centre.y;
      const dz = atom.coords[2] - centre.z;

      const yawX = dx * cosYaw - dz * sinYaw;
      const yawZ = dx * sinYaw + dz * cosYaw;

      const pitchY = dy * cosPitch - yawZ * sinPitch;
      const pitchZ = dy * sinPitch + yawZ * cosPitch;

      const screenX = yawX * scale + width / 2;
      const screenY = pitchY * scale + height / 2;

      const baseRadius = ATOM_RADII[atom.element] ?? 0.5;
      const radius = Math.max(2.2, baseRadius * scale * 0.35);

      return {
        ...atom,
        screenX,
        screenY,
        screenZ: pitchZ,
        radius,
      };
    });

    const minZ = projectedAtoms.reduce(
      (acc, atom) => Math.min(acc, atom.screenZ),
      Number.POSITIVE_INFINITY
    );
    const maxZ = projectedAtoms.reduce(
      (acc, atom) => Math.max(acc, atom.screenZ),
      Number.NEGATIVE_INFINITY
    );
    const depthRange = Math.max(1e-3, maxZ - minZ);

    const projectedMap = new Map<number, ProjectedAtom>();
    projectedAtoms.forEach((atom) => {
      projectedMap.set(atom.id, atom);
    });

    projectedCARef.current = projectedAtoms
      .filter((atom) => atom.name === "CA")
      .map((atom) => ({
        residueIndex: atom.residueIndex,
        x: atom.screenX,
        y: atom.screenY,
        z: atom.screenZ,
      }));

    const sortedBonds = [...bonds].sort((a, b) => {
      const startA = projectedMap.get(a.startId);
      const endA = projectedMap.get(a.endId);
      const startB = projectedMap.get(b.startId);
      const endB = projectedMap.get(b.endId);
      const depthA = startA && endA ? (startA.screenZ + endA.screenZ) / 2 : 0;
      const depthB = startB && endB ? (startB.screenZ + endB.screenZ) / 2 : 0;
      return depthA - depthB;
    });

    sortedBonds.forEach((bond) => {
      const start = projectedMap.get(bond.startId);
      const end = projectedMap.get(bond.endId);
      if (!start || !end) {
        return;
      }

      const avgZ = (start.screenZ + end.screenZ) / 2;
      const depthFactor = 1 - (avgZ - minZ) / depthRange;
      const colour = BOND_COLORS[bond.type];
      const tint = colourString(scaleColour(colour, 0.7 + depthFactor * 0.3), 0.85);
      const glow = colourString(offsetColour(colour, 40), 0.5);
      const gradient = context.createLinearGradient(
        start.screenX,
        start.screenY,
        end.screenX,
        end.screenY
      );
      gradient.addColorStop(0, glow);
      gradient.addColorStop(0.45, tint);
      gradient.addColorStop(1, glow);
      context.strokeStyle = gradient;
      const baseWidth = BOND_WIDTH[bond.type] ?? 5;
      const widthScale = 0.55 + depthFactor * 0.6;
      context.lineWidth = Math.max(1.2, baseWidth * 0.35 * widthScale);
      context.lineCap = "round";
      context.beginPath();
      context.moveTo(start.screenX, start.screenY);
      context.lineTo(end.screenX, end.screenY);
      context.stroke();
    });

    const sortedAtoms = [...projectedAtoms].sort((a, b) => a.screenZ - b.screenZ);

    sortedAtoms.forEach((atom) => {
      const depthFactor = 1 - (atom.screenZ - minZ) / depthRange;
      const highlight = selectedResidue !== null && atom.name === "CA" && atom.residueIndex === selectedResidue;

      const fallbackColour: [number, number, number] = [226, 232, 240];
      const baseColour: [number, number, number] = highlight
        ? [56, 189, 248]
        : ATOM_COLORS[atom.element] ?? fallbackColour;
      const shaded = scaleColour(baseColour, 0.6 + depthFactor * 0.4);
      const highlightColour: [number, number, number] = highlight
        ? [125, 211, 252]
        : offsetColour(baseColour, 55);

      const radius = highlight ? atom.radius * 1.3 : atom.radius;
      const gradient = context.createRadialGradient(
        atom.screenX - radius * 0.35,
        atom.screenY - radius * 0.35,
        Math.max(1, radius * 0.2),
        atom.screenX,
        atom.screenY,
        radius
      );
      gradient.addColorStop(0, colourString(highlightColour));
      gradient.addColorStop(0.95, colourString(shaded));
      gradient.addColorStop(1, colourString([15, 23, 42], 0.65));

      context.beginPath();
      context.fillStyle = gradient;
      context.arc(atom.screenX, atom.screenY, radius, 0, Math.PI * 2);
      context.fill();

      context.lineWidth = highlight ? 1.8 : 1.2;
      context.strokeStyle = highlight
        ? "rgba(14, 165, 233, 0.8)"
        : "rgba(15, 23, 42, 0.75)";
      context.stroke();
    });

    context.restore();
  }, [dimensions, rotation.pitch, rotation.yaw, selectedResidue, structure, zoom]);

  useEffect(() => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
    }
    frameRef.current = requestAnimationFrame(renderScene);
    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
      }
      frameRef.current = null;
    };
  }, [renderScene, dimensions, structure, rotation, zoom, selectedResidue]);

  const handlePointerDown = useCallback((event: ReactPointerEvent<HTMLCanvasElement>) => {
    draggingRef.current = true;
    dragStartRef.current = { x: event.clientX, y: event.clientY };
    lastPointerRef.current = { x: event.clientX, y: event.clientY };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }, []);

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLCanvasElement>) => {
      if (!draggingRef.current || !lastPointerRef.current) {
        return;
      }
      const deltaX = event.clientX - lastPointerRef.current.x;
      const deltaY = event.clientY - lastPointerRef.current.y;
      lastPointerRef.current = { x: event.clientX, y: event.clientY };
      setRotation((prev) => ({
        yaw: prev.yaw + deltaX * 0.01,
        pitch: clamp(prev.pitch + deltaY * 0.01, -Math.PI / 2 + 0.01, Math.PI / 2 - 0.01),
      }));
    },
    []
  );

  const handlePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLCanvasElement>) => {
      if (!draggingRef.current) {
        return;
      }
      draggingRef.current = false;
      (event.target as HTMLElement).releasePointerCapture(event.pointerId);

      const start = dragStartRef.current;
      dragStartRef.current = null;
      lastPointerRef.current = null;

      if (!start) {
        return;
      }

      const movedDistance = Math.hypot(event.clientX - start.x, event.clientY - start.y);
      if (movedDistance > 6 || !onSelectResidue) {
        return;
      }

      const bounds = canvasRef.current?.getBoundingClientRect();
      if (!bounds) {
        return;
      }

      const x = event.clientX - bounds.left;
      const y = event.clientY - bounds.top;
      const dpr = window.devicePixelRatio || 1;
      const px = x * dpr;
      const py = y * dpr;

      let nearest: { residueIndex: number; distance: number } | undefined;
      projectedCARef.current.forEach((point) => {
        const dx = point.x * dpr - px;
        const dy = point.y * dpr - py;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (!nearest || distance < nearest.distance) {
          nearest = { residueIndex: point.residueIndex, distance };
        }
      });

      if (nearest && nearest.distance <= 28) {
        onSelectResidue(nearest.residueIndex);
      }
    },
    [onSelectResidue]
  );

  const handleWheel = useCallback((event: ReactWheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const nextZoom = clamp(
      zoom * (event.deltaY > 0 ? 0.9 : 1.1),
      ZOOM_RANGE[0],
      ZOOM_RANGE[1]
    );
    setZoom(nextZoom);
  }, [zoom]);

  return (
    <div className="protein-viewer" ref={containerRef}>
      <canvas
        ref={canvasRef}
        className="protein-viewer__canvas"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => {
          draggingRef.current = false;
          dragStartRef.current = null;
          lastPointerRef.current = null;
        }}
        onWheel={handleWheel}
        role="presentation"
      />
      {structure.atoms.length === 0 ? (
        <div className="protein-viewer__empty">No structure available</div>
      ) : null}
      <style jsx>{`
        .protein-viewer {
          position: relative;
          width: 100%;
          height: 100%;
          border-radius: 1rem;
          overflow: hidden;
          background: radial-gradient(circle at 30% 20%, rgba(59, 130, 246, 0.28), transparent 55%),
            radial-gradient(circle at 70% 80%, rgba(56, 189, 248, 0.2), transparent 60%),
            #020617;
          border: 1px solid rgba(148, 163, 184, 0.12);
        }

        .protein-viewer__canvas {
          width: 100%;
          height: 100%;
          cursor: grab;
          touch-action: none;
        }

        .protein-viewer__canvas:active {
          cursor: grabbing;
        }

        .protein-viewer__empty {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          color: rgba(226, 232, 240, 0.7);
          font-size: 0.95rem;
          pointer-events: none;
        }
      `}</style>
    </div>
  );
}
