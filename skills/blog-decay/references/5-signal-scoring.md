# 5-Signal Decay Scoring — Detailed Criteria

> Companion to `SKILL.md`. Provides per-signal scoring criteria with edge cases.

## Signal 1 — Age (weight: 0.20)

### Score thresholds

| Days since publish/refresh | Score | Bucket interpretation |
|---------------------------:|------:|-----------------------|
| 0-89 | 0 | Fresh — no decay |
| 90-179 | 25 | Recent, watch |
| 180-364 | 50 | Aging |
| 365-729 | 75 | Stale |
| 730+ | 100 | Very stale |

### How to compute

```python
from datetime import datetime, timezone

def score_age(post):
    """post = WP post dict with 'modified' field (ISO 8601)."""
    last_update = datetime.fromisoformat(post["modified"].replace("Z", "+00:00"))
    days_old = (datetime.now(timezone.utc) - last_update).days

    if days_old < 90:
        return 0
    elif days_old < 180:
        return 25
    elif days_old < 365:
        return 50
    elif days_old < 730:
        return 75
    else:
        return 100
```

### Modifier — was this article refreshed?

If article has custom meta `_refreshed_at` set within last 90 days → subtract 25 from age score (encourages users to ACTUALLY update vs just changing modified date).

```python
def score_age_with_refresh(post, refreshed_at_meta):
    base = score_age(post)
    if refreshed_at_meta:
        refresh_date = datetime.fromisoformat(refreshed_at_meta)
        days_since_refresh = (datetime.now(timezone.utc) - refresh_date).days
        if days_since_refresh < 90:
            base = max(0, base - 25)
    return base
```

## Signal 2 — GSC Click Decline (weight: 0.30)

### Source

Google Search Console click data per URL. Compare:
- Last 90 days: clicks
- Prior 90-day window: clicks
- Decline % = (prior - last) / prior * 100

### Score thresholds

| Decline | Score |
|--------:|------:|
| < 10% (stable or growing) | 0 |
| 10-30% | 25 |
| 30-50% | 50 |
| 50-70% | 75 |
| 70%+ | 100 |

### How to compute

```python
def score_gsc_decline(slug, gsc_cli_path="/usr/local/bin/gsc"):
    """Query GSC for URL click trend."""
    import subprocess
    from datetime import datetime, timedelta

    end_date = datetime.now().date()
    last_90_start = end_date - timedelta(days=90)
    prior_90_start = last_90_start - timedelta(days=90)
    prior_90_end = last_90_start - timedelta(days=1)

    # Query last 90d
    result = subprocess.run([
        gsc_cli_path, "query", "--site", "sc-domain:yoursite.com",
        "--start", str(last_90_start), "--end", str(end_date),
        "--dimensions", "page",
    ], capture_output=True, text=True)
    last_90_clicks = sum(row.get("clicks", 0) for row in parse_gsc_output(result.stdout) if slug in row.get("page", ""))

    # Query prior 90d
    result = subprocess.run([
        gsc_cli_path, "query", "--site", "sc-domain:yoursite.com",
        "--start", str(prior_90_start), "--end", str(prior_90_end),
        "--dimensions", "page",
    ], capture_output=True, text=True)
    prior_90_clicks = sum(row.get("clicks", 0) for row in parse_gsc_output(result.stdout) if slug in row.get("page", ""))

    if prior_90_clicks == 0:
        return None  # No baseline — skip Signal 2

    decline_pct = (prior_90_clicks - last_90_clicks) / prior_90_clicks * 100
    if decline_pct < 10:
        return 0
    elif decline_pct < 30:
        return 25
    elif decline_pct < 50:
        return 50
    elif decline_pct < 70:
        return 75
    else:
        return 100
```

### Edge cases

- New article (< 90 days old, no prior window) → return `None` (skip Signal 2)
- Article with 0 clicks both windows → return `None` (data insufficient)
- Article with 0 prior, N current → return 0 (growth signal, exclude from decay)

## Signal 3 — External Link Rot (weight: 0.15)

### Source

Sampled HTTP HEAD requests on external links in article body.

### How to compute

```python
import re, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

def score_link_rot(post_content, sample_size=10):
    """HEAD external links, count failures."""
    # Extract external links
    pattern = r'<a[^>]+href="(https?://[^"]+)"'
    external_links = re.findall(pattern, post_content)
    # Filter same-domain
    external_links = [url for url in external_links if "yoursite.com" not in url]

    if not external_links:
        return 0  # No external links, no rot

    # Random sample if > sample_size
    import random
    if len(external_links) > sample_size:
        external_links = random.sample(external_links, sample_size)

    broken_count = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        def head_check(url):
            try:
                req = urllib.request.Request(url, method="HEAD")
                urllib.request.urlopen(req, timeout=10)
                return True
            except (urllib.error.URLError, urllib.error.HTTPError):
                return False
        results = list(ex.map(head_check, external_links))
        broken_count = sum(1 for ok in results if not ok)

    if broken_count == 0:
        return 0
    elif broken_count == 1:
        return 30
    elif broken_count == 2:
        return 60
    else:
        return 100
```

### Edge cases

- Site returns 403 for HEAD but 200 for GET → counts as broken (Cloudflare anti-bot can cause false positives — accept this trade-off)
- Rate limiting (429) → counts as broken
- Site requires User-Agent → add UA header to HEAD request

## Signal 4 — Jaccard SERP Cannibalization (weight: 0.20)

### Source

For each article's primary keyword, fetch top-10 Google SERP. Check overlap with sibling articles' top-10 SERPs.

### How to compute

```python
def score_cannibal_jaccard(article_a, article_b, top_n=10):
    """Jaccard overlap of top-N SERP URLs for two articles' primary keywords."""
    serp_a = set(get_serp_top_n(article_a["primary_keyword"], top_n))
    serp_b = set(get_serp_top_n(article_b["primary_keyword"], top_n))
    intersection = serp_a & serp_b
    union = serp_a | serp_b
    if not union:
        return 0
    jaccard = len(intersection) / len(union)

    if jaccard < 0.2:
        return 0
    elif jaccard < 0.4:
        return 25
    elif jaccard < 0.6:
        return 50
    elif jaccard < 0.8:
        return 75
    else:
        return 100
```

### Computational cost

For N articles, pairwise comparison = O(N²) SERP queries. For 50 articles = 1,225 pairs. At ~$0.001 per SERP query → ~$1.25 per scan. Accept this cost for accuracy.

Optimization: cache SERP results per keyword for 7 days. Re-use across articles with same keyword.

### Edge cases

- Article's primary keyword not in brief.md → use slugified URL as proxy keyword (less accurate)
- SERP API rate limit → fall back to last cached SERP

## Signal 5 — Orphan / Dead-End (weight: 0.15)

### Source

Build internal link graph across all site articles.

### How to compute

```python
def score_orphan_deadend(article, all_articles, site_domain):
    """Score article's position in internal link graph."""
    import re

    inbound_count = 0
    outbound_count = 0

    # Count outbound (links from this article to others)
    article_url = f"/{article['slug']}/"
    outbound_pattern = re.compile(r'<a[^>]+href="(?:' + re.escape(site_domain) + r')?(/[^"]+/)"')
    outbound_links = outbound_pattern.findall(article.get("content", ""))
    outbound_count = len([l for l in outbound_links if l != article_url])

    # Count inbound (links from other articles to this article)
    for other in all_articles:
        if other["id"] == article["id"]:
            continue
        if outbound_pattern.search(other.get("content", "")):
            other_outbound = outbound_pattern.findall(other.get("content", ""))
            if article_url in other_outbound:
                inbound_count += 1

    if inbound_count >= 1 and outbound_count >= 1:
        return 0  # Healthy
    elif inbound_count >= 1 and outbound_count == 0:
        return 50  # Dead-end
    elif inbound_count == 0 and outbound_count >= 1:
        return 75  # Orphan
    else:
        return 100  # Isolated
```

### Edge cases

- Internal link uses absolute URL instead of relative → still detected via regex
- Anchor includes query string → strip query before comparison
- Redirected internal links → follow redirect, score based on final URL

## How to handle missing data

| Signal | If data unavailable | Behavior |
|--------|---------------------|----------|
| 1 (Age) | (always available — WP API has modified) | n/a |
| 2 (GSC) | No GSC access OR no baseline | Return None, redistribute 0.30 weight to other 4 signals proportionally |
| 3 (Link rot) | No external links | Return 0 |
| 4 (Cannibal) | SERP API unavailable | Return None, redistribute 0.20 weight |
| 5 (Orphan) | (always available — WP REST) | n/a |

## Composite formula with redistribution

```python
def composite_with_redistribution(signals):
    base_weights = {"age": 0.20, "gsc_decline": 0.30, "link_rot": 0.15, "cannibal": 0.20, "orphan": 0.15}
    available = {k: v for k, v in signals.items() if v is not None}
    if not available:
        return 0
    total_weight = sum(base_weights[k] for k in available)
    composite = sum(available[k] * base_weights[k] / total_weight * 1.0 for k in available)
    return composite * 100  # Scale to 0-100
```
