import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";

interface Props {
  score: number; // 0..1
}

/** Animated similarity meter — percentage, not raw text. */
export default function ConfidenceMeter({ score }: Props) {
  const reduced = usePrefersReducedMotion();
  const pct = Math.round(score * 100);

  // Animate the number up when it changes rather than jumping.
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    setDisplay(pct);
  }, [pct]);

  return (
    <div className="meter">
      <div className="meter-head">
        <span>Similarity</span>
        <span>cosine</span>
      </div>
      <div className="meter-bar">
        <motion.div
          className="meter-fill"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ duration: reduced ? 0 : 0.6, ease: "easeOut" }}
        />
      </div>
      <motion.div
        className="meter-pct"
        initial={false}
        animate={{ opacity: 1 }}
      >
        {display}%
      </motion.div>
    </div>
  );
}
