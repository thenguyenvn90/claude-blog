# Post-Publish Verification (9 checks)

Run all 9 checks in parallel via `concurrent.futures.ThreadPoolExecutor` after WP scheduling. Failures flag in `publish-info.json` but DON'T rollback — user inspects manually.

## Check 1 — All image URLs HTTP 200

```python
import urllib.request
def check_images(image_urls):
    failures = []
    for url in image_urls:
        try:
            urllib.request.urlopen(
                urllib.request.Request(url, method="HEAD"),
                timeout=10
            )
        except Exception as e:
            failures.append((url, str(e)))
    return len(failures) == 0, failures
```

## Check 2 — All internal links HTTP 200

```python
import re
def extract_internal_links(html, site_url):
    # Match <a href="/slug/"> or <a href="https://yoursite.com/slug/">
    pattern = r'<a[^>]+href="(?:' + re.escape(site_url) + r')?(/[^"]+)"'
    return [site_url + path for path in re.findall(pattern, html)]

# Then HEAD each, same as Check 1
```

## Check 3 — `featured_media > 0`

```python
import json, urllib.request
def check_featured_media(post_id, site_url, auth):
    req = urllib.request.Request(
        f"{site_url}/wp-json/wp/v2/posts/{post_id}",
        headers={"Authorization": auth}
    )
    post = json.loads(urllib.request.urlopen(req).read())
    return post.get("featured_media", 0) > 0, post.get("featured_media", 0)
```

## Check 4 — Hero inline

Hero URL must appear as `<img src=` in body content (featured_media + inline both required for max LCP):

```python
def check_hero_inline(post_content, hero_url):
    return f'<img' in post_content and hero_url in post_content[:5000]
```

If absent: WARN (some themes use featured-only hero). Don't halt.

## Check 5 — FAQ H2 present

```python
import re
def check_faq_h2(content):
    return bool(re.search(r"<h2[^>]*>.*?FAQ.*?</h2>", content, re.IGNORECASE | re.DOTALL))
```

WARN if missing (low priority).

## Check 6 — OG meta complete

Fetch rendered live page (not REST API) + parse `<head>`:

```python
from html.parser import HTMLParser
import urllib.request

class OGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            attrs_d = dict(attrs)
            prop = attrs_d.get("property", "")
            if prop.startswith("og:"):
                self.og[prop] = attrs_d.get("content", "")

def check_og_meta(live_url):
    html = urllib.request.urlopen(live_url, timeout=15).read().decode("utf-8", errors="replace")
    parser = OGParser()
    parser.feed(html)
    required = ["og:title", "og:description", "og:image", "og:type", "og:url", "og:site_name"]
    missing = [r for r in required if not parser.og.get(r)]
    return len(missing) == 0, missing
```

## Check 7 — Twitter Card

```python
def check_twitter_card(live_url):
    html = urllib.request.urlopen(live_url, timeout=15).read().decode("utf-8", errors="replace")
    return 'name="twitter:card"' in html
```

Only run if BRAND.md has `twitter_handle` set. Otherwise skip.

## Check 8 — Title + Meta lengths

```python
def check_title_meta_lengths(rank_math_title, rank_math_description):
    return {
        "title_length_50_60": 50 <= len(rank_math_title) <= 60,
        "title_chars": len(rank_math_title),
        "meta_length_150_160": 150 <= len(rank_math_description) <= 160,
        "meta_chars": len(rank_math_description),
    }
```

## Check 9 — Schema JSON-LD valid

Fetch live page, extract `<script type="application/ld+json">` blocks, validate structure:

```python
import json, re

def check_schema_jsonld(live_url):
    html = urllib.request.urlopen(live_url, timeout=15).read().decode("utf-8", errors="replace")
    schemas = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    found_types = set()
    for s in schemas:
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                if "@type" in data:
                    found_types.add(data["@type"])
                if "@graph" in data:
                    for item in data["@graph"]:
                        if "@type" in item:
                            found_types.add(item["@type"])
        except json.JSONDecodeError:
            return False, "Invalid JSON-LD"
    required = {"BlogPosting", "BreadcrumbList"}
    return required.issubset(found_types), {"found": list(found_types), "missing": list(required - found_types)}
```

## Parallel execution

```python
from concurrent.futures import ThreadPoolExecutor

def run_all_checks(post_id, content, hero_url, live_url, image_urls, rank_math_title, rank_math_description, site_url, auth):
    with ThreadPoolExecutor(max_workers=9) as ex:
        futures = {
            "images_200":       ex.submit(check_images, image_urls),
            "internal_links_200": ex.submit(check_internal_links, content, site_url),
            "featured_set":     ex.submit(check_featured_media, post_id, site_url, auth),
            "hero_inline":      ex.submit(check_hero_inline, content, hero_url),
            "faq_present":      ex.submit(check_faq_h2, content),
            "og_meta_complete": ex.submit(check_og_meta, live_url),
            "twitter_card":     ex.submit(check_twitter_card, live_url),
            "title_meta_lens":  ex.submit(check_title_meta_lengths, rank_math_title, rank_math_description),
            "schema_valid":     ex.submit(check_schema_jsonld, live_url),
        }
        return {name: f.result() for name, f in futures.items()}
```

## Output to publish-info.json

Verification block in publish-info.json:

```json
{
  "verification": {
    "images_200": true,
    "internal_links_200": true,
    "featured_set": true,
    "hero_inline": true,
    "faq_present": false,
    "og_meta_complete": true,
    "twitter_card": true,
    "title_chars": 56,
    "title_length_50_60": true,
    "meta_chars": 158,
    "meta_length_150_160": true,
    "schema_valid": true
  }
}
```

## Optional Vietnamese check (--strict-diacritics)

Only when flag set:

```python
def check_diacritics_ratio(content):
    """Strip HTML, count Vietnamese diacritic chars vs total alpha chars."""
    import re
    text = re.sub(r"<[^>]+>", " ", content)
    vn_chars = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃ..."
    vn_count = sum(1 for c in text if c in vn_chars)
    total = sum(1 for c in text if c.isalpha())
    ratio = vn_count / total if total > 0 else 0
    return ratio > 0.13, {"ratio": ratio, "vn_count": vn_count, "total": total}
```

## Don't rollback automatically

Verification failures flag in `publish-info.json`. User decides:
- Fix + re-run `--update [post_id]`
- Accept failures (e.g., FAQ missing if not relevant article type)
- Manual edit in WP Admin
