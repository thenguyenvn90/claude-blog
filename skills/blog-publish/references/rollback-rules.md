# Rollback Procedures

When to rollback a publish, and how.

## When NOT to rollback

Per Step 7 verification: failures are flagged in `publish-info.json` but DON'T trigger automatic rollback. User inspects + decides.

Common case: FAQ missing, hero inline missing — these are WARNs, not catastrophic. Leave the post and fix later via `--update [post_id]`.

## When TO rollback

Rollback only if:
- ✅ Post body has corrupted content (raw markdown leaked into HTML, broken structure)
- ✅ Wrong post slug — published to wrong URL
- ✅ Cross-site corruption: pushed content to post on wrong site
- ✅ Catastrophic SEO meta: title is empty, meta is empty, FK is wrong

For minor issues (1 broken link, 1 missing image), prefer `--update [post_id]` over rollback.

## Rollback options

### Option 1: Set back to DRAFT (safest)

```python
import json, urllib.request

def revert_to_draft(post_id, site_url, auth):
    """Set post status back to 'draft', removing schedule + immediate publish."""
    payload = {"status": "draft"}
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": auth, "Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req).read()
```

Pros: Reversible (just re-schedule). URL stays.

### Option 2: Restore prior version (WP revisions)

WP keeps revision history. Restore via REST API:

```python
def list_revisions(post_id, site_url, auth):
    """List all revisions of a post."""
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}/revisions",
        headers={"Authorization": auth}
    )
    return json.loads(urllib.request.urlopen(req).read())

def restore_revision(post_id, revision_id, site_url, auth):
    """Restore a specific revision's content."""
    rev = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}/revisions/{revision_id}",
        headers={"Authorization": auth}
    )).read())
    payload = {
        "title": rev["title"]["raw"],
        "content": rev["content"]["raw"],
        "excerpt": rev["excerpt"]["raw"],
    }
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": auth, "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return urllib.request.urlopen(req).read()
```

Pros: Restores exact content. Cons: User must identify correct revision.

### Option 3: Delete post (permanent)

```python
def delete_post(post_id, site_url, auth, force=False):
    """Delete a post. force=True permanently deletes; False sends to trash."""
    url = f"{site_url}/wp-json/wp/v2/posts/{post_id}"
    if force:
        url += "?force=true"
    req = urllib.request.Request(
        url,
        headers={"Authorization": auth},
        method="DELETE"
    )
    return urllib.request.urlopen(req).read()
```

**ONLY use as last resort** — destroys post + breaks all incoming links. Prefer Option 1 (revert to draft) instead.

## Rollback decision tree

```
Publish failed/corrupted?
├─ Step 7 verification flagged warnings (FAQ missing, hero inline, etc.)
│  → Don't rollback. Use --update [post_id] later. Continue.
│
├─ Content corrupted (raw markdown in HTML, broken HTML)
│  → Option 1: revert to draft + fix locally + re-publish
│
├─ Wrong slug published
│  → Don't rollback. Patch slug via REST + redirect old URL to new
│
├─ Cross-site corruption (pushed to wrong site)
│  → Option 2: restore prior revision IMMEDIATELY
│  → File incident note for later cross-corruption audit
│
└─ Catastrophic SEO meta (empty title/meta/FK wrong)
   → Just re-run Step 4 (Rank Math update) — no rollback needed
```

## Cross-site corruption prevention

Prevent rollback need by enforcing pre-push slug check (Step 0.5 in SKILL.md):

```python
# Before any content push, verify:
local_slug == live_wp_slug
```

If mismatch → halt push. Surface to user.

## After rollback

1. Document in `publish-info.json`:
   ```json
   {
     "rollback": {
       "reason": "raw markdown leaked",
       "action": "revert_to_draft",
       "rollback_time": "2026-05-23T16:30:00Z",
       "next_steps": "fix locally + re-run publish"
     }
   }
   ```

2. Notify user with clear next steps
3. Don't delete article folder — keep all phase outputs for debugging
4. After fix: `--update [post_id]` to re-publish

## Don't

- ❌ Auto-rollback on Step 7 verification failure (warnings != catastrophic)
- ❌ Delete posts without user confirmation
- ❌ Restore revisions without showing user the diff first
- ❌ Skip Step 0.5 slug drift check (the #1 cause of cross-site corruption)
