# Report Templates

## Single-Article Report: `workflow-report.md`

```markdown
# Workflow Report: [Article Title]

**Article:** `articles/[slug]/`
**Seed keyword:** [seed_keyword]
**Site:** [site]
**Workflow started:** [workflow_started_at]
**Status:** ✅ complete | ⚠️ in_progress | ❌ failed

---

## 1. Executive Summary

> **Score [N]/100** · **$[total_usd]** · **[duration_human]**
> [One-sentence verdict: "Published successfully, quality strong, cost within target" OR "Failed at Phase X" OR "Over budget by $X"]

---

## 2. Phase Breakdown

| # | Skill | Status | Duration | Cost | Outputs |
|---|-------|--------|----------|------|---------|
| 1 | ng-research | ✅ | 3m 45s | $0.084 | keyword-report.md (12KB), cluster-plan.json (8KB) |
| 2 | ng-cluster | ✅ | 2m 10s | $0.032 | cluster-plan.json, cluster-map.html |
| 3 | ng-brief | ✅ | 4m 20s | $0.128 | brief.md (5KB) |
| 4 | ng-write | ✅ | 6m 50s | $0.182 | blog.md (18KB), write-log.md |
| 5 | ng-audit | ✅ | 2m 15s | $0.046 | audit-report.md |
| 6 | ng-image | ✅ | 3m 50s | $0.080 | 4 × .webp images |
| 7 | ng-publish | ✅ | 1m 30s | $0.008 | publish-info.json |

**Total:** [total_duration] · $[total_usd]

---

## 3. Cost by Tool

| Tool | Calls | Cost | % of total |
|------|-------|------|-----------|
| DataForSEO API | 28 | $0.0067 | 1.3% |
| Gemini (image gen) | 4 | $0.32 | 61.5% |
| Firecrawl | 5 | $0.005 | 1.0% |
| Claude LLM (est.) | — | $0.19 | 36.2% |

Pie-chart ASCII (optional):
```
Gemini         ████████████████████████ 61%
Claude LLM     ██████████████████░░░░░░ 36%
DataForSEO     █░░░░░░░░░░░░░░░░░░░░░░░  1%
Firecrawl      █░░░░░░░░░░░░░░░░░░░░░░░  1%
```

---

## 4. Cost by LLM Model

| Model | Est. tokens | Cost | Phases that used it |
|-------|------------|------|---------------------|
| claude-sonnet-4-6 | 11,600 in / 4,200 out | $0.097 | ng-research, ng-brief, ng-write |
| claude-opus-4-6 | 3,400 in / 1,800 out | $0.186 | ng-audit (parallel agents) |

**⚠️ Notice:** Token counts are ESTIMATED via character-count heuristic (char/4). Actual usage may differ by ±20%.

---

## 5. Quality Scores

| Metric | Score | Status |
|--------|-------|--------|
| Composite audit | [N]/100 | ✅/⚠️/❌ |
| SEO validation | [N]/[max] | |
| GEO citability | [N]/100 | |
| E-E-A-T | [N]/100 | |
| AI detection risk | [N]% | ✅ < 30% = safe |
| Word count | [N] | within target? |
| Images | [N] | featured + [N] section |
| Internal links | [N] | ≥ 3 required |

---

## 6. ROI Projection

Based on Phase 1 research data:

| Signal | Value |
|--------|-------|
| Est. monthly search volume | [N] |
| Avg CPC (Google Ads benchmark) | $[X] |
| Est. organic CTR at rank 1-3 | 30% |
| Est. monthly organic clicks | [N] |
| Est. article value (30 days) | $[N] |
| Est. breakeven | Month [N] |

**Cost-to-value ratio:** $[total_usd] invested → $[monthly_value] expected monthly return.

---

## 7. Optimization Hints

Rule-based suggestions to reduce future cost:

- 🔸 **[Rule A]**: "ng-audit used claude-opus-4-6 ($0.186). Switching to sonnet-4-6 would save ~$0.149 (-80%). Only applicable if audit quality remained ≥ 85."
- 🔸 **[Rule B]**: "ng-image generated 4 × 2K images ($0.32). If 1K is acceptable, switching saves ~$0.16 (-50%)."
- 🔸 **[Rule C]**: "Phase 2 DataForSEO ran 15 SERP calls. Cache expiry 7 days — reuse saved ng-research output cuts ~$0.030 on next article in same cluster."

Hints are advisory. User decides tradeoffs.

---

## 8. Error & Retry Log

| Phase | Errors | Retries | Notes |
|-------|--------|---------|-------|
| ng-research | 0 | 0 | — |
| ng-write | 1 | 1 | "Word count short, retried with expanded outline" |
| ng-image | 0 | 2 | "Style filter rejected 2 prompts, 3rd attempt succeeded" |

---

## Metadata

- Report generated: [timestamp]
- Schema version: 2.0
- Tracker version: workflow_tracker.py v1.0.0
```

---

## Compare Report: `workflow-compare-[slug2].md`

```markdown
# Article Comparison: [slug1] vs [slug2]

| Metric | [slug1] | [slug2] | Δ |
|--------|---------|---------|---|
| Audit score | 86 | 91 | +5 |
| Total cost | $0.52 | $0.68 | +$0.16 |
| Duration | 24m 40s | 31m 20s | +6m 40s |
| Word count | 1,992 | 2,450 | +458 |
| Words per $ | 3,831 | 3,603 | -228 |
| Images | 4 | 5 | +1 |

### Cost per phase side-by-side
| Phase | [slug1] | [slug2] |
|-------|---------|---------|
| ng-research | $0.084 | $0.091 |
| ng-brief | $0.128 | $0.140 |
...

### Verdict
[slug2] is 31% more expensive but 5 points higher quality. $0.032 per quality point — acceptable/not acceptable for your budget.
```

---

## Site Aggregate: `reports/site-[domain]-aggregate.md`

```markdown
# Site Aggregate Report: [domain]

**Period:** [start_date] → [end_date]
**Articles published:** [N]

## Summary
| Metric | Value |
|--------|-------|
| Total spend | $[N] |
| Avg cost per article | $[N] |
| Median cost per article | $[N] |
| Total words published | [N] |
| Avg quality score | [N]/100 |
| Avg production time | [N] min |

## Most expensive articles
| Slug | Cost | Score |
|------|------|-------|
| ... | ... | ... |

## Most efficient (words per $)
| Slug | Words/$ | Score |
|------|---------|-------|
| ... | ... | ... |

## Phase-level averages (across all articles)
| Phase | Avg duration | Avg cost |
|-------|--------------|----------|
| ng-research | [N]s | $[X] |
| ng-brief | [N]s | $[X] |
...
```
