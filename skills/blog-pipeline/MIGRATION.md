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

### M0 — WordPress Publish skill (CRITICAL) ✅ DONE

- **Source**: `~/.claude/skills/ng-publish/SKILL.md` v2.2.0 — 10-step WP REST + Rank Math + 24h schedule + 9-check verification
- **Target**: NEW skill `skills/blog-publish/SKILL.md` on `thenguyenvn90/claude-blog` fork main
- **Pipeline call site**: Phase 6 — now uses `/blog-publish` (was `/ng-publish` fallback)
- **Effort actual**: 4-5h (planned: 4h)
- **Status**: ✅ **Done 2026-05-23**
- **Commit SHA**: `e6b51f6` on fork main
- **Files shipped**:
  - `SKILL.md` (493 lines: full 10-step orchestration)
  - `references/md-to-html.md` (155 lines)
  - `references/image-upload.md` (188 lines)
  - `references/rankmath-api.md` (135 lines)
  - `references/post-publish-verify.md` (210 lines)
  - `references/tag-selection.md` (104 lines)
  - `references/rollback-rules.md` (150 lines)
- **Total**: 1435 lines
- **Generalization from ng-publish**:
  - Vietnamese-specific bits → `--strict-diacritics` flag (off by default)
  - `directives/[site]/overrides.md` references → `BRAND.md` (Daniel pattern) or `sites/[name]/BRAND.md` (multi-site)
  - ongboit category/tag IDs → resolved per-site via WP REST API
- **Pending** (next commits):
  - M10 (bidirectional links) — extend `blog-publish` with Phase 6.5 sibling injection
  - Step 4.5 hardened pre-validation already included in v0.1.0

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

### M8 — 5-signal decay detection (MEDIUM) ✅ SPEC DONE

- **Source**: ng-decay v5.15 — age + GSC click decline + external link rot + Jaccard SERP cannibalization + orphan/dead-end. Composite Critical/High/Medium/Low ranking.
- **Target**: ✅ NEW skill `skills/blog-decay/` on fork main
- **Pipeline call site**: Phase 7 — `/blog-decay --site [name]`
- **Effort actual**: 1.5h spec (full Python impl ~2-3h additional, deferred to v0.2)
- **Status**: ✅ **Spec Done 2026-05-23**
- **Files shipped**:
  - `skills/blog-decay/SKILL.md` (5-signal scoring + composite formula + ranking buckets + output format)
  - `skills/blog-decay/references/5-signal-scoring.md` (per-signal Python pseudocode + edge cases)

### M9 — Multi-site overrides (HIGH) ✅ SPEC DONE

- **Source**: ng-* `directives/[site]/overrides.md` pattern — `--site` flag routes to per-site config
- **Target**: ✅ documented in `skills/blog-pipeline/SKILL.md` (Multi-site mode section)
- **Pipeline call site**: Phase 0 setup verification logic + multi-site folder convention
- **Effort actual**: 0.5h documentation (full Daniel scripts/load_untrusted_root.py extension deferred to v0.2 — orchestrator handles fallback via cd + Daniel skill auto-loads from CWD)
- **Status**: ✅ **Spec Done 2026-05-23**
- **Note**: Full implementation = extend `scripts/load_untrusted_root.py` to detect `sites/[name]/BRAND.md` based on env var or CLI flag. Documented but not Python-implemented since orchestrator-level cd approach works.

### M10 — Bidirectional internal links (MEDIUM) ✅ SPEC DONE

- **Source**: ng-publish v5.24 Phase 6.5 — sibling injection with priority rules (P0 pillar→spoke, P1 sibling, P2 cross-cluster)
- **Target**: ✅ extended `skills/blog-publish/SKILL.md` Step 9 + new reference doc
- **Pipeline call site**: Phase 6 — built into `/blog-publish` Step 9
- **Effort actual**: 1.5h spec
- **Status**: ✅ **Spec Done 2026-05-23**
- **Files shipped**:
  - `skills/blog-publish/SKILL.md` (Step 9 added)
  - `skills/blog-publish/references/bidirectional-links.md` (full logic: extract → check → suggest → patch with slug guard + priority rules + skip rules + JSON output schema)

### M11 — Pipeline resume support (LOW) ✅ SPEC DONE

- **Source**: ng-* doesn't have this — new design for kit reliability
- **Target**: ✅ documented in `skills/blog-pipeline/SKILL.md` (Resume support section)
- **Pipeline call site**: Phase 0 — auto-detect existing `pipeline-state.json` + reuse outputs
- **Effort actual**: 0.5h documentation
- **Status**: ✅ **Spec Done 2026-05-23**
- **Flags supported**: `--resume-from [N]`, `--no-resume`, `--restart`

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
