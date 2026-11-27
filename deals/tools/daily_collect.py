"""신약 딜북 일일 자동 수집 (토큰 없이 GitHub Actions에서 실행)

1) FDA CDER 신약 승인: FDA Novel Drug Approvals 표 + openFDA(허가 보유사, 우선심사) + PubChem(구조)
   → data/fda.json에 바로 추가(auto: true). 한국어 요약과 정밀 분류는 주간 Claude 작업이 채운다.
2) CBER 신규 BLA, 기술거래, 투자 후보: FDA CBER 표, 보도자료 RSS, SEC EDGAR 전문검색
   → data/candidates.json에 후보로만 쌓는다(앱은 읽지 않음). 주간 Claude 작업이 원문 확인 후 반영.
"""
import datetime as dt, hashlib, html, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
UA = 'Mozilla/5.0 (compatible; kosdaq-cases-dealbook/1.0; +https://github.com/schung-pixel/kosdaq-cases)'
SEC_UA = os.environ.get('SEC_UA', 'kosdaq-cases-dealbook schung-pixel@users.noreply.github.com')
TODAY = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=9)  # KST
LOG = []

def log(*a):
    s = ' '.join(str(x) for x in a); LOG.append(s); print(s)

def get(url, ua=UA, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def jget(url):
    return json.loads(get(url))

def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default

def save(name, obj):
    with open(os.path.join(DATA, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

# ---------- 1. FDA CDER ----------
STEMS = [  # (정규식, modality, mod_sub) 성분명 어미 기반 1차 분류. 주간 작업이 출처로 확정한다.
    (r'(vedotin|deruxtecan|govitecan|tirumotecan|mafodotin|ozogamicin|emtansine|soravtansine|tesirine|duocarmazine)', 'ADC', 'Unspecified'),
    (r'mab\b', 'Antibody', 'Monoclonal Antibody'),
    (r'(siran)$', 'RNA Therapeutics', 'siRNA/RNAi'),
    (r'(rsen|ersen)$', 'RNA Therapeutics', 'ASO'),
    (r'tide$', 'Peptide', 'Unspecified'),
    (r'(tinib|rafenib)$', 'Small Molecule', 'Kinase Inhibitor'),
    (r'(cept)$', 'Protein Therapeutic', 'Fusion Protein'),
    (r'(ase|alfa|beta)$', 'Protein Therapeutic', 'Unspecified'),
    (r'(gene|vec|parvovec)\b', 'Gene Therapy', 'Unspecified'),
    (r'(leucel|temcel)$', 'Cell Therapy', 'Unspecified'),
    (r'^(fluorine|gallium|technetium|lutetium|copper|zirconium|iodine|indium|flurpiridaz|piflufolastat)|\b(f ?18|ga ?68|lu ?177|cu ?64|tc ?99m)\b', 'Radiopharmaceutical', 'Unspecified'),
]

def guess_modality(generic, appl):
    g = generic.lower().strip()
    for pat, m, s in STEMS:
        if re.search(pat, g): return m, s
    if appl.startswith('BLA'): return 'Protein Therapeutic', 'Unspecified'
    return 'Small Molecule', 'Unspecified'

def openfda_info(brand, generic):
    out = {}
    for q in [f'products.brand_name:"{brand}"', f'openfda.generic_name:"{generic}"']:
        try:
            r = jget('https://api.fda.gov/drug/drugsfda.json?' + urllib.parse.urlencode({'search': q, 'limit': 5}))['results']
        except Exception:
            continue
        for a in r:
            orig = [s for s in a.get('submissions', []) if s.get('submission_type') == 'ORIG']
            if not orig: continue
            o = orig[0]
            out = {'appl': a.get('application_number', ''), 'sponsor': a.get('sponsor_name', ''),
                   'priority': (o.get('review_priority') or '').upper().startswith('PRIORITY')}
            return out
    return out

def pubchem(name):
    u = ('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/' + urllib.parse.quote(name)
         + '/property/MolecularFormula,MolecularWeight,SMILES/JSON')
    try:
        p = jget(u)['PropertyTable']['Properties'][0]
    except Exception:
        return None
    mw = round(float(p['MolecularWeight']), 1)
    c = {'name': name, 'cid': p['CID'], 'formula': p['MolecularFormula'], 'mw': mw}
    smi = p.get('SMILES') or p.get('IsomericSMILES') or p.get('CanonicalSMILES')
    if smi and mw <= 2000: c['smiles'] = smi
    return c

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def fda_cder(fda):
    items = fda['items']
    have = {(norm(i['brand']), i['date']) for i in items} | {(norm(i['generic']), i['date']) for i in items}
    years = {TODAY.year} | ({TODAY.year - 1} if TODAY.month == 1 else set())
    added = []
    for y in sorted(years):
        url = f'https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-{y}'
        try:
            t = get(url)
        except Exception as e:
            log('FDA 표 실패', y, e); continue
        tb = re.search(r'<table.*?</table>', t, re.S)
        if not tb: log('FDA 표 없음', y); continue
        for row in re.findall(r'<tr.*?</tr>', tb.group(0), re.S)[1:]:
            c = [text(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
            if len(c) < 5: continue
            brand, generic, d, use = c[1], c[2], c[3], c[4]
            try:
                date = dt.datetime.strptime(d, '%m/%d/%Y').strftime('%Y-%m-%d')
            except ValueError:
                continue
            if (norm(brand), date) in have or (norm(generic), date) in have: continue
            if any(norm(brand) == norm(i['brand']) for i in items): continue
            info = openfda_info(brand, generic)
            appl = info.get('appl', '')
            mod, sub = guess_modality(generic, appl)
            rec = {'brand': brand, 'generic': generic.lower(), 'date': date, 'center': 'CDER',
                   'type': 'BLA' if appl.startswith('BLA') else 'NME',
                   'sponsor': info.get('sponsor') or '(확인 중)', 'indication': use,
                   'moa': '', 'modality': mod, 'mod_sub': sub, 'mod_src': url, 'src': url,
                   'designations': ['Priority'] if info.get('priority') else [], 'deals': [],
                   'origin': '불명', 'auto': True, 'added': TODAY.strftime('%Y-%m-%d') + ' 자동 수집'}
            if rec['type'] == 'NME' and mod in ('Small Molecule', 'Peptide', 'Radiopharmaceutical'):
                ch = [x for x in (pubchem(p.strip()) for p in re.split(r';| and |,', generic) if p.strip()) if x]
                if ch: rec['chem'] = ch
            added.append(rec); have.add((norm(brand), date))
            time.sleep(0.5)
    if added:
        mx = max(int(i['id'].split('-')[1]) for i in items)
        for n, r in enumerate(sorted(added, key=lambda r: r['date']), start=1):
            r['id'] = f"f{r['date'][:4]}{r['date'][5:7]}-{mx + n:03d}"
        items.extend(dict(sorted(r.items())) for r in added)
        items.sort(key=lambda r: r['date'], reverse=True)
    for i in items:
        if i.get('auto') and i.get('sponsor') == '(확인 중)':
            info = openfda_info(i['brand'], i['generic'])
            if info.get('sponsor'):
                i['sponsor'] = info['sponsor']; i['type'] = 'BLA' if info['appl'].startswith('BLA') else 'NME'
                if info.get('priority') and 'Priority' not in i['designations']: i['designations'].append('Priority')
                added.append(i)  # 변경 표시용
    log('FDA CDER 신규/보완', len(added), [r['brand'] for r in added])
    return added

# ---------- 2. 후보 ----------
DEAL_RX = re.compile(r'licen[cs]|collaborat|option to|partnership|exclusive rights|co-develop|strategic agreement|worldwide rights|acqui|merger|to buy|royalt|equity investment|strategic investment|commerciali[sz]ation rights', re.I)
INV_RX = re.compile(r'series [a-f]\b|seed|financing|crossover|private placement|pipe\b|raises?|closes? .* round|initial public offering|\bipo\b|prices? .* offering|public offering|registered direct', re.I)
EXCL_RX = re.compile(r'market (size|report|analysis)|delveinsight|research and markets|webinar|conference call|to present at|annual meeting|at-the-market|convertible (notes?|senior)', re.I)
AMT_RX = re.compile(r'(?:US)?\$\s?([\d.,]+)\s*(billion|million|bn|mn|m|b)\b', re.I)

def amounts(s):
    out = []
    for v, u in AMT_RX.findall(s):
        try:
            x = float(v.replace(',', ''))
        except ValueError:
            continue
        out.append(x * 1000 if u.lower() in ('billion', 'bn', 'b') else x)
    return out

def classify(title, desc):
    s = f'{title} {desc}'
    if EXCL_RX.search(s): return None
    amt = max(amounts(s) or [0])
    if DEAL_RX.search(s) and amt >= 100: return 'deal', amt
    if INV_RX.search(s) and amt >= 100: return ('ipo' if re.search(r'initial public offering|\bipo\b', s, re.I) else 'invest'), amt
    return None

FEEDS = [
    ('PR Newswire biotech', 'https://www.prnewswire.com/rss/health-latest-news/biotechnology-list.rss'),
    ('PR Newswire pharma', 'https://www.prnewswire.com/rss/health-latest-news/pharmaceuticals-list.rss'),
    ('GlobeNewswire biotech', 'https://www.globenewswire.com/RssFeed/industry/4573-Biotechnology/feedTitle/GlobeNewswire%20-%20Industry%20News%20on%20Biotechnology'),
    ('GlobeNewswire pharma', 'https://www.globenewswire.com/RssFeed/industry/4577-Pharmaceuticals/feedTitle/GlobeNewswire%20-%20Industry%20News%20on%20Pharmaceuticals'),
    ('Endpoints', 'https://endpts.com/feed/'),
    ('Fierce Biotech', 'https://www.fiercebiotech.com/rss/xml'),
    ('BioSpace', 'https://www.biospace.com/feed'),
]

def rss(name, url):
    out = []
    try:
        root = ET.fromstring(get(url).encode('utf-8'))
    except Exception as e:
        log('RSS 실패', name, str(e)[:80]); return out
    for it in root.iter('item'):
        te = it.find('title'); t = text(''.join(te.itertext())) if te is not None else ''
        if not t:
            m = re.search(r'/([a-z0-9-]{12,})/?$', it.findtext('link') or ''); t = m.group(1).replace('-', ' ') if m else ''
        l = (it.findtext('link') or '').strip()
        d = text(it.findtext('description') or '')[:600]; pd = it.findtext('pubDate') or ''
        try:
            date = dt.datetime.strptime(pd[:25].strip(), '%a, %d %b %Y %H:%M:%S').strftime('%Y-%m-%d')
        except ValueError:
            date = TODAY.strftime('%Y-%m-%d')
        out.append({'title': t, 'url': l, 'desc': d, 'date': date, 'source': name})
    log('RSS', name, len(out))
    return out

def sec_fts():
    out = []
    start = (TODAY - dt.timedelta(days=3)).strftime('%Y-%m-%d'); end = TODAY.strftime('%Y-%m-%d')
    for q in ['"upfront payment" "license agreement"', '"upfront payment" "collaboration"', '"exclusive license" "milestone payments"']:
        u = 'https://efts.sec.gov/LATEST/search-index?' + urllib.parse.urlencode({'q': q, 'forms': '8-K,6-K', 'dateRange': 'custom', 'startdt': start, 'enddt': end})
        try:
            h = json.loads(get(u, ua=SEC_UA))['hits']['hits']
        except Exception as e:
            log('SEC 실패', str(e)[:80]); return out
        for x in h:
            s = x.get('_source', {}); cik = (s.get('ciks') or [''])[0]; adsh = x['_id'].split(':')[0]
            out.append({'title': ' / '.join(s.get('display_names') or [])[:200] + f" {s.get('form', '')} ({q})",
                        'url': f'https://www.sec.gov/Archives/edgar/data/{cik.lstrip("0")}/{adsh.replace("-", "")}/{x["_id"].split(":")[1]}',
                        'desc': '', 'date': s.get('file_date', end), 'source': 'SEC EDGAR'})
        time.sleep(0.5)
    log('SEC', len(out))
    return out

def cber(cand):
    y = TODAY.year
    url = f'https://www.fda.gov/vaccines-blood-biologics/development-approval-process-cber/{y}-biological-license-application-approvals'
    try:
        t = get(url)
    except Exception as e:
        log('CBER 실패', e); return []
    tb = re.search(r'<table.*?</table>', t, re.S)
    if not tb: return []
    out = []
    for row in re.findall(r'<tr.*?</tr>', tb.group(0), re.S)[1:]:
        c = [text(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
        if len(c) < 5: continue
        try:
            date = dt.datetime.strptime(c[-1].split()[0], '%m/%d/%Y').strftime('%Y-%m-%d')
        except ValueError:
            continue
        out.append({'kind': 'fda_cber', 'title': c[0], 'desc': c[1][:400], 'date': date, 'url': url, 'source': 'FDA CBER', 'amount_musd': None})
    return out

def candidates(fda):
    cand = load('candidates.json', {'updated': '', 'items': []})
    cand['items'] = [c for c in cand['items'] if c.get('title')]
    known = {c['url'] + c.get('title', '') for c in cand['items']} | {c['url'] for c in cand['items'] if c.get('kind') != 'fda_cber'}
    fda_names = {norm(i['brand']) for i in fda['items']}
    new = []
    for c in cber(cand):
        if norm(c['title'].split()[0]) in fda_names: continue
        if re.search(r'plasma|assay|blood group|reagent|\btest\b|cord blood|hpc|antibody to|nucleic acid|screening', c['title'] + ' ' + c['desc'][:120], re.I): continue
        if c['url'] + c['title'] not in known: new.append(c)
    raw = []
    for n, u in FEEDS: raw += rss(n, u)
    for r in raw:
        k = classify(r['title'], r['desc'])
        if not k or r['url'] in known or not r['title']: continue
        new.append({'kind': k[0], 'title': r['title'], 'desc': r['desc'][:300], 'date': r['date'], 'url': r['url'], 'source': r['source'], 'amount_musd': k[1]})
        known.add(r['url'])
    for r in sec_fts():
        if r['url'] in known: continue
        new.append({'kind': 'deal_filing', **r, 'amount_musd': None}); known.add(r['url'])
    for c in new:
        c['id'] = 'c' + hashlib.md5((c['url'] + c['title']).encode()).hexdigest()[:10]
        c['found'] = TODAY.strftime('%Y-%m-%d')
    cut = (TODAY - dt.timedelta(days=45)).strftime('%Y-%m-%d')
    cand['items'] = sorted([c for c in cand['items'] + new if c.get('found', c['date']) >= cut], key=lambda c: c['date'], reverse=True)
    cand['updated'] = TODAY.strftime('%Y-%m-%d %H:%M KST')
    log('후보 신규', len(new), '누적', len(cand['items']))
    return cand, new

def main():
    fda = load('fda.json', {'items': []})
    added = fda_cder(fda)
    cand, new = candidates(fda)
    if added:
        save('fda.json', fda)
        try:
            sys.path.insert(0, HERE); import render_chem; render_chem.main(os.path.join(DATA, 'fda.json'))
        except Exception as e:
            log('구조 렌더 실패', e)
        sw = os.path.join(ROOT, 'sw.js'); s = open(sw, encoding='utf-8').read()
        s = re.sub(r"const VERSION\s*=\s*'[^']*'", f"const VERSION = 'dealbook-{TODAY:%Y-%m-%d}-auto'", s, count=1)
        open(sw, 'w', encoding='utf-8').write(s)
    if new or added:
        save('candidates.json', cand)
    with open(os.environ.get('GITHUB_STEP_SUMMARY', os.devnull), 'a') as f:
        f.write('\n'.join(LOG) + '\n')

if __name__ == '__main__':
    main()
