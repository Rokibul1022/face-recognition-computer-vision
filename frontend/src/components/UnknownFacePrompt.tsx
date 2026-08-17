import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import type { FaceResult } from "../types";
import EnrollForm from "./EnrollForm";

interface Props {
  face: FaceResult;
  /** Optional cropped face image captured from the current frame. */
  cropFile?: File | null;
  /** The full source frame (or media) file + face bbox so the backend can crop reliably. */
  fullFile?: File | null;
  bbox?: [number, number, number, number];
  /** Called when the identity is successfully enrolled (before onClose). */
  onEnrolled?: () => void;
  onClose: () => void;
}

type Stage = "ask" | "confirm" | "form";

/**
 * Unknown-face flow:
 *   ask      → "DO YOU KNOW THIS FACE?"   (YES / NO)
 *   confirm  → "ADD THIS FACE TO DATABASE?" (YES / NO)
 *   form     → the enrollment form
 * Any "NO" answer dismisses the prompt without showing the form.
 */
export default function UnknownFacePrompt({ face, cropFile, fullFile, bbox, onEnrolled, onClose }: Props) {
  const [stage, setStage] = useState<Stage>("ask");
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: 0 });
  }, [stage]);

  return (
    <motion.div
      className="prompt-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        ref={boxRef}
        className="prompt-box"
        initial={{ scale: 0.94, y: 14 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        <AnimatePresence mode="wait">
          {stage === "ask" && (
            <motion.div
              key="ask"
              className="prompt-stage"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="prompt-kicker">UNKNOWN FACE DETECTED</div>
              <FacePreview face={face} cropFile={cropFile} />
              <div className="prompt-question">DO YOU KNOW THIS FACE?</div>
              <div className="prompt-actions">
                <button className="btn primary" onClick={() => setStage("confirm")}>
                  YES
                </button>
                <button className="btn danger" onClick={onClose}>
                  NO
                </button>
              </div>
            </motion.div>
          )}

          {stage === "confirm" && (
            <motion.div
              key="confirm"
              className="prompt-stage"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="prompt-kicker">IDENTITY STORAGE</div>
              <FacePreview face={face} cropFile={cropFile} />
              <div className="prompt-question">SHOULD I PUT THIS FACE ON THE DATABASE?</div>
              <div className="prompt-actions">
                <button className="btn primary" onClick={() => setStage("form")}>
                  YES
                </button>
                <button className="btn danger" onClick={onClose}>
                  NO
                </button>
              </div>
            </motion.div>
          )}

          {stage === "form" && (
            <motion.div
              key="form"
              className="prompt-stage"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="prompt-kicker">REGISTER NEW IDENTITY</div>
              <EnrollForm
                defaultFile={fullFile ?? cropFile}
                bbox={bbox}
                onEnrolled={() => {
                  onEnrolled?.();
                  onClose();
                }}
                onCancelled={onClose}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}

function FacePreview({ face, cropFile }: { face: FaceResult; cropFile?: File | null }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!cropFile) return;
    const url = URL.createObjectURL(cropFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [cropFile]);

  if (previewUrl) {
    return (
      <div className="prompt-face-preview">
        <img src={previewUrl} alt="detected face" />
      </div>
    );
  }

  return (
    <div className="prompt-face-empty strict">
      FACE {face.matched ? "MATCHED" : "NO MATCH"} · SIM {Math.round((face.score ?? 0) * 100)}%
    </div>
  );
}