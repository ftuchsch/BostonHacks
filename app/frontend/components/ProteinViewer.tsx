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

type ProjectedPoint = {
  index: number;
  x: number;
  y: number;
  z: number;
};

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const ZOOM_RANGE: [number, number] = [0.6, 2.5];
const INITIAL_ROTATION: Rotation = { yaw: Math.PI / 6, pitch: -Math.PI / 8 };

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
  const projectedRef = useRef<ProjectedPoint[]>([]);
  const frameRef = useRef<number | null>(null);

  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [rotation, setRotation] = useState<Rotation>(INITIAL_ROTATION);
  const [zoom, setZoom] = useState(1);

  const residuePoints = useMemo(() => residues ?? [], [residues]);

  useEffect(() => {
    if (!containerRef.current) {
      return () => undefined;
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const { width, height } = entry.contentRect;
        setDimensions((prev) => {
          if (Math.abs(prev.width - width) < 0.5 && Math.abs(prev.height - height) < 0.5) {
            return prev;
          }
          return { width, height };
        });
      }
    });
    observer.observe(containerRef.current);
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

    if (residuePoints.length === 0) {
      context.restore();
      return;
    }

    const centre = residuePoints.reduce(
      (acc, residue) => {
        return {
          x: acc.x + residue.coords[0],
          y: acc.y + residue.coords[1],
          z: acc.z + residue.coords[2],
        };
      },
      { x: 0, y: 0, z: 0 }
    );

    centre.x /= residuePoints.length;
    centre.y /= residuePoints.length;
    centre.z /= residuePoints.length;

    const yaw = rotation.yaw;
    const pitch = clamp(rotation.pitch, -Math.PI / 2 + 0.01, Math.PI / 2 - 0.01);

    const sinYaw = Math.sin(yaw);
    const cosYaw = Math.cos(yaw);
    const sinPitch = Math.sin(pitch);
    const cosPitch = Math.cos(pitch);

    let maxRadius = 1;
    residuePoints.forEach((residue) => {
      const dx = residue.coords[0] - centre.x;
      const dy = residue.coords[1] - centre.y;
      const dz = residue.coords[2] - centre.z;
      const radius = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (radius > maxRadius) {
        maxRadius = radius;
      }
    });

    const scale = ((Math.min(width, height) * 0.4) / maxRadius) * zoom;
    const projection: ProjectedPoint[] = residuePoints.map((residue) => {
      const dx = residue.coords[0] - centre.x;
      const dy = residue.coords[1] - centre.y;
      const dz = residue.coords[2] - centre.z;

      const yawX = dx * cosYaw - dz * sinYaw;
      const yawZ = dx * sinYaw + dz * cosYaw;

      const pitchY = dy * cosPitch - yawZ * sinPitch;
      const pitchZ = dy * sinPitch + yawZ * cosPitch;

      return {
        index: residue.index,
        x: yawX * scale + width / 2,
        y: pitchY * scale + height / 2,
        z: pitchZ,
      };
    });

    projectedRef.current = projection;

    // Draw bonds between consecutive residues
    context.lineJoin = "round";
    context.lineCap = "round";
    context.lineWidth = 3;
    context.strokeStyle = "rgba(148, 163, 184, 0.65)";

    for (let i = 0; i < projection.length - 1; i += 1) {
      const start = projection[i];
      const end = projection[i + 1];
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.stroke();
    }

    // Draw nodes
    const sorted = [...projection].sort((a, b) => a.z - b.z);
    const highlightIndex = selectedResidue ?? null;

    sorted.forEach((point) => {
      const depthFactor = clamp(1 - point.z / (maxRadius * 2), 0.2, 1);
      const radius = highlightIndex === point.index ? 7 : 5;
      context.beginPath();
      context.fillStyle = highlightIndex === point.index
        ? "#38bdf8"
        : `rgba(${Math.floor(94 * depthFactor)}, ${Math.floor(
            234 * depthFactor
          )}, ${Math.floor(212 * depthFactor)}, 0.9)`;
      context.strokeStyle = "rgba(15, 23, 42, 0.9)";
      context.lineWidth = 1.5;
      context.arc(point.x, point.y, radius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
    });

    context.restore();
  }, [dimensions, residuePoints, rotation.pitch, rotation.yaw, selectedResidue, zoom]);

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
  }, [renderScene, dimensions, residuePoints, rotation, zoom, selectedResidue]);

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

let nearest: { index: number; distance: number } | undefined;

projectedRef.current.forEach((point) => {
  const dx = point.x * dpr - px;
  const dy = point.y * dpr - py;
  const distance = Math.hypot(dx, dy);
  const best = nearest?.distance ?? Number.POSITIVE_INFINITY;
  if (distance < best) {
    nearest = { index: point.index, distance };
  }
});

if (nearest && nearest.distance <= 24 && onSelectResidue) {
  onSelectResidue(nearest.index);
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
      {residuePoints.length === 0 ? (
        <div className="protein-viewer__empty">No structure available</div>
      ) : null}
      <style jsx>{`
        .protein-viewer {
          position: relative;
          width: 100%;
          height: 100%;
          border-radius: 1rem;
          overflow: hidden;
          background: radial-gradient(circle at 30% 20%, rgba(59, 130, 246, 0.25), transparent 55%),
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