# Integration Guide: workflow_tracker.py in Every ng-* Skill

This document is the **single source of truth** for how each ng-* skill must call `workflow_tracker.py` during its execution. Skills should reference this file rather than duplicating the logic.

## Convention

| Skill | Phase # |
|-------|---------|
| ng-setup | 0 |
| ng-research | 1 |
| ng-cluster | 2 |
| ng-brief | 3 |
| ng-write | 4 |
| ng-audit | 5 |
| ng-image | 6 |
| ng-publish | 7 |
| /repurpose | 8 |

## Universal Pattern (all skills)

```bash
# At skill ENTRY (first Bash step):
python3 ~/.claude/scripts/workflow_tracker.py start \
  --slug [slug] --phase N --skill ng-[name]

# After each API batch (as you discover calls):
python3 ~/.claude/scripts/workflow_tracker.py log-api \
  --slug [slug] --phase N --tool [tool] --endpoint [endpoint] --count [N]

# Near end of skill, before final output (estimate LLM):
python3 ~/.claude/scripts/workflow_tracker.py log-llm \
  --slug [slug] --phase N --model claude-sonnet-4-6 \
  --input-chars [sum_of_input_text_sent] --output-chars [sum_of_generated_output]

# At DELIVERY step (last thing before showing success):
python3 ~/.claude/scripts/workflow_tracker.py end \
  --slug [slug] --phase N --status complete \
  --outputs "articles/[slug]/file1.md,articles/[slug]/file2.json" \
  --metrics '{"key":"value"}'
```

**LLM char estimation:** Sum the character counts of:
- Input: all prompts + tool results + reference files read
- Output: the final markdown/JSON/HTML written

Rough heuristic: `tokens ≈ chars / 4` (English/Vietnamese mix). Better than nothing.

---

## Per-Skill Recipes

### ng-setup (phase 0)

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [site-slug] --phase 0 --skill ng-setup
# ... skill does work ...
# Log API calls if WebFetch/Firecrawl used:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [site-slug] --phase 0 --tool firecrawl --endpoint scrape --count 3
python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [site-slug] --phase 0 --model claude-sonnet-4-6 --input-chars 5000 --output-chars 3000
python3 ~/.claude/scripts/workflow_tracker.py end --slug [site-slug] --phase 0 --status complete --outputs "directives/[site]/overrides.md,directives/[site]/quality-rules.md"
```

### ng-research (phase 1) — MOST API-HEAVY

Track every DataForSEO call:
```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 1 --skill ng-research

# Log SERP calls:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 1 --tool dataforseo --endpoint serp_organic_live_advanced --count 5

# Log labs calls:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 1 --tool dataforseo --endpoint dataforseo_labs_google_keyword_overview --count 12
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 1 --tool dataforseo --endpoint dataforseo_labs_google_related_keywords --count 10

python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 1 --model claude-sonnet-4-6 --input-chars 30000 --output-chars 10000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 1 --status complete \
  --outputs "articles/[slug]/keyword-report.md,articles/[slug]/cluster-plan.json" \
  --metrics '{"keywords_found":N,"clusters_identified":N,"cannibalization_alerts":N,"primary_volume":N,"primary_cpc_usd":N}'
```

**IMPORTANT for ROI projection:** Include `primary_volume` (monthly search volume) and `primary_cpc_usd` (avg CPC) in the metrics JSON. Without these, ng-report cannot compute article ROI.

### ng-cluster (phase 2) — cannibalization SERP checks

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [pillar-slug] --phase 2 --skill ng-cluster

# Log cannibalization SERP verification calls:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [pillar-slug] --phase 2 --tool dataforseo --endpoint serp_organic_live_advanced --count 5

python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [pillar-slug] --phase 2 --model claude-sonnet-4-6 --input-chars 15000 --output-chars 6000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [pillar-slug] --phase 2 --status complete \
  --outputs "articles/[pillar-slug]/cluster-plan.json,articles/[pillar-slug]/cluster-map.html" \
  --metrics '{"total_articles":N,"merges_applied":N,"total_interlinks":N}'
```

### ng-brief (phase 3) — competitor WebFetch

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 3 --skill ng-brief

# Track competitor crawls if Firecrawl used:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 3 --tool firecrawl --endpoint scrape --count 5
# (If using WebFetch instead of Firecrawl: no API cost, skip this line)

python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 3 --model claude-sonnet-4-6 --input-chars 25000 --output-chars 8000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 3 --status complete \
  --outputs "articles/[slug]/brief.md" \
  --metrics '{"angle_score":N,"format":"format_id","competitors_analyzed":N}'
```

### ng-write (phase 4) — LARGEST LLM usage

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 4 --skill ng-write

# ng-write is writing-heavy, output_chars will be large (18-25KB typical):
python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 4 --model claude-sonnet-4-6 \
  --input-chars 40000 --output-chars 25000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 4 --status complete \
  --outputs "articles/[slug]/blog.md,articles/[slug]/write-log.md" \
  --metrics '{"word_count":N,"h2_sections":N,"mode":"default|tutorial|comparison|listicle"}'
```

### ng-audit (phase 5) — parallel agents = Opus cost

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 5 --skill ng-audit

# Audit uses parallel Agent calls. If using Opus for thoroughness:
python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 5 --model claude-opus-4-6 \
  --input-chars 60000 --output-chars 8000

# If factcheck uses WebFetch:
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 5 --tool firecrawl --endpoint scrape --count 3

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 5 --status complete \
  --outputs "articles/[slug]/audit-report.md" \
  --metrics '{"audit_score":N,"ai_detection_risk":"N%","word_count":N,"images":N,"internal_links":N,"composite_score":N}'
```

**CRITICAL:** The `metrics` field in ng-audit feeds directly into ng-report's Quality section. Must include `audit_score` or `composite_score`.

### ng-image (phase 6) — Gemini image generation

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 6 --skill ng-image

# Log each image generation (default 2K resolution):
python3 ~/.claude/scripts/workflow_tracker.py log-api --slug [slug] --phase 6 --tool gemini_image --endpoint "gemini-3.1-flash-image-preview_2K" --count 1
# Repeat for each image generated

python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 6 --model claude-sonnet-4-6 --input-chars 10000 --output-chars 3000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 6 --status complete \
  --outputs "articles/[slug]/images/hero.webp,articles/[slug]/image-manifest.json" \
  --metrics '{"images_generated":N,"hero_resolution":"2K"}'
```

### ng-publish (phase 7) — WP REST (free) + ng-report call

```bash
python3 ~/.claude/scripts/workflow_tracker.py start --slug [slug] --phase 7 --skill ng-publish

# WP REST is free — no log-api needed

python3 ~/.claude/scripts/workflow_tracker.py log-llm --slug [slug] --phase 7 --model claude-sonnet-4-6 --input-chars 20000 --output-chars 4000

python3 ~/.claude/scripts/workflow_tracker.py end --slug [slug] --phase 7 --status complete \
  --outputs "articles/[slug]/blog.html,articles/[slug]/publish-info.json" \
  --metrics '{"post_id":N,"scheduled_date":"ISO","status":"future"}'

# GENERATE FINAL REPORT (last step):
python3 ~/.claude/scripts/workflow_tracker.py totals --slug [slug]
# Then invoke /ng-report articles/[slug]/ to produce workflow-report.md
```

---

## Displaying the Phase Report (in skill delivery)

After `end` command, skills can fetch their phase entry and display it:

```bash
python3 -c "
import json, sys
from pathlib import Path
p = Path('articles/[slug]/workflow-log.json')
data = json.loads(p.read_text())
ph = [x for x in data['phases'] if x['phase'] == N][0]
print(f\"\"\"
📊 Phase {ph['phase']} {ph['skill']} Complete
├─ Duration: {ph['duration_sec']//60}m {ph['duration_sec']%60}s
├─ Outputs: {len(ph['outputs'])} files
├─ Cost: \\${ph['costs']['total_usd']:.4f}
└─ Errors: {len(ph['errors'])}
\"\"\")
"
```

Or simpler — just print what you tracked, since the skill has the data in memory already.

---

## Common Gotchas

| Gotcha | Fix |
|--------|-----|
| Skill runs without `start` first | Log commands fail silently. Always start first. |
| Wrong phase number | Overwrites previous phase data. Use convention table above. |
| Forgot to call `end` | workflow_status stays "in_progress" forever. ng-report handles this (reports as incomplete). |
| API endpoint not in pricing table | Uses `_default` fallback — cost accurate enough for reporting |
| LLM chars grossly wrong | Token estimate off ±20%, but consistent — still useful for trends |
| Slug mismatch between phases | Each phase writes to its own file. Use same slug throughout. |

## When NOT to Track

Small skills that don't have a meaningful cost (e.g., /ng-setup if purely interactive, no API calls) can skip if token cost is negligible. But consistency > minor cost-savings — just always track.
