---
name: blog-pipeline
description: >
  Master orchestrator for the 7-phase blog publishing pipeline. Auto-chains
  research → cluster → brief → write → audit → image → publish → repurpose
  on a single invocation. Creates a per-article folder (articles/[slug]/) and
  saves each phase's output there. Routes to Daniel's claude-blog +
  claude-seo skills where coverage exists, falls back to ng-* skills for
  features Daniel doesn't have yet. Mirrors the SOP doc at
  claude-growth/workflow.md. Use when user says "/blog-pipeline",
  "run blog pipeline", "publish blog end-to-end", "auto write and publish
  blog", or wants single-command article production.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Skill
user-invokable: true
argument-hint: "[keyword] [--site URL] [--skip-phase N] [--pause-at N] [--cluster] [--dry-run]"
license: MIT
metadata:
  author: thenguyenvn90
  version: "0.1.0-alpha"
  category: orchestrator
  references:
    - claude-growth/workflow.md (SOP doc — canonical reference)
    - skills/blog-pipeline/MIGRATION.md (ng-* → Daniel migration log)
---

# Blog Pipeline — Master Orchestrator

> Single entry-point for the 7-phase blog publishing pipeline. Per article folder
> `articles/[slug]/` (or `articles/[site]/[slug]/` with `--site` flag) holds all
> phase outputs. Reads `workflow.md` for canonical SOP, chains Daniel's
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
Step 0.6: Verify ~/.config/claude-seo/google-api.json exists
Step 0.7: ToolSearch dataforseo-mcp + nanobanana-mcp + wp-mcp-ultimate availability
Step 0.8: Initialize pipeline-state.json:
          {"slug": SLUG, "site": SITE, "keyword": ARG, "started_at": ISO_NOW, "phases": {...}}
Step 0.9: If any prerequisite missing → halt + invoke /claude-growth-welcome
```

**Output**: `articles/[slug]/pipeline-state.json` (Phase 0 status: done)

---

### Phase 1 — Research

**Invokes**: `/blog discourse` + `/blog google` + optional `/blog notebooklm`

```bash
Step 1.1: cd to ARTICLE_DIR (or pass --out flag if Daniel skill supports)
Step 1.2: /blog discourse "[keyword]"
          → Daniel writes DISCOURSE.md to project root by default
          → After: mv DISCOURSE.md $ARTICLE_DIR/DISCOURSE.md
Step 1.3: /blog google query "[keyword]"
          → capture output → save to $ARTICLE_DIR/google-research.md
Step 1.4: /blog google crux-history (optional, append to google-research.md)
Step 1.5: /blog google nlp [keyword] (optional, append to google-research.md)
Step 1.6 (OPTIONAL): /blog notebooklm ask [notebook] "[research question]"
          → save output to $ARTICLE_DIR/notebooklm-answers.md
Step 1.7: Update pipeline-state.json: phases.1_research.status = "done", outputs, duration, api_cost
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

### Phase 2 — Brief

**Invokes**: `/blog brief [keyword]`

```bash
Step 2.1: Read DISCOURSE.md + google-research.md from $ARTICLE_DIR
Step 2.2: /blog brief "[keyword]" --research-from $ARTICLE_DIR
          → produces brief.md (12-template auto-detect, competitive gap, H2/H3, TL;DR draft)
Step 2.3: mv brief.md $ARTICLE_DIR/brief.md
Step 2.4: User reviews brief.md (--pause-at 2 if flag set)
Step 2.5: Update pipeline-state.json
```

**Migration TODO M3**: ng-brief v5.8 has Information Gain Prompts (3 slots). Daniel's blog-brief lacks these.

---

### Phase 3 — Write (BLOCKING 5-gate)

**Invokes**: `/blog write [keyword]`

```bash
Step 3.1: Read brief.md from $ARTICLE_DIR
Step 3.2: /blog write "[keyword]" --from-brief $ARTICLE_DIR/brief.md
          → internally chains agents (researcher → writer → seo → reviewer BLOCKING ≥90)
          → 5-gate Delivery Contract enforces .md + .html + .pdf + hero.png
          → iteration loop max 3 retries
Step 3.3: After Daniel's blog-write completes, move outputs to $ARTICLE_DIR:
          - draft.md → $ARTICLE_DIR/draft.md
          - draft.html → $ARTICLE_DIR/draft.html
          - draft.pdf → $ARTICLE_DIR/draft.pdf (if exists)
          - hero.png → $ARTICLE_DIR/images/hero.webp (Pillow convert)
          - section-*.png → $ARTICLE_DIR/images/section-*.webp
          - image-manifest.json → $ARTICLE_DIR/image-manifest.json
Step 3.4: Update pipeline-state.json: iterations, final_score, outputs
```

**Note**: Phase 5 (image) auto-runs INSIDE blog-write via Hero Image Ladder. Images saved to $ARTICLE_DIR/images/ as part of Step 3.3.

**Migration TODO M4**: ng-write has Visual Rhythm enforcement. Daniel lacks.
**Migration TODO M5**: ng-write Naturalness Pass hard fail. Daniel detects but warns only.

---

### Phase 4 — Audit (parallel)

**Invokes**: 4 parallel skills: `/blog analyze` + `/blog seo-check` + `/blog geo` + `/blog factcheck`

```bash
Step 4.1: Read $ARTICLE_DIR/draft.md
Step 4.2: Spawn 4 parallel Skill invocations (single message, multiple tool calls):
          - /blog analyze $ARTICLE_DIR/draft.md
          - /blog seo-check $ARTICLE_DIR/draft.md
          - /blog geo $ARTICLE_DIR/draft.md
          - /blog factcheck $ARTICLE_DIR/draft.md
Step 4.3: Aggregate 4 results → write to $ARTICLE_DIR/audit-report.md
Step 4.4: Composite score:
          - composite_score = weighted_avg(analyze, seo-check, geo)
          - If ≥ 90: proceed to Phase 6
          - If 75-89: show fix list, prompt user (proceed / rewrite)
          - If < 75: halt, suggest /blog rewrite
Step 4.5: Update pipeline-state.json: composite_score, outputs
```

**Migration TODO M6**: ng-audit composite orchestrator (5 agents in 1 invocation). Daniel requires 4 separate calls.

---

### Phase 5 — Image (auto via Phase 3)

No separate invocation. Already handled inside `/blog write` Step 3.3.

**Migration TODO M7 (LOW)**: ng-image site-style routing. Daniel uses flexible per-prompt style.

---

### Phase 6 — Publish

**Invokes**: `/blog-publish` if available, else fallback `/ng-publish`

```bash
Step 6.1: Read $ARTICLE_DIR/draft.md + $ARTICLE_DIR/draft.html + $ARTICLE_DIR/images/
Step 6.2: Detect if skill /blog-publish exists:
          - If exists: /blog-publish $ARTICLE_DIR/draft.md
          - Else: /ng-publish $ARTICLE_DIR/draft.md (FALLBACK, warns user about VN-specific bits)
Step 6.3: Publish skill outputs publish-info.json → $ARTICLE_DIR/publish-info.json
Step 6.4: Update pipeline-state.json: post_id, scheduled_for, fallback_to_ng (bool)
```

**Migration TODO M0 (CRITICAL)**: build `/blog-publish` on fork main from ng-publish.

---

### Phase 7 — Maintain (OPTIONAL, on demand)

Not auto-chained. User invokes manually after publish:

```
/blog repurpose $ARTICLE_DIR/publish-info.json
/blog audit                                          ← site-wide health
/blog cannibalization                                ← keyword overlap
/blog calendar                                       ← editorial calendar
```

**Migration TODO M8**: ng-decay 5-signal composite ranking. Daniel blog-audit lacks.

---

## Flags

- `--site [name]` — multi-site mode (article folder becomes `articles/[name]/[slug]/`)
- `--slug [slug]` — override auto-slugify
- `--skip-phase [N]` — skip phase N (e.g., `--skip-phase 1.5` for cluster, `--skip-phase 6` for publish)
- `--pause-at [N]` — pause after phase N for user review before continuing
- `--cluster` — invoke Phase 1.5 cluster planning
- `--dry-run` — execute Phases 1-5 only, skip Phase 6 publish

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

## Resume support

Currently NOT implemented (would require Phase 0 to detect existing `pipeline-state.json` and skip completed phases). Workaround: user manually deletes failed phase's outputs from `$ARTICLE_DIR/` and re-runs.

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

- **SOP doc**: `claude-growth/workflow.md` (canonical, English)
- **Migration log**: `MIGRATION.md` (this folder)
- **Comparison matrix**: `claude-growth/pipeline-comparison-matrix.md`
- **Source ng-* workflow**: `claude_ongBoIT/directives/blog-publishing-workflow.md` (Vietnamese, ongboit-specific)
