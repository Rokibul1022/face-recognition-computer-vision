import { motion } from "framer-motion";
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";

/** Horizontal gradient sweep animating top → bottom on a loop. */
export default function ScanLine() {
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    return (
      <div
        className="scan-line"
        style={{ top: "50%", transform: "translateY(-50%)", opacity: 0.5 }}
      />
    );
  }

  return (
    <motion.div
      className="scan-line"
      initial={{ top: "-12%" }}
      animate={{ top: "112%" }}
      transition={{
        duration: 1.7,
        repeat: Infinity,
        ease: "linear",
        repeatDelay: 0.25,
      }}
    />
  );
}
