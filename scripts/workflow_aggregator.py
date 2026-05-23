"""
workflow_aggregator.py — SQLite index of all ng-* workflow-log.json files.

Rebuilds on demand (no incremental writes). Enables fast cross-article and
cross-site queries without scanning every article folder.

Subcommands:
  index-all --working-dir PATH
      Scan articles/*/*/workflow-log.json → rebuild ~/.claude/data/ng-workflows.db

  query cost-by-site [--days N]
      Total cost per site over last N days (default 30).

  query top-expensive [--site X] [--days N] [--limit 10]
      Most expensive articles.

  query trend --skill SKILL [--site X] [--days N]
      Cost/duration/quality trend for a given skill.

  query errors [--days N]
      Recent errors across all articles.

DB lives at: ~/.claude/data/ng-workflows.db (SQLite, rebuilt from scratch each index-all)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


DB_PATH = Path.home() / ".claude" / "data" / "ng-workflows.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    slug         TEXT NOT NULL,
    site         TEXT NOT NULL,
    started_at   TEXT,
    status       TEXT,
    total_usd    REAL,
    duration_sec INTEGER,
    composite_score REAL,
    word_count   INTEGER,
    seed_keyword TEXT,
    -- v5.2 additions (lifecycle timestamps + decay signal)
    publish_date   TEXT,    -- from publish-info.json; drives age-based decay
    last_updated   TEXT,    -- any content PUT via ng-publish or ng-rewrite
    last_audit_at  TEXT,    -- set by ng-audit end
    last_refresh_at TEXT,   -- set by ng-rewrite end
    decay_signal   TEXT,    -- set by ng-decay: Critical|High|Medium|Low|null
    PRIMARY KEY (slug, site)
);

CREATE TABLE IF NOT EXISTS phases (
    slug         TEXT NOT NULL,
    site         TEXT NOT NULL,
    phase        INTEGER NOT NULL,
    skill        TEXT NOT NULL,
    status       TEXT,
    started_at   TEXT,
    ended_at     TEXT,
    duration_sec INTEGER,
    total_usd    REAL,
    llm_model    TEXT,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    errors_count INTEGER,
    retries      INTEGER,
    -- v5.2 additions
    cache_hit    INTEGER DEFAULT 0,   -- 1 if phase reused cached artefacts
    PRIMARY KEY (slug, site, phase)
);

CREATE INDEX IF NOT EXISTS idx_articles_site ON articles(site);
CREATE INDEX IF NOT EXISTS idx_articles_started ON articles(started_at);
CREATE INDEX IF NOT EXISTS idx_articles_publish ON articles(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_decay ON articles(decay_signal);
CREATE INDEX IF NOT EXISTS idx_phases_skill ON phases(skill);
CREATE INDEX IF NOT EXISTS idx_phases_site_skill ON phases(site, skill);
CREATE INDEX IF NOT EXISTS idx_phases_cache ON phases(cache_hit);
"""


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def find_workflow_logs(working_dir: Path):
    """Yield (site, slug, log_path) for all workflow-log.json files."""
    articles_root = working_dir / "articles"
    if not articles_root.is_dir():
        return
    # Multi-site layout: articles/[site]/[slug]/workflow-log.json
    for site_dir in articles_root.iterdir():
        if not site_dir.is_dir() or site_dir.name == "_site":
            continue
        # Real site dirs contain "."; anything else is legacy flat slug
        if "." in site_dir.name:
            for slug_dir in site_dir.iterdir():
                if not slug_dir.is_dir() or slug_dir.name == "_site":
                    continue
                log = slug_dir / "workflow-log.json"
                if log.exists():
                    yield site_dir.name, slug_dir.name, log
        else:
            # Legacy flat layout (shouldn't exist after migration, but support it)
            log = site_dir / "workflow-log.json"
            if log.exists():
                yield "unknown", site_dir.name, log


def cmd_index_all(args):
    working_dir = Path(args.working_dir).resolve()
    # Wipe existing data (rebuild from scratch)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = ensure_db()
    cur = conn.cursor()

    total = 0
    for site, slug, log_path in find_workflow_logs(working_dir):
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  skip {log_path}: {e}", file=sys.stderr)
            continue

        totals = data.get("totals", {})
        quality = totals.get("quality", {})
        started_at = data.get("workflow_started_at")

        # v5.2: pull lifecycle timestamps from publish-info.json (migrated by migrate_publish_info.py)
        publish_date = last_updated = last_audit_at = last_refresh_at = decay_signal = None
        pub_info_path = log_path.parent / "publish-info.json"
        if pub_info_path.is_file():
            try:
                pub = json.loads(pub_info_path.read_text(encoding="utf-8"))
                publish_date = pub.get("publish_date")
                last_updated = pub.get("last_updated")
                last_audit_at = pub.get("last_audit_at")
                last_refresh_at = pub.get("last_refresh_at")
                decay_signal = pub.get("decay_signal")
            except (OSError, json.JSONDecodeError):
                pass

        cur.execute(
            "INSERT OR REPLACE INTO articles (slug, site, started_at, status, total_usd, "
            "duration_sec, composite_score, word_count, seed_keyword, "
            "publish_date, last_updated, last_audit_at, last_refresh_at, decay_signal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                slug, site, started_at,
                data.get("workflow_status"),
                totals.get("total_usd", 0.0),
                totals.get("duration_sec", 0),
                quality.get("composite_score") or quality.get("audit_score"),
                quality.get("word_count"),
                data.get("seed_keyword"),
                publish_date, last_updated, last_audit_at, last_refresh_at, decay_signal,
            ),
        )
        for phase in data.get("phases", []):
            costs = phase.get("costs", {})
            llm = costs.get("llm", {})
            metrics = phase.get("metrics", {}) or {}
            # v5.2: cache_hit flag. Either status=="cached" OR metrics.cache_source != "fresh"
            cache_hit = 1 if (
                phase.get("status") == "cached"
                or metrics.get("cache_source") in {"cached", "cache-expired-reused"}
            ) else 0
            cur.execute(
                "INSERT OR REPLACE INTO phases (slug, site, phase, skill, status, "
                "started_at, ended_at, duration_sec, total_usd, llm_model, tokens_in, "
                "tokens_out, errors_count, retries, cache_hit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    slug, site, phase.get("phase"), phase.get("skill"),
                    phase.get("status"), phase.get("started_at"), phase.get("ended_at"),
                    phase.get("duration_sec", 0), costs.get("total_usd", 0.0),
                    llm.get("model"), llm.get("tokens_in_est"), llm.get("tokens_out_est"),
                    len(phase.get("errors", [])), phase.get("retries", 0),
                    cache_hit,
                ),
            )
        total += 1

    conn.commit()
    conn.close()
    print(f"Indexed {total} articles into {DB_PATH}")


def cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_query(args):
    if not DB_PATH.exists():
        print("ERROR: DB not built. Run `index-all` first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    q = args.query_type
    since = cutoff_iso(args.days)

    if q == "cost-by-site":
        cur.execute(
            "SELECT site, COUNT(*) AS n, ROUND(SUM(total_usd), 4) AS total, "
            "ROUND(AVG(total_usd), 4) AS avg "
            "FROM articles WHERE started_at >= ? GROUP BY site ORDER BY total DESC",
            (since,),
        )
        rows = cur.fetchall()
        print(f"Cost by site (last {args.days}d)")
        print(f"{'Site':<25} {'Count':>6} {'Total USD':>12} {'Avg USD':>10}")
        print("-" * 55)
        for r in rows:
            print(f"{r['site']:<25} {r['n']:>6} {r['total']:>12.4f} {r['avg']:>10.4f}")

    elif q == "top-expensive":
        where = "WHERE started_at >= ?"
        params = [since]
        if args.site:
            where += " AND site = ?"
            params.append(args.site)
        cur.execute(
            f"SELECT slug, site, total_usd, duration_sec, composite_score "
            f"FROM articles {where} ORDER BY total_usd DESC LIMIT ?",
            params + [args.limit],
        )
        rows = cur.fetchall()
        print(f"Top {args.limit} expensive articles (last {args.days}d"
              + (f", site={args.site})" if args.site else ")"))
        print(f"{'Slug':<40} {'Site':<20} {'Cost':>9} {'Dur (s)':>8} {'Score':>6}")
        print("-" * 90)
        for r in rows:
            score = r['composite_score'] if r['composite_score'] is not None else "—"
            print(f"{r['slug']:<40} {r['site']:<20} {r['total_usd']:>9.4f} "
                  f"{r['duration_sec']:>8} {score:>6}")

    elif q == "trend":
        if not args.skill:
            print("ERROR: trend requires --skill", file=sys.stderr)
            sys.exit(1)
        where = "WHERE started_at >= ? AND skill = ?"
        params = [since, args.skill]
        if args.site:
            where += " AND site = ?"
            params.append(args.site)
        cur.execute(
            f"SELECT slug, site, total_usd, duration_sec, llm_model "
            f"FROM phases {where} ORDER BY started_at",
            params,
        )
        rows = cur.fetchall()
        if not rows:
            print(f"No phases found for skill={args.skill}")
            return
        costs = [r['total_usd'] for r in rows]
        durs = [r['duration_sec'] for r in rows]
        print(f"Trend for skill={args.skill} (last {args.days}d, n={len(rows)})")
        print(f"  Avg cost:     ${sum(costs)/len(costs):.4f}")
        print(f"  Avg duration: {sum(durs)/len(durs):.0f}s")
        print(f"  Total cost:   ${sum(costs):.4f}")
        models = {}
        for r in rows:
            m = r['llm_model'] or 'none'
            models[m] = models.get(m, 0) + 1
        print(f"  Models used:  {dict(models)}")

    elif q == "errors":
        cur.execute(
            "SELECT slug, site, skill, errors_count FROM phases "
            "WHERE errors_count > 0 AND started_at >= ? ORDER BY started_at DESC",
            (since,),
        )
        rows = cur.fetchall()
        print(f"Phases with errors (last {args.days}d, n={len(rows)})")
        for r in rows:
            print(f"  [{r['site']}] {r['slug']} — {r['skill']}: {r['errors_count']} error(s)")

    else:
        print(f"Unknown query type: {q}", file=sys.stderr)
        sys.exit(1)

    conn.close()


def cmd_build_stats(args):
    """Write articles/[site]/_site/workflow-stats.json — rolling per-site aggregate (v5.2).

    Consumed by ng-report for fast monthly reports without scanning all workflow-log.json.
    Idempotent: overwrites each run. Cheap to call after every phase end if desired.
    """
    if not DB_PATH.exists():
        print("ERROR: DB not built. Run `index-all` first.", file=sys.stderr)
        sys.exit(1)

    working_dir = Path(args.working_dir).resolve()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sites = [args.site] if args.site else [
        r["site"] for r in cur.execute("SELECT DISTINCT site FROM articles WHERE site != 'unknown'")
    ]

    for site in sites:
        stats_path = working_dir / "articles" / site / "_site" / "workflow-stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)

        # Lifetime totals
        lifetime_row = cur.execute(
            "SELECT COUNT(*) AS n, ROUND(SUM(total_usd), 4) AS cost, "
            "ROUND(AVG(composite_score), 1) AS avg_score, SUM(word_count) AS total_words, "
            "SUM(duration_sec) AS total_sec "
            "FROM articles WHERE site = ?", (site,)
        ).fetchone()

        # Per-month rollup (YYYY-MM from started_at)
        monthly_rows = cur.execute(
            "SELECT substr(started_at, 1, 7) AS month, COUNT(*) AS n, "
            "ROUND(SUM(total_usd), 4) AS cost, ROUND(AVG(composite_score), 1) AS avg_score, "
            "SUM(duration_sec) AS duration_sec "
            "FROM articles WHERE site = ? AND started_at IS NOT NULL "
            "GROUP BY month ORDER BY month DESC", (site,)
        ).fetchall()

        # Cache hits — how much cost saved via cache?
        cache_rows = cur.execute(
            "SELECT COUNT(*) AS n, skill FROM phases "
            "WHERE site = ? AND cache_hit = 1 GROUP BY skill", (site,)
        ).fetchall()

        # Skill breakdown (lifetime)
        skill_rows = cur.execute(
            "SELECT skill, COUNT(*) AS phase_count, ROUND(SUM(total_usd), 4) AS cost, "
            "SUM(duration_sec) AS dur, AVG(duration_sec) AS avg_dur "
            "FROM phases WHERE site = ? GROUP BY skill ORDER BY cost DESC", (site,)
        ).fetchall()

        # Decay inventory (v5.2)
        decay_rows = cur.execute(
            "SELECT decay_signal, COUNT(*) AS n FROM articles "
            "WHERE site = ? AND decay_signal IS NOT NULL GROUP BY decay_signal", (site,)
        ).fetchall()

        # Oldest publish_date still live — candidate for refresh
        oldest = cur.execute(
            "SELECT slug, publish_date FROM articles WHERE site = ? "
            "AND publish_date IS NOT NULL ORDER BY publish_date ASC LIMIT 5", (site,)
        ).fetchall()

        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload = {
            "schema_version": "5.2",
            "generated_at": now_iso,
            "site": site,
            "lifetime": {
                "articles": lifetime_row["n"] or 0,
                "total_cost_usd": lifetime_row["cost"] or 0.0,
                "avg_composite_score": lifetime_row["avg_score"],
                "total_words": lifetime_row["total_words"] or 0,
                "total_workflow_seconds": lifetime_row["total_sec"] or 0,
            },
            "monthly": [dict(r) for r in monthly_rows],
            "cache_hits_by_skill": {r["skill"]: r["n"] for r in cache_rows},
            "skill_breakdown": [dict(r) for r in skill_rows],
            "decay_inventory": {r["decay_signal"]: r["n"] for r in decay_rows},
            "oldest_published": [
                {"slug": r["slug"], "publish_date": r["publish_date"]} for r in oldest
            ],
        }

        stats_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {stats_path} ({len(monthly_rows)} months, {len(skill_rows)} skills)")

    conn.close()


def cmd_month_report(args):
    """Fast monthly report: reads workflow-stats.json + decay-report.json, no DB scan (v5.2 Track 6)."""
    working_dir = Path(args.working_dir).resolve()
    site = args.site
    stats_path = working_dir / "articles" / site / "_site" / "workflow-stats.json"
    decay_path = working_dir / "articles" / site / "_site" / "decay-report.json"
    roadmap_path = working_dir / "articles" / site / "_site" / "roadmap.md"

    if not stats_path.is_file():
        print(f"ERROR: {stats_path} not found. Run `workflow_aggregator.py build-stats --site {site}` first.", file=sys.stderr)
        sys.exit(1)

    stats = json.loads(stats_path.read_text(encoding="utf-8"))

    # Filter to target month
    month = args.month  # YYYY-MM
    month_row = next((m for m in stats.get("monthly", []) if m.get("month") == month), None)

    # Pull decay counts if available
    decay_summary = None
    if decay_path.is_file():
        try:
            decay_data = json.loads(decay_path.read_text(encoding="utf-8"))
            decay_summary = decay_data.get("summary")
        except json.JSONDecodeError:
            pass

    # Roadmap queue depth
    roadmap_depth = 0
    if roadmap_path.is_file():
        try:
            import re
            text = roadmap_path.read_text(encoding="utf-8")
            m = re.search(r'"entries":\s*\[([^\]]*)\]', text, re.DOTALL)
            if m:
                roadmap_depth = m.group(1).count('"slug":')
        except OSError:
            pass

    # Compose report
    print(f"# Monthly report: {site} — {month}\n")
    if not month_row:
        print(f"  (no activity indexed for {month})")
    else:
        print(f"**Shipped:**         {month_row['n']} articles")
        cost = month_row.get('cost', 0) or 0
        score = month_row.get('avg_score')
        duration = (month_row.get('duration_sec') or 0) / 60
        print(f"**Cost:**            ${cost:.4f}")
        print(f"**Avg composite:**   {score if score is not None else '—'}")
        print(f"**Total time:**      {duration:.1f} min")

    print()
    print(f"## Lifetime (site {site})")
    lifetime = stats.get("lifetime", {})
    print(f"  articles:       {lifetime.get('articles', 0)}")
    print(f"  total cost:     ${lifetime.get('total_cost_usd', 0):.4f}")
    print(f"  avg score:      {lifetime.get('avg_composite_score') or '—'}")
    print(f"  total words:    {lifetime.get('total_words', 0):,}")

    # Cache efficiency
    cache_hits = stats.get("cache_hits_by_skill", {})
    total_cache = sum(cache_hits.values())
    print(f"\n## Cache efficiency")
    if cache_hits:
        for skill, n in sorted(cache_hits.items()):
            print(f"  {skill:<20} {n} cache hit(s)")
    else:
        print(f"  (no cache hits yet — Track 1 kw-cache still warming up)")

    # Decay queue
    if decay_summary:
        print(f"\n## Decay inventory (from last /ng-decay scan)")
        for sig in ["Critical", "High", "Medium", "Low"]:
            n = decay_summary.get(sig) or 0
            if n:
                print(f"  {sig:<10} {n}")

    # Roadmap
    print(f"\n## Roadmap queue")
    print(f"  pending/drafted entries:  {roadmap_depth}")

    # Top-expensive month articles
    if not DB_PATH.exists():
        print(f"\n(DB not built — skip top-expensive section. Run `index-all` for full detail.)")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT slug, total_usd, composite_score, duration_sec "
        "FROM articles WHERE site = ? AND substr(started_at, 1, 7) = ? "
        "ORDER BY total_usd DESC LIMIT 3", (site, month)
    ).fetchall()
    if rows:
        print(f"\n## Top 3 expensive articles in {month}")
        for r in rows:
            score = r["composite_score"] if r["composite_score"] is not None else "—"
            print(f"  {r['slug']:<40} ${r['total_usd']:.4f}  score={score}")
    conn.close()


def main():
    p = argparse.ArgumentParser(prog="workflow_aggregator")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("index-all", help="Rebuild DB from workflow-log.json files")
    s.add_argument("--working-dir", default=os.getcwd())
    s.set_defaults(func=cmd_index_all)

    s = sub.add_parser("query", help="Run pre-canned query")
    s.add_argument("query_type", choices=["cost-by-site", "top-expensive", "trend", "errors"])
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--site", default=None)
    s.add_argument("--skill", default=None, help="For trend query")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("build-stats", help="Write per-site workflow-stats.json aggregates (v5.2)")
    s.add_argument("--working-dir", default=os.getcwd())
    s.add_argument("--site", default=None, help="Build for one site (default: all sites in DB)")
    s.set_defaults(func=cmd_build_stats)

    s = sub.add_parser("month-report", help="Fast monthly report from workflow-stats.json + decay-report (v5.2 Track 6)")
    s.add_argument("--working-dir", default=os.getcwd())
    s.add_argument("--site", required=True)
    s.add_argument("--month", required=True, help="YYYY-MM (e.g. 2026-04)")
    s.set_defaults(func=cmd_month_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
