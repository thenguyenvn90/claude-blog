# Cannibalization Check — Phase 4.5 Reference

> Decision rules for resolving keyword overlap between new H2 sections (refresh) and existing published articles on the same site.

## Why this check exists

When refreshing an article, the temptation is to add new H2 sections covering related topics. Risk: a new H2 may target queries that an existing sibling article on the same site already ranks for. Result:

- Both articles confuse Google about which is the primary signal for those queries
- Both rank lower than either would alone
- Article freshness signal is wasted because the new section just steals from existing one

The cannibalization check prevents this by running BEFORE write (Phase 4.5), not after.

## When to run

| Mode | Run Phase 4.5? |
|------|----------------|
| Light refresh (stats update, no new H2) | ❌ SKIP (no new content to cannibalize) |
| Medium / Full refresh adding new H2 | ✅ RUN |
| Site has <10 published articles | ⚠️ Optional (low collision risk) |
| User passes `--skip-cannibal` flag | ❌ SKIP |

## Detection method

### Check 1 — GSC query overlap (Tier 1 only, if GSC connected)

For each "Add New" H2 in `refresh-plan.md`, extract target keywords, then query GSC for last 90 days:

```python
gsc --format json query "sc-domain:[site]" \
  --start-date [90d_ago] --end-date [3d_ago] \
  --dimensions query,page --row-limit 25000 \
  --filter "query contains [keyword]"
```

If multiple pages on the same site rank for that query → cannibalization risk.

### Check 2 — Title overlap (universal, all tiers)

Pull all article titles via WP REST API:

```python
GET /wp-json/wp/v2/posts?per_page=100&_fields=slug,title&page=N (paginate)
```

Grep titles for keyword fragments. List sibling articles whose title contains any new-H2 keywords.

### Check 3 — DataForSEO page-intersection (Tier 2, optional)

If GSC unavailable but DataForSEO subscribed:

```python
/seo dataforseo page-intersection [site] --keyword "[new H2 keyword]"
```

DFS reports which pages on the site rank for that keyword.

## Severity decision matrix

For each new H2 vs each candidate sibling article:

| Match type | Severity | Action |
|------------|----------|--------|
| Same exact phrase + same intent (informational vs informational) | 🔴 HIGH | **REMOVE** new H2 from refresh-plan.md OR merge target into sibling article instead |
| Same exact phrase + different intent (informational vs transactional) | 🟡 MED | Proceed but add bidirectional internal link; differentiate H2 angle clearly |
| Related phrase + same intent (e.g., "claude code skills" vs "claude code skill examples") | 🟡 MED | Proceed with cross-link; ensure each article has unique value |
| Related phrase + different intent | 🟢 LOW | Proceed with optional cross-link |
| Same broad topic + different specific angle | 🟢 LOW | Proceed |
| No overlap detected | ✅ SAFE | Proceed |

## Intent classification heuristics

Determine intent from article title + URL + first H2:

| Signal | Intent |
|--------|--------|
| Title contains "what is", "định nghĩa", "guide" | **Informational** |
| Title contains "best", "vs", "comparison" | **Commercial investigation** |
| Title contains "buy", "price", "pricing", "discount" | **Transactional** |
| Title contains "how to", "tutorial", "step-by-step" | **Informational (procedural)** |
| Title is brand name + "review" | **Commercial review** |

## Output format — `cannibal-check.md`

```markdown
# Cannibalization Check — [slug]

Generated: 2026-05-24T14:00:00Z
Site: [site]
Sibling articles scanned: 47 (via WP REST)
GSC queries analyzed: 1,247 (last 90 days)

## Decision per new H2

### ✅ New H2 "Cập Nhật MCP Tháng 5/2026" — SAFE
- No GSC queries overlap with other ongboit articles
- No title contains "mcp tháng 5"
- Action: Proceed as planned

### 🟡 New H2 "Code Execution Pattern" — MED overlap
- GSC: /claude-code-prompt-engineering/ has 3 queries containing "code execution"
- Intent: Both informational
- Action: Proceed BUT add `<a>` cross-link from new section to /claude-code-prompt-engineering/
- Differentiate: this article covers MCP-specific patterns, sibling covers general prompt engineering

### 🔴 New H2 "Sub-Agents là gì?" — HIGH overlap (REMOVED)
- GSC: /claude-code-sub-agents/ ranks #4 for "sub agents claude" (45 impressions/mo)
- Sibling title: "Sub-Agents trong Claude Code — Hướng dẫn 2026"
- Intent: Both informational, same target
- Action: REMOVED from refresh-plan.md
- Alternative: link to /claude-code-sub-agents/ from a brief mention in this article's existing FAQ

## Summary

| New H2 | Severity | Final action |
|--------|----------|--------------|
| Cập Nhật MCP Tháng 5/2026 | ✅ SAFE | Proceed |
| Code Execution Pattern | 🟡 MED | Proceed + cross-link |
| Sub-Agents là gì? | 🔴 HIGH | REMOVED |

Effective new H2 count after cannibal check: 2 of 3 planned.
```

## Update refresh-plan.md after check

Append a `## Cannibalization Check` section to refresh-plan.md mirroring the decision table. Future agents reading the plan see the cannibal context.

## Anti-patterns

| Pattern | Why bad |
|---------|---------|
| Skip cannibal check because "small site" without counting articles | Confirmation bias — count first, then decide |
| Run cannibal check AFTER writing | Too late — wasted effort on H2 you'll remove |
| Treat every overlap as HIGH | Most are MED/LOW with good cross-linking |
| Add overlap H2 anyway "because the angle is different" without cross-link | Google still gets confused — must link explicitly |
| Manually scan sibling articles via WP admin instead of REST API | Slow + incomplete — use the script |
