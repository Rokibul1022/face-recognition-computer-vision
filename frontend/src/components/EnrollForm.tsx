import { useRef, useState } from "react";
import { useFaceRecognition } from "../hooks/useFaceRecognition";
import type { EnrollResponse } from "../types";

interface Props {
  defaultFile?: File | null;
  /** Face bbox in original source pixels, so the backend can crop a clean face itself. */
  bbox?: [number, number, number, number];
  onEnrolled?: (res: EnrollResponse) => void;
  onCancelled?: () => void;
}

const ACCEPT = ".jpg,.jpeg,.png,.jfif,.webp,.bmp,image/*";

export default function EnrollForm({ defaultFile = null, bbox, onEnrolled, onCancelled }: Props) {
  const { enroll } = useFaceRecognition();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(defaultFile);
  const [form, setForm] = useState({
    person_id: "",
    name: "",
    nid: "",
    age: "",
    address: "",
    number: "",
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pickFile(files: FileList | null) {
    if (files && files[0]) {
      setFile(files[0]);
      setMsg(null);
    }
  }

  async function submit() {
    if (!file) {
      setMsg("Select a photo first.");
      return;
    }
    if (!form.person_id.trim()) {
      setMsg("person_id is required.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const res = await enroll(file, { ...form, person_id: form.person_id.trim() }, bbox);
      setMsg(
        `Enrolled "${res.person_id}" — ${res.embedded ? "embedded" : "no face found"} (gallery: ${res.gallery_size}).`
      );
      onEnrolled?.(res);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Enroll failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="upload-row" style={{ marginBottom: 12 }}>
        <button className="btn" onClick={() => inputRef.current?.click()}>
          {file ? `✓ ${file.name}` : "Select Photo"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden-file-input"
          onChange={(e) => pickFile(e.target.files)}
        />
        {onCancelled && (
          <button className="btn danger" onClick={onCancelled}>
            Cancel
          </button>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <EnrollField label="ID" value={form.person_id} onChange={(v) => setForm({ ...form, person_id: v })} />
        <EnrollField label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
        <EnrollField label="NID" value={form.nid} onChange={(v) => setForm({ ...form, nid: v })} />
        <EnrollField label="Age" value={form.age} onChange={(v) => setForm({ ...form, age: v })} />
        <EnrollField
          label="Address"
          value={form.address}
          onChange={(v) => setForm({ ...form, address: v })}
          style={{ gridColumn: "1 / -1" }}
        />
        <EnrollField
          label="Phone"
          value={form.number}
          onChange={(v) => setForm({ ...form, number: v })}
          style={{ gridColumn: "1 / -1" }}
        />
      </div>

      <div className="upload-row" style={{ marginTop: 12 }}>
        <button className="btn primary" onClick={submit} disabled={busy}>
          {busy ? "ENROLLING…" : "Enroll"}
        </button>
      </div>
      {msg && <div className="hint" style={{ marginTop: 10 }}>{msg}</div>}
    </>
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