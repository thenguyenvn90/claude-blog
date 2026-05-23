---
name: blog-pipeline
description: >
  Master orchestrator for the 7-phase blog publishing pipeline. Auto-chains
  research → cluster → brief → write → audit → image → publish → repurpose
  on a single invocation. Creates a per-article folder (articles/[slug]/) and
  saves each phase's output there. Routes to Daniel's claude-blog +
  claude-seo skills where coverage exists, falls back to ng-* skills for
  features Daniel doesn't have yet. Mirrors the SOP doc at
  claude-growth/blog-publishing-workflow.md. Use when user says "/blog-pipeline",
  "run blog pipeline", "publish blog end-to-end", "auto write and publish
  blog", or wants single-command article production.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Skill
user-invokable: true
argument-hint: "[keyword] [--site URL] [--no-publish] [--skip-phase N] [--pause-at N] [--cluster] [--dry-run]"
license: MIT
metadata:
  author: thenguyenvn90
  version: "0.1.0-alpha"
  category: orchestrator
  references:
    - claude-growth/blog-publishing-workflow.md (SOP doc — canonical reference)
    - skills/blog-pipeline/MIGRATION.md (ng-* → Daniel migration log)
---

# Blog Pipeline — Master Orchestrator

> Single entry-point for the 7-phase blog publishing pipeline. Per article folder
> `articles/[slug]/` (or `articles/[site]/[slug]/` with `--site` flag) holds all
> phase outputs. Reads `blog-publishing-workflow.md` for canonical SOP, chains Daniel's
> claude-blog + claude-seo skills with ng-* fallback markers.

## When to invoke

User says any of:
- `/blog-pipeline [keyword]`
- "Run blog pipeline for X"
- "Publish blog end-to-end on X"
- "Auto write and publish a blog about X"

## Prerequisites

Project folder MUST have at root:
- `BRAND.md` (or `sites/[site]/BRAND.md` for multi-site — M9 migration pending)
- `VOICE.md`
- `~/.config/claude-seo/google-api.json` for `/blog google` family
- MCP servers in `.mcp.json`: DataForSEO, Banana (Gemini), WP REST credentials

If any missing → halt + invoke `/claude-growth-welcome`.

---

## Article folder convention

Every invocation creates a per-article folder. All phase outputs go here.

**Single-site (default)**:
```
[project-root]/
├── BRAND.md                     ← stays at root (Daniel auto-loads)
├── VOICE.md                     ← stays at root
└── articles/[slug]/             ← NEW per-article folder
    ├── pipeline-state.json
    ├── DISCOURSE.md
    ├── google-research.md
    ├── notebooklm-answers.md    (optional)
    ├── cluster-plan.json        (if --cluster)
    ├── cluster-map.html         (if --cluster)
    ├── brief.md
    ├── draft.md
    ├── draft.html
    ├── draft.pdf                (if weasyprint configured)
    ├── images/
    │   ├── hero.webp
    │   └── section-*.webp
    ├── image-manifest.json
    ├── audit-report.md
    └── publish-info.json
```

**Multi-site (`--site [name]` flag)**:
```
[project-root]/
├── sites/[name]/BRAND.md         (multi-site mode)
├── sites/[name]/VOICE.md
└── articles/[site]/[slug]/       ← nested under site folder
    └── ... (same files)
```

**Slug derivation**: from `[keyword]` argument via slugify (`Claude Code Skills` → `claude-code-skills`). User can override via `--slug` flag.

**`pipeline-state.json` schema**:
```json
{
  "slug": "claude-code-skills",
  "site": null,
  "keyword": "claude code skills",
  "started_at": "2026-05-23T14:30:00Z",
  "phases": {
    "0_setup":     {"status": "done", "duration_s": 5, "outputs": [], "errors": []},
    "1_research":  {"status": "done", "duration_s": 180, "outputs": ["DISCOURSE.md", "google-research.md"], "api_cost_usd": 0.0067},
    "1.5_cluster": {"status": "skipped"},
    "2_brief":     {"status": "done", "duration_s": 240, "outputs": ["brief.md"], "api_cost_usd": 0.02},
    "3_write":     {"status": "done", "duration_s": 600, "outputs": ["draft.md", "draft.html", "draft.pdf", "images/hero.webp"], "iterations": 2, "final_score": 92},
    "4_audit":     {"status": "done", "duration_s": 180, "outputs": ["audit-report.md"], "composite_score": 91},
    "5_image":     {"status": "auto-via-phase-3"},
    "6_publish":   {"status": "pending", "outputs": [], "fallback_to_ng": true},
    "7_maintain":  {"status": "manual-on-demand"}
  },
  "total_duration_s": 1205,
  "total_api_cost_usd": 0.42
}
```

---

## Output language

The pipeline + all sub-skills write OUTPUT in the language declared in BRAND.md `language` field. Skill prompts/rules remain in English (single source of truth); only the article output adapts.

**Behavior:**
- `language: en` → Write blog.md, briefs, social variants in English
- `language: vi` → Viết blog.md bằng tiếng Việt + apply Vietnamese-specific rules from quality-rubric.md `## vi` subsection (diacritics >15%, em-dash 0, H2 questions 60-70%)
- `language: es` → Escribir en español + apply `## es` subsection rules
- `language: ja` → 日本語で書く + apply `## ja` subsection rules
- (any ISO 639-1 code → check `quality-rubric.md ## Language-specific quirks` for special rules; default to universal if absent)

**Locale field** (e.g., `en-US`, `vi-VN`, `es-MX`, `pt-BR`) controls:
- Number/decimal formatting (`1,000` vs `1.000` vs `1.000,00`)
- Date format (`MM/DD/YYYY` vs `DD/MM/YYYY` vs ISO)
- Currency symbol placement
- Regional dialect / Latin vs Castilian Spanish, etc.

**Implementation in each phase prompt** — when invoking sub-skills, pipeline must prepend:
```
[CONFIG] output_language={{BRAND.language}} locale={{BRAND.locale}}
Apply language-specific rules from quality-rubric.md `## {{BRAND.language}}` subsection if present.
Write article body, headings, FAQ, meta description, and TL;DR in {{BRAND.language}}.
```

---

## Master flow — 7 phases

### Phase 0 — Setup

```bash
Step 0.1: Compute SLUG from [keyword] arg (slugify or --slug override)
Step 0.2: Compute SITE from --site flag (or null for single-site mode)
Step 0.3: Compute ARTICLE_DIR:
          - If SITE: articles/[SITE]/[SLUG]/
          - Else:    articles/[SLUG]/
Step 0.4: mkdir -p $ARTICLE_DIR + $ARTICLE_DIR/images
Step 0.5: Verify BRAND.md + VOICE.md exist at root (or sites/[SITE]/ if multi-site)
Step 0.5a: Read BRAND.md fields: language (default: en), locale, timezone
           → set OUTPUT_LANG = BRAND.language
           → log to pipeline-state.json.config.output_language
           → all downstream skills MUST write output in OUTPUT_LANG
Step 0.6: Verify ~/.config/claude-seo/google-api.json exists
Step 0.7: ToolSearch dataforseo-mcp + nanobanana-mcp + wp-mcp-ultimate availability
Step 0.8: Initialize pipeline-state.json:
          {"slug": SLUG, "site": SITE, "keyword": ARG, "started_at": ISO_NOW,
           "config": {"output_language": OUTPUT_LANG, "locale": LOCALE, "timezone": TZ},
           "phases": {...}}
Step 0.9: If any prerequisite missing → halt + invoke /claude-growth-welcome
```

**Output**: `articles/[slug]/pipeline-state.json` (Phase 0 status: done)

---

### Phase 0.7 — Research capability detection (NEW v0.2)

Before Phase 1, probe what research skills are available + determine tier:

```bash
Step 0.7.1: Check ~/.config/claude-seo/google-api.json + gsc_property → set gsc_available
Step 0.7.2: ToolSearch select:dataforseo-mcp → set dataforseo_available
Step 0.7.3: ToolSearch select:gsc-opportunities → set gsc_extras_available (ng-* setup)
Step 0.7.4: Check user notebooks configured → set notebooklm_available
Step 0.7.5: Determine research tier:
            tier = 1 if gsc_available else 2 if dataforseo_available else 3
Step 0.7.6: Log to pipeline-state.json:
            phases.0_setup.research_capabilities = {...all flags above...}
            phases.0_setup.research_tier = tier
```

This drives Phase 1 + Phase 4 routing — graceful degrade if GSC absent (agency client scenario).

---

### Phase 1 — Research (3-tier graceful degrade)

**Discourse layer** (always runs, all tiers):
```bash
Step 1.1: cd to ARTICLE_DIR
Step 1.2: /blog discourse "[keyword]"
          → produces DISCOURSE.md at project root
          → mv DISCOURSE.md → $ARTICLE_DIR/DISCOURSE.md
```

**Tier 1 — GSC CONNECTED (preferred, owned site)**:
```bash
Step 1.3 (Tier 1): /blog google query "[keyword]"
          → save to $ARTICLE_DIR/google-research.md
Step 1.4 (Tier 1): /blog google crux-history (optional)
Step 1.5 (Tier 1): /blog google nlp [keyword] (optional, NLP entities)
Step 1.6 (Tier 1, if gsc_extras_available): /gsc-opportunities --site [domain]
          → save to $ARTICLE_DIR/gsc-opportunities.md (striking-distance pos 5-20)
```

**Tier 2 — DataForSEO PAID (client site, no GSC access)**:
```bash
Step 1.3 (Tier 2): /seo dataforseo serp "[keyword]"
          → save top 10 + PAA to $ARTICLE_DIR/dataforseo-research.md
Step 1.4 (Tier 2): /seo dataforseo keywords "[keyword]"
          → volume + KD + intent → append to dataforseo-research.md
Step 1.5 (Tier 2): /seo dataforseo competitors "[keyword]"
          → top competitor analysis → append to dataforseo-research.md
```

**Tier 3 — WebSearch FALLBACK (free, last resort)**:
```bash
Step 1.3 (Tier 3): WebSearch "[keyword]" + WebFetch top 3-5 URLs
          → save to $ARTICLE_DIR/websearch-research.md (lighter data)
Step 1.4 (Tier 3): WebSearch "[keyword] competitor analysis"
          → competitor signals → append
```

**Optional NotebookLM (any tier)**:
```bash
Step 1.6 (if notebooklm_available + topic matches user's notebooks):
          /blog notebooklm ask [notebook] "[research question]"
          → save to $ARTICLE_DIR/notebooklm-answers.md
```

**Phase 1 close**:
```bash
Step 1.7: Update pipeline-state.json: phases.1_research.status = "done"
          + outputs list + tier_used + duration + api_cost
```

**Migration TODO M1**: ng-research v5.6 has engagement formula + content_format/hook_type auto-classify + 6-type gap analysis. Daniel's `blog-discourse` lacks these. → See MIGRATION.md item M1.

---

### Phase 1.5 — Cluster planning (OPTIONAL, only if `--cluster` flag)

**Invokes**: `/blog cluster plan [seed-keyword]`

```bash
Step 1.5.1: /blog cluster plan "[seed-keyword]"
            → cluster-plan.json + cluster-map.html (D3.js viz)
            → After: mv outputs to $ARTICLE_DIR/
Step 1.5.2: User approves cluster plan (interactive confirm)
Step 1.5.3 (if --execute, BLOCKED until M2):
            → warns "cluster execute not ported yet; running single-article only"
Step 1.5.4: Update pipeline-state.json
```

**Migration TODO M2**: ng-cluster has `execute` chain. Daniel's blog-cluster lacks it.

---

### Phase 2 — Brief (consolidates research_packet for Phase 3)

**Invokes**: `/blog brief [keyword]`

```bash
Step 2.1: Read all research files present in $ARTICLE_DIR:
          - DISCOURSE.md (always present)
          - google-research.md (Tier 1) OR dataforseo-research.md (Tier 2) OR websearch-research.md (Tier 3)
          - gsc-opportunities.md (Tier 1 + ng-* installed)
          - notebooklm-answers.md (if user notebooks)
Step 2.2: cd to $ARTICLE_DIR (so /blog brief auto-detects research files via Step 5.5)
Step 2.3: /blog brief "[keyword]"
          → /blog brief Step 5.5 (v0.2) consolidates research files into brief.md.research_packet
          → produces brief.md (12-template auto-detect + competitive gap + H2/H3 + TL;DR + Research Packet section)
Step 2.4: mv brief.md $ARTICLE_DIR/brief.md (if not already in article dir)
Step 2.5: User reviews brief.md (--pause-at 2 if flag set)
Step 2.6: Update pipeline-state.json: phases.2_brief.research_packet_consolidated = true
```

**Key contract**: brief.md MUST include `## Research Packet` section. This signals Phase 3 /blog write Step 2.0 to skip blog-researcher agent (NO duplicate research).

**Migration TODO M3**: ng-brief v5.8 has Information Gain Prompts (3 slots). Daniel's blog-brief lacks these.

---

### Phase 3 — Write (BLOCKING 5-gate)

**Invokes**: `/blog write [keyword]`

```bash
Step 3.1: Verify $ARTICLE_DIR/brief.md exists with ## Research Packet section
          (consolidated by Phase 2 /blog brief Step 5.5 v0.2)
Step 3.2: cd to $ARTICLE_DIR (so /blog write Step 2.0 detects brief.md + research_packet)
Step 3.3: /blog write "[keyword]"
          → /blog write Step 2.0 (v0.2) detects brief.md w/ research_packet → SKIPS blog-researcher agent
          → blog-writer agent receives research from brief.md (no duplicate WebSearch)
          → blog-seo agent → on-page validation
          → blog-reviewer agent BLOCKING ≥90 + zero P0 issues
          → 5-gate Delivery Contract enforces .md + .html + .pdf + hero.png
          → iteration loop max 3 retries → escalate to user if still fail
Step 3.4: After /blog write completes, move outputs to $ARTICLE_DIR:
          - draft.md → $ARTICLE_DIR/draft.md
          - draft.html → $ARTICLE_DIR/draft.html
          - draft.pdf → $ARTICLE_DIR/draft.pdf (if exists)
          - hero.png → $ARTICLE_DIR/images/hero.webp (Pillow convert)
          - section-*.png → $ARTICLE_DIR/images/section-*.webp
          - image-manifest.json → $ARTICLE_DIR/image-manifest.json
Step 3.5: Update pipeline-state.json:
          - phases.3_write.research_packet_reused = true (proves no duplication)
          - phases.3_write.iterations = N
          - phases.3_write.final_score = S
          - phases.3_write.outputs = [list]
```

**🔑 Critical contract (v0.2 fix for v1 duplication risk)**:
- Phase 1 outputs research files to $ARTICLE_DIR
- Phase 2 /blog brief Step 5.5 consolidates into brief.md ## Research Packet section
- Phase 3 /blog write Step 2.0 detects research packet → SKIPS blog-researcher
- Result: research happens ONCE in Phase 1, never duplicated in Phase 3

If Step 2.0 skip fails (e.g., brief.md lacks Research Packet section), blog-researcher spawns as fallback (backward compat). Log warning to pipeline-state.json.

**Note**: Phase 5 (image) auto-runs INSIDE blog-write via Hero Image Ladder. Images saved to $ARTICLE_DIR/images/ as part of Step 3.3.

**Migration TODO M4**: ng-write has Visual Rhythm enforcement. Daniel lacks.
**Migration TODO M5**: ng-write Naturalness Pass hard fail. Daniel detects but warns only.

---

### Phase 4 — Audit (parallel + tier-aware extras)

**Invokes**: 4 always-on parallel skills + optional tier-1 extras.

```bash
Step 4.1: Read $ARTICLE_DIR/draft.md
Step 4.2: Spawn 4 always-on parallel Skill invocations:
          - /blog analyze $ARTICLE_DIR/draft.md
          - /blog seo-check $ARTICLE_DIR/draft.md
          - /blog geo $ARTICLE_DIR/draft.md
          - /blog factcheck $ARTICLE_DIR/draft.md
Step 4.3 (TIER 1 only — if gsc_extras_available from Phase 0.7):
          - /gsc-cannibalization --slug [slug]
            → save to $ARTICLE_DIR/cannibal-check.md (keyword overlap with sibling articles)
Step 4.4 (TIER 2 only — if dataforseo_available, GSC unavailable):
          - /seo dataforseo page-intersection [site] [slug]
            → DFS alternative to GSC cannibalization
Step 4.5: Aggregate all results → write to $ARTICLE_DIR/audit-report.md
Step 4.6: Composite score:
          - composite_score = weighted_avg(analyze, seo-check, geo)
          - If ≥ 90: proceed to Phase 6
          - If 75-89: show fix list, prompt user (proceed / rewrite)
          - If < 75: halt, suggest /blog rewrite
Step 4.7: Update pipeline-state.json: composite_score, outputs, tier_extras_used
```

**Migration TODO M6**: ng-audit composite orchestrator (5 agents in 1 invocation). Daniel requires 4 separate calls.

---

### Phase 5 — Image (auto via Phase 3)

No separate invocation. Already handled inside `/blog write` Step 3.3.

**Migration TODO M7 (LOW)**: ng-image site-style routing. Daniel uses flexible per-prompt style.

---

### Phase 6 — Publish (DEFAULT ON; `--no-publish` opts out)

**Invokes**: `/blog-publish` (v0.1.0+ on fork main — M0 ✅ Done 2026-05-23)

```bash
Step 6.0: Check flags:
          - If --no-publish flag set → SKIP Phase 6 entirely; log "user opted out of publish"
          - Else: proceed to Step 6.1
Step 6.1: Read $ARTICLE_DIR/draft.md + $ARTICLE_DIR/draft.html + $ARTICLE_DIR/images/
Step 6.2: /blog-publish $ARTICLE_DIR/draft.md
          → 10-step pipeline: load config → slug drift check → lock images
          → md→HTML → pre-upload HTML validation → create DRAFT → patch image URLs
          → set featured → Rank Math SEO (with Step 4.5 pre-validation HARD gate)
          → tags → schedule 24h → 9-check post-publish verification (parallel)
Step 6.3: Skill outputs publish-info.json → $ARTICLE_DIR/publish-info.json
Step 6.4: Update pipeline-state.json: post_id, scheduled_for, verification flags
```

**Multi-site**: pass `--site [name]` to resolve BRAND.md from `sites/[name]/`.
**Vietnamese sites**: pass `--strict-diacritics` to enforce diacritic ratio >13%.
**Never auto-publish**: always creates DRAFT (status: future, scheduled 24h out). Use `--now` flag + explicit user confirmation for immediate publish.

**Migration M0 ✅ Done**: `/blog-publish` v0.1.0 — see MIGRATION.md.

---

### Phase 6.5 — Cost report (NEW v0.3, auto-runs after Phase 6 or Phase 5 if --no-publish)

```bash
Step 6.5.1: python3 ~/.claude/scripts/workflow_tracker.py totals \
              --slug $SLUG ${SITE:+--site $SITE}
Step 6.5.2: /blog report $ARTICLE_DIR
          → Reads workflow-log.json (auto-populated by each phase's tracker calls)
          → Generates workflow-report.md in $ARTICLE_DIR
          → Sections: exec summary + phase breakdown + cost-by-tool + cost-by-LLM + quality + ROI + hints
Step 6.5.3: Console output 1-line summary: "✓ $0.42 / 3m 24s / score 92"
```

**Workflow tracker integration**: Every phase from 0 onwards calls `workflow_tracker.py phase_start` at entry + `phase_end` at exit. Each tool/LLM call emits an event with cost. Aggregation runs in Step 6.5.1.

**Budget gate** (optional): pipeline accepts `--max-usd N` flag → fails after Phase 6.5 if total > N.

---

### Phase 7 — Maintain (OPTIONAL, on demand)

Not auto-chained. User invokes manually after publish:

```
/blog repurpose $ARTICLE_DIR/publish-info.json
/blog audit                                          ← site-wide health
/blog cannibalization                                ← keyword overlap
/blog calendar                                       ← editorial calendar
/blog decay [site]                                   ← 5-signal decay scan (M8 NEW v0.2)
```

**Migration M8 ✅ Done**: `/blog decay` 5-signal composite ranking — see MIGRATION.md.

---

## Flags

- `--site [name]` — multi-site mode (article folder becomes `articles/[name]/[slug]/`)
- `--slug [slug]` — override auto-slugify
- `--no-publish` — **NEW v0.2** — skip Phase 6 publish entirely (default IS publish). Stops at Phase 5 with draft + audit done. Useful for: agency client review before publish, testing pipeline without WP commits.
- `--skip-phase [N]` — skip arbitrary phase N (e.g., `--skip-phase 1.5` for cluster)
- `--pause-at [N]` — pause after phase N for user review before continuing
- `--cluster` — invoke Phase 1.5 cluster planning
- `--dry-run` — execute Phases 1-5 only, no Phase 6 writes (similar to --no-publish but verbose preview)

## Failure handling

Per-phase failure behavior:
| Phase | On failure |
|-------|-----------|
| 0 (setup) | Halt + redirect to `/claude-growth-welcome` |
| 1 (research) | Halt with diagnostic, allow user retry |
| 1.5 (cluster) | Skip cluster, continue single-article pipeline |
| 2 (brief) | Halt, user retries or adjusts |
| 3 (write) | BLOCKING 5-gate handles internal retry (max 3); escalate if still fail |
| 4 (audit) | Show fix list, user decides |
| 5 (image) | Hero Ladder handles fallback automatically |
| 6 (publish) | Show error + manual recovery guidance; DON'T auto-retry (write ops to WP) |

If any phase fails, `pipeline-state.json` records `phases.[name].status = "failed"` + error details. User can resume by invoking pipeline with `--resume-from [N]` (BLOCKED until M11 resume support lands).

## Resume support (M11 ✅ implemented in v0.2)

If `articles/[slug]/pipeline-state.json` exists at invocation:

```bash
Step 0.6 (resume detection):
  - Read existing pipeline-state.json
  - For each phase with status == "done":
    - Mark as ALREADY DONE (skip re-run)
    - Reuse existing outputs from $ARTICLE_DIR
  - For first phase with status != "done":
    - That's the resume point
    - Resume from there

User override:
  --resume-from [N]    → force resume from phase N (override auto-detection)
  --no-resume          → ignore existing state, start fresh (overwrite $ARTICLE_DIR)
  --restart            → delete $ARTICLE_DIR and start fresh

Resume conditions:
  - pipeline-state.json must be valid JSON
  - Schema version must match (skill version)
  - Output files referenced in pipeline-state.json.phases[].outputs must exist
  - If any condition fails → halt with diagnostic, ask user (--no-resume or --restart)
```

**Example resume scenarios:**

| Scenario | Behavior |
|----------|----------|
| Phase 3 (write) failed iteration 3, escalated to user | Resume from Phase 3 with `--resume-from 3` after user fixes brief.md |
| Phase 6 (publish) failed (WP 503) | Resume from Phase 6 — Phase 1-5 outputs reused |
| Pipeline ran 2 hours ago, user wants to refresh research | `--no-resume` re-runs Phase 1, reuses Phase 2+ outputs if state still valid |
| Article folder corrupted | `--restart` clears everything |

## Multi-site mode (M9 ✅ documented in v0.2)

With `--site [name]` flag, pipeline reads BRAND.md + VOICE.md from `sites/[name]/` instead of project root:

```
[project-root]/
├── BRAND.md                      ← default (single-site fallback)
├── VOICE.md
└── sites/
    ├── client-a/
    │   ├── BRAND.md              ← /blog-pipeline --site client-a uses this
    │   └── VOICE.md
    └── client-b/
        ├── BRAND.md
        └── VOICE.md
```

Phase 0 setup verification logic:

```bash
if --site [name] flag set:
  CONFIG_DIR=sites/[name]/
  if NOT exists $CONFIG_DIR/BRAND.md:
    halt "Multi-site mode: sites/[name]/BRAND.md not found. Create it first."
else:
  CONFIG_DIR=.  (project root)
  if NOT exists BRAND.md:
    halt "BRAND.md not found at project root. Run /claude-growth-welcome."

# Article folder reflects site:
ARTICLE_DIR = articles/[name]/[slug]/  (multi-site)
            = articles/[slug]/         (single-site default)
```

Daniel's `scripts/load_untrusted_root.py` reads project-root BRAND.md by default. For multi-site mode, blog-pipeline orchestrator sets working directory to `sites/[name]/` before invoking Daniel skills, OR passes `--brand-md sites/[name]/BRAND.md` flag if Daniel skill supports it.

## Implementation status

🚧 **v0.1.0-alpha** — skeleton orchestrator + folder convention + MIGRATION.md log.

Ready to use:
- Phase chain logic + per-phase folder output paths
- Skill routing (Daniel + ng-* fallback markers)
- `pipeline-state.json` observability schema

NOT yet ready:
- Phase 6 `/blog-publish` (waits for M0)
- `--cluster --execute` (waits for M2)
- `--resume-from` (future)

## References

- **SOP doc**: `claude-growth/blog-publishing-workflow.md` (canonical)
- **Migration log**: `MIGRATION.md` (this folder)
- **Comparison matrix**: `claude-growth/pipeline-comparison-matrix.md`
- **Source ng-* workflow**: `claude_ongBoIT/directives/blog-publishing-workflow.md` (Vietnamese, ongboit-specific)
