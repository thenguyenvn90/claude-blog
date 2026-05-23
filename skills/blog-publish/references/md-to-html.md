# Markdown → HTML Conversion Rules

## Canonical converter call

**Use Python `markdown` library, never hand-roll regex.** Hand-rolled converters drop H2/H3 inside HTML blocks.

```python
import markdown
html = markdown.markdown(
    md,
    extensions=["tables", "fenced_code", "attr_list", "md_in_html"],
)
```

Why each extension:
- `tables` — pipe-table syntax → `<table>`
- `fenced_code` — ``` blocks → `<pre><code>`
- `attr_list` — `{#anchor}` heading syntax → `id="anchor"` attribute
- `md_in_html` — markdown inside HTML blocks (e.g. headings inside `<div>`) renders correctly

After `markdown.markdown()`, apply component detection + image wrapping as a post-pass.

**Verification gate**: before pushing, `re.findall(r"^## ", html, re.M)` must be 0. If non-zero, converter dropped an H2 → fix before push.

## Standard Conversions

| Markdown | HTML |
|----------|------|
| `## Heading` | `<h2>Heading</h2>` |
| `### Heading` | `<h3>Heading</h3>` |
| `**bold**` | `<strong>bold</strong>` |
| `*italic*` | `<em>italic</em>` |
| `[text](url)` | `<a href="url">text</a>` |
| `![alt](path)` | `<picture>` wrapped (see below) |
| `` `code` `` | `<code>code</code>` |
| `> quote` | Component detection (see below) |
| `- item` | `<ul><li>item</li></ul>` |
| `1. item` | `<ol><li>item</li></ol>` |

## Component Detection & Injection

Load HTML templates from `BRAND.md` → HTML Component Templates section.

### TL;DR Box
**Detect**: `> **TL;DR**` or `> **Key Takeaways**` or custom label from BRAND.md
**Replace with**: TL;DR box HTML template with brand colors injected

### Stats Banner
**Detect**: 4 stat blocks after TL;DR (pattern: number + label)
**Replace with**: Stats banner HTML template with 4 gradient cards

### Citation Capsule
**Detect**: `> **Source:**` or custom citation label
**Replace with**: Citation capsule HTML template

### Warning Box
**Detect**: `> **Warning:**` or custom warning label
**Replace with**: Warning box HTML template (amber border)

### Info Box
**Detect**: `> **Tip:**` or `> **Info:**`
**Replace with**: Info box HTML template (light bg)

### Code Blocks
**Detect**: Triple backtick code blocks with language tag
**Replace with**: Code block template from BRAND.md (night-owl or custom theme)

### Tables
**Detect**: Markdown table syntax `| col | col |`
**Replace with**: Dark header table template from BRAND.md
- First row → `<thead>` with dark background
- Alternating row colors for `<tbody>`
- Wrapped in `<div style="overflow-x:auto">`

**First-column cells**: Wrap content in `<strong>` tags (semantic, not inline style):
```html
<td style="..."><strong>cell text</strong></td>
<td><strong><a href="/slug/">Link text</a></strong></td>
<td><strong><code>command</code></strong></td>
```

## Image Wrapping

### Hero (first image)
```html
<figure>
  <picture>
    <source srcset="image.avif" type="image/avif">
    <source srcset="image.webp" type="image/webp">
    <img src="image.jpg" alt="[alt text]" width="1200" height="630"
         fetchpriority="high" decoding="async">
  </picture>
  <figcaption>[Caption]</figcaption>
</figure>
```

### All other images
```html
<figure>
  <picture>
    <source srcset="image.avif" type="image/avif">
    <source srcset="image.webp" type="image/webp">
    <img src="image.jpg" alt="[alt text]" width="W" height="H"
         loading="lazy" decoding="async">
  </picture>
  <figcaption>[Caption]</figcaption>
</figure>
```

### Image rules
- `width: 100%` — no max-width
- Hero: `fetchpriority="high"`, NO `loading="lazy"`
- Others: `loading="lazy"`, `decoding="async"`
- Width + height MUST be set (CLS prevention)
- Format fallback: AVIF → WebP → JPEG

## Link Handling

### Internal links
`[anchor](/slug/)` → `<a href="/slug/">anchor</a>`

### External links
`[anchor](https://external.com)` → `<a href="https://external.com" target="_blank" rel="noopener noreferrer">anchor</a>`

**IMPORTANT**: After component injection, scan full HTML for any `<a href="https://` or `<a href="http://` tags missing `target="_blank"` (can appear inside passed-through citation capsules, author blocks). Add attributes before saving.

## Clean-Up

After conversion, remove leftover markers:
```
[INTERNAL-LINK:...]   → remove
[PERSONAL EXPERIENCE] → remove
[ORIGINAL DATA]       → remove
[UNIQUE INSIGHT]      → remove
[IMAGE:...]           → remove (should already be replaced by Step 1 image lock)
<!-- comments -->     → remove non-functional comments
Empty <p></p>         → remove
```

## HTML Head Comment (line 1)

Before any content, write:

```html
<!-- Meta description: [meta_description from brief.md, 150-160 chars] -->
```

Rules:
- Strip any `([0-9]+ chars)` debug annotations from the meta text before writing
- If brief.md has no `meta_description` field → halt and prompt; do NOT write placeholder
- This comment is stripped before WP upload via regex: `re.sub(r'^<!-- Meta description:.*?-->\s*', '', raw, flags=re.DOTALL)`

## Save

Output: `articles/[slug]/draft.html`
