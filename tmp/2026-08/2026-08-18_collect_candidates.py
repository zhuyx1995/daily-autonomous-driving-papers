#!/usr/bin/env python3
import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path('/Users/zhuyuxiao/.openclaw/workspace')
TODAY = date(2026, 8, 18)
WINDOW_START = TODAY - timedelta(days=6)
OUT_DIR = ROOT / 'tmp' / '2026-08' / '2026-08-18'
OUT_DIR.mkdir(parents=True, exist_ok=True)
UA = 'daily-autonomous-driving-papers/2.0 (local automation)'

FEEDS = {
    'cs.RO': 'https://rss.arxiv.org/rss/cs.RO',
    'cs.CV': 'https://rss.arxiv.org/rss/cs.CV',
    'eess.SY': 'https://rss.arxiv.org/rss/eess.SY',
    'cs.AI': 'https://rss.arxiv.org/rss/cs.AI',
}
QUERIES = [
    'autonomous driving',
    'self-driving',
    'end-to-end autonomous driving',
    'autonomous vehicle perception',
    'autonomous vehicle planning',
    'autonomous vehicle control',
    'driving scene understanding autonomous driving',
    'traffic rule understanding autonomous driving',
    'cooperative perception autonomous driving',
    'autonomous driving world model',
]


def norm_title(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def clean_text(s: str) -> str:
    s = html.unescape(s or '')
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    m = re.search(r'Abstract:\s*(.*)', s, re.I)
    return m.group(1).strip() if m else s


def request(url: str, label: str, accept: str = 'application/atom+xml,text/html;q=0.9,*/*;q=0.8') -> str:
    last_err = None
    for attempt in range(1, 5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            last_err = e
            if attempt == 4:
                raise
            wait_s = 3.5 * attempt
            print(f'[WARN] {label} attempt {attempt} failed: {e}; retrying in {wait_s:.1f}s')
            time.sleep(wait_s)
    raise RuntimeError(f'{label} failed: {last_err}')


def relevance_score(title: str, summary: str, cats: str = '') -> int:
    t = (title + ' ' + summary).lower()
    score = 0
    strong = [
        'autonomous driving', 'automated driving', 'autonomous vehicle', 'self-driving', 'self driving',
        'end-to-end driving', 'end-to-end autonomous driving', 'urban driving',
        'driving scene', 'ego vehicle', 'traffic rule', 'cooperative perception',
        'occupancy forecasting', 'world model', 'trajectory planning', 'motion planning',
        'parking trajectory', 'bev reasoning', 'driving policy', 'traffic scene prediction',
        'localization', 'mapping', 'waypoint', 'driving'
    ]
    medium = [
        'planning', 'control', 'trajectory', 'occupancy', 'perception', 'v2x', 'bev',
        'vehicle', 'road', 'lane', 'navigation', 'scene understanding', 'risk', 'sensor',
        'lidar', 'radar', 'forecasting', 'prediction'
    ]
    negative = [
        'uav', 'drone', 'aerial', 'aircraft', 'ship', 'vessel', 'underwater', 'medical',
        'satellite', 'railway', 'driver monitoring', 'passenger', 'cabin', 'sport',
        'platoon', 'platooning', 'quadruped', 'humanoid', 'manipulation', 'grasp',
        'robot arm', 'corridor', 'soccer', 'off-road jumping', 'planetary', 'surgical'
    ]
    for kw in strong:
        if kw in t:
            score += 10
    for kw in medium:
        if kw in t:
            score += 2
    for kw in negative:
        if kw in t:
            score -= 30
    tl = title.lower()
    if 'autonomous driving' in tl or 'automated driving' in tl:
        score += 10
    if 'self-driving' in tl or 'self driving' in tl:
        score += 8
    if any(c in cats for c in ['cs.RO', 'cs.CV', 'cs.AI', 'eess.SY']):
        score += 1
    return score


def fetch_submitted_v1(aid: str):
    html_text = request(f'https://arxiv.org/abs/{aid}', f'abs:{aid}', accept='text/html,application/xhtml+xml')
    (OUT_DIR / 'abs').mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'abs' / f'{aid}.html').write_text(html_text, encoding='utf-8')
    m_sub = re.search(r'Submitted on\s+([0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{4})', html_text, re.I)
    submitted_on = m_sub.group(1) if m_sub else None
    m = re.search(r'\[v1\]\s*(?:<a [^>]*>)?([^<\n]+?)(?:</a>)?\s*\(([^\)]*)\)', html_text, re.I)
    if not m:
        m = re.search(r'Submission history.*?\[v1\]\s*([^<\n]+)', html_text, re.I | re.S)
    raw = None
    dt = None
    if m:
        raw = re.sub(r'\s+', ' ', m.group(1).strip())
        for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%d %b %Y %H:%M:%S %Z']:
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                break
            except Exception:
                pass
        if dt is None:
            raw2 = re.sub(r'^[A-Za-z]{3},\s*', '', raw)
            for candidate in [raw2, raw2.split(' GMT')[0]]:
                try:
                    dt = datetime.strptime(candidate, '%d %b %Y %H:%M:%S').replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    pass
    if submitted_on and dt is None:
        try:
            dt = datetime.strptime(submitted_on, '%d %b %Y').replace(tzinfo=timezone.utc)
        except Exception:
            dt = None
    return dt, raw, submitted_on


history_ids = set()
history_titles = set()
for md in sorted((ROOT / 'reports').rglob('*.md')):
    txt = md.read_text(encoding='utf-8', errors='replace')
    history_ids.update(re.findall(r'<!--\s*PAPER:\s*arxiv-([0-9]{4}\.[0-9]{4,5})\s+START\s*-->', txt, re.I))
    history_titles.update(norm_title(title) for title in re.findall(r'^##\s+\d+\.\s+(.+)$', txt, re.M))

raw_candidates = {}
for cat, url in FEEDS.items():
    xml_text = request(url, f'rss:{cat}', accept='application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8')
    (OUT_DIR / f"rss_{cat.replace('.', '_')}.xml").write_text(xml_text, encoding='utf-8')
    root = ET.fromstring(xml_text)
    channel = root.find('channel')
    if channel is None:
        continue
    for item in channel.findall('item'):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        aid = link.rsplit('/', 1)[-1]
        summary = clean_text(item.findtext('description') or '')
        if not aid or not title:
            continue
        score = relevance_score(title, summary, cat)
        row = {'aid': aid, 'title': title, 'summary': summary, 'cats': cat, 'score': score, 'source': f'rss:{cat}', 'nt': norm_title(title)}
        prev = raw_candidates.get(aid)
        if prev is None or row['score'] > prev['score']:
            raw_candidates[aid] = row


def parse_search_html(text: str):
    rows = []
    for block in re.findall(r'<li class="arxiv-result".*?</li>\s*</ol>|<li class="arxiv-result".*?</li>', text, re.S):
        m_id = re.search(r'href="https://arxiv.org/abs/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?"', block)
        m_title = re.search(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>', block, re.S)
        m_abs = re.search(r'<span class="abstract-full has-text-grey-dark mathjax".*?>\s*(.*?)\s*</span>', block, re.S)
        cats = ' '.join(re.findall(r'data-tooltip="([^"]+)"', block))
        if not m_id or not m_title:
            continue
        aid = m_id.group(1)
        title = clean_text(m_title.group(1))
        summary = clean_text(m_abs.group(1) if m_abs else '')
        rows.append((aid, title, summary, cats))
    return rows

for i, query in enumerate(QUERIES, start=1):
    params = urllib.parse.urlencode({'query': query, 'searchtype': 'all', 'abstracts': 'show', 'order': '-announced_date_first', 'size': 50})
    html_text = request(f'https://arxiv.org/search/?{params}', f'html:{i}', accept='text/html,application/xhtml+xml')
    (OUT_DIR / f'search_q{i}.html').write_text(html_text, encoding='utf-8')
    for aid, title, summary, cats in parse_search_html(html_text):
        score = relevance_score(title, summary, cats)
        row = {'aid': aid, 'title': title, 'summary': summary, 'cats': cats, 'score': score, 'source': f'html:q{i}', 'nt': norm_title(title)}
        prev = raw_candidates.get(aid)
        if prev is None or row['score'] > prev['score']:
            raw_candidates[aid] = row
    time.sleep(3.6)

rows = []
for aid, row in sorted(raw_candidates.items()):
    if row['score'] < 12:
        continue
    if aid in history_ids or row['nt'] in history_titles:
        continue
    dt, raw_v1, submitted_on = fetch_submitted_v1(aid)
    time.sleep(1.3)
    if not dt:
        continue
    sub_date = dt.date()
    if not (WINDOW_START <= sub_date <= TODAY):
        continue
    rows.append((aid, row['title'], sub_date.isoformat(), dt.isoformat().replace('+00:00', 'Z'), raw_v1 or '', submitted_on or '', str(row['score']), row['cats'], row['source'], row['summary'], row['nt']))

rows.sort(key=lambda r: (r[2], r[3], int(r[6]), r[0]), reverse=True)
out = OUT_DIR / 'recent_candidates.tsv'
with out.open('w', encoding='utf-8') as f:
    f.write('aid\ttitle\tdate\tv1_utc\tv1_raw\tsubmitted_on\tscore\tcats\tsource\tsummary\tnorm_title\n')
    for row in rows:
        f.write('\t'.join(row) + '\n')

print(f'window={WINDOW_START}..{TODAY}')
print(f'history_ids={len(history_ids)} history_titles={len(history_titles)} raw_candidates={len(raw_candidates)} filtered_recent_new={len(rows)}')
for row in rows[:20]:
    print(f'{row[2]}\t{row[6]}\t{row[0]}\t{row[1]}')
print(f'wrote {out}')
