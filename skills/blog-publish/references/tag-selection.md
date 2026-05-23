# Tag Selection Rules

WordPress tags are per-installation IDs. Resolve names → IDs at publish time.

## Selection rules

- **Max 2 tags per post**: 1 primary + 0-1 secondary
- Don't bloat tag taxonomy (>30 tags becomes hard to manage at scale)
- Reuse existing tags before creating new
- Tag should be a **topic** (e.g., "claude code"), not a category (which is hierarchical)

## Resolve names → IDs

```python
import json, urllib.request

def resolve_tag_id(name, site_url, auth, create_if_missing=False):
    """Look up WP tag ID by name. Optionally create if missing."""
    search = urllib.request.urlopen(urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/tags?search={urllib.parse.quote(name)}&per_page=10",
        headers={"Authorization": auth}
    )).read()
    candidates = json.loads(search)
    # Exact match
    for c in candidates:
        if c["name"].lower() == name.lower():
            return c["id"]
    # Create if requested
    if create_if_missing:
        req = urllib.request.Request(
            f"{site_url}/wp-json/wp/v2/tags",
            data=json.dumps({"name": name}).encode("utf-8"),
            headers={"Authorization": auth, "Content-Type": "application/json"},
            method="POST"
        )
        return json.loads(urllib.request.urlopen(req).read())["id"]
    return None
```

## Cache tag IDs in BRAND.md

To avoid repeat lookups, cache common tag IDs in BRAND.md:

```markdown
## CMS Config

### Tags (WP tag ID cache)

| Tag name | WP ID | Last verified |
|----------|------:|---------------|
| claude code | 14 | 2026-05-23 |
| n8n | 27 | 2026-05-23 |
| seo | 19 | 2026-05-23 |
| ai | 31 | 2026-05-23 |
| automation | 42 | 2026-05-23 |
```

Resolver logic:
1. First check BRAND.md cache → use cached ID if present
2. If miss → call WP REST API → cache result in BRAND.md (write back)
3. Cache invalidation: re-verify if last_verified > 90 days

## Apply tags to post

```python
def set_tags(post_id, tag_ids, site_url, auth):
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}",
        data=json.dumps({"tags": tag_ids}).encode("utf-8"),
        headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return urllib.request.urlopen(req).read()
```

## Tag suggestion from content

If brief.md doesn't specify tags, auto-suggest from content NLP:

```python
# Naive approach: extract proper nouns + tech terms from title/H2
import re

def suggest_tags(title, content, known_tags):
    # Tokenize title + H2s
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", content, re.DOTALL)
    text = " ".join([title] + [re.sub(r"<[^>]+>", " ", h) for h in h2s])
    text_lower = text.lower()
    # Match against known tags
    matches = []
    for tag in known_tags:
        if tag.lower() in text_lower:
            matches.append(tag)
    return matches[:2]  # max 2 tags
```

For better NLP, integrate with `/blog google nlp` skill (entity extraction).

## Don't

- ❌ Create tag for every keyword variation (bloat)
- ❌ Use tags as categories (hierarchical structure goes in `categories`)
- ❌ Tag with brand names if you're not the brand (link equity dilution)
- ❌ Reuse old tags that are now unmaintained (audit `category` count per tag)
