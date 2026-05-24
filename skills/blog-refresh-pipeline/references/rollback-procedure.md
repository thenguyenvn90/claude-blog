# Rollback Procedure — Reference

> 1-command revert if `/blog-refresh-pipeline` Phase 5+ push goes wrong. Always available because Phase 1 unconditionally saves `blog-v1-backup.html`.

## When to rollback

Trigger immediately (no questions asked) if ANY of these conditions after Phase 5.4 (WP push):

- Live page render broken (layout broken, wpautop spitting raw HTML/markdown)
- HTTP 5xx on live URL
- Internal links mass-broken (>30% of `<a href>` return 404)
- Schema markup invalid (Rich Results Test fails)
- >50% diacritic loss vs backup (Vietnamese sites only — encoding corruption)
- Featured image lost / hero broken
- Critical content missing from live (Phase 6 verify FAIL on "Add New" H2 checks)

## 1-command rollback

```bash
python3 ~/.claude/scripts/wp_push_safe.py $POST_ID \
  articles/$SLUG/blog-v1-backup.html \
  --slug $SLUG \
  --expected-slug $SLUG
```

`wp_push_safe.py` (from `/blog-publish` skill) validates:
- POST_ID's WP slug matches `--expected-slug` (prevents cross-slug corruption)
- Backup HTML doesn't have raw-markdown leak indicators (sanity check on rollback target)

Exit 0 = rollback successful, original content restored.
Exit 1 = rollback rejected (mismatch detected) — investigate manually.

## Verify rollback worked

```bash
curl -s "https://$SITE/$SLUG/?nc=$(date +%s)" \
  -A "Mozilla/5.0" -H "Cache-Control: no-cache" | head -200
```

Check:
1. Title matches `backup-meta.json.title`
2. H2 sections match backup HTML's H2s
3. No broken layout
4. Internal links resolve (spot-check 5-10)

## After rollback

1. **Diagnose root cause** — DO NOT just retry the same flow.

   Common causes:
   | Symptom | Likely cause | Fix |
   |---------|--------------|-----|
   | wpautop spitting markdown | `> -` blockquote leak in `blog.html` | Run `refresh_preflight.py` more strictly, strip MD before push |
   | Image broken | URL not patched after WP media upload | Re-check Phase 5.4 image URL substitution |
   | Schema invalid | Rank Math focus keyword had special chars | Sanitize Rank Math meta payload |
   | Mass 404 internal links | Wrong URL prefix in refresh-plan.md | Audit refresh-plan.md absolute vs relative paths |
   | Diacritic loss (vi) | Wrong encoding on REST push (latin-1 vs utf-8) | Ensure wp_push_safe.py forces UTF-8 |
   | Layout break | New `<figure>` blocks have inline style conflict | Validate HTML with `tidy` before push |

2. **Fix HTML locally** in `articles/$SLUG/blog.html`

3. **Re-run preflight**:
   ```bash
   python3 ~/.claude/scripts/refresh_preflight.py \
     articles/$SLUG/blog.html \
     --backup articles/$SLUG/blog-v1-backup.html \
     --language $LANG \
     --min-delta-pct 15
   ```

4. **Re-push** via `wp_push_safe.py` once preflight passes.

5. **Re-verify** via Phase 6.

## Pipeline-state.json after rollback

Update `pipeline-state.json` to reflect rollback event:

```json
{
  "phases": {
    "5_write_push": {
      "status": "rolled_back",
      "rollback_at": "2026-05-24T15:00:00Z",
      "rollback_reason": "live page wpautop leak",
      "outputs_at_failure": ["blog.html"],
      "rolled_back_to": "blog-v1-backup.html",
      "verify_rollback_passed": true
    }
  }
}
```

Update `workflow-log.json` with rollback event:
```bash
python3 ~/.claude/scripts/workflow_tracker.py log-api \
  --slug $SLUG --phase 5 --tool wp-rest \
  --endpoint posts_update_rollback --count 1
```

## Multiple rollback attempts

If first rollback also fails (very rare), escalate:

1. Manual WP REST direct call (bypass wp_push_safe):
   ```bash
   curl -X POST "$WP_BASE/posts/$POST_ID" \
     -H "Authorization: Basic $WP_AUTH" \
     -H "Content-Type: application/json" \
     -d @articles/$SLUG/blog-v1-backup.html
   ```

2. WP Admin manual revision restore: Posts → Edit post → Revisions sidebar → select pre-refresh version → Restore

3. Database-level revert (last resort, only DBA): restore `wp_posts.post_content` from MySQL backup taken before refresh

## Anti-patterns

| Pattern | Why bad |
|---------|---------|
| Roll forward "I'll just push another fix" without rolling back broken state first | Each broken push compounds; live page stays broken longer |
| Rollback without diagnosing → retry same flow | Same bug ships again |
| Skip Phase 1 backup to "save time" | Cannot rollback at all if push fails |
| Use `git revert` to fix WP content | WP content is in MySQL, not git — irrelevant |
| Manually edit live HTML via WP Admin | Loses sync with `articles/[slug]/blog.html` local state |

## Reference: backup-meta.json schema

```json
{
  "id": 12345,
  "slug": "my-old-article",
  "title": "Original article title",
  "modified": "2026-04-15T10:30:00Z",
  "char_count": 41746,
  "fetched_at": "2026-05-24T14:00:00Z",
  "wp_base": "https://yoursite.com/wp-json/wp/v2/posts",
  "site": "yoursite.com"
}
```

This metadata is the ground truth for rollback. Never delete `backup-meta.json` until Phase 6 verify passes + 7-day cooldown elapsed.
