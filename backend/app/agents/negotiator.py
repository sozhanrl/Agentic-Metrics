"""
Negotiator Agent — Cross-Metric Conflict Resolution (v2).

Responsibility:
  After the Evaluator has scored every recommendation independently, the
  Negotiator detects and resolves two kinds of over-counting:

  1. Static conflict pairs (unchanged from v1)
     Metric pairs that are structurally in tension (e.g. "reduce code churn"
     and "increase test coverage" both compete for the same focused refactoring
     bandwidth).  When both appear, the lower-priority member takes a small
     score penalty.

  2. Empirical graph-discount (NEW in v2)
     When the Dependency Discovery engine has found a causal edge
     source → target (e.g. cyclomatic_complexity → defect_density),
     surfacing both as independent top priorities double-counts the problem:
     fixing the source should also fix the target.  The downstream target
     (symptom) is discounted so the root-cause source floats to the top.

Penalty stacking and cap
------------------------
Both penalties may apply to the same recommendation.  To prevent a single
metric from being unfairly suppressed, the COMBINED penalty is capped at
cfg.max_total_penalty (default 25%).  Individual penalties are applied
additively up to this cap.

Design principles
-----------------
* Only penalise the *lower* member of a conflict pair / the *downstream target*
  of a graph edge — never inflate the higher / upstream member.
* Apply at most one conflict-pair penalty per recommendation (even if it
  participates in multiple conflict pairs).
* Graph-discount and conflict penalties stack additively up to max_total_penalty.
* Record every applied penalty in the reasoning trail so it is fully auditable.
"""

from app.agents.perceiver import MetricSignal
from app.agents.config import AgentConfig, default_config


def negotiate(
    scored: list[tuple[MetricSignal, float]],
    cfg: AgentConfig | None = None,
    graph_edges: list | None = None,
) -> list[tuple[MetricSignal, float, str | None]]:
    """
    Apply conflict-resolution and graph-discount penalties to scored recommendations.

    Parameters
    ----------
    scored      : list of (MetricSignal, priority_score) tuples, sorted highest-first
                  (as returned by evaluator.evaluate_all)
    cfg         : AgentConfig
    graph_edges : list of MetricDependencyGraph ORM objects (or any object/dict with
                  source_metric_key and target_metric_key attributes), as returned by
                  crud.get_latest_dependency_edges.  May be None or empty — the agent
                  degrades gracefully to static-conflict-only behaviour.

    Returns
    -------
    list of (MetricSignal, adjusted_score, conflict_note | None)
      Sorted highest adjusted_score first.
      conflict_note is non-None only for penalised recommendations.
    """
    cfg = cfg or default_config()

    # Map metric key → (index in list, current score) for O(1) lookups.
    key_index: dict[str, int] = {sig.key: i for i, (sig, _) in enumerate(scored)}

    # Track accumulated penalty fraction per index (caps at max_total_penalty).
    accumulated_penalty: dict[int, float] = {}

    # Working copies — we mutate these, not the originals.
    scores         = [s for _, s in scored]
    conflict_notes: list[str | None] = [None] * len(scored)
    note_parts: list[list[str]] = [[] for _ in range(len(scored))]

    # -----------------------------------------------------------------------
    # Pass 1 — Static conflict pairs (same as v1)
    # -----------------------------------------------------------------------
    penalised_by_conflict: set[int] = set()

    for (key_a, key_b) in cfg.conflict_pairs:
        idx_a = key_index.get(key_a)
        idx_b = key_index.get(key_b)

        if idx_a is None or idx_b is None:
            continue  # one or both not in this batch

        lower_idx  = idx_a if scores[idx_a] <= scores[idx_b] else idx_b
        higher_idx = idx_b if lower_idx == idx_a else idx_a

        if lower_idx in penalised_by_conflict:
            continue  # already got a conflict penalty; cap at one per rec

        penalty = min(cfg.conflict_penalty,
                      cfg.max_total_penalty - accumulated_penalty.get(lower_idx, 0.0))
        if penalty <= 0:
            continue

        sig_higher = scored[higher_idx][0]
        sig_lower  = scored[lower_idx][0]
        old_score  = scores[lower_idx]
        new_score  = round(old_score * (1 - penalty), 1)
        scores[lower_idx] = new_score
        accumulated_penalty[lower_idx] = accumulated_penalty.get(lower_idx, 0.0) + penalty
        penalised_by_conflict.add(lower_idx)

        note = (
            f"[Negotiator] conflict-penalty −{penalty:.0%}: "
            f"'{sig_lower.display_name}' conflicts with higher-priority "
            f"'{sig_higher.display_name}' (both compete for developer capacity). "
            f"Score {old_score} → {new_score}."
        )
        note_parts[lower_idx].append(note)

        sig_lower.agent_steps.append({
            "agent":  "Negotiator",
            "action": "conflict-penalty",
            "detail": note,
        })
        scored[higher_idx][0].agent_steps.append({
            "agent":  "Negotiator",
            "action": "conflict-noted",
            "detail": (
                f"'{sig_higher.display_name}' retained full priority; "
                f"'{sig_lower.display_name}' penalised as lower-priority conflict member."
            ),
        })

    # -----------------------------------------------------------------------
    # Pass 2 — Graph-discount for discovered causal dependency edges
    # -----------------------------------------------------------------------
    if graph_edges:
        # Build a set of (source_key, target_key) pairs from the discovered edges.
        edge_pairs: set[tuple[str, str]] = set()
        for e in graph_edges:
            src = getattr(e, "source_metric_key", None) or e.get("source_metric_key", "")
            tgt = getattr(e, "target_metric_key", None) or e.get("target_metric_key", "")
            if src and tgt:
                edge_pairs.add((src, tgt))

        for (source_key, target_key) in edge_pairs:
            src_idx = key_index.get(source_key)
            tgt_idx = key_index.get(target_key)

            if src_idx is None or tgt_idx is None:
                continue  # one or both not in this recommendation batch

            # Discount the downstream target (symptom); leave source (root cause) untouched.
            current_accumulated = accumulated_penalty.get(tgt_idx, 0.0)
            remaining_capacity  = cfg.max_total_penalty - current_accumulated
            penalty = min(cfg.graph_discount, remaining_capacity)
            if penalty <= 0:
                continue  # already at max total penalty

            sig_source = scored[src_idx][0]
            sig_target = scored[tgt_idx][0]
            old_score  = scores[tgt_idx]
            new_score  = round(old_score * (1 - penalty), 1)
            scores[tgt_idx] = new_score
            accumulated_penalty[tgt_idx] = current_accumulated + penalty

            note = (
                f"[Negotiator] graph-discount −{penalty:.0%}: "
                f"'{sig_target.display_name}' is empirically downstream of "
                f"'{sig_source.display_name}' (discovered causal edge). "
                f"Treating source as root cause; suppressing symptom. "
                f"Score {old_score} → {new_score}."
            )
            note_parts[tgt_idx].append(note)

            sig_target.agent_steps.append({
                "agent":  "Negotiator",
                "action": "graph-discount",
                "detail": note,
            })
            scored[src_idx][0].agent_steps.append({
                "agent":  "Negotiator",
                "action": "graph-root-cause",
                "detail": (
                    f"'{sig_source.display_name}' identified as root cause of "
                    f"'{sig_target.display_name}'; root cause retained full priority."
                ),
            })

    # -----------------------------------------------------------------------
    # Assemble notes and re-sort by adjusted score
    # -----------------------------------------------------------------------
    for i, parts in enumerate(note_parts):
        if parts:
            conflict_notes[i] = " | ".join(parts)

    result = [
        (sig, scores[i], conflict_notes[i])
        for i, (sig, _) in enumerate(scored)
    ]
    result.sort(key=lambda t: t[1], reverse=True)
    return result
