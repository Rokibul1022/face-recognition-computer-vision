import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ScanStage, { type ScanMode } from "./components/ScanStage";
import UploadPanel from "./components/UploadPanel";
import IncidentsTab from "./components/tabs/IncidentsTab";
import ChatTab from "./components/tabs/ChatTab";
import FacesTab from "./components/tabs/FacesTab";
import SettingsTab from "./components/tabs/SettingsTab";

type Job = { mode: ScanMode; file?: File } | null;
type Tab = "scan" | "incidents" | "faces" | "chat" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "scan", label: "SCAN" },
  { id: "incidents", label: "INCIDENTS" },
  { id: "faces", label: "FACES" },
  { id: "chat", label: "CHAT" },
  { id: "settings", label: "SETTINGS" },
];

export default function App() {
  const [job, setJob] = useState<Job>(null);
  const [tab, setTab] = useState<Tab>("scan");

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">◈ IDENT-SCAN</div>
        <div className="status-tag">SYS-ONLINE // GALLERY-LINKED</div>
      </header>

      <nav className="tab-nav">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab-btn${tab === t.id ? " active" : ""}`}
            onClick={() => {
              setJob(null);
              setTab(t.id);
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="app-main">
        <AnimatePresence mode="wait">
          {tab === "scan" &&
            (!job ? (
              <motion.div
                key="upload"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, scale: 0.99 }}
                transition={{ duration: 0.3 }}
                style={{ height: "100%" }}
              >
                <UploadPanel
                  onImage={(f) => setJob({ mode: "image", file: f })}
                  onVideo={(f) => setJob({ mode: "video", file: f })}
                  onLive={() => setJob({ mode: "live" })}
                />
              </motion.div>
            ) : (
              <motion.div
                key={`${job.mode}-${job.file?.name ?? "live"}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                style={{ height: "100%" }}
              >
                <ScanStage mode={job.mode} file={job.file} onBack={() => setJob(null)} />
              </motion.div>
            ))}
          {tab === "incidents" && <IncidentsTab />}
          {tab === "faces" && <FacesTab />}
          {tab === "chat" && <ChatTab />}
          {tab === "settings" && <SettingsTab />}
        </AnimatePresence>
      </main>
    </div>
  );
}
