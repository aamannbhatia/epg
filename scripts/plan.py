#!/usr/bin/env python3
"""
Plan the grab: pick a guide source for every Teleora channel and split the
work into buckets that run in parallel.

For each channel the best source is used first and up to two others are kept
as fallbacks, in case the first one returns nothing.
"""
import argparse, collections, glob, json, os, urllib.request, xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

# Sources that are usually fast and complete are tried first.
PREFERRED = ['i.mjh.nz', 'pluto.tv', 'tataplay.com', 'sky.com', 'tvtv.us', 'tvpassport.com']


def load_ids(url):
    if not url:
        return None
    req = urllib.request.Request(url, headers={'User-Agent': 'teleora-epg'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode('utf-8'))
    ids = data.get('ids', data) if isinstance(data, dict) else data
    return set(str(i) for i in ids if i)


def rank(entry):
    site = entry['site']
    pref = PREFERRED.index(site) if site in PREFERRED else len(PREFERRED)
    feed = entry['xmltv_id'].split('@', 1)[1] if '@' in entry['xmltv_id'] else ''
    main_feed = 0 if feed in ('', 'SD', 'HD') else 1
    return (pref, main_feed, site)


def write_channels(path, entries):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<channels>\n')
        for e in entries:
            f.write('  <channel site=%s site_id=%s lang=%s xmltv_id=%s>%s</channel>\n' % (
                quoteattr(e['site']), quoteattr(e['site_id']), quoteattr(e['lang'] or 'en'),
                quoteattr(e['xmltv_id']), escape(e['name'] or e['xmltv_id'])))
        f.write('</channels>\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epg', required=True)
    ap.add_argument('--ids-url', default='')
    ap.add_argument('--buckets', type=int, default=20)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    wanted = load_ids(a.ids_url)
    by_channel = collections.defaultdict(list)
    for path in glob.glob(os.path.join(a.epg, 'sites', '*', '*.channels.xml')):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for c in root.findall('channel'):
            xid = (c.get('xmltv_id') or '').strip()
            if not xid or not c.get('site') or not c.get('site_id'):
                continue
            base = xid.split('@', 1)[0]
            if wanted is not None and base not in wanted:
                continue
            by_channel[base].append({
                'site': c.get('site'), 'site_id': c.get('site_id'), 'lang': c.get('lang') or 'en',
                'xmltv_id': xid, 'name': (c.text or '').strip(),
            })

    # Choose sources: 1 primary + up to 2 fallbacks on other sites
    plan = {}
    for base, entries in by_channel.items():
        entries.sort(key=rank)
        chosen, sites = [], set()
        for e in entries:
            if e['site'] in sites:
                continue
            chosen.append(e); sites.add(e['site'])
            if len(chosen) == 3:
                break
        plan[base] = chosen

    # Buckets are balanced by primary site so one slow site does not hold up the rest
    site_load = collections.Counter(p[0]['site'] for p in plan.values())
    buckets = [[] for _ in range(a.buckets)]
    load = [0] * a.buckets
    site_bucket = {}
    for site, n in site_load.most_common():
        i = load.index(min(load))
        site_bucket[site] = i
        load[i] += n

    os.makedirs(a.out, exist_ok=True)
    per_bucket = collections.defaultdict(lambda: {'primary': collections.defaultdict(list), 'fallback': []})
    for base, chosen in plan.items():
        b = site_bucket[chosen[0]['site']]
        per_bucket[b]['primary'][chosen[0]['site']].append(chosen[0])
        for i, e in enumerate(chosen[1:], start=1):
            per_bucket[b]['fallback'].append(dict(e, base=base, order=i))

    used = []
    for b, work in sorted(per_bucket.items()):
        d = os.path.join(a.out, 'bucket-%d' % b)
        os.makedirs(d, exist_ok=True)
        for site, entries in work['primary'].items():
            write_channels(os.path.join(d, 'primary--%s.channels.xml' % site), entries)
        with open(os.path.join(d, 'fallback.json'), 'w', encoding='utf-8') as f:
            json.dump(work['fallback'], f)
        used.append(b)

    summary = {'channels': len(plan), 'buckets': len(used),
               'sites': len(site_load), 'with_fallback': sum(1 for p in plan.values() if len(p) > 1)}
    with open(os.path.join(a.out, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary))

    gh = os.environ.get('GITHUB_OUTPUT')
    if gh:
        with open(gh, 'a') as f:
            f.write('buckets=%s\n' % json.dumps(used))


if __name__ == '__main__':
    main()
