#!/usr/bin/env python3
"""
fix_encoding.py — Run this after EVERY edit to frontend/edgar_v2.html

WHY: htmlpreview.github.io serves files without charset=utf-8.
Any non-ASCII character (em-dash, arrows, curly quotes, etc.) inside
a <script> tag gets corrupted into garbage characters in the browser.

FIX: Escape all chars with ord > 127 as \uXXXX unicode literals.
HTML outside of script tags is unaffected.
"""

import re
import sys
import os

TARGET = os.path.join(os.path.dirname(__file__), 'frontend', 'edgar_v2.html')

def escape_script(m):
    text = m.group(1)
    result = []
    for ch in text:
        if ord(ch) > 127:
            result.append('\\u{:04x}'.format(ord(ch)))
        else:
            result.append(ch)
    return '<script>' + ''.join(result) + '</script>'

def fix_encoding(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_size = len(content)
    fixed = re.sub(r'<script>(.*?)</script>', escape_script, content, flags=re.DOTALL)
    fixed_size = len(fixed)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed)

    print(f'[fix_encoding] Done.')
    print(f'  File: {filepath}')
    print(f'  Original: {original_size:,} bytes  ->  Fixed: {fixed_size:,} bytes')

def verify_encoding(filepath):
    """Verify no non-ASCII chars remain inside script tags."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    bad = []
    for m in re.finditer(r'<script>(.*?)</script>', content, re.DOTALL):
        for i, ch in enumerate(m.group(1)):
            if ord(ch) > 127:
                bad.append(f'  pos {i}: {ch!r} (U+{ord(ch):04X})')
    if bad:
        print(f'[fix_encoding] WARNING — {len(bad)} bad chars found:')
        for b in bad[:10]:
            print(b)
    else:
        print('[fix_encoding] Verification passed — no non-ASCII chars in script tags.')
    return len(bad) == 0

if __name__ == '__main__':
    if not os.path.exists(TARGET):
        print(f'ERROR: {TARGET} not found. Run from repo root.')
        sys.exit(1)

    fix_encoding(TARGET)
    ok = verify_encoding(TARGET)
    sys.exit(0 if ok else 1)
