#!/usr/bin/env python3
import sys
import urllib.parse
import urllib.request

query = sys.argv[1] if len(sys.argv) > 1 else 'autonomous driving arXiv'
headers = {'User-Agent': 'daily-autonomous-driving-papers/1.0 (contact: local-bot)'}

api_url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode({
    'search_query': f'all:{query}',
    'start': 0,
    'max_results': 30,
    'sortBy': 'submittedDate',
    'sortOrder': 'descending',
})

try:
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode('utf-8', errors='replace')
except Exception:
    web_url = 'https://arxiv.org/search/?' + urllib.parse.urlencode({
        'query': query,
        'searchtype': 'all',
        'abstracts': 'show',
        'order': '-announced_date_first',
        'size': 50,
    })
    req = urllib.request.Request(web_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode('utf-8', errors='replace')

print(data)
