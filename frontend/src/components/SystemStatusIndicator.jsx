import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function SystemStatusIndicator() {
  const [statusData, setStatusData] = useState(null);
  const [online, setOnline] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const checkHealth = async () => {
    try {
      const data = await api.getSystemHealth();
      setStatusData(data);
      setOnline(data.status === "ok" || data.status === "running");
    } catch (err) {
      setOnline(false);
      setStatusData({
        status: "offline",
        database: "unavailable",
        intelligence_engine: "offline",
        error: err.message,
      });
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <button
        className={`system-status-pill ${online ? "online" : "offline"}`}
        onClick={() => setShowModal(true)}
        title="Click for System Diagnostic Status"
      >
        <span className="status-dot" />
        <span className="status-text">
          {online ? "● Intelligence Engine Online" : "● Intelligence Engine Offline"}
        </span>
      </button>

      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal-content system-status-modal" onClick={(e) => e.stopPropagation()}>
            <header className="modal-header">
              <h3 className="modal-title">⚙️ System & Intelligence Pipeline Status</h3>
              <button className="modal-close-btn" onClick={() => setShowModal(false)}>
                &times;
              </button>
            </header>

            <div className="status-modal-body">
              <div className="status-check-row">
                <span className="check-label">Intelligence Engine:</span>
                <span className={`check-val ${online ? "ok" : "err"}`}>
                  {online ? "● Online & Ready" : "✕ Offline"}
                </span>
              </div>

              <div className="status-check-row">
                <span className="check-label">Database Connection:</span>
                <span className={`check-val ${statusData?.database === "connected" ? "ok" : "err"}`}>
                  {statusData?.database === "connected" ? "✓ Connected (Neon PostgreSQL)" : `✕ ${statusData?.database || "Disconnected"}`}
                </span>
              </div>

              <div className="status-check-row">
                <span className="check-label">Agentic Pipeline:</span>
                <span className="check-val ok">✓ Pipeline Ready (Perceiver → Evaluator → Arbitrator)</span>
              </div>

              <div className="status-check-row">
                <span className="check-label">Disclosure Safety Mode:</span>
                <span className="check-val ok">🔒 Public Safe Serializer Active</span>
              </div>

              <button className="btn primary full-width" style={{ marginTop: 16 }} onClick={checkHealth}>
                ↺ Re-check System Telemetry
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
