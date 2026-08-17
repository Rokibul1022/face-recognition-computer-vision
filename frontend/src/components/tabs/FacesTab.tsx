import { useCallback, useEffect, useState } from "react";
import { useAgentApi } from "../../hooks/useAgentApi";
import type { FaceDetail } from "../../types";
import { API_BASE } from "../../hooks/useFaceRecognition";
import FaceDetailModal from "../FaceDetailModal";

export default function FacesTab() {
  const { listFaces, updateFace, deleteFace } = useAgentApi();
  const [faces, setFaces] = useState<FaceDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FaceDetail | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setFaces(await listFaces());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load faces.");
    }
  }, [listFaces]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (data: Omit<FaceDetail, "person_id" | "photo_url">) => {
    if (!selected) return;
    await updateFace(selected.person_id, data);
    await load();
    setSelected({ ...selected, ...data });
  };

  const handleDelete = async () => {
    if (!selected) return;
    await deleteFace(selected.person_id);
    setSelected(null);
    await load();
  };

  return (
    <section className="tab-page">
      <div className="tab-head">
        <h2>ENROLLED FACES</h2>
        <button className="btn ghost" onClick={load}>REFRESH</button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {!faces && !error && <div className="muted">Loading faces…</div>}
      <div className="face-grid">
        {faces?.map((f) => (
          <button key={f.person_id} className="face-tile" onClick={() => setSelected(f)}>
            {f.photo_url ? (
              <img className="face-thumb" src={`${API_BASE}${f.photo_url}`} alt={f.person_id} />
            ) : (
              <div className="face-thumb empty">{f.person_id[0]?.toUpperCase()}</div>
            )}
            <span className="face-id">{f.person_id.toUpperCase()}</span>
            <span className="muted">{f.name || "—"}</span>
          </button>
        ))}
      </div>

      {selected && (
        <FaceDetailModal
          person={selected}
          onSave={handleSave}
          onDelete={handleDelete}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}