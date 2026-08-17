import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { FaceDetail } from "../types";
import { API_BASE } from "../hooks/useFaceRecognition";

interface Props {
  person: FaceDetail;
  onSave: (data: Omit<FaceDetail, "person_id" | "photo_url">) => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
}

export default function FaceDetailModal({ person, onSave, onDelete, onClose }: Props) {
  const [form, setForm] = useState({
    name: person.name,
    nid: person.nid,
    age: String(person.age),
    address: person.address,
    number: person.number,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await onSave({ ...form, age: Number(form.age) || 0 });
      setMsg("Saved.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await onDelete();
      onClose();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Delete failed.");
      setBusy(false);
    }
  };

  return (
    <motion.div
      className="prompt-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="prompt-box face-detail-box"
        initial={{ scale: 0.94, y: 14 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="prompt-kicker">ENROLLED IDENTITY</div>

        {person.photo_url && (
          <div className="face-detail-photo">
            <img src={`${API_BASE}${person.photo_url}`} alt={person.person_id} />
          </div>
        )}
        <div className="face-detail-id">{person.person_id.toUpperCase()}</div>

        <div className="face-detail-grid">
          <Field label="NAME" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
          <Field label="ID (person_id)" value={person.person_id} disabled />
          <Field label="NID" value={form.nid} onChange={(v) => setForm({ ...form, nid: v })} />
          <Field label="AGE" value={form.age} onChange={(v) => setForm({ ...form, age: v })} />
          <Field label="ADDRESS" value={form.address} onChange={(v) => setForm({ ...form, address: v })} wide />
          <Field label="PHONE" value={form.number} onChange={(v) => setForm({ ...form, number: v })} wide />
        </div>

        {msg && <div className="hint" style={{ marginTop: 10 }}>{msg}</div>}

        <div className="face-detail-actions">
          <button className="btn danger" onClick={remove} disabled={busy}>
            {confirmingDelete ? "CONFIRM DELETE?" : "DELETE"}
          </button>
          <button className="btn primary" onClick={save} disabled={busy}>
            {busy ? "SAVING…" : "SAVE"}
          </button>
          <button className="btn ghost" onClick={onClose}>
            CLOSE
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Field({
  label,
  value,
  onChange,
  disabled,
  wide,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  disabled?: boolean;
  wide?: boolean;
}) {
  return (
    <label style={{ textAlign: "left", gridColumn: wide ? "1 / -1" : undefined }}>
      <span className="hint" style={{ display: "block" }}>{label}</span>
      <input
        value={value}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.value)}
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