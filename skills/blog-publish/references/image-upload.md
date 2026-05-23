# Image Upload Pipeline

Upload local images to WordPress via WP REST API. Handles PNG→WebP conversion, upload, URL patching, featured image setting.

## Step 1: Convert PNG to WebP (if not already)

```python
from PIL import Image
import os

img_dir = 'articles/[slug]/images'
for f in os.listdir(img_dir):
    if f.endswith('.png'):
        img = Image.open(os.path.join(img_dir, f))
        # Resize if width > 2400px
        if img.width > 2400:
            ratio = 2400 / img.width
            new_height = int(img.height * ratio)
            img = img.resize((2400, new_height), Image.LANCZOS)
        out = os.path.join(img_dir, f.replace('.png', '.webp'))
        img.save(out, 'WEBP', quality=85, method=6)
```

Naming convention:
- Hero: `hero-[slug].webp` (one per article)
- Section: `section-[descriptor].webp` (no slug prefix to allow reuse)

## Step 2: Upload all images via WP REST API

```python
import json, urllib.request, os

auth = 'Basic [BASE64_AUTH]'  # from .mcp.json wp-mcp-ultimate entry
site = 'https://[site-domain]'
img_dir = 'articles/[slug]/images'

# Read alt texts from image-manifest.json
manifest = json.load(open(f'articles/[slug]/image-manifest.json'))
alt_map = {img['filename']: img['alt'] for img in manifest['images']}

uploaded = {}
for f in sorted(os.listdir(img_dir)):
    if not f.endswith('.webp'):
        continue
    with open(os.path.join(img_dir, f), 'rb') as fh:
        img_data = fh.read()
    req = urllib.request.Request(
        f'{site}/wp-json/wp/v2/media',
        data=img_data,
        headers={
            'Authorization': auth,
            'Content-Type': 'image/webp',
            'Content-Disposition': f'attachment; filename={f}',
        },
        method='POST',
    )
    result = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))

    # Set alt text
    alt = alt_map.get(f, alt_map.get(f.replace('.webp', '.png'), ''))
    if alt:
        urllib.request.urlopen(urllib.request.Request(
            f'{site}/wp-json/wp/v2/media/{result["id"]}',
            data=json.dumps({'alt_text': alt}).encode('utf-8'),
            headers={'Authorization': auth, 'Content-Type': 'application/json; charset=utf-8'},
            method='POST',
        ))

    uploaded[f] = {'id': result['id'], 'url': result['source_url']}

# Write back to manifest for re-run idempotency
for entry in manifest['images']:
    if entry['filename'] in uploaded:
        entry['wp_media_id'] = uploaded[entry['filename']]['id']
        entry['wp_source_url'] = uploaded[entry['filename']]['url']

with open(f'articles/[slug]/image-manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
```

## Step 3: Handle WP -1 Suffix Issue

If WP appends `-1`, `-2` suffix to filename (duplicate detection), the upload succeeded but `source_url` has the suffix. Two options:

**Option A**: Accept the suffix (just use whatever URL WP returned).

**Option B**: Delete old file + re-upload with clean filename:
```python
# Detect suffix
if '-1.webp' in result['source_url'] or '-2.webp' in result['source_url']:
    # Find the original (clean filename) WP media ID
    search = urllib.request.urlopen(urllib.request.Request(
        f'{site}/wp-json/wp/v2/media?search={f.replace(".webp", "")}&per_page=10',
        headers={'Authorization': auth}
    )).read()
    candidates = json.loads(search)
    for c in candidates:
        if c['source_url'].endswith(f'/{f}'):  # exact match (no suffix)
            # Delete the suffix version we just uploaded
            urllib.request.urlopen(urllib.request.Request(
                f'{site}/wp-json/wp/v2/media/{result["id"]}?force=true',
                headers={'Authorization': auth},
                method='DELETE',
            ))
            # Use the clean original
            result = c
            break
```

Recommend Option A for simplicity. Use Option B only if old version is stale.

## Step 4: Patch image URLs in post content

After Step 2 uploaded images, replace local paths in HTML body with WP media URLs:

```python
# Via WP MCP Ultimate (if available):
# mcp: wp-mcp-ultimate -> ability: "content/patch-post"
# params: { "id": POST_ID, "find": "images/[local-filename]", "replace": "[wp-media-url]" }

# Via REST API (fallback):
def patch_image_urls(html_content, uploaded):
    for filename, info in uploaded.items():
        local_path = f'images/{filename}'
        # Also patch PNG references that map to WebP uploads
        if filename.endswith('.webp'):
            png_path = f'images/{filename.replace(".webp", ".png")}'
            html_content = html_content.replace(png_path, info['url'])
        html_content = html_content.replace(local_path, info['url'])
    return html_content

# Then POST updated content:
urllib.request.urlopen(urllib.request.Request(
    f'{site}/wp-json/wp/v2/posts/{post_id}',
    data=json.dumps({'content': patched_html}).encode('utf-8'),
    headers={'Authorization': auth, 'Content-Type': 'application/json; charset=utf-8'},
    method='POST',
))
```

## Step 5: Set Featured Image

```python
urllib.request.urlopen(urllib.request.Request(
    f'{site}/wp-json/wp/v2/posts/{post_id}',
    data=json.dumps({'featured_media': hero_media_id}).encode('utf-8'),
    headers={'Authorization': auth, 'Content-Type': 'application/json; charset=utf-8'},
    method='POST',
))
```

`hero_media_id` comes from `uploaded` dict (entry for `hero-*.webp`).

## Auth

Extract Basic auth from `.mcp.json` wp-mcp-ultimate args:

```json
{
  "mcpServers": {
    "wp-mcp-ultimate": {
      "args": ["...", "--auth", "Basic dXNlcjphcHBfcGFzc3dvcmQ="]
    }
  }
}
```

Or compose manually:
```python
import base64
auth = "Basic " + base64.b64encode(f"{wp_user}:{wp_app_password}".encode()).decode()
```

## Failure modes

| Failure | Fix |
|---------|-----|
| 401/403 | Regenerate WP Application Password |
| 413 (Payload too large) | Reduce image size; resize to 1800px instead of 2400px |
| 500 | Check WP debug.log; possible plugin conflict |
| Network timeout | Retry once with `urllib.request.urlopen(req, timeout=60)` |

## Don't forget

- Convert PNG → WebP BEFORE upload (size reduction 89-95%)
- Write back `wp_media_id` + `wp_source_url` to manifest for re-run idempotency
- Set alt text from manifest (don't leave empty alt for accessibility)
- Use `urllib.request` (not `requests`) — UTF-8 safer for non-ASCII filenames on Windows
