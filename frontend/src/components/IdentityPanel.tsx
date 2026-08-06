import { AnimatePresence, motion } from "framer-motion";
import { forwardRef, useEffect, useState } from "react";
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";
import type { FaceMatch } from "../types";
import ConfidenceMeter from "./ConfidenceMeter";

export interface PanelItem {
  /** Stable key so a persistent match doesn't re-trigger its reveal. */
  key: string;
  match: FaceMatch | null; // null => unknown/no match card
  score: number;
}

interface Props {
  items: PanelItem[];
  processingMs?: number;
}

const CHARSET = "!<>-_\\/[]{}—=+*^?#01@$%&";

function randChar(): string {
  return CHARSET[Math.floor(Math.random() * CHARSET.length)];
}

/**
 * Decode-in text: characters flicker through scrambled symbols and resolve
 * left → right, monospace while decoding. The final text inherits the parent
 * font once resolved.
 */
function GlitchText({ text, speed = 28 }: { text: string; speed?: number }) {
  const reduced = usePrefersReducedMotion();
  const [buffer, setBuffer] = useState<string>(() =>
    reduced ? text : text.replace(/./g, randChar)
  );

  useEffect(() => {
    if (reduced) {
      setBuffer(text);
      return;
    }
    let resolved = 0;
    const id = setInterval(() => {
      resolved += 1;
      setBuffer((prev) => {
        const next = prev.split("");
        next[resolved - 1] = text[resolved - 1];
        for (let i = resolved; i < text.length; i++) {
          if (Math.random() < 0.6) next[i] = randChar();
        }
        return next.join("");
      });
      if (resolved >= text.length) clearInterval(id);
    }, speed);
    return () => clearInterval(id);
  }, [text, reduced, speed]);

  return <span className="decode-text">{buffer}</span>;
}

const IdentityCard = forwardRef<HTMLDivElement, { item: PanelItem }>(
  function IdentityCard({ item }, ref) {
    const { match, score } = item;
    const info = match?.info;

    return (
      <motion.div
        ref={ref}
        className={`id-card ${match ? "match" : "nomatch"}`}
        initial={{ opacity: 0, x: 30 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
      >
        {match ? (
          <>
            <div className="id-name">
              <GlitchText text={info?.name ?? match.person_id} />
            </div>
            <div className="id-field">
              <div className="k">NID</div>
              <div className="v mono">
                <GlitchText text={info?.nid ?? "—"} />
              </div>
            </div>
            <div className="id-field">
              <div className="k">AGE</div>
              <div className="v mono">
                <GlitchText text={String(info?.age ?? "—")} />
              </div>
            </div>
            <div className="id-field">
              <div className="k">ADDRESS</div>
              <div className="v">
                <GlitchText text={info?.address ?? "—"} speed={16} />
              </div>
            </div>
            <div className="id-field">
              <div className="k">CONTACT</div>
              <div className="v mono">
                <GlitchText text={info?.number ?? "—"} />
              </div>
            </div>
            <ConfidenceMeter score={score} />
          </>
        ) : (
          <>
            <div className="id-name">
              <GlitchText text="NO MATCH FOUND" speed={40} />
            </div>
            <p
              style={{
                fontFamily: "var(--mono)",
                fontSize: 12,
                color: "var(--hud-dim)",
                lineHeight: 1.6,
              }}
            >
              No enrolled identity exceeds the similarity threshold for this face.
            </p>
            <ConfidenceMeter score={Math.min(score, 1)} />
          </>
        )}
      </motion.div>
    );
  }
);

export default function IdentityPanel({ items, processingMs }: Props) {
  const reduced = usePrefersReducedMotion();
  const resolved = items.filter((i) => i.match).length;

  return (
    <div className="identity-panel">
      <div className="panel-title">
        <span>{resolved > 0 ? "IDENTITIES RESOLVED" : "IDENTITY SCAN"}</span>
        {processingMs != null && <span>{processingMs}ms</span>}
      </div>

      <AnimatePresence initial={false} mode="popLayout">
        {items.map((item) => (
          <IdentityCard key={item.key} item={item} />
        ))}
      </AnimatePresence>

      {items.length === 0 && (
        <p style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--hud-dim)" }}>
          {reduced ? "NO FACES DETECTED." : "NO FACES DETECTED."}
        </p>
      )}
    </div>
  );
}
