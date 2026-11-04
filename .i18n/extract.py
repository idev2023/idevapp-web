#!/usr/bin/env python3
"""Thai text that still has no English, in page order (run build-en.py first). Usage: extract.py [page.html ...]"""
import json, os, sys
m = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'missing.json'), encoding='utf8'))
for page, keys in m.items():
    if len(sys.argv) > 1 and page not in sys.argv[1:]: continue
    for k in keys: print(json.dumps(k, ensure_ascii=False))
