"""
AI Action Planner Agent — AI Software Engineering Intelligence Platform.

Enriches prioritized recommendations with structured, actionable engineering plans:
- Problem: Precise statement of the finding
- Why it matters: System impact and business risk
- Root cause: Diagnostic causality based on upstream dependencies
- Recommended action: Concrete remediation step
- Expected impact: Projected metric turnaround %
- Estimated effort: Engineering story points / sprint days
- Priority: Critical / High / Medium / Low
- Confidence: Statistical confidence %
- Success criteria: Clear, measurable verification milestone
"""

from dataclasses import dataclass
from typing import Optional, Any
from app.agents.config import AgentConfig, default_config, DEFAULT_TARGETS, METRIC_DEPENDENCIES


@dataclass
class ActionPlan:
    problem: str
    why_it_matters: str
    root_cause: str
    recommended_action: str
    expected_impact: str
    estimated_effort: str  # e.g., "3 story points (~2-3 days)"
    priority: str
    confidence_pct: int
    success_criteria: str


ACTION_TEMPLATES = {
    "test_coverage": {
        "why": "Uncovered code paths allow regressions to slip into production, inflating defect density and MTTR.",
        "root": "Accelerated release cadences without corresponding unit/integration test coverage mandates on pull requests.",
        "action": "Enforce PR coverage gates in CI pipeline and mandate tests for all newly modified domain service methods.",
        "impact": "Expected +15% to +25% increase in test coverage within 1 sprint.",
        "success": "Test coverage exceeds target threshold of {target}% with 0 uncovered PR merges.",
        "effort_base": 3.0,
    },
    "cycle_time": {
        "why": "Long cycle times delay feature delivery, increase work-in-progress inventory, and slow customer feedback loops.",
        "root": "PRs awaiting review for extended durations, large PR sizes (>500 lines), and bottlenecks in stage verification.",
        "action": "Cap PR sizes to max 300 lines, introduce automated reviewer rotation, and implement 4-hour SLA alerts.",
        "impact": "Expected 30% reduction in lead/cycle time over next 2 sprints.",
        "success": "Average cycle time falls to < {target} days with 90% of PRs reviewed within 8 business hours.",
        "effort_base": 2.0,
    },
    "change_failure_rate": {
        "why": "High failure rates disrupt customer experience, trigger unplanned incident response, and reduce engineering velocity.",
        "root": "Insufficient automated integration tests, manual deployment steps, and environmental configuration drift.",
        "action": "Automate deployment smoke testing, enable canary traffic splitting, and introduce automated rollback triggers.",
        "impact": "Expected >40% decrease in deployment failure incidence.",
        "success": "Change failure rate drops below {target}% across all production deployments.",
        "effort_base": 5.0,
    },
    "deployment_frequency": {
        "why": "Infrequent deployments mean large batch sizes, higher blast radius per release, and slow delivery cadence.",
        "root": "Coupled release dependencies, lengthy manual QA sign-off cycles, and lack of feature toggle architecture.",
        "action": "Adopt trunk-based development with feature flags to decouple deployment from feature release.",
        "impact": "Expected 2x increase in deployment frequency.",
        "success": "Deployment frequency reaches at least {target} deployments per week.",
        "effort_base": 4.0,
    },
    "mttr": {
        "why": "Extended recovery times prolong user outages, breach SLAs, and severely damage operational reliability.",
        "root": "Missing distributed tracing, fragmented alerting, and manual diagnostic runbooks during live incidents.",
        "action": "Create standardized runbooks, automate rollback pipelines, and set up unified APM service dashboards.",
        "impact": "Expected 50% reduction in time-to-recovery.",
        "success": "Mean Time to Recovery stabilizes below {target} hours.",
        "effort_base": 3.5,
    },
    "code_churn": {
        "why": "High code churn signals developer confusion, shifting requirements, and architectural instability.",
        "root": "Unclear acceptance criteria, rushed initial implementations, or churn in shared core library abstractions.",
        "action": "Conduct backlog refinement pre-sprint and require architectural design sign-off on complex modules.",
        "impact": "Expected 35% decrease in rework and code churn.",
        "success": "Code churn rate drops below {target}%.",
        "effort_base": 2.5,
    },
    "defect_density": {
        "why": "High defect rates degrade product quality, inflate customer support costs, and deplete developer morale.",
        "root": "Missing automated static analysis, lack of boundary testing, and accumulated technical debt.",
        "action": "Integrate SonarQube/linter scanning into PR pre-commit hooks and schedule dedicated bug-squash days.",
        "impact": "Expected 45% reduction in production bug reports.",
        "success": "Defect density drops below {target} defects/kloc.",
        "effort_base": 3.0,
    },
    "cyclomatic_complexity": {
        "why": "Complex code paths are difficult to reason about, prone to hidden bugs, and resistant to safe refactoring.",
        "root": "Deeply nested conditional logic, procedural design in OOP codebases, and monolithic utility classes.",
        "action": "Refactor complex branching into strategy patterns, polymorphic handlers, and decomposed helper functions.",
        "impact": "Expected 30% reduction in complexity scores across hotspot modules.",
        "success": "Average cyclomatic complexity drops to < {target} per function.",
        "effort_base": 4.0,
    },
    "sprint_velocity": {
        "why": "Volatile sprint velocity prevents predictable roadmap commitments and causes sprint spillover.",
        "root": "Unestimated spike tasks, unplanned production interrupt work, and over-committing story points.",
        "action": "Enforce strict Definition of Ready (DoR) and dedicate a fixed 15% capacity buffer for maintenance.",
        "impact": "Expected 20% improvement in velocity stability.",
        "success": "Sprint velocity consistently reaches or exceeds {target} story points with <10% variance.",
        "effort_base": 1.5,
    },
    "lead_time": {
        "why": "Long lead time delays value realization and indicates friction between product specification and engineering.",
        "root": "Backlog items sitting idle in 'Ready for Dev' or protracted staging QA verification queues.",
        "action": "Implement Kanban pull limits and automate staging environment provisioning for rapid acceptance testing.",
        "impact": "Expected 25% reduction in total concept-to-production lead time.",
        "success": "Lead time reduces to < {target} days.",
        "effort_base": 2.0,
    },
}


def build_action_plan(
    metric_key: str,
    title: str,
    priority_score: float,
    confidence_score: float,
    deviation_pct: float = 0.0,
    upstream_deps: Optional[list[str]] = None,
    cfg: Optional[AgentConfig] = None,
) -> ActionPlan:
    """
    Generate a complete AI action plan for a recommendation.
    """
    cfg = cfg or default_config()
    target_info = cfg.default_targets.get(metric_key, {"target": 10.0, "tolerance": 5.0})
    target_val = target_info.get("target", 10.0)

    template = ACTION_TEMPLATES.get(metric_key, {
        "why": "Metric is deviating from target threshold, indicating operational risk in software delivery.",
        "root": "Process bottlenecks or lack of continuous automated telemetry enforcement.",
        "action": "Conduct focused team retrospective and institute automated verification gates.",
        "impact": "Expected progressive return to baseline targets within 1-2 sprints.",
        "success": f"Metric recovers to target threshold of {target_val}.",
        "effort_base": 3.0,
    })

    # Derive priority label
    if priority_score >= 60:
        priority_label = "Critical"
    elif priority_score >= 30:
        priority_label = "High" if priority_score >= 45 else "Medium"
    else:
        priority_label = "Low"

    # Derive effort estimate
    effort_scale = max(0.8, min(2.5, 1.0 + (abs(deviation_pct) / 100.0)))
    points = round(template["effort_base"] * effort_scale, 1)
    days = max(1, round(points * 0.8))
    effort_str = f"{points} story points (~{days} days)"

    # Upstream causality
    deps = upstream_deps or METRIC_DEPENDENCIES.get(metric_key, [])
    root_cause_text = template["root"]
    if deps:
        root_cause_text = f"{root_cause_text} Driven by upstream metrics: {', '.join(deps)}."

    conf_pct = int(round(confidence_score * 100)) if confidence_score <= 1.0 else int(confidence_score)

    return ActionPlan(
        problem=title,
        why_it_matters=template["why"],
        root_cause=root_cause_text,
        recommended_action=template["action"],
        expected_impact=template["impact"],
        estimated_effort=effort_str,
        priority=priority_label,
        confidence_pct=max(10, min(99, conf_pct)),
        success_criteria=template["success"].format(target=target_val),
    )
