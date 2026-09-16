#!/usr/bin/env python3
"""
Turn the downloaded XMLTV guides into the package the Teleora website reads.

dist/manifest.json      version, time, counts
dist/teleora-epg.zip    ch/<2 hex>/<channel id>.json  -> [[start, stop, title, category, description], ...]
"""
import argparse, glob, gzip, hashlib, json, os, re, time, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

KEEP_BEFORE = 12 * 3600      # keep programmes that ended up to 12 h ago
KEEP_AFTER = 48 * 3600       # and up to 48 h ahead
DESC_MAX = 220
ZIP_LIMIT = 95 * 1024 * 1024


def ts(value):
    if not value:
        return None
    m = re.match(r'^(\d{14})\s*([+-]\d{4})?', value.strip())
    if not m:
        return None
    dt = datetime.strptime(m.group(1), '%Y%m%d%H%M%S')
    off = m.group(2) or '+0000'
    sign = 1 if off[0] == '+' else -1
    seconds = sign * (int(off[1:3]) * 3600 + int(off[3:5]) * 60)
    return int(dt.replace(tzinfo=timezone.utc).timestamp()) - seconds


def text(el, tag):
    node = el.find(tag)
    return (node.text or '').strip() if node is not None and node.text else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    now = int(time.time())
    lo, hi = now - KEEP_BEFORE, now + KEEP_AFTER
    # channel id -> source file -> list of programmes; the fullest source wins
    found = {}
    files = sorted(glob.glob(os.path.join(a.src, '**', '*.xml'), recursive=True)
                   + glob.glob(os.path.join(a.src, '**', '*.xml.gz'), recursive=True))
    for path in files:
        opener = gzip.open if path.endswith('.gz') else open
        try:
            with opener(path, 'rb') as f:
                for _, el in ET.iterparse(f, events=('end',)):
                    if el.tag != 'programme':
                        continue
                    cid = (el.get('channel') or '').split('@', 1)[0]
                    start, stop = ts(el.get('start')), ts(el.get('stop'))
                    title = text(el, 'title')
                    el.clear()
                    if not cid or not start or not title:
                        continue
                    if not stop or stop <= start:
                        stop = start + 1800
                    if stop < lo or start > hi:
                        continue
                    found.setdefault(cid, {}).setdefault(path, [])
                    found[cid][path].append([start, stop, title[:160], '', ''])
        except (ET.ParseError, OSError, EOFError) as e:
            print('skip', path, e)
            continue

    # Second pass for category and description, only for the winning file per channel
    best = {cid: max(srcs.items(), key=lambda kv: len(kv[1])) for cid, srcs in found.items()}
    wanted = {}
    for cid, (path, _) in best.items():
        wanted.setdefault(path, set()).add(cid)
    details = {}
    for path, cids in wanted.items():
        opener = gzip.open if path.endswith('.gz') else open
        try:
            with opener(path, 'rb') as f:
                for _, el in ET.iterparse(f, events=('end',)):
                    if el.tag != 'programme':
                        continue
                    cid = (el.get('channel') or '').split('@', 1)[0]
                    if cid in cids:
                        key = (cid, ts(el.get('start')))
                        details[key] = (text(el, 'category')[:40], re.sub(r'\s+', ' ', text(el, 'desc'))[:DESC_MAX])
                    el.clear()
        except (ET.ParseError, OSError, EOFError):
            pass

    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, 'teleora-epg.zip')
    programmes = 0
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for cid, (path, progs) in sorted(best.items()):
            progs.sort(key=lambda p: p[0])
            clean, last = [], None
            for p in progs:
                if last is not None and p[0] < last:     # drop overlaps and duplicates
                    continue
                cat, desc = details.get((cid, p[0]), ('', ''))
                p[3], p[4] = cat, desc
                clean.append(p)
                last = p[1]
            if not clean:
                continue
            programmes += len(clean)
            shard = hashlib.md5(cid.encode('utf-8')).hexdigest()[:2]
            z.writestr('ch/%s/%s.json' % (shard, cid), json.dumps(clean, ensure_ascii=False, separators=(',', ':')))

    size = os.path.getsize(zpath)
    if size > ZIP_LIMIT:
        raise SystemExit('Package is %d MB, over the GitHub file limit. Lower DAYS.' % (size // 1048576))

    version = hashlib.sha1(open(zpath, 'rb').read()).hexdigest()[:12]
    manifest = {
        'version': version,
        'generated': now,
        'generated_iso': datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'channels': len(best),
        'programmes': programmes,
        'bytes': size,
        'window': [lo, hi],
    }
    with open(os.path.join(a.out, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(a.out, 'README.md'), 'w') as f:
        f.write('Generated TV guide for Teleora. Do not edit; rebuilt by the workflow.\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
