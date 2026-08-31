"""
GitHub REST API Data Connector for Real Repository Metric Ingestion.

Strict Non-Randomness Guarantee:
- No synthetic values, no random generation, no fallbacks to other projects.
- Computes metrics strictly from live GitHub REST API responses for the exact repository.
- Unverifiable metrics (e.g. cyclomatic_complexity, test_coverage without badges) are
  explicitly omitted and recorded in `skipped_metrics`.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import re
import statistics
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import HTTPException
import httpx


@dataclass
class MetricSample:
    """A computed metric value derived from real GitHub API payloads."""
    value: float
    recorded_at: datetime
    raw_payload: Any = field(default_factory=dict)


def parse_github_url(repo_url: str) -> tuple[str, str]:
    """
    Parse and validate a GitHub repository URL.
    Accepts:
      - https://github.com/owner/repo
      - http://github.com/owner/repo
      - github.com/owner/repo
      - with or without trailing slashes and .git suffix

    Returns (owner, repo) or raises HTTPException 400.
    """
    if not repo_url or not isinstance(repo_url, str):
        raise HTTPException(
            status_code=400,
            detail="Repository URL is required and must be a valid GitHub URL (e.g. https://github.com/owner/repo).",
        )

    clean_url = repo_url.strip()
    if clean_url.endswith("/"):
        clean_url = clean_url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]

    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    parsed = urlparse(clean_url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in ("github.com", "www.github.com"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid repository URL host '{parsed.hostname}'. Only github.com repositories are supported.",
        )

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL format. Expected: https://github.com/{owner}/{repo}",
        )

    owner, repo = path_parts[0], path_parts[1]
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", owner) or not re.match(r"^[a-zA-Z0-9_\-\.]+$", repo):
        raise HTTPException(
            status_code=400,
            detail="Invalid characters in GitHub repository owner or name.",
        )

    return owner, repo


def _parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO8601 string from GitHub API into UTC datetime."""
    if not dt_str:
        return datetime.now(timezone.utc)
    # GitHub timestamps are usually like '2023-01-01T12:00:00Z'
    clean = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(clean)


async def _github_get(client: httpx.AsyncClient, endpoint: str) -> httpx.Response:
    """Execute a GET request against GitHub API with status code checking."""
    url = f"https://api.github.com{endpoint}"
    resp = await client.get(url)

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="GitHub repository not found or is private without sufficient token permissions.",
        )
    elif resp.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired GitHub authentication token.",
        )
    elif resp.status_code == 403:
        rate_limit_remaining = resp.headers.get("x-ratelimit-remaining")
        if rate_limit_remaining == "0":
            raise HTTPException(
                status_code=403,
                detail="GitHub API rate limit exceeded. Please provide a valid GitHub personal access token.",
            )
        raise HTTPException(
            status_code=403,
            detail=f"GitHub API access forbidden: {resp.text}",
        )
    return resp


async def fetch_repo_metrics(
    owner: str,
    repo: str,
    token: Optional[str] = None,
) -> tuple[dict[str, list[MetricSample]], list[str]]:
    """
    Calls the GitHub REST API (via httpx) for exactly one repository and
    returns real, computed MetricSample objects keyed by metric definition key,
    along with a list of skipped_metrics that could not be computed from real data.

    Returns:
        samples_by_metric: dict[metric_key, list[MetricSample]]
                           (list of samples permits backfilling weekly history)
        skipped_metrics: list of metric keys omitted due to lack of verifiable signal.
    """
    headers = {
        "User-Agent": "metrics-agent/2.0",
        "Accept": "application/vnd.github+json",
    }
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    samples_by_metric: dict[str, list[MetricSample]] = {}
    skipped_metrics: list[str] = []
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Explicitly omitted metrics (unverifiable from GitHub API alone)
    # -------------------------------------------------------------------------
    skipped_metrics.append("cyclomatic_complexity")
    skipped_metrics.append("test_coverage")

    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        # Verify repository accessibility
        repo_resp = await _github_get(client, f"/repos/{owner}/{repo}")
        repo_data = repo_resp.json()
        default_branch = repo_data.get("default_branch", "main")

        # ---------------------------------------------------------------------
        # 1. code_churn: GET /repos/{o}/{r}/stats/code_frequency
        # ---------------------------------------------------------------------
        try:
            cf_resp = await _github_get(client, f"/repos/{owner}/{repo}/stats/code_frequency")
            # GitHub returns 202 if calculating stats in background
            if cf_resp.status_code == 202:
                for _ in range(2):
                    await asyncio.sleep(1.0)
                    cf_resp = await _github_get(client, f"/repos/{owner}/{repo}/stats/code_frequency")
                    if cf_resp.status_code == 200:
                        break

            cf_data = cf_resp.json() if cf_resp.status_code == 200 else None
            if isinstance(cf_data, list) and len(cf_data) > 0:
                # Each element is [timestamp_seconds, additions, deletions] (deletions is negative)
                churn_samples = []
                recent_weeks = cf_data[-6:]  # Backfill up to last 6 weeks for trend detection
                for week in recent_weeks:
                    if isinstance(week, (list, tuple)) and len(week) >= 3:
                        ts, adds, dels = week[0], week[1], week[2]
                        week_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        total_churn = float(adds + abs(dels))
                        churn_samples.append(
                            MetricSample(
                                value=round(total_churn, 2),
                                recorded_at=week_dt,
                                raw_payload={"timestamp": ts, "additions": adds, "deletions": dels},
                            )
                        )
                if churn_samples:
                    samples_by_metric["code_churn"] = churn_samples
                else:
                    skipped_metrics.append("code_churn")
            else:
                skipped_metrics.append("code_churn")
        except Exception:
            skipped_metrics.append("code_churn")

        # ---------------------------------------------------------------------
        # 2. defect_density: GET /repos/{o}/{r}/issues?labels=bug & /languages
        # ---------------------------------------------------------------------
        try:
            lang_resp = await _github_get(client, f"/repos/{owner}/{repo}/languages")
            lang_data = lang_resp.json() if lang_resp.status_code == 200 else {}
            total_code_bytes = sum(lang_data.values()) if isinstance(lang_data, dict) else 0

            if total_code_bytes > 0:
                # ~35 bytes per line of code is standard across languages
                kloc = max(0.1, (total_code_bytes / 35.0) / 1000.0)

                issues_resp = await _github_get(
                    client, f"/repos/{owner}/{repo}/issues?labels=bug&state=all&per_page=100"
                )
                raw_issues = issues_resp.json() if issues_resp.status_code == 200 else []
                # Filter out PRs which GitHub issues API includes
                bug_issues = [i for i in raw_issues if isinstance(i, dict) and "pull_request" not in i]
                density = round(len(bug_issues) / kloc, 2)

                samples_by_metric["defect_density"] = [
                    MetricSample(
                        value=density,
                        recorded_at=now,
                        raw_payload={
                            "bug_count": len(bug_issues),
                            "kloc": round(kloc, 2),
                            "total_bytes": total_code_bytes,
                            "languages": lang_data,
                        },
                    )
                ]
            else:
                skipped_metrics.append("defect_density")
        except Exception:
            skipped_metrics.append("defect_density")

        # ---------------------------------------------------------------------
        # 3. sprint_velocity: GET /repos/{o}/{r}/issues?state=closed
        # ---------------------------------------------------------------------
        try:
            closed_resp = await _github_get(
                client, f"/repos/{owner}/{repo}/issues?state=closed&per_page=100"
            )
            raw_closed = closed_resp.json() if closed_resp.status_code == 200 else []
            closed_issues = [i for i in raw_closed if isinstance(i, dict) and "pull_request" not in i]

            if closed_issues:
                # Closed issues in trailing 28 days (4 weeks)
                cutoff_28d = now - timedelta(days=28)
                recent_closed = [
                    i for i in closed_issues
                    if i.get("closed_at") and _parse_iso_datetime(i["closed_at"]) >= cutoff_28d
                ]
                # If there are closed issues in 28d, compute per-week velocity
                # Otherwise if older closed issues exist, compute velocity over sample span
                if recent_closed:
                    velocity = round(len(recent_closed) / 4.0, 2)
                else:
                    # Trailing span of available closed issues
                    oldest_closed = min(_parse_iso_datetime(i["closed_at"]) for i in closed_issues if i.get("closed_at"))
                    span_weeks = max(1.0, (now - oldest_closed).total_seconds() / (7 * 86400))
                    velocity = round(len(closed_issues) / span_weeks, 2)

                samples_by_metric["sprint_velocity"] = [
                    MetricSample(
                        value=velocity,
                        recorded_at=now,
                        raw_payload={
                            "closed_issues_recent_28d": len(recent_closed),
                            "total_closed_sample": len(closed_issues),
                            "velocity_per_week": velocity,
                        },
                    )
                ]
            else:
                skipped_metrics.append("sprint_velocity")
        except Exception:
            skipped_metrics.append("sprint_velocity")

        # ---------------------------------------------------------------------
        # 4. cycle_time & 5. lead_time: GET /repos/{o}/{r}/pulls?state=closed
        # ---------------------------------------------------------------------
        merged_prs = []
        try:
            pulls_resp = await _github_get(
                client, f"/repos/{owner}/{repo}/pulls?state=closed&per_page=100"
            )
            raw_pulls = pulls_resp.json() if pulls_resp.status_code == 200 else []
            merged_prs = [p for p in raw_pulls if isinstance(p, dict) and p.get("merged_at")]
        except Exception:
            pass

        # Cycle time: issue/PR created_at -> PR merged_at (median hours)
        if merged_prs:
            cycle_hours_list = []
            for p in merged_prs:
                c_at = _parse_iso_datetime(p["created_at"])
                m_at = _parse_iso_datetime(p["merged_at"])
                hours = max(0.0, (m_at - c_at).total_seconds() / 3600.0)
                cycle_hours_list.append(hours)

            median_cycle = round(statistics.median(cycle_hours_list), 2)
            samples_by_metric["cycle_time"] = [
                MetricSample(
                    value=median_cycle,
                    recorded_at=now,
                    raw_payload={
                        "merged_prs_sample_size": len(merged_prs),
                        "median_cycle_time_hours": median_cycle,
                    },
                )
            ]
        else:
            skipped_metrics.append("cycle_time")

        # Lead time: first commit on PR -> merged_at (median hours)
        if merged_prs:
            lead_hours_list = []
            # Inspect first 15 merged PRs for commits
            sample_prs = merged_prs[:15]
            for p in sample_prs:
                pr_num = p.get("number")
                m_at = _parse_iso_datetime(p["merged_at"])
                try:
                    commits_resp = await _github_get(
                        client, f"/repos/{owner}/{repo}/pulls/{pr_num}/commits?per_page=10"
                    )
                    commits_data = commits_resp.json() if commits_resp.status_code == 200 else []
                    if isinstance(commits_data, list) and commits_data:
                        first_commit = commits_data[0]
                        commit_author_date = (
                            first_commit.get("commit", {}).get("author", {}).get("date")
                            or first_commit.get("commit", {}).get("committer", {}).get("date")
                        )
                        if commit_author_date:
                            first_commit_dt = _parse_iso_datetime(commit_author_date)
                            l_hours = max(0.0, (m_at - first_commit_dt).total_seconds() / 3600.0)
                            lead_hours_list.append(l_hours)
                except Exception:
                    continue

            if lead_hours_list:
                median_lead = round(statistics.median(lead_hours_list), 2)
                samples_by_metric["lead_time"] = [
                    MetricSample(
                        value=median_lead,
                        recorded_at=now,
                        raw_payload={
                            "lead_time_sample_size": len(lead_hours_list),
                            "median_lead_time_hours": median_lead,
                        },
                    )
                ]
            else:
                skipped_metrics.append("lead_time")
        else:
            skipped_metrics.append("lead_time")

        # ---------------------------------------------------------------------
        # DevOps metrics: deployment_frequency, change_failure_rate, mttr
        # GET /repos/{o}/{r}/actions/runs
        # ---------------------------------------------------------------------
        runs_data = []
        try:
            runs_resp = await _github_get(
                client, f"/repos/{owner}/{repo}/actions/runs?per_page=100"
            )
            if runs_resp.status_code == 200:
                raw_runs = runs_resp.json()
                runs_data = raw_runs.get("workflow_runs", []) if isinstance(raw_runs, dict) else []
        except Exception:
            runs_data = []

        if runs_data:
            # 6. deployment_frequency: successful deploy-tagged workflow runs / day
            deploy_keywords = ("deploy", "release", "prod", "publish", "cd", "delivery")
            successful_runs = [r for r in runs_data if r.get("conclusion") == "success" or r.get("status") == "completed"]
            deploy_runs = [
                r for r in successful_runs
                if any(kw in (r.get("name") or "").lower() or kw in (r.get("head_branch") or "").lower() for kw in deploy_keywords)
            ]

            target_runs = deploy_runs if deploy_runs else successful_runs
            if target_runs:
                run_dates = [_parse_iso_datetime(r["created_at"]) for r in target_runs if r.get("created_at")]
                oldest_run = min(run_dates) if run_dates else now
                days_span = max(1.0, (now - oldest_run).total_seconds() / 86400.0)
                deploy_freq = round(len(target_runs) / days_span, 2)

                samples_by_metric["deployment_frequency"] = [
                    MetricSample(
                        value=deploy_freq,
                        recorded_at=now,
                        raw_payload={
                            "successful_deploy_runs": len(target_runs),
                            "days_span": round(days_span, 2),
                            "deploy_frequency_per_day": deploy_freq,
                            "used_deploy_tag_filter": bool(deploy_runs),
                        },
                    )
                ]
            else:
                skipped_metrics.append("deployment_frequency")

            # 7. change_failure_rate: failed runs / total runs on default branch
            default_branch_runs = [r for r in runs_data if r.get("head_branch") == default_branch]
            evaluation_runs = default_branch_runs if default_branch_runs else runs_data

            if evaluation_runs:
                failed_runs = [
                    r for r in evaluation_runs
                    if r.get("conclusion") in ("failure", "timed_out", "cancelled")
                ]
                cfr = round((len(failed_runs) / len(evaluation_runs)) * 100.0, 2)
                samples_by_metric["change_failure_rate"] = [
                    MetricSample(
                        value=cfr,
                        recorded_at=now,
                        raw_payload={
                            "total_runs": len(evaluation_runs),
                            "failed_runs": len(failed_runs),
                            "change_failure_rate_pct": cfr,
                            "branch": default_branch if default_branch_runs else "all",
                        },
                    )
                ]
            else:
                skipped_metrics.append("change_failure_rate")

            # 8. mttr: failed run -> next successful run on same workflow (median hours)
            # Group by workflow_id
            by_workflow: dict[int, list] = {}
            for r in runs_data:
                wid = r.get("workflow_id")
                if wid is not None and r.get("created_at"):
                    by_workflow.setdefault(wid, []).append(r)

            mttr_hours = []
            for wid, w_runs in by_workflow.items():
                # Sort ascending by created_at
                sorted_w_runs = sorted(w_runs, key=lambda x: _parse_iso_datetime(x["created_at"]))
                for i in range(len(sorted_w_runs) - 1):
                    curr = sorted_w_runs[i]
                    nxt = sorted_w_runs[i + 1]
                    if curr.get("conclusion") == "failure" and nxt.get("conclusion") == "success":
                        t_fail = _parse_iso_datetime(curr["created_at"])
                        t_succ = _parse_iso_datetime(nxt["created_at"])
                        delta_h = max(0.0, (t_succ - t_fail).total_seconds() / 3600.0)
                        mttr_hours.append(delta_h)

            if mttr_hours:
                median_mttr = round(statistics.median(mttr_hours), 2)
                samples_by_metric["mttr"] = [
                    MetricSample(
                        value=median_mttr,
                        recorded_at=now,
                        raw_payload={
                            "recovery_events_count": len(mttr_hours),
                            "median_mttr_hours": median_mttr,
                        },
                    )
                ]
            else:
                skipped_metrics.append("mttr")
        else:
            skipped_metrics.append("deployment_frequency")
            skipped_metrics.append("change_failure_rate")
            skipped_metrics.append("mttr")

    return samples_by_metric, skipped_metrics
