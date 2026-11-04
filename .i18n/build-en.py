#!/usr/bin/env python3
"""Builds the English site under /en/ from the Thai pages, using .i18n/en.json (Thai text → English).

    python3 .i18n/build-en.py            # all pages
    python3 .i18n/extract.py page.html   # Thai text still missing an English version

Also adds the TH / EN switch and hreflang links to the Thai pages (safe to run again).
After editing a Thai page: run extract.py, add the English to a file in .i18n/parts/, run this script.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, '.i18n')
SITE = 'https://idevapp.me'
# Each file in parts/ lists the pages it was written for ("_pages"); its wording wins on those pages,
# other pages fall back to the first file that has the text.
EN = {}; SCOPED = {}
for f in sorted(glob.glob(os.path.join(HERE, 'parts', '*.json'))):
    d = json.load(open(f, encoding='utf8'))
    for page in d.pop('_pages', []): SCOPED.setdefault(page, {}).update(d)
    for k, v in d.items(): EN.setdefault(k, v)
json.dump(EN, open(os.path.join(HERE, 'en.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0, sort_keys=True)
TH = re.compile(r'[฀-๿]')
ASSET = re.compile(r'\.(css|js|png|jpe?g|webp|gif|svg|ico|zip|json|pdf|woff2?|mp4|webm)(\?.*)?$', re.I)
missing = {}

SWITCH_CSS = ('<style id="lang-sw-css">.lang-sw{display:inline-flex;border:1px solid #d6dce6;border-radius:999px;overflow:hidden;font:700 13px/1 inherit;'
              'margin:0 10px;flex:none}.lang-sw a{padding:7px 11px;color:#4b5563;text-decoration:none}.lang-sw a[aria-current]{background:#1d3f8b;color:#fff}'
              '.nav ul a{white-space:nowrap}.nav .brand{flex:none}html[lang=en] .nav ul{gap:20px}'
              '@media (max-width:1240px){.nav ul{gap:14px!important}.nav ul a{font-size:14px!important}}'
              '@media (max-width:640px){.lang-sw{margin:0 6px}.lang-sw a{padding:6px 9px}}</style>')

def page_url(rel):  # 'plugins/index.html' -> '/plugins/'
    p = '/' + rel
    return p[:-len('index.html')] if p.endswith('index.html') else p

def switch(th_url, en_url, lang):
    return ('<nav class="lang-sw" aria-label="Language / ภาษา">'
            '<a href="%s" hreflang="th" lang="th"%s>TH</a><a href="%s" hreflang="en" lang="en"%s>EN</a></nav>'
            % (th_url, ' aria-current="true"' if lang == 'th' else '', en_url, ' aria-current="true"' if lang == 'en' else ''))

def add_switch(s, th_url, en_url, lang):
    s = re.sub(r'\s*<style id="lang-sw-css">.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<nav class="lang-sw".*?</nav>', '', s, flags=re.S)
    s = re.sub(r'\s*<link rel="alternate" hreflang="[^"]+" href="[^"]+">', '', s)
    alt = ('\n<link rel="alternate" hreflang="th" href="%s%s">\n<link rel="alternate" hreflang="en" href="%s%s">\n<link rel="alternate" hreflang="x-default" href="%s%s">'
           % (SITE, th_url, SITE, en_url, SITE, th_url))
    s = s.replace('</head>', alt + '\n' + SWITCH_CSS + '\n</head>', 1)
    # the switch goes right before the header's main button (or at the end of the nav)
    sw = switch(th_url, en_url, lang)
    m = re.search(r'<header\b.*?</header>', s, flags=re.S)
    if m:
        hdr = m.group(0)
        b = re.search(r'<a class="btn[^"]*"[^>]*>(?:(?!</a>).)*</a>\s*(?=(?:<button[^>]*>.*?</button>\s*)?</div>\s*</header>)', hdr, flags=re.S)
        if b: hdr = hdr[:b.start()] + sw + hdr[b.start():]
        else: hdr = re.sub(r'(</div>\s*</header>)$', sw + r'\1', hdr, flags=re.S)
        s = s[:m.start()] + hdr + s[m.end():]
    return s

def tr(text, page):
    key = text.strip()
    if not TH.search(key): return text
    val = SCOPED.get(page, {}).get(key, EN.get(key))
    if val is not None:
        lead = text[:len(text) - len(text.lstrip())]; trail = text[len(text.rstrip()):]
        return lead + val + trail
    missing.setdefault(page, []).append(key)
    return text

def esc_attr(v): return v.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')

def translate(s, page, rel):
    base = os.path.dirname('/' + rel)
    out = []
    pos = 0
    for m in re.finditer(r'<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->|<[^>]+>', s, flags=re.S):
        out.append(tr_text(s[pos:m.start()], page))
        tag = m.group(0)
        if tag.startswith('<script'):
            tag = re.sub(r"(['\"`])((?:(?!\1)[^\\\n]|\\.)*[฀-๿](?:(?!\1)[^\\\n]|\\.)*)\1",
                         lambda q: q.group(1) + tr(q.group(2), page).replace(q.group(1), '\\' + q.group(1)) + q.group(1), tag)
        elif not tag.startswith(('<style', '<!--')):
            tag = re.sub(r'\b(content|alt|title|aria-label|placeholder|data-[a-z-]+)="([^"]*)"',
                         lambda q: '%s="%s"' % (q.group(1), esc_attr(tr(q.group(2).replace('&quot;', '"').replace('&amp;', '&'), page))) if TH.search(q.group(2)) else q.group(0), tag)
            tag = re.sub(r'\b(href|src|srcset|action)="([^"]*)"', lambda q: '%s="%s"' % (q.group(1), relink(q.group(1), q.group(2), base)), tag)
        out.append(tag)
        pos = m.end()
    out.append(tr_text(s[pos:], page))
    return ''.join(out)

def tr_text(chunk, page):
    return tr(chunk, page) if TH.search(chunk) else chunk

def relink(attr, v, base):
    if attr == 'srcset':
        return ', '.join(relink('src', p.strip().split(' ')[0], base) + (' ' + ' '.join(p.strip().split(' ')[1:]) if ' ' in p.strip() else '') for p in v.split(','))
    if re.match(r'^(https?:|mailto:|tel:|data:|javascript:|#|//)', v) or v == '':
        if v.startswith(SITE + '/') and not ASSET.search(v.split('#')[0]) and not v.startswith(SITE + '/en/') and not v.startswith(SITE + '/updates/'):
            return SITE + '/en' + v[len(SITE):]
        return v
    if v.startswith('/'):
        path = v.split('#')[0].split('?')[0]
        if ASSET.search(path) or path.startswith(('/updates/', '/img/', '/en/')): return v
        return '/en' + v
    # relative: assets point back to the original files, pages stay relative (they exist under /en/ too)
    if ASSET.search(v.split('#')[0].split('?')[0]):
        return os.path.normpath(os.path.join(base, v)).replace('\\', '/')
    return v

pages = sorted(p for p in glob.glob('**/*.html', root_dir=ROOT, recursive=True) if not p.startswith(('en/', '.')))
for rel in pages:
    src = os.path.join(ROOT, rel)
    s = open(src, encoding='utf8').read()
    th_url = page_url(rel); en_url = '/en' + th_url
    open(src, 'w', encoding='utf8').write(add_switch(s, th_url, en_url, 'th'))
    e = translate(s, rel, rel)
    e = re.sub(r'<html lang="th"', '<html lang="en"', e, count=1)
    e = e.replace('<link rel="canonical" href="%s%s">' % (SITE, th_url), '<link rel="canonical" href="%s%s">' % (SITE, en_url))
    e = re.sub(r'<meta property="og:locale" content="[^"]*">', '<meta property="og:locale" content="en_US">', e)
    e = add_switch(e, th_url, en_url, 'en')
    rawf = os.path.join(HERE, 'raw', os.path.dirname(rel).replace('/', '_') + '.json') if os.path.dirname(rel) else ''
    if rawf and os.path.exists(rawf):  # page-specific code changes (scripts built from template strings)
        for a, b in json.load(open(rawf, encoding='utf8')):
            if a.startswith('@@FUNC '):
                name = a[7:]
                m2 = re.search(r'function %s\(.*?\n}\n' % name, e, flags=re.S)
                if not m2: sys.exit('function not found: ' + name)
                e = e[:m2.start()] + b + '\n' + e[m2.end():]
            elif a in e: e = e.replace(a, b)
            else: print('raw replacement not found in', rel, ':', a[:60])
    rest = [k for k in missing.get(rel, []) if k in e]
    if rel in missing: missing[rel] = [k for k in missing[rel] if TH.search(k) and k in e]
    dst = os.path.join(ROOT, 'en', rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf8').write(e)

seen = set(); ordered = {}
for page, keys in missing.items():
    ordered[page] = [k for k in keys if not (k in seen or seen.add(k))]
json.dump(ordered, open(os.path.join(HERE, 'missing.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
for page, keys in missing.items():
    print('%s: %d Thai strings without English' % (page, len(set(keys))))
print('built %d pages' % len(pages))
