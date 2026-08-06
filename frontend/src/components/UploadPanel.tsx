import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { useFaceRecognition } from "../hooks/useFaceRecognition";

interface Props {
  onImage: (file: File) => void;
  onVideo: (file: File) => void;
  onLive: () => void;
}

const ACCEPT = ".jpg,.jpeg,.png,.jfif,.webp,.bmp,image/*";

export default function UploadPanel({ onImage, onVideo, onLive }: Props) {
  const { enroll } = useFaceRecognition();
  const inputRef = useRef<HTMLInputElement>(null);
  const enrollInputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enrollFile, setEnrollFile] = useState<File | null>(null);
  const [enrollForm, setEnrollForm] = useState({
    person_id: "",
    name: "",
    nid: "",
    age: "",
    address: "",
    number: "",
  });
  const [enrollMsg, setEnrollMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  function pickEnrollFile(files: FileList | null) {
    if (files && files[0]) {
      setEnrollFile(files[0]);
      setEnrollMsg(null);
    }
  }

  async function submitEnroll() {
    if (!enrollFile) {
      setEnrollMsg("Select a photo first.");
      return;
    }
    if (!enrollForm.person_id.trim()) {
      setEnrollMsg("person_id is required.");
      return;
    }
    setBusy(true);
    setEnrollMsg(null);
    try {
      const res = await enroll(enrollFile, { ...enrollForm, person_id: enrollForm.person_id.trim() });
      setEnrollMsg(`Enrolled "${res.person_id}" — ${res.embedded ? "embedded" : "no face found"} (gallery: ${res.gallery_size}).`);
      setEnrollFile(null);
      setEnrollForm({ person_id: "", name: "", nid: "", age: "", address: "", number: "" });
    } catch (e) {
      setEnrollMsg(e instanceof Error ? e.message : "Enroll failed.");
    } finally {
      setBusy(false);
    }
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
        <div className="hint">or click to browse · .jpg .jpeg .png .jfif .webp .bmp</div>
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
        <button className="btn" onClick={() => setEnrollOpen((o) => !o)}>
          {enrollOpen ? "Close Enroll" : "+ Enroll Face"}
        </button>
      </div>

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
          <div className="upload-row" style={{ marginBottom: 12 }}>
            <button className="btn" onClick={() => enrollInputRef.current?.click()}>
              {enrollFile ? `✓ ${enrollFile.name}` : "Select Photo"}
            </button>
            <input
              ref={enrollInputRef}
              type="file"
              accept={ACCEPT}
              className="hidden-file-input"
              onChange={(e) => pickEnrollFile(e.target.files)}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <EnrollField label="ID" value={enrollForm.person_id} onChange={(v) => setEnrollForm({ ...enrollForm, person_id: v })} />
            <EnrollField label="Name" value={enrollForm.name} onChange={(v) => setEnrollForm({ ...enrollForm, name: v })} />
            <EnrollField label="NID" value={enrollForm.nid} onChange={(v) => setEnrollForm({ ...enrollForm, nid: v })} />
            <EnrollField label="Age" value={enrollForm.age} onChange={(v) => setEnrollForm({ ...enrollForm, age: v })} />
            <EnrollField label="Address" value={enrollForm.address} onChange={(v) => setEnrollForm({ ...enrollForm, address: v })} style={{ gridColumn: "1 / -1" }} />
            <EnrollField label="Phone" value={enrollForm.number} onChange={(v) => setEnrollForm({ ...enrollForm, number: v })} style={{ gridColumn: "1 / -1" }} />
          </div>
          <div className="upload-row" style={{ marginTop: 12 }}>
            <button className="btn primary" onClick={submitEnroll} disabled={busy}>
              {busy ? "ENROLLING…" : "Enroll"}
            </button>
          </div>
          {enrollMsg && <div className="hint" style={{ marginTop: 10 }}>{enrollMsg}</div>}
        </motion.div>
      )}
    </div>
  );
}

function EnrollField({
  label,
  value,
  onChange,
  style,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  style?: React.CSSProperties;
}) {
  return (
    <label style={{ textAlign: "left", ...style }}>
      <span className="hint" style={{ display: "block" }}>{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: "100%",
          padding: "8px 10px",
          background: "rgba(0,0,0,0.4)",
          border: "1px solid var(--hud-line)",
          color: "var(--hud-text)",
          fontFamily: "var(--mono)",
          fontSize: 13,
          borderRadius: 4,
        }}
      />
    </label>
  );
}
