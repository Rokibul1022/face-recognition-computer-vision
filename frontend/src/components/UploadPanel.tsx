import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import EnrollForm from "./EnrollForm";

interface Props {
  onImage: (file: File) => void;
  onVideo: (file: File) => void;
  onLive: () => void;
}

const ACCEPT = ".jpg,.jpeg,.png,.jfif,.webp,.bmp,image/*,.mp4,.avi,.mov,.mkv,.webm,video/*";

export default function UploadPanel({ onImage, onVideo, onLive }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const cctvInputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [cctvOpen, setCctvOpen] = useState(false);

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    setError(null);
    if (file.type.startsWith("video/")) {
      onVideo(file);
      return;
    }
    if (file.type.startsWith("image/") || /\.(jpe?g|png|jfif|webp|bmp)$/i.test(file.name)) {
      onImage(file);
      return;
    }
    setError("Unsupported file. Drop an image or video.");
  }

  return (
    <div className="upload-wrap">
      <motion.h1
        className="upload-title"
        initial={{ opacity: 0, letterSpacing: "0.5em" }}
        animate={{ opacity: 1, letterSpacing: "0.3em" }}
        transition={{ duration: 0.8 }}
      >
        IDENT-SCAN
      </motion.h1>
      <p style={{ fontFamily: "var(--mono)", color: "var(--hud-dim)", fontSize: 12, letterSpacing: "0.2em", marginTop: -12 }}>
        FACIAL RECOGNITION TERMINAL
      </p>

      <div
        className={`upload-drop ${drag ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <div style={{ fontSize: 15, letterSpacing: "0.12em" }}>DROP IMAGE / VIDEO</div>
        <div className="hint">or click to browse · .jpg .jpeg .png .jfif .webp .bmp · .mp4 .avi .mov .mkv .webm</div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden-file-input"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {error && <div className="error-msg">{error}</div>}

      <div className="upload-row">
        <button className="btn primary" onClick={onLive}>
          ▶ Start Live Scan
        </button>
        <button className="btn" onClick={() => setCctvOpen((o) => !o)}>
          ▣ CCTV FOOTAGE
        </button>
        <button className="btn" onClick={() => setEnrollOpen((o) => !o)}>
          {enrollOpen ? "Close Enroll" : "+ Enroll Face"}
        </button>
      </div>

      <AnimatePresence>
        {cctvOpen && (
          <motion.div
            className="cctv-menu"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
          >
            <div className="cctv-menu-title">CCTV FOOTAGE SOURCE</div>
            <div className="upload-row">
              <button className="btn cctv-btn" onClick={() => cctvInputRef.current?.click()}>
                ▤ LOCAL FOOTAGE
              </button>
              <button className="btn cctv-btn primary" onClick={onLive}>
                ◉ LIVE FOOTAGE
              </button>
            </div>
            <div className="hint" style={{ marginTop: 10 }}>
              Local: pick an image/video from this device · Live: open the attached camera stream
            </div>
            <input
              ref={cctvInputRef}
              type="file"
              accept={ACCEPT}
              className="hidden-file-input"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {enrollOpen && (
        <motion.div
          className="upload-drop"
          style={{ padding: 20, width: "min(560px, 90vw)" }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div style={{ fontSize: 13, letterSpacing: "0.15em", marginBottom: 12 }}>
            ENROLL NEW IDENTITY
          </div>
          <EnrollForm />
        </motion.div>
      )}
    </div>
  );
}