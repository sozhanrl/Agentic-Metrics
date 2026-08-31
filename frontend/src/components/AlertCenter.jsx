import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function AlertCenter({ projectId, onClose }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const data = await api.getAlerts(projectId);
      setAlerts(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) loadAlerts();
  }, [projectId]);

  const handleMarkRead = async (alertId) => {
    try {
      await api.markAlertRead(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_read: true } : a))
      );
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content alerts-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">🔔 Alert & Notification Center</h3>
            <span className="modal-subtitle">Real-time telemetry threshold triggers & AI notices</span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        {loading && (
          <div className="modal-loading-state">
            <div className="spinner" />
            <p>Loading alerts…</p>
          </div>
        )}

        {!loading && alerts.length === 0 && (
          <div className="empty-state">
            <p>No active alerts for this project.</p>
          </div>
        )}

        <div className="alerts-list">
          {alerts.map((a) => (
            <div key={a.id} className={`alert-card type-${a.alert_type} ${a.is_read ? "read" : "unread"}`}>
              <div className="alert-card-header">
                <span className={`alert-type-badge ${a.alert_type}`}>{a.alert_type.toUpperCase()}</span>
                <span className="alert-time">
                  {new Date(a.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
              <h4 className="alert-title">{a.title}</h4>
              <p className="alert-msg">{a.message}</p>

              {!a.is_read && (
                <button className="btn-sm btn-ghost alert-read-btn" onClick={() => handleMarkRead(a.id)}>
                  Mark as read
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
