#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io as _io, sys as _sys
_sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
_sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
workflow_tracker.py — Shared observability helper for ng-* blog workflow.

Usage from SKILL.md delivery step (via Bash):

  # Start a phase
  python3 ~/.claude/scripts/workflow_tracker.py start \
    --slug dataforseo-review --phase 1 --skill ng-research

  # Log an API call (incremental)
  python3 ~/.claude/scripts/workflow_tracker.py log-api \
    --slug dataforseo-review --phase 1 --tool dataforseo \
    --endpoint serp_organic_live_advanced --count 5

  # Log LLM usage (estimated from character counts)
  python3 ~/.claude/scripts/workflow_tracker.py log-llm \
    --slug dataforseo-review --phase 1 --model claude-sonnet-4-6 \
    --input-chars 33600 --output-chars 12800

  # End the phase — computes duration, aggregates costs
  python3 ~/.claude/scripts/workflow_tracker.py end \
    --slug dataforseo-review --phase 1 --status complete \
    --outputs articles/dataforseo-review/keyword-report.md,articles/dataforseo-review/cluster-plan.json

  # Get totals for reporting (reads everything, prints JSON summary)
  python3 ~/.claude/scripts/workflow_tracker.py totals --slug dataforseo-review

Writes to: articles/[slug]/workflow-log.json (appends, never overwrites completed phases).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PRICING_PATH = Path(__file__).parent / "pricing_tables.json"
ARTICLES_DIR = Path("articles")


def load_pricing():
    if not PRICING_PATH.exists():
        return {}
    with open(PRICING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def auto_resolve_site(slug):
    """Scan articles/*/[slug]/ to discover site. Returns site name or None."""
    if not ARTICLES_DIR.is_dir():
        return None
    hits = []
    for site_dir in ARTICLES_DIR.iterdir():
        if not site_dir.is_dir():
            continue
        if "." not in site_dir.name:
            continue
        if (site_dir / slug).is_dir():
            hits.append(site_dir.name)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"[warn] slug '{slug}' in multiple sites: {hits}. Pass --site.", file=sys.stderr)
        return None
    return None


def resolve_site(slug, site_flag):
    """Site resolution: explicit flag → auto-scan → legacy fallback → 'unknown'."""
    if site_flag:
        return site_flag
    resolved = auto_resolve_site(slug)
    if resolved:
        return resolved
    if (ARTICLES_DIR / slug).is_dir():
        print(
            f"[warn] slug '{slug}' at legacy flat path articles/{slug}/. "
            f"Run migrate_to_multisite.py. Using site='unknown'.",
            file=sys.stderr,
        )
    return "unknown"


def log_path(slug, site):
    """New: articles/[site]/[slug]/workflow-log.json. Legacy: articles/[slug]/ when site=='unknown'."""
    if site and site != "unknown":
        return ARTICLES_DIR / site / slug / "workflow-log.json"
    return ARTICLES_DIR / slug / "workflow-log.json"


CURRENT_SCHEMA_VERSION = "2.0"


def load_log(slug, site):
    p = log_path(slug, site)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "article_slug": slug,
            "site": site,
            "workflow_started_at": now_iso(),
            "workflow_status": "in_progress",
            "phases": [],
            "totals": {},
        }
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Backfill + version check
    if not data.get("site"):
        data["site"] = site
    found_version = data.get("schema_version")
    if not found_version:
        print(f"[warn] workflow-log.json missing schema_version, assuming {CURRENT_SCHEMA_VERSION}", file=sys.stderr)
        data["schema_version"] = CURRENT_SCHEMA_VERSION
    elif found_version != CURRENT_SCHEMA_VERSION:
        print(
            f"[warn] workflow-log.json schema_version={found_version} (expected {CURRENT_SCHEMA_VERSION}). "
            f"Some fields may fall back to defaults.",
            file=sys.stderr,
        )
    return data


def save_log(slug, site, data):
    p = log_path(slug, site)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def with_site(args):
    """Resolve site from --site flag or auto-detect. Mutates args.site."""
    args.site = resolve_site(args.slug, getattr(args, "site", None))
    return args


def find_phase(data, phase_num):
    for ph in data["phases"]:
        if ph["phase"] == phase_num:
            return ph
    return None


def cmd_start(args):
    args = with_site(args)
    data = load_log(args.slug, args.site)
    existing = find_phase(data, args.phase)
    if existing and existing.get("status") in ("complete", "cached") and not args.force:
        print(f"[skip] Phase {args.phase} ({args.skill}) already {existing.get('status')}. Use --force to re-run.")
        return
    phase = {
        "phase": args.phase,
        "skill": args.skill,
        "status": "in_progress",
        "started_at": now_iso(),
        "ended_at": None,
        "duration_sec": 0,
        "outputs": [],
        "costs": {
            "api": {},
            "llm": {},
            "total_usd": 0.0,
        },
        "metrics": {},
        "errors": [],
        "retries": 0,
    }
    if existing:
        phase["retries"] = existing.get("retries", 0) + 1
        data["phases"] = [p for p in data["phases"] if p["phase"] != args.phase]
    data["phases"].append(phase)
    save_log(args.slug, args.site, data)
    print(f"[start] Phase {args.phase} {args.skill} at {phase['started_at']}")


def cmd_log_api(args):
    args = with_site(args)
    data = load_log(args.slug, args.site)
    phase = find_phase(data, args.phase)
    if not phase:
        print(f"[err] Phase {args.phase} not started. Run 'start' first.", file=sys.stderr)
        sys.exit(1)
    pricing = load_pricing().get(args.tool, {})
    per_call = pricing.get(args.endpoint, pricing.get("_default", 0))
    total_usd = per_call * args.count
    api_entry = phase["costs"]["api"].setdefault(args.tool, {"calls": 0, "breakdown": {}, "usd": 0.0})
    api_entry["calls"] += args.count
    api_entry["breakdown"][args.endpoint] = api_entry["breakdown"].get(args.endpoint, 0) + args.count
    api_entry["usd"] = round(api_entry["usd"] + total_usd, 6)
    save_log(args.slug, args.site, data)
    print(f"[api] {args.tool} {args.endpoint} x{args.count} = ${total_usd:.6f}")


def cmd_log_llm(args):
    args = with_site(args)
    data = load_log(args.slug, args.site)
    phase = find_phase(data, args.phase)
    if not phase:
        print(f"[err] Phase {args.phase} not started.", file=sys.stderr)
        sys.exit(1)
    pricing = load_pricing().get("claude_llm", {}).get(args.model, {})
    tokens_in = args.input_chars // 4
    tokens_out = args.output_chars // 4
    in_rate = pricing.get("cached_input_per_1m" if args.cached else "input_per_1m", 0)
    out_rate = pricing.get("output_per_1m", 0)
    usd = (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
    llm_entry = phase["costs"]["llm"]
    llm_entry["model"] = args.model
    llm_entry["tokens_in_est"] = llm_entry.get("tokens_in_est", 0) + tokens_in
    llm_entry["tokens_out_est"] = llm_entry.get("tokens_out_est", 0) + tokens_out
    llm_entry["usd_est"] = round(llm_entry.get("usd_est", 0) + usd, 6)
    llm_entry["estimation_method"] = "char_count/4"
    save_log(args.slug, args.site, data)
    print(f"[llm] {args.model} in={tokens_in} out={tokens_out} = ~${usd:.4f}")


def cmd_end(args):
    args = with_site(args)
    data = load_log(args.slug, args.site)
    phase = find_phase(data, args.phase)
    if not phase:
        print(f"[err] Phase {args.phase} not started.", file=sys.stderr)
        sys.exit(1)
    phase["ended_at"] = now_iso()
    started = datetime.fromisoformat(phase["started_at"].replace("Z", "+00:00"))
    ended = datetime.fromisoformat(phase["ended_at"].replace("Z", "+00:00"))
    phase["duration_sec"] = int((ended - started).total_seconds())
    phase["status"] = args.status
    if args.outputs:
        for path in args.outputs.split(","):
            path = path.strip()
            if not path:
                continue
            size_kb = 0
            try:
                if Path(path).exists():
                    size_kb = round(Path(path).stat().st_size / 1024, 1)
            except OSError:
                pass
            ptype = "data" if path.endswith((".json", ".csv")) else ("image" if path.endswith((".webp", ".png", ".jpg", ".avif")) else "report")
            phase["outputs"].append({"path": path, "size_kb": size_kb, "type": ptype})
    if args.metrics:
        try:
            phase["metrics"] = json.loads(args.metrics)
        except json.JSONDecodeError:
            phase["errors"].append(f"bad --metrics JSON: {args.metrics}")
    if args.error:
        phase["errors"].append(args.error)
    api_total = sum(v.get("usd", 0) for v in phase["costs"]["api"].values())
    llm_total = phase["costs"]["llm"].get("usd_est", 0)
    phase["costs"]["total_usd"] = round(api_total + llm_total, 6)
    save_log(args.slug, args.site, data)
    print(f"[end] Phase {args.phase} {phase['skill']} in {phase['duration_sec']}s, ${phase['costs']['total_usd']:.4f}")


def compute_roi(data):
    """Project ROI from Phase 1 metrics (volume, cpc) + standard CTR assumption."""
    research_phase = next((p for p in data["phases"] if p["skill"] == "ng-research"), None)
    if not research_phase:
        return None
    metrics = research_phase.get("metrics", {})
    volume = metrics.get("primary_volume") or metrics.get("est_monthly_searches") or 0
    cpc = metrics.get("primary_cpc_usd") or metrics.get("est_cpc_usd") or 0
    if not volume or not cpc:
        return None
    est_ctr_rank_1_3 = 0.30
    est_monthly_clicks = int(volume * est_ctr_rank_1_3)
    est_monthly_value = round(est_monthly_clicks * cpc, 2)
    return {
        "est_monthly_searches": volume,
        "est_cpc_usd": cpc,
        "est_ctr_rank_1_3": est_ctr_rank_1_3,
        "est_monthly_clicks": est_monthly_clicks,
        "est_monthly_value_usd": est_monthly_value,
        "note": "Assumes ranking 1-3. Actual CTR varies 10-35%. Break-even month = cost / monthly_value."
    }


def cmd_totals(args):
    args = with_site(args)
    data = load_log(args.slug, args.site)
    total_sec = sum(p.get("duration_sec", 0) for p in data["phases"])
    total_usd = round(sum(p["costs"].get("total_usd", 0) for p in data["phases"]), 6)
    cost_by_phase = {p["skill"]: round(p["costs"].get("total_usd", 0), 4) for p in data["phases"]}
    cost_by_tool = {}
    for p in data["phases"]:
        for tool, entry in p["costs"].get("api", {}).items():
            cost_by_tool[tool] = round(cost_by_tool.get(tool, 0) + entry.get("usd", 0), 6)
        llm_model = p["costs"].get("llm", {}).get("model")
        if llm_model:
            key = f"claude_llm:{llm_model}"
            cost_by_tool[key] = round(cost_by_tool.get(key, 0) + p["costs"]["llm"].get("usd_est", 0), 6)
    quality = next((p.get("metrics", {}) for p in data["phases"] if p["skill"] == "ng-audit"), {})
    errors_all = []
    retries_total = 0
    for p in data["phases"]:
        retries_total += p.get("retries", 0)
        for e in p.get("errors", []):
            errors_all.append(f"[{p['skill']}] {e}")
    roi = compute_roi(data)
    totals = {
        "duration_sec": total_sec,
        "duration_human": f"{total_sec // 60}m {total_sec % 60}s",
        "total_usd": total_usd,
        "cost_by_phase": cost_by_phase,
        "cost_by_tool": cost_by_tool,
        "quality": quality,
        "errors": errors_all,
        "retries_total": retries_total,
    }
    if roi:
        totals["roi_projection"] = roi
        if total_usd > 0 and roi["est_monthly_value_usd"] > 0:
            totals["roi_projection"]["breakeven_months"] = round(total_usd / roi["est_monthly_value_usd"], 2)
    data["totals"] = totals
    if all(p["status"] == "complete" for p in data["phases"]) and len(data["phases"]) >= 4:
        data["workflow_status"] = "complete"
    save_log(args.slug, args.site, data)
    print(json.dumps(totals, indent=2, ensure_ascii=False))


def cmd_budget_check(args):
    """Exit 1 if total_usd exceeds max_usd. For CI/pre-publish gate."""
    args = with_site(args)
    data = load_log(args.slug, args.site)
    total_usd = sum(p["costs"].get("total_usd", 0) for p in data["phases"])
    if total_usd > args.max_usd:
        overage = round(total_usd - args.max_usd, 4)
        print(f"FAIL: total ${total_usd:.4f} exceeds budget ${args.max_usd:.4f} (over by ${overage:.4f})")
        print("Breakdown by phase:")
        for p in data["phases"]:
            print(f"  {p['skill']}: ${p['costs'].get('total_usd', 0):.4f}")
        sys.exit(1)
    remaining = round(args.max_usd - total_usd, 4)
    print(f"PASS: ${total_usd:.4f} / ${args.max_usd:.4f} budget ({remaining:.4f} remaining)")
    sys.exit(0)


def add_site_arg(parser):
    """Add --site flag; optional because we auto-resolve from articles/*/[slug]/."""
    parser.add_argument("--site", default=None,
                        help="Site identifier (e.g. ongboit.com). Auto-resolved if omitted.")


def main():
    p = argparse.ArgumentParser(prog="workflow_tracker")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.add_argument("--phase", type=int, required=True)
    s.add_argument("--skill", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("log-api")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.add_argument("--phase", type=int, required=True)
    s.add_argument("--tool", required=True, help="dataforseo, firecrawl, gemini_image")
    s.add_argument("--endpoint", required=True)
    s.add_argument("--count", type=int, default=1)
    s.set_defaults(func=cmd_log_api)

    s = sub.add_parser("log-llm")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.add_argument("--phase", type=int, required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--input-chars", type=int, required=True)
    s.add_argument("--output-chars", type=int, required=True)
    s.add_argument("--cached", action="store_true")
    s.set_defaults(func=cmd_log_llm)

    s = sub.add_parser("end")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.add_argument("--phase", type=int, required=True)
    s.add_argument("--status", default="complete", choices=["complete", "failed", "skipped", "cached"])
    s.add_argument("--outputs", default="", help="comma-separated file paths")
    s.add_argument("--metrics", default="", help="JSON string of metrics")
    s.add_argument("--error", default="")
    s.set_defaults(func=cmd_end)

    s = sub.add_parser("totals")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.set_defaults(func=cmd_totals)

    s = sub.add_parser("budget-check", help="Exit 1 if total cost exceeds --max-usd")
    s.add_argument("--slug", required=True)
    add_site_arg(s)
    s.add_argument("--max-usd", type=float, required=True)
    s.set_defaults(func=cmd_budget_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
