#!/usr/bin/env python3
r"""
fix_encoding.py - run after EVERY edit to the website files.

Keeps the static site pure ASCII:
  * inside <script> blocks and .js files, non-ASCII chars become \uXXXX escapes
  * elsewhere in .html files, non-ASCII chars become &#xHHHH; entities
  * in .css files, non-ASCII chars become \HHHHHH escapes

Why: the site used to be served by htmlpreview.github.io without charset=utf-8,
which corrupted any char > 127. GitHub Pages serves UTF-8 correctly, but staying
ASCII keeps every page safe no matter how it is served.

Usage:  python3 fix_encoding.py          (fix + verify)
        python3 fix_encoding.py --check  (verify only, exit 1 on problems)
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PATTERNS = ['*.html', 'frontend/edgar_v2.html', 'assets/js/*.js', 'assets/css/*.css',
            '*.xml', 'robots.txt', '*.webmanifest', 'assets/img/*.svg']


def targets():
    seen = []
    for p in PATTERNS:
        for f in sorted(glob.glob(os.path.join(ROOT, p))):
            if f not in seen:
                seen.append(f)
    return seen


def js_escape(text):
    return ''.join('\\u{:04x}'.format(ord(c)) if ord(c) > 127 else c for c in text)


def html_escape(text):
    return ''.join('&#x{:x};'.format(ord(c)) if ord(c) > 127 else c for c in text)


def css_escape(text):
    return ''.join('\\{:06x}'.format(ord(c)) if ord(c) > 127 else c for c in text)


def fix_html(content):
    out, pos = [], 0
    for m in re.finditer(r'(<script\b[^>]*>)(.*?)(</script>)', content, flags=re.DOTALL | re.IGNORECASE):
        out.append(html_escape(content[pos:m.start()]))
        out.append(m.group(1) + js_escape(m.group(2)) + m.group(3))
        pos = m.end()
    out.append(html_escape(content[pos:]))
    return ''.join(out)


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if path.endswith('.js'):
        fixed = js_escape(content)
    elif path.endswith('.css'):
        fixed = css_escape(content)
    elif path.endswith('.html') or path.endswith('.svg'):
        fixed = fix_html(content)
    else:
        fixed = html_escape(content)
    if fixed != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(fixed)
        return True
    return False


def bad_chars(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return [(i, c) for i, c in enumerate(content) if ord(c) > 127]


def main():
    check_only = '--check' in sys.argv
    ok = True
    for path in targets():
        rel = os.path.relpath(path, ROOT)
        if not check_only and fix_file(path):
            print('[fix_encoding] fixed  ' + rel)
        bad = bad_chars(path)
        if bad:
            ok = False
            print('[fix_encoding] WARNING {} non-ASCII chars in {} (first: U+{:04X} at {})'.format(len(bad), rel, ord(bad[0][1]), bad[0][0]))
    print('[fix_encoding] ' + ('Verification passed - all site files are pure ASCII.' if ok else 'Problems found.'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
