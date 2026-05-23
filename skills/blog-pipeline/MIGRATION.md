# Blog Pipeline — ng-* → Daniel Migration Log

> Per ng-* fallback in `SKILL.md`, this log tracks the migration path:
> source ng-* feature → target Daniel skill update → status → fork commit SHA.
>
> Migration philosophy: **lazy**. Replace ng-* call in pipeline only when Daniel skill is updated. No big-bang sprints. Each cycle = 1 ng-* feature → 1 Daniel skill update → push to fork main → update pipeline call site.

## Status legend

- ⏳ **Pending** — known gap, not started
- 🚧 **In-progress** — actively migrating
- ✅ **Done** — Daniel skill updated, pushed to fork main, pipeline updated to use Daniel version
- ❌ **Skipped** — decided not to migrate (e.g., too ongboit-specific)

## Migration items

### M0 — WordPress Publish skill (CRITICAL)

- **Source**: `~/.claude/skills/ng-publish/SKILL.md` — 10-step WP REST + Rank Math + 24h schedule + 9-check verification
- **Target**: NEW skill `skills/blog-publish/SKILL.md` on `thenguyenvn90/claude-blog` fork **main** (direct edit, no feature branch per 2026-05-23 pivot)
- **Pipeline call site**: Phase 6 — currently falls back to `/ng-publish`; will use `/blog-publish` after migration
- **Effort**: 4h
- **Status**: 🚧 In-progress
  - Skeleton already committed to feature branch `feature/blog-publish` (8 files, 250-line SKILL.md + 5 Python stubs)
  - Next: merge or cherry-pick from feature branch → fork main, then full Python implementation
- **Commit SHA**: TBD on fork main

### M1 — Engagement formula + format/hook auto-classify (LOW)

- **Source**: ng-research v5.6 — engagement = (likes×2 + comments×3 + shares×5) / views × 1000; content_format + hook_type auto-classify; 6-type gap analysis (content/format/angle/hook/visual/distribution)
- **Target**: extend `skills/blog-discourse/SKILL.md` on fork main
- **Pipeline call site**: Phase 1 Step 1.2 — Daniel skill currently produces DISCOURSE.md but doesn't classify/score engagement
- **Effort**: 3-4h
- **Status**: ⏳ Pending

### M2 — Cluster execute engine (MEDIUM)

- **Source**: ng-cluster `--execute` chains brief→write→audit per spoke automatically
- **Target**: extend `skills/blog-cluster/SKILL.md` on fork main with `execute` subcommand
- **Pipeline call site**: Phase 1.5 `--cluster --execute` (currently shows warning)
- **Effort**: 2-3h
- **Status**: ⏳ Pending

### M3 — Information Gain Prompts (LOW)

- **Source**: ng-brief v5.8 — 3 prompt slots `[ORIGINAL DATA]` / `[PERSONAL EXPERIENCE]` / `[UNIQUE INSIGHT]` in brief.md, resolved + stripped during write
- **Target**: extend `skills/blog-brief/SKILL.md` to add 3 slots; extend `skills/blog-write/SKILL.md` to resolve+strip
- **Pipeline call site**: Phase 2 — Daniel produces solid brief but no info-gain markers
- **Effort**: 2h
- **Status**: ⏳ Pending

### M4 — Visual Rhythm enforcement (LOW)

- **Source**: ng-write — every H2 ≥250w MUST have ≥1 visual element (image/table/list/callout); article-wide flag if 0 diagrams in educational type
- **Target**: extend `agents/blog-reviewer.md` scorecard with Visual Rhythm dimension (10pt of 100pt total)
- **Pipeline call site**: Phase 3 (handled inside blog-write's blog-reviewer agent)
- **Effort**: 1h
- **Status**: ⏳ Pending

### M5 — Naturalness Pass hardening (LOW)

- **Source**: ng-write v5.4 — burstiness SD > 6, TTR > 0.50, banned phrase list HARD FAIL gates
- **Target**: promote AI detection signals in `agents/blog-reviewer.md` from WARN to FAIL gates
- **Pipeline call site**: Phase 3 (BLOCKING gate)
- **Effort**: 2h
- **Status**: ⏳ Pending

### M6 — Audit composite orchestration (LOW — likely SKIP)

- **Source**: ng-audit chains 5 parallel agents (Quality + SEO + GEO + Factcheck + Forensic) in single invocation
- **Target**: 🔧 Extend `skills/blog-analyze/SKILL.md` — add optional sub-skill spawn (`--with-seo-check --with-geo --with-factcheck`) + weighted composite output
  - **ALTERNATIVE**: SKIP entirely. Pipeline Phase 4 already calls 4 parallel skills + aggregates audit-report.md. No new skill needed.
- **Pipeline call site**: Phase 4
- **Effort**: 1-2h (if extend); 0h (if skip)
- **Status**: ⏳ Pending — **revised round 5 (2026-05-23)**: demoted from NEW skill `blog-audit-composite` to extension/skip
- **Reasoning**: Daniel's `blog-analyze` already covers 5-category 100pt scoring (content, SEO, E-E-A-T, technical, AI citation). Adding sub-skill spawn for richer aggregation is incremental, not architectural.

### M7 — Site-style image routing (LOW)

- **Source**: ng-image — per-site style preset config (Style #1 Whiteboard / #2 Dark Tech / #3 Pastel / #4 Premium 3D) loaded from `directives/[site]/image-styles.md`
- **Target**: extend `skills/blog-image/SKILL.md` to support per-site style config block
- **Pipeline call site**: Phase 5 (inside blog-write) — Daniel uses flexible per-prompt style
- **Effort**: 2h
- **Status**: ⏳ Pending

### M8 — 5-signal decay detection (MEDIUM)

- **Source**: ng-decay — age + GSC click decline + external link rot + Jaccard SERP cannibalization + orphan/dead-end. Composite Critical/High/Medium/Low ranking.
- **Target**: NEW skill `skills/blog-decay/SKILL.md` OR extend `skills/blog-audit/SKILL.md` with composite ranking
- **Pipeline call site**: Phase 7 — Daniel's blog-audit has site health but no composite decay
- **Effort**: 3h
- **Status**: ⏳ Pending

### M9 — Multi-site overrides (HIGH)

- **Source**: ng-* `directives/[site]/overrides.md` pattern — `--site` flag routes to per-site config
- **Target**: extend Daniel's v1.8.0+ untrusted-data contract (`scripts/load_untrusted_root.py`) to support `sites/[name]/BRAND.md` lookup
- **Pipeline call site**: Phase 0 — currently single-site only. Agency buyer use case needs multi-site.
- **Effort**: 2h
- **Status**: ⏳ Pending

### M10 — Bidirectional internal links (MEDIUM)

- **Source**: ng-publish Step 11 (P0/P1/P2 reciprocal injection) + ng-* v5.24 Phase 6.5 explicit bidirectional pass
- **Target**: extend `skills/blog-publish` Step 9 (Asset Integrity) OR new sub-skill `blog-internal-links`
- **Pipeline call site**: Phase 6 (after publish)
- **Effort**: 2h
- **Status**: ⏳ Pending (depends on M0 landing first)

### M11 — Pipeline resume support (LOW)

- **Source**: ng-* doesn't have this; new design need
- **Target**: extend `skills/blog-pipeline/SKILL.md` Phase 0 to detect existing `articles/[slug]/pipeline-state.json` and skip completed phases
- **Pipeline call site**: Phase 0 (new flag `--resume-from [N]`)
- **Effort**: 2h
- **Status**: ⏳ Pending

---

## DO NOT migrate (too ongboit-specific)

These ng-* features stay in ng-* (parent repo `claude_ongBoIT`). NOT ported to Daniel fork:

- Vietnamese diacritics audit gate (>13% target)
- Vietnamese banned phrases (Vietnamese-specific terms)
- `#FF7F00` brand color literal (ongboit-specific)
- Vietnamese H2 question ratio rules (Vietnamese grammar feature)
- RankMath Vietnamese URL slug logic
- ongboit category IDs (17 Claude Code, 18 n8n, etc. — WP installation-specific)
- ongboit category-specific tag taxonomy (Bắt đầu / So sánh / Hướng dẫn)
- Skool affiliate CTA injection (v5.24 Phase 8 — ongboit business-specific)

Vietnamese buyers can enable `--strict-diacritics` flag on `/blog-publish` (M0 includes this).

## Migration cadence

Per plan (2026-05-23 evening pivot):
- **Day 1 (DONE today)**: Build pipeline skeleton + folder convention + this log
- **Day 2-3**: M0 (WP publish) full Python — merge skeleton from feature branch to fork main + implement
- **Week 2-4**: M9 (multi-site) → M2 (cluster execute) → M8 (decay) → M10 (bidirectional) → M3-M7 (incremental quality)
- **Each cycle**: 1-2h work → push to fork main → update pipeline call site → update this log

## How to update this log

After each migration cycle:
1. Update status: ⏳ → 🚧 → ✅
2. Add commit SHA on fork main + completion date
3. Update pipeline `SKILL.md` Phase X call site to use Daniel skill
4. Bump submodule pointer in `claude-growth` repo

Single source of truth = this file.
