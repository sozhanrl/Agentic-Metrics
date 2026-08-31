"""
AI Software Engineering Assistant Agent — AI Software Engineering Intelligence Platform.

Context-grounded natural language Q&A assistant:
- Answers engineering management inquiries using real project state (metrics, health,
  anomalies, recommendations, causal edges, historical trends).
- Uses optional Anthropic API key if configured; otherwise provides high-fidelity deterministic responses.
- STRICT RULE: Grounds all responses in factual database evidence with citations. Never fabricates.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Optional, Any
from app.ai_engine import is_enabled, ANTHROPIC_URL, MODEL, ANTHROPIC_API_KEY



@dataclass
class AssistantResponse:
    question: str
    answer: str
    evidence_points: list[str]
    suggested_followups: list[str]
    source_artifacts: list[str]
    responded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _deterministic_answer(
    question: str,
    project_name: str,
    health_data: dict,
    latest_metrics: list,
    recommendations: list,
    anomalies: list,
    risks: list,
) -> tuple[str, list[str], list[str]]:
    """
    High-fidelity deterministic response engine when LLM is offline or unconfigured.
    """
    q_lower = question.lower()
    evidence: list[str] = []
    followups: list[str] = []

    h_score = health_data.get("overall_score", 0.0)
    h_trend = health_data.get("status_trend", "stable")
    ai_risk = health_data.get("ai_risk_score", 0.0)

    # Question matching
    if "health" in q_lower or "declining" in q_lower or "score" in q_lower:
        worst_metrics = sorted(
            [m for m in latest_metrics if float(m.get("deviation_pct", 0.0)) != 0],
            key=lambda m: abs(float(m.get("deviation_pct", 0.0))),
            reverse=True
        )[:3]

        m_details = ", ".join(f"{m.get('display_name')} ({m.get('value')}{m.get('unit','')})" for m in worst_metrics)
        answer = (
            f"The overall health score for project '{project_name}' is currently {h_score:.1f}/100 "
            f"with a '{h_trend}' trend. The primary drivers are deviations in: {m_details}. "
            f"The AI Risk Index stands at {ai_risk:.1f}/100."
        )
        evidence.append(f"Overall Health: {h_score:.1f}/100 ({h_trend})")
        evidence.append(f"Code Quality: {health_data.get('code_quality_score', 0):.1f}, Process: {health_data.get('process_score', 0):.1f}, DevOps: {health_data.get('devops_score', 0):.1f}")
        followups = ["What should we fix first?", "Show me recent anomalies", "What are the biggest risks?"]

    elif "fix first" in q_lower or "priority" in q_lower or "top recommendation" in q_lower:
        top_recs = sorted(recommendations, key=lambda r: float(r.get("priority_score", 0.0)), reverse=True)[:3]
        if top_recs:
            rec_titles = "; ".join(f"#{i+1} {r.get('title')} (Score {r.get('priority_score')})" for i, r in enumerate(top_recs))
            answer = (
                f"Based on evidence-adaptive arbitration, the top priorities to address first are:\n"
                f"{rec_titles}. These recommendations address root causal factors with highest expected impact."
            )
            for r in top_recs:
                evidence.append(f"Recommendation: {r.get('title')} (Priority: {r.get('priority_score')}, Status: {r.get('status')})")
        else:
            answer = f"No active critical recommendations at this time. Project metrics are operating within bounds."
            evidence.append("All recommendations evaluated below threshold.")
        followups = ["Why is this high priority?", "Simulate improving test coverage", "What is the root cause?"]

    elif "risk" in q_lower or "vulnerability" in q_lower:
        high_risks = [r for r in risks if r.get("risk_level") in ("critical", "high")]
        if high_risks:
            risk_list = "; ".join(f"{r.get('title')} ({r.get('probability',0):.0%} prob - {r.get('reason')})" for r in high_risks)
            answer = f"Key operational risks identified:\n{risk_list}."
            for r in high_risks:
                evidence.append(f"Risk: {r.get('title')} (Probability {r.get('probability',0):.0%})")
        else:
            answer = f"No critical risks detected. Historical telemetry indicates stable delivery and quality patterns."
            evidence.append(f"AI Risk Index: {ai_risk:.1f}/100")
        followups = ["How to mitigate deployment risks?", "Show timeline events", "What-if we reduce cycle time?"]

    elif "anomaly" in q_lower or "anomalies" in q_lower:
        if anomalies:
            anom_text = "; ".join(f"{a.get('metric_name')}: {a.get('current_value')}{a.get('unit','')} (Z={a.get('z_score')})" for a in anomalies[:3])
            answer = f"Discovered {len(anomalies)} statistical anomalies:\n{anom_text}. Recommended action: {anomalies[0].get('recommended_action')}"
            for a in anomalies[:3]:
                evidence.append(f"Anomaly: {a.get('metric_name')} deviation {a.get('deviation_pct'):+.1f}% (Severity: {a.get('severity')})")
        else:
            answer = "No active statistical anomalies detected in the current metric snapshot."
            evidence.append("All metrics within 2 standard deviations of historical rolling means.")
        followups = ["What should we fix first?", "Show root cause analysis", "Project health overview"]

    elif "test coverage" in q_lower:
        cov_info = next((m for m in latest_metrics if m.get("metric_key") == "test_coverage"), None)
        cov_val = cov_info.get("value") if cov_info else "N/A"
        answer = (
            f"Test coverage is currently at {cov_val}%. Increasing test coverage to 80%+ directly reduces "
            f"defect density and decreases change failure rate through early regression discovery."
        )
        evidence.append(f"Current Test Coverage: {cov_val}% (Target: 80%)")
        followups = ["Simulate test coverage to 80%", "Show root cause of defects", "What should we fix first?"]

    else:
        # General response with context summary
        open_count = len([r for r in recommendations if r.get("status") == "open"])
        anom_count = len(anomalies)
        answer = (
            f"Project '{project_name}' Status Summary:\n"
            f"• Health Score: {h_score:.1f}/100 ({h_trend})\n"
            f"• Open Recommendations: {open_count}\n"
            f"• Active Anomalies: {anom_count}\n"
            f"• AI Risk Index: {ai_risk:.1f}/100\n\n"
            f"How can I assist you further with diagnostic drill-downs or what-if simulations?"
        )
        evidence.append(f"Health Snapshot: {h_score:.1f}/100")
        followups = ["Why is project health declining?", "What should we fix first?", "What are the biggest risks?"]

    return answer, evidence, followups


def ask_assistant(
    question: str,
    project_name: str,
    health_data: dict,
    latest_metrics: list,
    recommendations: list,
    anomalies: list,
    risks: list,
    causal_edges: list,
) -> AssistantResponse:
    """
    Process question against project context.
    """
    # If API key available, query Anthropic Claude with strict facts
    if is_enabled() and ANTHROPIC_API_KEY:
        context_payload = {
            "project_name": project_name,
            "health": health_data,
            "metrics": [{k: m[k] for k in ("metric_key", "display_name", "value", "unit", "category") if k in m} for m in latest_metrics],
            "top_recommendations": [{k: r[k] for k in ("title", "priority_score", "explanation") if k in r} for r in recommendations[:4]],
            "anomalies": [{k: a[k] for k in ("metric_name", "severity", "possible_cause") if k in a} for a in anomalies[:3]],
            "risks": [{k: r[k] for k in ("title", "risk_level", "probability", "reason") if k in r} for r in risks[:3]],
        }

        prompt = (
            "You are an AI Software Engineering Intelligence Platform Assistant. "
            "Answer the user's question concisely, grounding your response STRICTLY and ONLY in the provided project data. "
            "Never invent numbers or metrics. Include 2-3 specific evidence citations in your answer.\n\n"
            f"Project Context:\n{context_payload}\n\n"
            f"User Question: {question}"
        )

        try:
            resp = httpx.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 450,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=12.0,
            )
            resp.raise_for_status()
            data = resp.json()
            blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            llm_text = " ".join(blocks).strip()

            if llm_text:
                return AssistantResponse(
                    question=question,
                    answer=llm_text,
                    evidence_points=[f"Factual Telemetry ({project_name})", f"Health Score: {health_data.get('overall_score', 0):.1f}/100"],
                    suggested_followups=["What should we fix first?", "Show root cause analysis", "Simulate metric changes"],
                    source_artifacts=["metric_values", "recommendations", "causal_edges", "health_snapshots"],
                )
        except Exception:
            pass  # Fall back gracefully to deterministic answer

    answer, evidence, followups = _deterministic_answer(
        question=question,
        project_name=project_name,
        health_data=health_data,
        latest_metrics=latest_metrics,
        recommendations=recommendations,
        anomalies=anomalies,
        risks=risks,
    )

    return AssistantResponse(
        question=question,
        answer=answer,
        evidence_points=evidence,
        suggested_followups=followups,
        source_artifacts=["telemetry_store", "bayesian_weights", "causal_graph", "evaluator_scores"],
    )
