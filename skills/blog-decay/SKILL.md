---
name: blog-decay
description: >
  Site-wide content decay detection. Scans every published article and ranks them
  by 5 decay signals: (1) age since publish/refresh, (2) GSC click decline 90d vs
  prior 90d window, (3) external link rot via sampled HTTP HEAD, (4) Jaccard SERP
  cannibalization between article pairs, (5) orphan/dead-end internal link graph
  position. Produces Critical/High/Medium/Low ranked queue feeding refresh workflow.
  Wraps Daniel's blog-audit (general health) with composite scoring for refresh
  prioritization. Use when user says "decay scan", "blog decay", "what should I
  refresh", "stale content audit", "content health check", "quarterly refresh".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
user-invokable: true
argument-hint: "[--site URL] [--gsc-property property] [--top N] [--export format]"
license: MIT
metadata:
  author: thenguyenvn90
  version: "0.3.1"
  category: maintenance
  source: "Ported from ng-decay (ongboit.com v5.15 — 5-signal composite ranking)"
---

# Blog Decay — Site-Wide Refresh Prioritization

> Scans every published article on a WordPress site, scores 5 decay signals, ranks Critical/High/Medium/Low. Output: prioritized refresh queue feeding `/blog rewrite` workflow.

## When to invoke

User says:
- "blog decay" / "decay scan"
- "what should I refresh?"
- "stale content audit"
- "content health check"
- "quarterly refresh planning"

Cadence: monthly OR after Google core update OR before quarterly content planning sprint.

## Prerequisites

- WordPress site with REST API + Application Password (read-only sufficient)
- Optional: Google Search Console access (for Signal 2 — click decline)
- Optional: `gsc` CLI tool installed (https://github.com/yourtools/gsc-cli)

If GSC access missing → Signal 2 skipped, composite weighted to other 4 signals.

## 5 Decay Signals

### Signal 1 — Age (weight: 0.20)

Days since last publish OR last meaningful update.

| Days | Score |
|-----:|------:|
| 0-90 | 0 (fresh) |
| 90-180 | 25 |
| 180-365 | 50 |
| 365-730 | 75 |
| 730+ | 100 (very stale) |

Modifier: -25 points if article was refreshed (`refreshed_at` meta) within last 90 days.

### Signal 2 — GSC click decline (weight: 0.30)

Clicks in last 90 days vs prior 90-day window. Requires GSC.

| Decline | Score |
|--------:|------:|
| < 10% | 0 (stable or growing) |
| 10-30% | 25 |
| 30-50% | 50 |
| 50-70% | 75 |
| 70%+ | 100 (cratered) |

If GSC unavailable → score = 0 (don't penalize when no data), redistribute weight to other signals.

### Signal 3 — External link rot (weight: 0.15)

Sampled HTTP HEAD on outbound external links.

Sample size: up to 10 external links per article (random sample if more).

| Broken links | Score |
|-------------:|------:|
| 0 | 0 |
| 1 | 30 |
| 2 | 60 |
| 3+ | 100 |

### Signal 4 — Jaccard SERP cannibalization (weight: 0.20)

Pairwise comparison: how many top-10 SERP URLs overlap with sibling articles on same site for same query?

Uses DataForSEO SERP cache OR live SERP fetch.

| Jaccard overlap | Score |
|----------------:|------:|
| 0-0.2 | 0 (distinct intents) |
| 0.2-0.4 | 25 |
| 0.4-0.6 | 50 |
| 0.6-0.8 | 75 |
| 0.8+ | 100 (cannibalizing) |

### Signal 5 — Orphan / dead-end (weight: 0.15)

| Internal link state | Score |
|---------------------|------:|
| Healthy (≥1 inbound + ≥1 outbound) | 0 |
| Dead-end (≥1 inbound, 0 outbound) | 50 |
| Orphan (0 inbound, ≥1 outbound) | 75 |
| Isolated (0 inbound, 0 outbound) | 100 (worst case) |

## Composite scoring

```python
def calculate_decay_score(signals):
    """
    signals = dict with keys: age, gsc_decline, link_rot, cannibal, orphan
    Each value: 0-100
    Returns composite 0-100.
    """
    weights = {
        "age":         0.20,
        "gsc_decline": 0.30,
        "link_rot":    0.15,
        "cannibal":    0.20,
        "orphan":      0.15,
    }
    # If GSC unavailable (gsc_decline = None), redistribute weight
    if signals.get("gsc_decline") is None:
        weights["gsc_decline"] = 0
        # Redistribute 0.30 proportionally to other 4 signals
        for k in ["age", "link_rot", "cannibal", "orphan"]:
            weights[k] += 0.30 * (weights[k] / 0.70)

    composite = sum(signals.get(k, 0) * w for k, w in weights.items() if signals.get(k) is not None)
    return composite
```

## Ranking buckets

| Composite | Bucket | Action |
|----------:|--------|--------|
| 75-100 | **Critical** | Refresh within 7 days |
| 50-74 | **High** | Refresh within 30 days |
| 25-49 | **Medium** | Refresh within 90 days |
| 0-24 | **Low** | Monitor, no immediate action |

## Workflow

```bash
Step 1: Enumerate published articles
  - GET /wp-json/wp/v2/posts?per_page=100&status=publish
  - Pagination until all retrieved
  - Extract: post_id, slug, title, published, modified, content

Step 2: Score each article on 5 signals
  - Signal 1 (Age): from modified field
  - Signal 2 (GSC): query gsc CLI OR Search Console API for slug
  - Signal 3 (Link rot): regex extract external <a href>, HEAD each
  - Signal 4 (Cannibal): for each article's primary keyword, compare SERP top-10 vs same site's other articles
  - Signal 5 (Orphan): for each article, count inbound + outbound internal links across site

Step 3: Calculate composite + bucket
  - Per article: composite_score (0-100), bucket (Critical/High/Medium/Low)
  - Sort by composite descending

Step 4: Output decay-report.md (or JSON if --export json)
```

## Output format

`decay-report-YYYY-MM-DD.md`:

```markdown
# Decay Report — yoursite.com (2026-05-23)

Total articles scanned: 47
GSC available: yes

## Critical (≥75) — 3 articles, refresh within 7 days

| Score | URL | Age | GSC Δ | Link rot | Cannibal | Orphan | Recommended action |
|------:|-----|----:|------:|---------:|---------:|-------:|--------------------|
| 87 | /old-pillar-article/ | 730d | -65% | 2/8 | 0.4 | healthy | Full refresh + restructure |
| 82 | /outdated-tutorial/ | 540d | -55% | 3/12 | 0.3 | dead-end | Add 3 outbound links + refresh content |
| 76 | /article-vs-old-tool/ | 365d | -40% | 1/5 | 0.7 | healthy | Distinguish from sibling cluster member |

## High (50-74) — 8 articles, refresh within 30 days

[...]

## Medium (25-49) — 15 articles, refresh within 90 days

[...]

## Low (<25) — 21 articles, monitor only

[...]

## Auto-queue suggestion

3 Critical + 8 High articles → queue for `/blog rewrite` per cadence:

Week 1: /blog rewrite /old-pillar-article/
Week 2: /blog rewrite /outdated-tutorial/
Week 3: /blog rewrite /article-vs-old-tool/
Week 4+: queue High bucket
```

## Flags

- `--site [name]` — multi-site mode (scans only articles for that site)
- `--gsc-property [property]` — GSC property override (default: derived from BRAND.md)
- `--top N` — show only top N articles by composite
- `--export json|md|csv` — output format
- `--no-gsc` — skip Signal 2 (faster, less accurate)
- `--auto-queue` — automatically add Critical + High to editorial calendar (via blog-calendar)

## Integration with blog-pipeline

After running blog-decay:
- Output `decay-report-YYYY-MM-DD.md` in project root
- Critical + High slugs feed into `/blog calendar` queue
- User invokes `/blog rewrite [slug]` per article (or `--auto-queue` automates)

## References

| File | What it covers |
|------|----------------|
| `references/5-signal-scoring.md` | Detailed scoring criteria per signal |
| `references/orphan-detection.md` | Internal link graph traversal logic |
| `references/cannibal-detection.md` | Jaccard SERP overlap calculation |

## Implementation status

🚧 **v0.1.0** — SKILL.md complete with 5-signal scoring spec. Python implementation pending — patterns documented in references but full code not shipped.

For Python impl, see `~/.claude/skills/ng-decay/scripts/decay.py` (ongboit.com production source) — has full 5-signal scorer + WP REST traversal + GSC integration. Port to fork main when needed.

## Source

Ported from ng-decay v5.15 (ongboit.com, 2026-04-XX). 5-signal composite + ranking buckets directly mapped. Vietnamese-specific scoring (diacritic ratio decay) NOT ported — English/generic only.
