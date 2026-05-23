# Rank Math API Integration

POST to `/wp-json/rankmath/v1/updateMeta` to set SEO fields on a WP post. Requires Rank Math Pro v1.0.220+.

## Endpoint

```
POST {site_url}/wp-json/rankmath/v1/updateMeta
Authorization: Basic [base64(user:app_password)]
Content-Type: application/json; charset=utf-8

{
  "objectID": post_id,
  "objectType": "post",
  "meta": {
    "rank_math_title": "...",
    "rank_math_description": "...",
    "rank_math_focus_keyword": "primary, lsi1, lsi2, lsi3, lsi4"
  }
}
```

Response: `{"slug": true, "schemas": []}`

## Field rules

### `rank_math_title` (50-60 chars)

- **Length**: 50-60 chars (Python `len()` for UTF-8 char count; non-ASCII = 1 char each)
- **Keyword placement**: primary keyword in FIRST 50% of title
- **Power word**: include 1 of: Best | Complete | Definitive | Essential | Guide | Proven | Ultimate
- **Number**: include year (2026) OR step count (10 Things, 7 Steps)
- **Format suggestions**:
  - `"[Keyword]: 7 Proven Steps for 2026"`
  - `"Best [Keyword] Tools (2026 Guide)"`
  - `"Ultimate [Keyword] Walkthrough: 10 Things"`

### `rank_math_description` (150-160 chars)

- **Length**: 150-160 chars exact
- **Keyword present**: appear at least once (preferably first half)
- **1 statistic**: 1 specific number (e.g., "saves 4 hours/week", "trusted by 50,000+ devs")
- **CTA at end**: end with verb-led call to action (e.g., "Read the full guide", "Try it free")
- **Format suggestion**:
  - `"Learn [keyword] with our 10-step guide. Real-world examples from [stat]. Save [N hours/week] by automating [pain]. Read the full walkthrough →"`

### `rank_math_focus_keyword` (5 comma-separated)

- **Format**: `primary, semantic1, semantic2, semantic3, semantic4`
- **No quotes**, no `[]` brackets
- **Primary**: exact match in title, meta, body (hyphen/slash/space-sensitive)
- **Semantic 1-4**: LSI variants (different word order, synonyms, related terms)
- **Example**: `"blog publish, wordpress publish, schedule blog post, blog publishing pipeline, wp rest api publish"`

## Python implementation

Use `urllib.request` for UTF-8 safety on Windows:

```python
import json
import urllib.request

def set_rankmath_meta(post_id, title, description, focus_keyword, site_url, auth):
    """Set Rank Math SEO meta. Returns True on success."""
    payload = {
        "objectID": post_id,
        "objectType": "post",
        "meta": {
            "rank_math_title": title,
            "rank_math_description": description,
            "rank_math_focus_keyword": focus_keyword,
        }
    }
    req = urllib.request.Request(
        f"{site_url}/wp-json/rankmath/v1/updateMeta",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": auth,
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        response = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        return json.loads(response).get("slug", False)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("ERROR: Rank Math endpoint not found. Check Rank Math Pro installed + version >= 1.0.220")
        elif e.code in (401, 403):
            print("ERROR: WP auth failed. Regenerate Application Password.")
        raise
```

## Why urllib NOT curl

`curl` breaks Vietnamese UTF-8 on Windows when passing JSON with diacritics:
```bash
# BAD — diacritics get mangled on Windows
curl -X POST -d '{"rank_math_title": "Hướng dẫn cài đặt"}' ...
```

```python
# GOOD — Python urllib handles UTF-8 correctly
data = json.dumps({"rank_math_title": "Hướng dẫn cài đặt"}, ensure_ascii=False).encode("utf-8")
```

## Failure handling

| Status | Cause | Fix |
|--------|-------|-----|
| 200 | Success | Verify `slug: true` in response |
| 401 | Invalid auth | Regenerate WP Application Password |
| 403 | User lacks `edit_posts` | Check WP user role (must be Author+) |
| 404 | Rank Math Pro not installed OR version too old | Install/update Rank Math Pro (≥ 1.0.220) |
| 500 | Plugin conflict | Check WP debug.log; disable plugins to isolate |

## Pre-validation (run BEFORE this endpoint)

See SKILL.md Step 4.5 — pre-validation checks 11 conditions on (title, meta, focus_keyword, content, slug) to catch FK mismatch bugs before pushing.

## Skip rules

Don't call this endpoint if:
- `--update [post_id]` AND only content changed (no FK/title/meta change)
- `--convert-only` mode (no upload)
- `--dry-run` mode (preview only)

## Verification (post-call)

After successful POST:
1. GET post via REST API
2. Verify `meta.rank_math_title` matches what was sent
3. Verify `meta.rank_math_description` matches
4. Verify `meta.rank_math_focus_keyword` matches
5. Open WP Admin → post edit page → Rank Math sidebar should show ≥ 75/100 score
