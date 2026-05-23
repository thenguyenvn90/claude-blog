---
name: blog-publish
description: >
  Publish a blog draft to WordPress as a scheduled draft post. Converts markdown
  to WordPress-ready HTML (component injection, picture wrapping with
  fetchpriority/lazy-load), uploads images to media library via REST API,
  creates DRAFT post, sets featured image, configures Rank Math SEO (title 50-60c
  + meta 150-160c + 5 focus keywords), schedules 24h out (status: future), and
  runs 9-check post-publish verification. ALWAYS draft first; never publishes
  immediately without explicit --now flag. Use when user says "publish",
  "/blog publish", "wp publish", "schedule blog post", "upload to WordPress",
  "publish article", or after blog-write completes and user wants to ship.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
user-invokable: true
argument-hint: "[article.md] [--site URL] [--convert-only] [--skip-convert] [--update post_id] [--verify post_id] [--now] [--dry-run] [--strict-diacritics]"
license: MIT
metadata:
  author: thenguyenvn90
  version: "0.1.0"
  category: publish
  source: "Ported from ng-publish v2.2.0 (ongboit.com Vietnamese workflow), generalized to remove VN-specific bits"
---

# Blog Publish — WordPress Publishing Pipeline

> Phase 6 of the blog publishing pipeline. Markdown article in → published WordPress post out. **CRITICAL RULE: ALWAYS create as DRAFT first. NEVER publish directly without explicit `--now` flag + user confirmation.**

## Quick Reference

| Command | Description |
|---------|-------------|
| `/blog-publish [article.md]` | Full pipeline: convert → upload → SEO → tags → schedule 24h → verify |
| `/blog-publish [article.md] --convert-only` | Convert md→HTML, save locally, no upload |
| `/blog-publish [article.html] --skip-convert` | Upload pre-converted HTML |
| `/blog-publish [article.md] --update [post_id]` | Update existing post (content + meta refresh) |
| `/blog-publish --verify [post_id]` | Run verification on already-published post |
| `/blog-publish [article.md] --now` | Publish immediately (REQUIRES explicit user confirmation) |
| `/blog-publish [article.md] --dry-run` | Preview all payloads without HTTP writes |

## Prerequisites

Project folder must have:
- `articles/[slug]/draft.md` (or path passed as arg) — finished article body
- `articles/[slug]/images/` — hero + section images (from blog-image / blog-write)
- `articles/[slug]/image-manifest.json` — image metadata with alt text
- `articles/[slug]/brief.md` — title, meta description, slug, primary keyword
- `BRAND.md` at project root (or `sites/[name]/BRAND.md` for multi-site) — CMS config, category ID, tag IDs
- WP credentials via env OR `.mcp.json` `wp-mcp-ultimate` block

If any missing → abort with setup guidance.

---

## Step 0: Load Config

Resolve `[site]` from: brief metadata `site` field → article path → working directory name.

**Read BRAND.md** (root or `sites/[name]/BRAND.md` if `--site` flag) → extract:
- HTML component templates (TL;DR, stats banner, citation capsule, warning, info)
- Brand colors
- WordPress URL, REST API auth
- Rank Math configuration
- Default category ID + tag IDs
- Publish mode (24h schedule vs immediate)

**Read `articles/[slug]/brief.md`** → extract:
- title (50-60 chars)
- meta_description (150-160 chars)
- slug
- primary_keyword
- secondary_keywords (4 for Rank Math focus_keyword)
- category

## Step 0.5: Slug Drift Check (MANDATORY for `--update`)

Skip on first publish (no live post to compare yet).

Compare local folder name vs live WP slug:

```python
import urllib.request, json, pathlib
local_slug = pathlib.Path(article_dir).name
live = json.loads(urllib.request.urlopen(
    urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}?_fields=id,slug",
        headers={"Authorization": auth, "User-Agent": "Mozilla/5.0"}
    )
).read())
live_slug = live["slug"]

if local_slug != live_slug:
    # WARN — user decides which slug to adopt
    print(f"⚠ SLUG DRIFT: local '{local_slug}' ≠ WP '{live_slug}' (post {post_id})")
    print(f"  Live URL: {site_url}/{live_slug}/")
    print(f"  Cross-links to '/{local_slug}/' will 404")
    print(f"  Pass expected_slug={live_slug} to push, or rename folder to match")
```

---

## Step 1: Lock Images (runs BEFORE conversion)

Goal: upload images once, never re-upload during a single publish run.

1. Read `articles/[slug]/image-manifest.json` (from blog-image / blog-write)
2. For each entry:
   - If `wp_media_id` + `wp_source_url` already present → SKIP upload (use existing)
   - Else → upload via WP REST API `/media`, write back `wp_media_id` + `wp_source_url` to manifest
3. Verify every `[IMAGE: ...]` placeholder in draft.md maps to exactly one manifest entry with live `wp_source_url`
4. Hero image: `fetchpriority="high"`; others: `loading="lazy"`
5. If any upload fails → halt; do NOT retry silently

After Step 1, manifest is **image-locked** for this run. Step 2 uses locked URLs only.

See `references/image-upload.md` for full upload script.

---

## Step 2: Convert Markdown → HTML

Skip if `--skip-convert` flag.

Use Python `markdown` library (never hand-roll regex — drops headings inside HTML blocks):

```python
import markdown
html = markdown.markdown(
    md,
    extensions=["tables", "fenced_code", "attr_list", "md_in_html"],
)
```

Then post-pass apply:
- Component injection (TL;DR, stats banner, citation, warning, info, code, tables)
- Image wrapping with `<picture>` using LOCKED URLs from Step 1
- External link attribute fixing (`target="_blank" rel="noopener noreferrer"`)
- Clean up leftover markers ([INTERNAL-LINK:...], [PERSONAL EXPERIENCE], etc.)

Verification: `re.findall(r"^## ", html, re.M)` must be 0. If non-zero, converter dropped an H2.

Save to `articles/[slug]/draft.html`.

If `--convert-only` → stop here. Otherwise proceed.

See `references/md-to-html.md` for full conversion rules.

---

## Step 2.5: --dry-run Halt

If `--dry-run` flag set, do NOT proceed past Step 2. Print complete preview of every payload that would be sent:

```
=== DRY-RUN preview: [slug] ===

Step 3 (Upload Content):
  POST {SITE}/wp-json/wp/v2/posts
  body: title, slug, status: draft, categories, featured_media, content (chars)

Step 4 (RankMath):
  POST {SITE}/wp-json/rankmath/v1/updateMeta
  body: objectID, meta: {rank_math_title, rank_math_description, rank_math_focus_keyword}

Step 5 (Tags):
  POST {SITE}/wp-json/wp/v2/posts/<post_id>
  body: {tags: [...]}

Step 6 (Schedule):
  POST {SITE}/wp-json/wp/v2/posts/<post_id>
  body: {status: future, date: <ISO 8601, now+24h>}
```

Halt with: `Dry run complete. Full HTML preview at articles/[slug]/draft.dryrun.html.` No HTTP writes, no manifest mutation.

---

## Step 2.8: HTML Pre-Upload Validation (HARD GATE)

Run BEFORE any WP API call. Auto-fix what can be fixed; halt on hard failures.

**Check 1 — External link attributes**: Every `<a href="https://` not on site's domain must have `target="_blank"` + `rel="noopener noreferrer"`. Auto-fix in place.

**Check 2 — Hero fetchpriority**: First `<figure>` or `<img>` must have `fetchpriority="high"`, must NOT have `loading="lazy"`. Auto-fix.

**Check 3 — Section image lazy-loading**: Every `<figure>` / `<img>` AFTER the first must have `loading="lazy"`. Auto-fix.

**Check 4 — No local image paths (HARD FAIL)**: Scan for `src="images/`. If found → HALT with: `FAIL: local image path. Run blog-image first.`

**Check 5 — Hero inline (WARN)**: Hero CDN URL must appear as `<img src="https://` within first 2,000 chars. WARN if absent. Do NOT halt.

After all checks: `HTML gate: N auto-fixes applied. [PASS / FAIL]`. If PASS → Step 3.

---

## Step 3: Upload Content as DRAFT

**ALWAYS draft first.** Never set status to "publish" directly (except `--now` + explicit confirm).

### Via WP MCP Ultimate (if available):
```
ability: "create_post"
params: { "title", "content", "slug", "status": "draft",
          "categories": [CATEGORY_ID], "featured_media": HERO_MEDIA_ID }
```

### Via WP REST API (fallback):
```python
import urllib.request, json
payload = {
    "title": title,
    "content": html,
    "slug": slug,
    "status": "draft",
    "categories": [category_id],
    "featured_media": hero_media_id,
    "meta": {"_kad_post_feature": "hide", "_kad_post_title": "normal"}  # Kadence theme
}
req = urllib.request.Request(
    f"{site_url}/wp-json/wp/v2/posts",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
post_id = json.loads(urllib.request.urlopen(req).read())["id"]
```

Save `post_id` for next steps.

### Re-run behavior (--update mode)

On `--update [post_id]`: Step 1 is no-op (manifest already has live media IDs); Step 3 is `POST /posts/{id}` with only the `content` field. Media library stays clean.

---

## Step 4: Set Rank Math SEO

See `references/rankmath-api.md` for full rules.

Summary:
- **Title**: 50-60 chars, keyword in first 50%, power word + number
- **Meta description**: 150-160 chars, keyword present, 1 stat, ends with CTA
- **Focus keyword**: 5 comma-separated (primary + 4 semantic variations)
- **Slug**: ≤75 chars, keyword, lowercase, no stop words/dates

```python
payload = {
    "objectID": post_id,
    "objectType": "post",
    "meta": {
        "rank_math_title": rm_title,
        "rank_math_description": rm_description,
        "rank_math_focus_keyword": ", ".join([primary_kw] + secondary_kws[:4]),
    }
}
req = urllib.request.Request(
    f"{site_url}/wp-json/rankmath/v1/updateMeta",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
urllib.request.urlopen(req).read()
```

**Use Python `urllib.request` (NOT `curl`) for UTF-8 safety on Windows.**

---

## Step 4.5: Rank Math Pre-Validation Gate (HARD)

**MANDATORY before Step 4 push.** Catches FK mismatch bugs (e.g., FK = "blog publish" with space but body uses "blog-publish" with hyphen → 0 match → Rank Math score 35/100).

```python
import re
fk_lower = primary_kw.lower().strip()
title_lower = rm_title.lower()
desc_lower = rm_description.lower()
slug_lower = slug.lower()
content_lower = blog_html.lower()

checks = {
    # Basic SEO (Rank Math)
    "fk_in_title":         fk_lower in title_lower,
    "fk_in_meta":          fk_lower in desc_lower,
    "fk_in_url":           fk_lower.replace(" ", "-") in slug_lower or fk_lower in slug_lower.replace("-", " "),
    "fk_at_content_start": fk_lower in content_lower[:max(len(content_lower)//10, 3000)],
    "fk_in_content":       content_lower.count(fk_lower) >= 1,
    "title_len_50_60":     50 <= len(rm_title) <= 60,
    "meta_len_150_160":    150 <= len(rm_description) <= 160,
    # Title readability
    "fk_at_title_start":   fk_lower in title_lower[:len(title_lower)//2 + 1],
    "title_has_number":    bool(re.search(r"\d", rm_title)),
    # Additional SEO
    "fk_in_subheading":    any(fk_lower in h.lower() for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", blog_html, re.DOTALL)),
    "keyword_density":     content_lower.count(fk_lower) * len(fk_lower.split()) / max(len(re.sub(r"<[^>]+>", " ", blog_html).split()), 1) >= 0.005,
}

failed = [k for k, v in checks.items() if not v]
if failed:
    raise ValueError(
        f"Rank Math pre-validation failed: {failed}. "
        f"Set focus_keyword = phrasing that EXACTLY appears in title/meta/body. "
        f"Common fix: change FK to match body hyphen/slash/space exactly."
    )
```

Halt on any failure. Skip rules:
- Skip if `--update [post_id]` AND content unchanged (only meta refresh)
- Skip is NOT allowed for first publish

---

## Step 5: Set Tags

Read `references/tag-selection.md` for selection rules.

Summary:
- Max 2 tags per post (1 primary + 0-1 secondary)
- Resolve tag names → tag IDs via `GET /wp-json/wp/v2/tags?search=<name>`
- Cache tag IDs in BRAND.md to avoid repeat lookups

```python
req = urllib.request.Request(
    f"{site_url}/wp-json/wp/v2/posts/{post_id}",
    data=json.dumps({"tags": tag_ids}).encode("utf-8"),
    headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
urllib.request.urlopen(req).read()
```

---

## Step 6: Schedule 24h Out (or `--now`)

Default: schedule 24h out (status: `future`):

```python
from datetime import datetime, timedelta, timezone
schedule_time = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
payload = {"status": "future", "date": schedule_time}
```

If `--now` flag: prompt user for explicit confirmation, then `status: "publish"`. Never auto-publish.

---

## Step 7: Post-Publish Verification (9 checks)

See `references/post-publish-verify.md` for full check list. Run all in parallel:

1. **All image URLs HTTP 200** (HEAD each)
2. **All internal links HTTP 200** (HEAD each)
3. **`featured_media > 0`** (GET post, check field)
4. **Hero inline check** — hero CDN URL appears as `<img src=` in body (featured_media + inline both required)
5. **FAQ H2 present** — regex match `<h2[^>]*>.*FAQ.*</h2>` (case-insensitive)
6. **OG meta complete** — og:title, og:description, og:image, og:type, og:url, og:site_name
7. **Twitter Card present** (if BRAND.md has `twitter_handle`)
8. **Title 50-60 chars** + **Meta 150-160 chars** (read Rank Math meta)
9. **Schema JSON-LD valid** (BlogPosting + FAQPage + BreadcrumbList structures)

Optional Vietnamese check (only with `--strict-diacritics` flag):
- Diacritic ratio > 13% in body text

Failures flag in `publish-info.json` but DON'T rollback — user inspects.

---

## Step 8: Save publish-info.json + Report

Write to `articles/[slug]/publish-info.json`:

```json
{
  "post_id": 12345,
  "url": "https://yoursite.com/slug/",
  "status": "future",
  "scheduled_for": "2026-05-24T13:00:00Z",
  "featured_media_id": 67890,
  "section_image_ids": [67891, 67892, 67893],
  "rankmath": {
    "title": "...",
    "description": "...",
    "focus_keyword": "primary, lsi1, lsi2, lsi3, lsi4"
  },
  "verification": {
    "images_200": true,
    "internal_links_200": true,
    "featured_set": true,
    "hero_inline": true,
    "faq_present": true,
    "og_meta_complete": true,
    "twitter_card": true,
    "title_length": 56,
    "meta_length": 158,
    "schema_valid": true
  },
  "next_steps": [
    "Article scheduled for 2026-05-24 13:00 UTC",
    "Run /blog repurpose [post_id] for social variants",
    "Run /blog google index inspect [url] after publish to verify GSC"
  ]
}
```

Print summary table to user. Open URL in browser for visual inspection.

---

## Flags

- `--site [name]` — multi-site mode (resolves BRAND.md from `sites/[name]/`)
- `--convert-only` — Step 1 + Step 2 only, no upload
- `--skip-convert` — input is pre-converted HTML
- `--update [post_id]` — update existing post (skip Step 1 image upload, only content + meta)
- `--verify [post_id]` — run Step 7 verification only
- `--now` — publish immediately (REQUIRES explicit user confirmation)
- `--dry-run` — preview all payloads without HTTP writes
- `--strict-diacritics` — enforce Vietnamese diacritics >13% in body

## Auth Configuration

Read WP credentials from env OR `.mcp.json`:

```json
{
  "mcpServers": {
    "wp-mcp-ultimate": {
      "env": {
        "WORDPRESS_URL": "https://yoursite.com",
        "WORDPRESS_USER": "admin",
        "WORDPRESS_PASSWORD": "your-application-password"
      }
    }
  }
}
```

Generate Application Password: WP Admin → Users → Profile → Application Passwords section. Use Basic auth header: `Basic {base64(WP_USER:WP_APP_PASSWORD)}`.

## Safety Rules (MANDATORY)

1. **NEVER publish immediately** without `--now` flag + explicit user confirmation
2. **NEVER overwrite** published post content silently — only DRAFT or scheduled posts
3. **NEVER touch posts** with different slug than expected (Step 0.5 guard)
4. **NEVER skip Step 7 verification** (silent failures = bad outcomes)
5. **NEVER expose WP_APP_PASSWORD** in logs (mask first/last 4 chars only)
6. **HALT on Rank Math pre-validation failure** (Step 4.5) — don't push broken meta

## Failure Recovery

| Failure | Behavior |
|---------|----------|
| WP REST 401/403 | Halt + guidance: regenerate Application Password |
| Rank Math endpoint 404 | Halt + check Rank Math Pro installed + version ≥ 1.0.220 |
| Image upload timeout | Retry once with smaller resize (1800px); 2nd fail → halt |
| Schedule date in past | Recalculate now+24h, log warning, continue |
| FAQ H2 missing | Verification flag `faq_present: false`, allow publish |
| Cross-site slug mismatch | Halt — Step 0.5 guard refuses push |
| Rank Math pre-validation fail | Halt — Step 4.5 surfaces specific failure + fix guidance |

## Step 9: Bidirectional Internal Link Injection (M10 ✅ v0.2)

After Step 7 verification passes, optionally inject reciprocal inbound links from sibling posts that this new article links TO.

Reason: cluster integrity. When new post X links to existing posts Y, Z, W → those should link BACK to X for topical authority signal + AI citation graph.

```bash
Step 9.1: Extract outbound internal links from new article (regex)
Step 9.2: For each target URL:
  - WP GET target post content
  - Check if new_url already linked from target (regex match)
  - If absent → suggest reciprocal anchor (auto-derive from new article title)
Step 9.3: User confirms suggestions interactively (per-target Y/N)
Step 9.4: Patch confirmed targets via WP REST API (with slug guard)
Step 9.5: Log to publish-info.json: backlinks_added: [{post_id, anchor, position}]
```

See `references/bidirectional-links.md` for full logic + priority rules (P0 pillar→spoke, P1 sibling, P2 cross-cluster).

Skip rules:
- Target post < 1500 chars (too short for paragraph injection) → skip
- Anchor not found in target's last 30% content → skip
- Existing link to new_url already present → skip silently
- `--no-backlinks` flag → skip entire step

## References

| File | What it covers |
|------|----------------|
| `references/md-to-html.md` | Markdown → HTML conversion rules + component injection |
| `references/image-upload.md` | WebP conversion + WP media upload + URL patching |
| `references/rankmath-api.md` | Rank Math REST endpoint + meta field rules |
| `references/post-publish-verify.md` | 9-check verification + parallel execution |
| `references/tag-selection.md` | Tag taxonomy + WP ID resolution |
| `references/rollback-rules.md` | When + how to rollback (post deletion, draft revert) |
| `references/bidirectional-links.md` | Phase 6.5 bidirectional injection (M10 v0.2) |

## Source attribution

Logic ported from `~/.claude/skills/ng-publish/SKILL.md` (ng-publish v2.2.0, ongboit.com Vietnamese workflow). Vietnamese-specific bits abstracted to optional `--strict-diacritics` flag. Original concept + WP pipeline patterns © Nguyễn Minh Thế (ongboit.com). MIT-licensed for use in this fork.

## Implementation status

✅ **v0.1.0** — SKILL.md complete with 10-step pipeline (Steps 0, 0.5, 1, 2, 2.5, 2.8, 3, 4, 4.5, 5, 6, 7, 8).

Reference docs needed (next commits):
- ⏳ `references/md-to-html.md` — full conversion + component injection rules
- ⏳ `references/image-upload.md` — full upload script
- ⏳ `references/rankmath-api.md` — Rank Math endpoint detail
- ⏳ `references/post-publish-verify.md` — 9-check implementations
- ⏳ `references/tag-selection.md` — tag taxonomy rules
- ⏳ `references/rollback-rules.md` — rollback procedures

Future enhancements (per MIGRATION.md M10):
- ⏳ Bidirectional internal link injection (Phase 6.5 from ng-publish v5.24)
