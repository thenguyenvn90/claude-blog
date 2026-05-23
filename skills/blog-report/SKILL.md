---
name: blog-report
description: >
  Workflow observability + cost reporting for the blog-pipeline. Reads
  articles/[slug]/workflow-log.json produced by the shared workflow_tracker.py
  and generates a comprehensive end-of-article report (workflow-report.md) with
  time breakdown, cost by phase, cost by tool/LLM model, quality scores, and
  ROI projection. Supports A/B comparison of 2 articles and site-level aggregation.
  Typically called as the last step of blog-pipeline Phase 6, but can run standalone.
  Use when: "generate report", "workflow report", "cost breakdown", "blog report",
  "article cost", "compare articles", "site totals", "how much did this cost",
  "phase breakdown".
  NOT for: generating the data (workflow_tracker.py does that), auditing content
  quality (blog-analyze does that).
user-invokable: true
argument-hint: "<article-slug-dir> [--compare other-slug-dir] [--site domain] [--budget-check --max-usd N]"
license: MIT
compatibility: "Claude Code. Requires Python 3 + workflow_tracker.py at ~/.claude/scripts/"
metadata:
  version: "0.3.1"
  pipeline: "blog-pipeline v0.3"
  author: thenguyenvn90
  origin: "Ported from ng-report (ongboit.com workflow v5.14)"
---

# blog-report — Workflow Observability & Cost Reports

> Reads `workflow-log.json` produced by `workflow_tracker.py` → produces human-readable `workflow-report.md` + ASCII tables. Generic version of the ng-report skill (ongboit), refactored for the Daniel-native pipeline. Multi-site aware (articles/[site]/[slug]/).

## Commands

| Command | Description |
|---------|-------|
| `/blog report articles/[slug]/` | End-of-article report |
| `/blog report --compare articles/[slug1]/ articles/[slug2]/` | A/B compare 2 articles |
| `/blog report --site [domain]` | Aggregate all articles for a site |
| `/blog report articles/[slug]/ --budget-check --max-usd 0.50` | Fail if total > max |

---

## Step 1: Load Data

Ensure the article directory has `workflow-log.json`:
```bash
test -f articles/[slug]/workflow-log.json || echo "No log — workflow_tracker.py wasn't called"
```

If missing → advise user that pipeline phases must call `workflow_tracker.py` (auto-wired in blog-pipeline v0.3+). See `references/integration-guide.md`.

## Step 2: Compute Totals

```bash
python3 ~/.claude/scripts/workflow_tracker.py totals --slug [slug]
```

Aggregates `cost_by_phase`, `cost_by_tool`, total duration, and surfaces quality metrics from Phase 4 audit entries.

## Step 3: Generate Report

Read `references/report-templates.md` for full markdown structure.

Output: `articles/[slug]/workflow-report.md` with 8 sections:

1. **Executive Summary** — 1-line verdict (score + cost + time)
2. **Phase Breakdown Table** — per-phase time, cost, status, outputs
3. **Cost by Tool** — DataForSEO vs Gemini vs Firecrawl vs Claude LLM vs WebSearch
4. **Cost by LLM Model** — Opus 4.7 vs Sonnet 4.6 vs Haiku 4.5 usage (optimization hints)
5. **Quality Scores** — composite, SEO, GEO, AI detection, word count
6. **ROI Projection** — est. monthly searches × avg CPC = article value
7. **Optimization Hints** — rule-based suggestions ("Phase X on Opus > $Y → switch to Sonnet")
8. **Error & Retry Log** — phases with errors, retry counts

## Step 4: Compare Mode (`--compare`)

Side-by-side table across:
- Total time, total cost
- Cost per phase
- Quality scores
- Word count per $ (efficiency metric)
- Tier (1 GSC / 2 DFS / 3 WebSearch) — explains research cost variance

Output: `articles/[slug1]/workflow-compare-[slug2].md`

## Step 5: Site Mode (`--site`)

Scan all `articles/[site]/*/workflow-log.json` → aggregate:
- Total articles published (last 30/90 days)
- Avg cost per article
- Avg duration per article
- Cost trend (improving / steady / regressing)
- Total spend over period
- ROI rollup

Output: `reports/[site]-monthly-rollup.md`

## Step 6: Budget Check (`--budget-check`)

If `--max-usd N` passed → exit 1 if total article cost > N. Useful for CI gates.

```bash
/blog report articles/my-slug/ --budget-check --max-usd 0.75
# exit 0 if cost ≤ 0.75
# exit 1 + error message if > 0.75
```

---

## Integration with blog-pipeline

Pipeline auto-invokes after Phase 6 (or Phase 5 if `--no-publish`):

```bash
# Inside blog-pipeline Phase 7 (NEW v0.3):
python3 ~/.claude/scripts/workflow_tracker.py totals --slug $SLUG --site $SITE
/blog report articles/$SITE/$SLUG/
```

Each phase emits to workflow-log.json:
- `phase_start` / `phase_end` events
- `tool_call` events with cost (DFS, Gemini, Firecrawl)
- `llm_usage` events (model, input_tokens, output_tokens, cost)
- `quality_score` event from Phase 4 audit

See `references/integration-guide.md` for the full event schema + how to wire new tools/phases.

---

## Pricing tables

`~/.claude/scripts/pricing_tables.json` — rates for cost computation:

- **Claude API**: Opus 4.7 ($15/$75 per Mtok), Sonnet 4.6 ($3/$15), Haiku 4.5 ($0.80/$4)
- **DataForSEO**: per endpoint pricing (organic SERP: $0.0006/req, keyword data: $0.0005/req, …)
- **Gemini API**: 2.0 Flash $0.075/$0.30 per Mtok; 2.5 Pro $1.25/$5
- **Firecrawl**: scrape $0.001/page, crawl $0.005/page, search $0.005/req
- **Banana MCP**: $0.039/image (Nano Banana)
- **WebSearch**: $0 (free fallback)

Update pricing table when API providers change rates → `python3 workflow_tracker.py reprice --slug [slug]` recomputes historical logs.

---

## Output template

See `references/report-templates.md` for the full markdown template covering:
- Executive Summary callout
- Phase breakdown table (ASCII)
- Cost-by-tool pie chart (text rendered)
- LLM usage bar chart (text rendered)
- Quality scorecard
- ROI projection formula
- Optimization hint rules

---

## Multi-site support

`/blog report --site [domain]` → reads all `articles/[domain]/*/workflow-log.json` and rolls up.

Path resolution (auto):
- Single-site: `articles/[slug]/workflow-log.json`
- Multi-site: `articles/[site]/[slug]/workflow-log.json`

`workflow_tracker.py` auto-injects `"site": "[site]"` field when called from a `--site` pipeline run.

---

## Source

Ported from `ng-report` v1.1.0 (ongboit.com workflow v5.14). Vietnamese-specific report templates generalized for any-language output. Multi-site path conventions preserved. Pricing tables shared between ng-* and blog-* via single `~/.claude/scripts/pricing_tables.json`.
