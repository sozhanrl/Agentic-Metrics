import React, { useState } from "react";
import { api } from "../api";

export default function AIAssistant({ projectId, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! I am your AI Software Engineering Assistant. I have real-time access to your project telemetry, causal dependencies, recommendations, and health scores. Ask me anything about this project!",
      evidence: [],
      followups: [
        "Why is project health declining?",
        "What should we fix first?",
        "What are the biggest risks?",
        "Show me recent anomalies",
      ],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (questionText) => {
    const q = questionText || input;
    if (!q.trim() || loading) return;

    // Append user message
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.askAssistant(projectId, q);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.answer,
          evidence: res.evidence_points || [],
          followups: res.suggested_followups || [],
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Error analyzing inquiry: ${err.message}`,
          evidence: [],
          followups: ["What should we fix first?", "Why is project health declining?"],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="assistant-drawer-backdrop" onClick={onClose}>
      <div className="assistant-drawer" onClick={(e) => e.stopPropagation()}>
        <header className="assistant-header">
          <div className="assistant-title-row">
            <div className="assistant-avatar">🤖</div>
            <div>
              <h3 className="assistant-title">AI Engineering Assistant</h3>
              <span className="assistant-sub">Grounded in project telemetry & causal graph</span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="assistant-messages-container">
          {messages.map((m, idx) => (
            <div key={idx} className={`chat-message ${m.role}`}>
              <div className="chat-bubble">
                <p className="chat-text">{m.text}</p>

                {m.evidence && m.evidence.length > 0 && (
                  <div className="chat-evidence-box">
                    <span className="evidence-label">📌 Grounded Evidence Sources:</span>
                    <ul>
                      {m.evidence.map((ev, i) => (
                        <li key={i}>{ev}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {m.followups && m.followups.length > 0 && (
                  <div className="chat-followups">
                    <span className="followup-label">Suggested follow-ups:</span>
                    <div className="followup-chips">
                      {m.followups.map((f, i) => (
                        <button
                          key={i}
                          className="followup-chip"
                          onClick={() => handleSend(f)}
                          disabled={loading}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-message assistant">
              <div className="chat-bubble loading">
                <span className="dot-pulse" /> Analyzing live project state & reasoning…
              </div>
            </div>
          )}
        </div>

        <form
          className="assistant-input-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            type="text"
            className="assistant-input"
            placeholder="Ask about project risks, anomalies, recommendations..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn primary assistant-send-btn" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
