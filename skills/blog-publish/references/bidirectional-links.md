# Bidirectional Internal Link Injection (M10 — Phase 6.5)

> When a new article links OUT to sibling articles, this step injects reciprocal inbound links FROM those siblings TO the new article. Closes cluster integrity loops.
>
> Ported from ng-publish v5.24 Phase 6.5 (ongboit.com pattern).

## Why bidirectional matters

Search engines + AI citation engines use the internal link graph as a topical authority signal. When pillar/cluster articles form a true graph (every node linked from multiple peers), the cluster:
- Ranks better than scattered articles
- Gets more AI citations (cluster-cited articles cited 3.2× more than standalone)
- Signals topical depth for E-E-A-T

Without bidirectional injection, new articles become "satellites" — they link IN to existing articles but no existing article links BACK. Asymmetric graph = weaker authority signal.

## Logic

### Step 1: Extract outbound internal links from new article

```python
import re

def extract_internal_links(html_content, site_domain):
    """Extract <a href> tags pointing to same domain or relative paths."""
    pattern = r'<a[^>]+href="(?:' + re.escape(site_domain) + r')?(/[^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html_content)
    # Return list of (url_path, anchor_text) tuples
    return [(path, anchor.strip()) for path, anchor in matches]
```

### Step 2: For each target, check existing inbound

```python
import urllib.request, json

def check_existing_inbound(target_url_path, new_url, site_url, auth):
    """Check if target post body already contains new_url as <a> link."""
    # Resolve target URL to post ID
    slug = target_url_path.strip('/').split('/')[-1]
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts?slug={slug}&_fields=id,content,modified",
        headers={"Authorization": auth}
    )
    posts = json.loads(urllib.request.urlopen(req).read())
    if not posts:
        return None, "target post not found"

    target_post = posts[0]
    target_content = target_post.get("content", {}).get("rendered", "")

    # Check if new_url appears as any <a href>
    pattern = re.compile(rf'<a[^>]+href="[^"]*{re.escape(new_url)}[^"]*"')
    existing = bool(pattern.search(target_content))

    return target_post, "exists" if existing else "missing"
```

### Step 3: Suggest reciprocal anchor

```python
def suggest_anchor(new_article_title, new_article_h1):
    """Auto-derive anchor text from new article title."""
    # Strategy 1: Use new article title as-is if 2-5 words
    title_words = new_article_title.split()
    if 2 <= len(title_words) <= 5:
        return new_article_title.lower()

    # Strategy 2: Use first H1 if shorter
    h1_words = new_article_h1.split() if new_article_h1 else []
    if 2 <= len(h1_words) <= 5:
        return new_article_h1.lower()

    # Strategy 3: Extract noun phrase (use first 3 nouns)
    # For simplicity: use first 3 words of title
    return " ".join(title_words[:3]).lower()
```

### Step 4: Find insertion point in target

```python
def find_insertion_point(target_content):
    """Find natural insertion point in target — last 30% of content, after last H2."""
    total_len = len(target_content)
    last_30pct_start = int(total_len * 0.7)

    # Look for last H2 in last 30%
    h2_positions = [m.start() for m in re.finditer(r'<h2[^>]*>', target_content[last_30pct_start:])]
    if h2_positions:
        # Insert after last H2's closing </h2>
        last_h2_pos = last_30pct_start + h2_positions[-1]
        closing_h2 = target_content.find('</h2>', last_h2_pos)
        if closing_h2 > 0:
            # Find next </p> after that H2 (insert after first paragraph)
            next_p_close = target_content.find('</p>', closing_h2)
            if next_p_close > 0:
                return next_p_close + len('</p>')

    # Fallback: insert before first </p> in last 30%
    last_30 = target_content[last_30pct_start:]
    p_match = re.search(r'</p>', last_30)
    if p_match:
        return last_30pct_start + p_match.end()

    return None  # No insertion point found
```

### Step 5: Build inbound link paragraph

```python
def build_inbound_paragraph(new_url, anchor, context_hint):
    """Build a natural-language paragraph that references new_url."""
    templates = [
        f'<p>For a deeper dive into {anchor}, see our full guide on <a href="{new_url}">{anchor}</a>.</p>',
        f'<p>Related: <a href="{new_url}">{anchor}</a> explores this in more detail with concrete examples.</p>',
        f'<p>If you want to go deeper on {anchor}, our <a href="{new_url}">comprehensive walkthrough</a> covers it end-to-end.</p>',
    ]
    # Pick template based on context_hint or rotation (simple modulo for determinism)
    template_idx = hash(new_url) % len(templates)
    return templates[template_idx]
```

### Step 6: Patch target post (with slug guard)

```python
def patch_inbound_link(post_id, original_content, insertion_offset, paragraph_html,
                      site_url, auth, expected_slug):
    """Patch target post via WP REST API. Slug guard prevents cross-site corruption."""
    # Re-fetch to verify slug match
    fetch = urllib.request.urlopen(urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}?_fields=id,slug",
        headers={"Authorization": auth}
    )).read()
    live = json.loads(fetch)
    if live["slug"] != expected_slug:
        raise ValueError(f"SLUG MISMATCH: post {post_id} slug '{live['slug']}' != expected '{expected_slug}'. ABORT.")

    # Insert paragraph
    new_content = original_content[:insertion_offset] + "\n" + paragraph_html + original_content[insertion_offset:]

    # PATCH
    payload = {"content": new_content}
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())
```

## Priority rules

Process outbound links in priority order:

| Priority | Pair type | Inject? |
|----------|-----------|---------|
| **P0** | Pillar → Spoke (pillar article in cluster) | YES — pillar MUST link back |
| **P1** | Sibling spoke in same cluster | YES |
| **P2** | Cross-cluster (related topic, different cluster) | OPTIONAL — only if anchor matches naturally |
| **P3** | Unrelated (e.g., legacy article off-topic) | SKIP |

Priority detection logic:
- Read brief.md for `cluster_pillar` field
- If outbound URL = pillar → P0
- If outbound URL is in same cluster's spokes → P1
- If outbound URL is in adjacent cluster (per cluster-plan.json) → P2
- Else → P3 (skip)

## Skip rules

Skip injection if any:

- Target post `<` 1500 chars (too short for natural paragraph insertion)
- Anchor not found in target's last 30% content (would inject mid-article unnaturally)
- Existing link to new_url already present in target (regex match) — silent skip
- Target post `modified` date < 7 days ago (recently edited, don't disturb)
- User passed `--no-backlinks` flag

## User confirmation

Default: interactive — show suggestion for each target, ask user Y/N before patching.

```
Bidirectional links suggested:

  1. → /existing-article-a/ — anchor "claude code skills"
     Priority: P0 (pillar)
     Target post #4521, last modified 2026-04-10
     Insert position: after H2 "Conclusion" (last 30%)
     Patch? (y/n/skip-all):

  2. → /existing-article-b/ — anchor "blog pipeline guide"
     Priority: P1 (sibling)
     Target post #4892, last modified 2026-05-01
     Insert position: after H2 "Next steps" (last 30%)
     Patch? (y/n/skip-all):
```

Auto-confirm with `--auto-backlinks` flag (use with caution — patches multiple posts without review).

## Log to publish-info.json

After Step 9 completes:

```json
{
  "backlinks_added": [
    {
      "target_post_id": 4521,
      "target_slug": "existing-article-a",
      "anchor": "claude code skills",
      "priority": "P0",
      "patched_at": "2026-05-23T14:15:00Z",
      "wp_revision_id": 4522
    },
    {
      "target_post_id": 4892,
      "target_slug": "existing-article-b",
      "anchor": "blog pipeline guide",
      "priority": "P1",
      "patched_at": "2026-05-23T14:15:30Z",
      "wp_revision_id": 4893
    }
  ],
  "backlinks_skipped": [
    {
      "target_url": "/short-stub-article/",
      "reason": "target_too_short (1200 chars < 1500 min)"
    }
  ]
}
```

## Rollback

If a patch was wrong:
- WP keeps revisions per post
- Use `revert_to_revision(target_post_id, prior_revision_id)` from `rollback-rules.md`
- Or manually undo via WP Admin → Revisions

## Source

Ported from ng-publish v5.24 Phase 6.5 (`articles/ongboit.com/_site/verify_bidirectional.py` proven 5/7 inbound injection success rate on claude-ads + codex-seo cluster, 2026-05-22).

Vietnamese-specific phrasing ("Anchor strategy" table for Vietnamese pair templates) NOT ported. English template rotation provided here.
