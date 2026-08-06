import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";

export type BoxState = "scanning" | "matching" | "match" | "nomatch";

interface Props {
  /** Normalized box in fractions of the media element (0..1). */
  box: { x: number; y: number; w: number; h: number };
  state: BoxState;
  label?: string;
}

const COLORS: Record<BoxState, string> = {
  scanning: "var(--hud-cyan)",
  matching: "var(--hud-amber)",
  match: "var(--hud-green)",
  nomatch: "var(--hud-red)",
};

const TELEMETRY = [
  "SCANNING…",
  "DETECT… 0x7F",
  "EMBEDDING…",
  "MATCHING…",
  "NORM… ✓",
];

/** Corner-only bracket box with the HUD color state machine. */
export default function FaceBoxOverlay({ box, state, label }: Props) {
  const reduced = usePrefersReducedMotion();
  const color = COLORS[state];
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (state === "match" || state === "nomatch") return;
    const id = setInterval(() => setTick((t) => t + 1), 350);
    return () => clearInterval(id);
  }, [state]);

  const readout = useMemo(() => {
    if (state === "match") return "IDENTIFIED";
    if (state === "nomatch") return "NO MATCH";
    if (state === "matching") return "MATCHING…";
    return TELEMETRY[tick % TELEMETRY.length];
  }, [state, tick]);

  const duration = reduced ? 0 : 0.25;

  return (
    <motion.div
      className="face-box"
      style={{
        color,
        left: `${box.x * 100}%`,
        top: `${box.y * 100}%`,
        width: `${box.w * 100}%`,
        height: `${box.h * 100}%`,
      }}
      initial={reduced ? false : { scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.9, opacity: 0 }}
      transition={{ duration }}
      layout
    >
      <span className="bracket b-tl" />
      <span className="bracket b-tr" />
      <span className="bracket b-bl" />
      <span className="bracket b-br" />
      <span className="bracket b-lt" />
      <span className="bracket b-rt" />
      <span className="bracket b-lb" />
      <span className="bracket b-rb" />
      {label && <div className="face-label">{label}</div>}
      <div className="face-readout">{readout}</div>
    </motion.div>
  );
}
