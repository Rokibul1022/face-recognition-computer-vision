import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ScanStage, { type ScanMode } from "./components/ScanStage";
import UploadPanel from "./components/UploadPanel";

type Job = { mode: ScanMode; file?: File } | null;

export default function App() {
  const [job, setJob] = useState<Job>(null);

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">◈ IDENT-SCAN</div>
        <div className="status-tag">SYS-ONLINE // GALLERY-LINKED</div>
      </header>

      <main className="app-main">
        <AnimatePresence mode="wait">
          {!job ? (
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
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
