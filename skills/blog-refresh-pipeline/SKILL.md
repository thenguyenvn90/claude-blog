---
name: blog-refresh-pipeline
description: >
  Master orchestrator for refreshing existing published blog articles. Auto-chains
  6 phases: pre-flight backup → diagnose → research → plan → cannibalization check
  → write+push → image audit → verify. Wraps Daniel's blog-rewrite + blog-cannibalization
  + blog-publish + blog-image with refresh-specific safety (live HTML backup, anti-pattern
  flags, per-H2 image audit). Mode auto-detected by char count (light/medium/full).
  Use when user says "/blog-refresh-pipeline", "refresh existing article",
  "update old blog post", "rewrite published article", or wants single-command
  refresh of a LIVE WordPress article (NOT for new article — use /blog-pipeline).
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Skill
user-invokable: true
argument-hint: "[url-or-path-or-slug] [--site URL] [--mode light|medium|full] [--skip-cannibal] [--skip-images] [--no-publish] [--dry-run]"
license: MIT
metadata:
  author: thenguyenvn90
  version: "0.4.0"
  category: orchestrator
  source: "Adapted from ng-* article-refresh-workflow v2.1 (ongboit.com — validated /mcp-la-gi/ indexed <24h)"
  references:
    - claude-growth/blog-publishing-workflow.md (canonical SOP)
    - skills/blog-refresh-pipeline/references/cannibalization-check.md
    - skills/blog-refresh-pipeline/references/rollback-procedure.md
---

# Blog Refresh Pipeline — Master Orchestrator

> Single entry-point for refreshing LIVE WordPress articles. 6-phase orchestration with rollback safety. Companion to `/blog-pipeline` (which writes NEW articles) — same folder convention, same tracker integration, opposite direction.

## When to invoke

User says any of:
- `/blog-refresh-pipeline [url]`
- "Refresh existing article on yoursite.com/slug"
- "Update old blog post"
- "Rewrite published article" (note: NOT `/blog rewrite` which is content-only)
- "Refresh content quality on [URL]"

**DO NOT** invoke for:
- Writing a NEW article from keyword → use `/blog-pipeline`
- Auditing without changing → use `/blog audit` or `/blog-pipeline --no-publish`
- "Crawled-not-indexed" recovery → this skill drops Phase 7/7.5/8 (GSC submit / escalation / performance tracking). Refresh content quality only.

## Prerequisites

Project folder MUST have:
- `BRAND.md` (or `sites/[site]/BRAND.md` for multi-site)
- `.mcp.json` with `wp-mcp-ultimate` credentials (for WP REST + Rank Math)
- Daniel skills loaded: `blog-rewrite`, `blog-cannibalization`, `blog-image`, `blog-publish` (via `/blog`)

If any missing → halt + invoke `/claude-growth-welcome`.

---

## Input formats (target argument)

`/blog-refresh-pipeline [target]` accepts 4 input formats:

| Input format | Resolution |
|--------------|------------|
| `https://site.com/slug/` | Parse domain → set `--site` + lookup `articles/[site]/[slug]/` (create if missing) |
| `articles/[site]/[slug]/` | Direct path, infer SITE from path |
| `[slug]` alone | Auto-detect SITE from current project root (single-site) OR prompt user (multi-site) |
| `[post_id]` (WP numeric) | Fetch slug from WP REST API via wp-mcp-ultimate, then resolve |

---

## Mode auto-detection

By char count of existing live HTML (backup taken in Phase 1):

| Backup char count | Mode | Phases enabled | Target delta |
|-------------------|------|----------------|--------------|
| **>5000** | `light` | 1, 2, 4, 5, 6 (skip 3, 4.5, 5.5) | +15-25% |
| **3000-5000** | `medium` (default) | All 6 phases | +25-40% |
| **<3000** | `full` | All 6 phases + deeper research | +50% |

User override: `--mode light|medium|full`.

---

## Article folder convention

Reuses `/blog-pipeline` folder convention. Refresh outputs append to existing folder (or create new if missing).

**Single-site (default)**:
```
[project-root]/
├── BRAND.md
└── articles/[slug]/
    ├── blog-v1-backup.html         ← Phase 1 backup (CRITICAL for rollback)
    ├── backup-meta.json            ← Phase 1 metadata snapshot
    ├── research.md                 ← Phase 3 (skip if Light mode)
    ├── refresh-plan.md             ← Phase 4
    ├── cannibal-check.md           ← Phase 4.5 (skip if --skip-cannibal)
    ├── blog.html                   ← Phase 5 new HTML
    ├── images/                     ← Phase 5.5 new images (skip if --skip-images)
    ├── pipeline-state.json         ← refresh-specific schema
    └── workflow-log.json           ← tracker events
```

**Multi-site (`--site` flag)**: `articles/[site]/[slug]/` (same as `/blog-pipeline`).

---

## Multi-language support

Inherits `BRAND.language` from project config (M13 pattern from `/blog-pipeline` v0.3):
- `language: en` → English-default rules (no diacritic gate)
- `language: vi` → Apply diacritic >13% gate + H2 question ratio 60-75% (Vietnamese rules from quality-rubric.md `## vi`)
- `language: es` / `fr` / `ja` / `zh` / etc. → Apply matching `quality-rubric.md ## [lang]` subsection
- Output language: same as `BRAND.language` (refresh keeps source article language)

---

## Workflow tracker integration

Every phase emits tracker events (same pattern as `/blog-pipeline` v0.3.1):

```bash
python3 ~/.claude/scripts/workflow_tracker.py start \
  --slug $SLUG ${SITE:+--site $SITE} --phase $N --skill blog-refresh-pipeline

python3 ~/.claude/scripts/workflow_tracker.py log-api \
  --slug $SLUG --phase $N --tool [wp-rest|dataforseo|gemini_image|firecrawl] \
  --endpoint $ENDPOINT --count 1

python3 ~/.claude/scripts/workflow_tracker.py log-llm \
  --slug $SLUG --phase $N --model claude-sonnet-4-6 \
  --input-chars $IN --output-chars $OUT

python3 ~/.claude/scripts/workflow_tracker.py end \
  --slug $SLUG --phase $N --status complete \
  --outputs "articles/$SLUG/blog.html,articles/$SLUG/refresh-plan.md"
```

Phase number mapping for refresh:
| Phase | --phase value |
|-------|---------------|
| 1 Pre-Flight | 1 |
| 2 Diagnose | 2 |
| 3 Research | 3 |
| 4 Plan | 4 |
| 4.5 Cannibalization | 4 (sub) |
| 5 Write+Push | 5 |
| 5.5 Image Audit | 5 (sub) |
| 6 Verify | 6 |

After Phase 6: `/blog report articles/[slug]/` generates `workflow-report.md` showing refresh cost + time.

---

## Master flow — 6 phases

### Phase 1 — Pre-Flight backup (5 min)

**CRITICAL — never skip**. Captures live HTML for rollback safety.

```bash
Step 1.0: workflow_tracker.py start --phase 1 --skill blog-refresh-pipeline
Step 1.1: Parse [target] input → resolve POST_ID, SITE, SLUG, WP_BASE
Step 1.2: mkdir -p articles/${SITE:+$SITE/}$SLUG/
Step 1.3: Fetch raw content via wp-mcp-ultimate (or WP REST direct):
          GET $WP_BASE/posts/$POST_ID?context=edit
          → save articles/$SLUG/blog-v1-backup.html (utf-8)
Step 1.4: Save backup-meta.json:
          { id, slug, title, modified, char_count, fetched_at }
Step 1.5: Decide MODE by char count (light/medium/full) unless --mode override
Step 1.6: Initialize pipeline-state.json (refresh schema):
          {
            "slug": $SLUG, "site": $SITE, "post_id": $POST_ID,
            "operation": "refresh",
            "started_at": ISO_NOW,
            "mode": $MODE,
            "schema_version": "0.4",
            "config": {"output_language": $LANG, "locale": $LOCALE, "timezone": $TZ},
            "phases": {...}
          }
Step 1.7: workflow_tracker.py end --phase 1 --status complete --outputs "blog-v1-backup.html,backup-meta.json"
```

**Output**: `articles/[slug]/blog-v1-backup.html` + `backup-meta.json` + `pipeline-state.json`

**Rollback ready**: at any later phase, if push fails:
```bash
python execution/wp_push_safe.py $POST_ID articles/$SLUG/blog-v1-backup.html --slug $SLUG
```

See `references/rollback-procedure.md` for full diagnostic + recovery flow.

---

### Phase 2 — Diagnose (10-15 min)

**Goal**: identify info gain opportunities + flag content issues.

```bash
Step 2.0: workflow_tracker.py start --phase 2 --skill blog-refresh-pipeline
Step 2.1: GSC top queries (Tier 1 only, skip if GSC unavailable):
          gsc --format json query "sc-domain:$SITE" \
            --dimensions query,page --row-limit 25000 \
            --filter "page contains $SLUG"
          → save articles/$SLUG/gsc-queries.md
          → log "diagnose.gsc_queries" to pipeline-state
Step 2.2: Anti-pattern flags (run refresh_preflight.py in diagnostic mode):
          python3 ~/.claude/scripts/refresh_preflight.py \
            articles/$SLUG/blog-v1-backup.html --diagnose --language $LANG
          → reports: em-dashes, en-dashes, MD leak, placeholder tokens,
                     diacritic % (if vi), H2 question ratio (if vi)
Step 2.3: Info gain WebSearch (3-5 parallel calls):
          WebSearch("[topic] 2026 updates OR news OR latest")
          WebSearch("[topic] site:[official-source]")
          WebFetch(top_competitor_url, "List H2 + unique angles")
          → save articles/$SLUG/diagnose-info-gain.md
Step 2.4: Output Phase 2 summary to refresh-plan.md (Phase 4 will expand):
          [HIGH] / [MED] / [LOW] opportunities ranked by ROI
Step 2.5: workflow_tracker.py end --phase 2 --status complete \
          --outputs "gsc-queries.md,diagnose-info-gain.md"
```

**Output**: `articles/[slug]/gsc-queries.md` (Tier 1 only) + `diagnose-info-gain.md`

---

### Phase 3 — Research (20-30 min, SKIP for Light mode)

**Goal**: gather concrete material for new H2 sections.

```bash
Step 3.0: If MODE == light → SKIP entirely, log "phase_3.status: skipped (light mode)"
Step 3.1: workflow_tracker.py start --phase 3 --skill blog-refresh-pipeline
Step 3.2: Parallel research (3-5 calls in 1 message):
          WebSearch("[topic] [year] news updates")
          WebSearch("[topic] competitor analysis 2026")
          WebFetch(competitor_url_1, "List H2 + unique angles")
          WebFetch(competitor_url_2, "List H2 + unique angles")
          (optional) Skill last30days "[topic] - what's new"
Step 3.3: Consolidate into articles/$SLUG/research.md (markdown):
          ## News/Updates 2026
          ## Competitor Gaps
          ## Stats To Add
Step 3.4: workflow_tracker.py end --phase 3 --status complete --outputs "research.md"
```

**Output**: `articles/[slug]/research.md` (skipped if Light mode)

---

### Phase 4 — Plan (10 min)

**Goal**: write change manifest — exactly what changes, no more.

```bash
Step 4.0: workflow_tracker.py start --phase 4 --skill blog-refresh-pipeline
Step 4.1: Spawn LLM agent (Sonnet 4.6) with:
          - articles/$SLUG/blog-v1-backup.html (current state)
          - articles/$SLUG/diagnose-info-gain.md (Phase 2)
          - articles/$SLUG/research.md (Phase 3, if exists)
          - BRAND.md + VOICE.md
          → produce articles/$SLUG/refresh-plan.md with:
            ## Strategy ($MODE)
            ## Keep As-Is (H2 list)
            ## Update (H2 list with specific changes)
            ## Add New (H2 list in order, with content outline + citation source)
            ## Stats Banner Update (old → new metrics)
            ## Title/Meta Update (if changed)
            ## Internal Links Update
Step 4.2: If --pause-at 4 flag set: prompt user review before Phase 4.5
Step 4.3: workflow_tracker.py end --phase 4 --status complete --outputs "refresh-plan.md"
```

**Output**: `articles/[slug]/refresh-plan.md`

---

### Phase 4.5 — Cannibalization Check (10 min, SKIP for Light mode OR `--skip-cannibal`)

**Goal**: verify new H2 sections don't compete with existing site articles for the same queries.

```bash
Step 4.5.0: If MODE == light OR --skip-cannibal → SKIP. Log "phase_4.5.status: skipped".
            If refresh-plan.md has no "Add New" H2 entries → also skip.
Step 4.5.1: workflow_tracker.py start --phase 4 --skill blog-cannibalization
Step 4.5.2: Extract target_keywords from refresh-plan.md "Add New" H2 titles
Step 4.5.3: Invoke /blog cannibalization (Daniel skill):
            /blog cannibalization --site $SITE --keywords "$target_keywords" \
              --current-slug $SLUG
Step 4.5.4: Save output to articles/$SLUG/cannibal-check.md with decision matrix:
            | New H2 | Overlap severity | Action |
            🔴 HIGH (same exact + same intent) → REMOVE from plan
            🟡 MED (related + different intent) → add cross-link
            🟢 LOW (broad topic + different specific) → proceed
            ✅ SAFE → proceed
Step 4.5.5: Update refresh-plan.md ## Cannibalization Check section
Step 4.5.6: workflow_tracker.py end --phase 4 --status complete --outputs "cannibal-check.md"
```

See `references/cannibalization-check.md` for severity rules.

---

### Phase 5 — Write + Push (60-120 min)

**Core phase** — actual refresh work + WP push.

```bash
Step 5.0: workflow_tracker.py start --phase 5 --skill blog-refresh-pipeline
Step 5.1: cd $ARTICLE_DIR (multi-site: pushd sites/$SITE/)
Step 5.2: Invoke /blog rewrite (Daniel) with refresh-plan.md as guide:
          /blog rewrite articles/$SLUG/blog-v1-backup.html \
            --plan articles/$SLUG/refresh-plan.md \
            --output articles/$SLUG/blog.html
          → blog-rewrite agent edits HTML per refresh-plan.md
          → 5-gate Delivery Contract applies (score ≥90)
Step 5.3: Run preflight quality script:
          python3 ~/.claude/scripts/refresh_preflight.py \
            articles/$SLUG/blog.html \
            --backup articles/$SLUG/blog-v1-backup.html \
            --language $LANG \
            --min-delta-pct $MIN_DELTA
          → checks: em-dashes=0, en-dashes=0, MD leak=0, placeholder tokens=0,
                    content delta ≥ MIN_DELTA, diacritic gate (if vi)
          → exit 1 if fail → halt + suggest fixes
Step 5.4: Push via wp_push_safe.py (MANDATORY safety):
          python3 ~/.claude/scripts/wp_push_safe.py $POST_ID \
            articles/$SLUG/blog.html --slug $SLUG --expected-slug $SLUG
Step 5.5: If refresh-plan.md changed title/meta → update Rank Math via REST:
          POST $WP_BASE_RANKMATH/updateMeta
          { objectID, objectType:"post", meta: {rank_math_title, ...} }
Step 5.6: workflow_tracker.py end --phase 5 --status complete \
          --outputs "blog.html"
```

**Output**: `articles/[slug]/blog.html` + live WP post updated

**Rollback trigger** — if Phase 5.4 fails (HTTP 5xx, slug mismatch):
```bash
python3 ~/.claude/scripts/wp_push_safe.py $POST_ID \
  articles/$SLUG/blog-v1-backup.html --slug $SLUG
```

---

### Phase 5.5 — Image Audit (15-30 min, SKIP for Light OR `--skip-images`)

**Goal**: regenerate images for new H2 sections to boost visual signal.

```bash
Step 5.5.0: If MODE == light OR --skip-images → SKIP. Log status.
Step 5.5.1: workflow_tracker.py start --phase 5 --skill blog-image
Step 5.5.2: Parse articles/$SLUG/blog.html → list H2 sections + image count per H2
Step 5.5.3: Decision per H2 (auto):
            | H2 type | Action |
            | Hero (first) | Reuse if topic same; regenerate Style #1 if topic shifted |
            | News/Update (new H2) | Generate Style #2 Dark Tech (fresh feel) |
            | Concept/architecture | Reuse existing diagram |
            | Tutorial/Setup | Reuse OR generate Style #3 Pastel |
            | FAQ/Conclusion | Skip (low ROI) |
Step 5.5.4: For each H2 needing new image:
            Invoke /blog image with:
              - target H2 title + body context
              - style hint (from decision table above)
              - brand colors from BRAND.md
            → save to articles/$SLUG/images/[slug]-[h2-keyword].webp
            → resize max 2400px, WebP quality 85
Step 5.5.5: Insert <figure> blocks before new H2 in blog.html
Step 5.5.6: Re-push via wp_push_safe.py (Phase 5.4 syntax) with image URLs patched
Step 5.5.7: Verify images live (200 + image/webp MIME)
Step 5.5.8: workflow_tracker.py end --phase 5 --status complete --outputs "images/*.webp"
```

---

### Phase 6 — Verify (10 min)

**Goal**: confirm live page render correctly after push.

```bash
Step 6.0: workflow_tracker.py start --phase 6 --skill blog-refresh-pipeline
Step 6.1: Fetch live URL with cache-bust:
          curl -s "https://$SITE/$SLUG/?nc=$(date +%s)" \
            -A "Mozilla/5.0" -H "Cache-Control: no-cache"
Step 6.2: Verify checks:
          - Live title matches refresh-plan.md new title
          - Meta description matches new meta
          - All "Add New" H2 sections from refresh-plan.md present in live HTML
          - No markdown leak ("> -" or "^## " on live)
          - All new image URLs return 200 + image/webp MIME
          - Stats banner shows new metrics (if updated)
Step 6.3: If any check fails → log to pipeline-state.json + recommend rollback
Step 6.4: Final summary console output:
          "✓ $SLUG refreshed | mode=$MODE | $delta_pct% content delta | $cost_usd cost | $duration"
Step 6.5: workflow_tracker.py end --phase 6 --status complete --outputs "verify-report.md"
```

**Output**: `articles/[slug]/verify-report.md` + console verdict + exit 0/1

---

## Flags

- `--site [name]` — multi-site mode (CWD-redirect, M9 pattern)
- `--mode light|medium|full` — override auto-detection
- `--skip-cannibal` — skip Phase 4.5 (small sites or no new H2)
- `--skip-images` — skip Phase 5.5 (Light refresh or quota saving)
- `--no-publish` — stop at Phase 5.3 (preflight done, no WP push) — useful for review before commit
- `--dry-run` — execute Phase 1-4 only, no Phase 5+ (preview refresh plan without touching live)
- `--pause-at [N]` — pause after phase N for user review

---

## Failure handling

Per-phase failure behavior:

| Phase | On failure |
|-------|-----------|
| 1 (backup) | HALT — cannot proceed without backup |
| 2 (diagnose) | Continue with warning (if GSC unavailable) |
| 3 (research) | Continue with warning (Light fallback) |
| 4 (plan) | HALT — user fixes refresh-plan.md or retry |
| 4.5 (cannibal) | HALT if HIGH overlap found — user removes affected H2 from plan |
| 5.3 (preflight) | HALT — fix quality issues, do not push broken |
| 5.4 (WP push) | TRIGGER ROLLBACK automatically (see `references/rollback-procedure.md`) |
| 5.5 (images) | Continue — images optional, log warning |
| 6 (verify) | HALT + suggest rollback if critical checks fail |

`pipeline-state.json.phases[N].status = "failed"` + error details + rollback_recommended flag.

---

## Performance expectation

| Mode | Total active time | Cost (DFS + Gemini + Claude LLM) |
|------|-------------------|----------------------------------|
| Light | 2-3h | $0.15-0.30 |
| Medium | 5-6h | $0.40-0.70 |
| Full | 7-9h | $0.80-1.20 |

(Time includes human review touchpoints; pure pipeline runtime is much shorter.)

---

## Difference vs `/blog-pipeline` (write new)

| Aspect | `/blog-pipeline` | `/blog-refresh-pipeline` |
|--------|------------------|--------------------------|
| Input | Keyword | URL / path / slug / post_id |
| Direction | Keyword → New article | Live article → Refreshed article |
| Phase 0 Setup | Verify configs | Pre-flight backup |
| Research | Phase 1 fresh | Phase 3 (skip if Light) |
| Brief | Phase 2 | (NA — uses refresh-plan.md instead) |
| Write | Phase 3 (blog write) | Phase 5 (blog rewrite + preflight) |
| Audit | Phase 4 parallel | (NA — preflight script + verify) |
| Cannibal check | (post-write) | Phase 4.5 (BEFORE write) |
| Image | Phase 3 auto (Hero ladder) | Phase 5.5 per-H2 audit |
| Publish | Phase 6 (default ON) | Phase 5.4 (WP push) |
| Indexing recovery (GSC submit + escalation + perf track) | (NA) | (NA — scope deliberately dropped) |

Both share: workflow_tracker integration, multi-site CWD-redirect, multi-language via BRAND.language, `--site`/`--no-publish`/`--dry-run` flags.

---

## Difference vs `/blog rewrite` (Daniel sub-skill)

| Aspect | `/blog rewrite` | `/blog-refresh-pipeline` |
|--------|-----------------|--------------------------|
| Input | Article markdown file or topic string | LIVE WP URL / post_id |
| Pre-flight backup | ❌ | ✅ |
| Multi-step orchestration | ❌ (single skill) | ✅ (6 phases) |
| Cannibalization check | ❌ | ✅ (Phase 4.5) |
| Image audit per H2 | ❌ | ✅ (Phase 5.5) |
| WP push + verify | ❌ (separate `/blog-publish`) | ✅ (Phase 5+6) |
| Rollback procedure | ❌ | ✅ |
| Mode auto-detect | ❌ | ✅ (light/medium/full by char count) |

`/blog rewrite` is a building block; `/blog-refresh-pipeline` orchestrates it as one of 6 phases.

---

## References

- **SOP doc** (canonical): `claude-growth/blog-publishing-workflow.md`
- **Cannibalization check rules**: `references/cannibalization-check.md`
- **Rollback procedure**: `references/rollback-procedure.md`
- **Preflight script**: `~/.claude/scripts/refresh_preflight.py`
- **Source workflow** (Vietnamese, ng-* parent): `claude_ongBoIT/directives/article-refresh-workflow.md` v2.1

---

## Implementation status (v0.4.0)

✅ **Production-ready** for single-site + multi-site + multi-language refresh.

Implemented:
- 6-phase orchestration with mode auto-detect (light/medium/full)
- Pre-flight backup + rollback safety
- Cannibalization check (Phase 4.5) via blog-cannibalization sub-skill
- Per-H2 image audit (Phase 5.5) via blog-image sub-skill
- workflow_tracker integration (start/log-api/log-llm/end per phase)
- Multi-site CWD-redirect (M9 pattern, sites/[name]/BRAND.md)
- Multi-language via BRAND.language (M13 pattern, diacritic gate only for `vi`)
- Flag support: --site, --mode, --skip-cannibal, --skip-images, --no-publish, --dry-run, --pause-at

NOT included (deliberately, scope decision):
- ❌ Phase 7 GSC submit / track (scope = content quality refresh, not "Crawled-Not-Indexed" recovery)
- ❌ Phase 7.5 Escalation Branch (no GSC tracking, no escalation)
- ❌ Phase 8 Performance Tracking D+14/D+30 (use `/blog decay` separately for site-wide tracking)
