#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_preflight.py — Quality gate for /blog-refresh-pipeline (Phase 5.3) + diagnostic flag report (Phase 2).

Generic version of ng-* refresh_preflight.py — language-aware via BRAND.language.

Usage:

  # Phase 5.3 preflight gate (BLOCKING) — checks new HTML against backup
  python3 refresh_preflight.py articles/[slug]/blog.html \\
    --backup articles/[slug]/blog-v1-backup.html \\
    --language [en|vi|es|fr|ja|zh|...] \\
    --min-delta-pct 15

  # Phase 2 diagnostic mode (NON-BLOCKING) — just reports flags on current HTML
  python3 refresh_preflight.py articles/[slug]/blog-v1-backup.html \\
    --diagnose --language [en|vi|...]

Exit codes:
  0 = all checks pass (Phase 5.3 only)
  1 = one or more checks fail (Phase 5.3 only)
  2 = diagnostic mode (always exits 2 to signal "not a gate, just a report")
"""

import io as _io
import sys as _sys
_sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')
_sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import re
import sys
from pathlib import Path


# Universal placeholders that must be resolved before push
PLACEHOLDER_TOKENS = [
    '[PLACEHOLDER]',
    '[ORIGINAL DATA]',
    '[PERSONAL EXPERIENCE]',
    '[UNIQUE INSIGHT]',
    '[TODO]',
    '[FIXME]',
]

# Vietnamese diacritic character set (composed + decomposed forms)
VN_DIACRITICS = (
    'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
    'ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ'
)


def strip_html_and_code(html: str) -> str:
    """Strip pre/code blocks first, then HTML tags. Returns plain text."""
    text = re.sub(r'<pre[\s\S]*?</pre>', '', html)
    text = re.sub(r'<code[\s\S]*?</code>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text


def count_dashes(html: str) -> dict:
    return {
        'em_dashes': html.count('—'),
        'en_dashes': html.count('–'),
    }


def count_md_leak(html: str) -> dict:
    """Markdown leaking through wpautop produces visible `## ` `### ` `> -` literal text."""
    return {
        'md_h2': len(re.findall(r'(?m)^## ', html)),
        'md_h3': len(re.findall(r'(?m)^### ', html)),
        'md_fence': len(re.findall(r'(?m)^```', html)),
        'md_blockquote_leak': len(re.findall(r'(?m)^> -', html)),
    }


def count_placeholders(html: str) -> dict:
    return {f'token_{t}': html.count(t) for t in PLACEHOLDER_TOKENS}


def diacritic_ratio(text: str) -> float:
    """Return % of alpha chars that are Vietnamese diacritics."""
    vn = sum(1 for c in text if c in VN_DIACRITICS)
    total = sum(1 for c in text if c.isalpha())
    return (vn / total * 100) if total else 0.0


def h2_stats(html: str) -> dict:
    h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
    h2_questions = [h for h in h2_matches if '?' in h]
    return {
        'h2_count': len(h2_matches),
        'h2_questions': len(h2_questions),
        'h2_question_ratio_pct': (len(h2_questions) / len(h2_matches) * 100) if h2_matches else 0.0,
    }


def content_delta(new_html: str, old_html: str) -> float:
    if not old_html:
        return 0.0
    return (len(new_html) - len(old_html)) / len(old_html) * 100


def run_checks(new_path: Path, backup_path: Path | None, language: str, min_delta_pct: float, diagnose_only: bool) -> int:
    if not new_path.exists():
        print(f"ERROR: {new_path} does not exist")
        return 1
    new_html = new_path.read_text(encoding='utf-8')
    old_html = backup_path.read_text(encoding='utf-8') if backup_path and backup_path.exists() else None

    text = strip_html_and_code(new_html)

    flags = {}
    flags.update(count_dashes(new_html))
    flags.update(count_md_leak(new_html))
    flags.update(count_placeholders(new_html))
    diac = diacritic_ratio(text)
    h2s = h2_stats(new_html)
    delta = content_delta(new_html, old_html) if old_html else 0.0

    # Print report header
    mode_label = "DIAGNOSE" if diagnose_only else "PREFLIGHT (BLOCKING)"
    print(f"\n=== {mode_label} — {new_path.name} ===")
    print(f"Language: {language}")
    print(f"Char count: {len(old_html):,} → {len(new_html):,} ({delta:+.1f}%)" if old_html else f"Char count: {len(new_html):,}")
    print(f"Diacritic ratio: {diac:.1f}%")
    print(f"H2 count: {h2s['h2_count']} ({h2s['h2_question_ratio_pct']:.0f}% questions)")
    print()

    # Universal checks (apply to all languages)
    checks = {
        'em_dashes == 0': flags['em_dashes'] == 0,
        'en_dashes == 0': flags['en_dashes'] == 0,
        'no_md_h2_leak': flags['md_h2'] == 0,
        'no_md_h3_leak': flags['md_h3'] == 0,
        'no_md_fence_leak': flags['md_fence'] == 0,
        'no_md_blockquote_leak': flags['md_blockquote_leak'] == 0,
    }
    for tok in PLACEHOLDER_TOKENS:
        checks[f'no_{tok}_token'] = flags[f'token_{tok}'] == 0

    # Language-specific checks
    if language == 'vi':
        # Vietnamese-specific rules from quality-rubric.md `## vi`
        checks['vi_diacritic_>=13%'] = diac >= 13.0
        checks['vi_h2_questions_60-80%'] = 60 <= h2s['h2_question_ratio_pct'] <= 80
    # English/other languages: skip diacritic + H2 question ratio (use universal rules only)

    # Content delta (only in non-diagnose mode + when backup provided)
    if not diagnose_only and old_html:
        checks[f'content_delta_>={min_delta_pct}%'] = delta >= min_delta_pct

    # Print checks
    fail = False
    for k, v in checks.items():
        status = '✓' if v else ('✗ FAIL' if not diagnose_only else '⚠ FLAG')
        print(f'{status:8s} {k}')
        if not v and not diagnose_only:
            fail = True

    print()
    if diagnose_only:
        print("(Diagnose mode — flags are informational only, not blocking.)")
        return 2
    if fail:
        print("✗ PREFLIGHT FAILED — fix issues before pushing to WP.")
        return 1
    print("✓ PREFLIGHT PASSED — safe to push.")
    return 0


def main():
    parser = argparse.ArgumentParser(prog='refresh_preflight')
    parser.add_argument('html_path', help='Path to HTML file to check (new for preflight, current for diagnose)')
    parser.add_argument('--backup', help='Path to backup HTML (for content delta check, Phase 5.3 only)')
    parser.add_argument('--language', default='en', help='ISO 639-1 language code (en, vi, es, fr, ja, zh, ...)')
    parser.add_argument('--min-delta-pct', type=float, default=15.0,
                        help='Min content delta %% required for refresh (default 15)')
    parser.add_argument('--diagnose', action='store_true',
                        help='Diagnostic mode (Phase 2) — flags only, never exit 1')
    args = parser.parse_args()

    new_path = Path(args.html_path)
    backup_path = Path(args.backup) if args.backup else None
    sys.exit(run_checks(new_path, backup_path, args.language, args.min_delta_pct, args.diagnose))


if __name__ == '__main__':
    main()
