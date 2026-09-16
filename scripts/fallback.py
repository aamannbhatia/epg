#!/usr/bin/env python3
"""Write channel files for fallback sources of channels that got no programmes yet."""
import argparse, collections, glob, json, os, re
from plan import write_channels

ap = argparse.ArgumentParser()
ap.add_argument('--bucket', required=True)
ap.add_argument('--guides', required=True)
ap.add_argument('--order', type=int, required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args()

have = set()
pat = re.compile(rb'<programme[^>]*\schannel="([^"]+)"')
for path in glob.glob(os.path.join(a.guides, '*.xml')):
    with open(path, 'rb') as f:
        for m in pat.finditer(f.read()):
            have.add(m.group(1).decode('utf-8', 'replace').split('@', 1)[0])

with open(os.path.join(a.bucket, 'fallback.json'), encoding='utf-8') as f:
    fallback = json.load(f)

todo = collections.defaultdict(list)
for e in fallback:
    if e['order'] == a.order and e['base'] not in have:
        todo[e['site']].append(e)

os.makedirs(a.out, exist_ok=True)
for site, entries in todo.items():
    write_channels(os.path.join(a.out, '%s.channels.xml' % site), entries)
print('fallback %d: %d channels on %d sites' % (a.order, sum(len(v) for v in todo.values()), len(todo)))
