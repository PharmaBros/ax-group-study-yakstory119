"""Aside로 받은 캡션 전문(수신 폴더의 {id}.json)을 약사님 폴더 01/게시물목록.json에 합친다.

사용:  python3 -I 도구/캡션합치기.py <01_수집 폴더> <수신폴더> [<수신폴더2> ...] [--write]
  --write 가 없으면 검증 결과만 보여 준다.
  수신 폴더가 여러 개면 같은 id는 "옛 80자 캡션과 앞부분이 맞는 것 → 더 긴 것" 순으로 고른다.

하는 일:
  1. 받은 글의 줄바꿈(\\r\\n)을 \\n으로 되돌린다. 줄 끝 공백·\\xa0 정리.
  2. 화면 머리글("hong_yaksa / 수정됨 / • / 2주")이 캡션 앞에 붙어 있으면 옛 캡션 앞부분을 찾아 잘라 낸다.
  3. 깨진 글자(\\ufffd)가 있으면 '인스타 제공 한계까지(약 1,070자에서 잘림)'로 표시한다.
  4. 좋아요·댓글 수("1,765", "19K")를 숫자로.
  5. --write: 기존 게시물목록.json을 {오늘}_게시물목록_이전(80자).json으로 보존하고 새로 쓴다.
"""
import json, pathlib, sys, re, datetime, shutil, unicodedata

args = [a for a in sys.argv[1:] if not a.startswith('--')]
write = '--write' in sys.argv
if len(args) < 2:
    print(__doc__); sys.exit(1)
작업폴더 = pathlib.Path(__file__).resolve().parents[1]  # 상대 경로는 작업 폴더 기준
src = 작업폴더 / pathlib.Path(args[0]).expanduser(); recv_dirs = [작업폴더 / pathlib.Path(a).expanduser() for a in args[1:]]
if not (src / '게시물목록.json').exists():
    print(f"[실패] 게시물목록.json이 없습니다: {src}"); sys.exit(1)

posts = json.load(open(src / '게시물목록.json'))
NFC = lambda s: unicodedata.normalize('NFC', s or '')

def clean(cap):
    cap = NFC(cap).replace('\r\n', '\n').replace('\r', '\n').replace('\xa0', ' ')
    if re.match(r'^\s*Photo (?:shared )?by ', cap) or re.match(r'^\s*Video by ', cap):
        return ''  # 인스타 og 기본 문구(실명 포함) — 캡션 없음으로 본다
    return '\n'.join(l.rstrip() for l in cap.split('\n')).strip('\n')

def strip_header(cap, old):
    """옛 캡션(80자) 앞 12자가 cap 안 앞쪽 200자 이내에 있으면 거기서부터 쓴다."""
    head = clean(old)[:12]
    if not head:
        return cap, False
    i = cap.find(head)
    if i == 0:
        return cap, True
    if 0 < i <= 200:
        return cap[i:], True
    return cap, False

def num(s):
    s = (s or '').replace(',', '').strip()
    m = re.match(r'^([\d.]+)K$', s)
    if m: return int(float(m.group(1)) * 1000)
    m = re.match(r'^([\d.]+)M$', s)
    if m: return int(float(m.group(1)) * 1_000_000)
    return int(s) if s.isdigit() else None

# 수신 파일 모으기: id → 후보 목록
cands = {}
for d in recv_dirs:
    if not d.exists():
        print(f"[실패] 수신 폴더가 없습니다: {d}"); sys.exit(1)
    for f in d.glob('*.json'):
        if f.stem in ('ping', 'test'): continue
        try:
            r = json.load(open(f))
        except Exception as e:
            print(f"[경고] 읽기 실패 {f.name}: {e}"); continue
        if 'id' in r and 'caption' in r:
            cands.setdefault(r['id'], []).append((d.name, r))

ok = miss = broken = nomatch = 0
chosen_from = {}
out = []
for p in posts:
    q = dict(p); old = p.get('캡션') or ''
    lst = cands.get(p['id'])
    if not lst:
        miss += 1; q['캡션상태'] = '미수신'; out.append(q); continue
    best = None
    for dname, r in lst:
        cap, matched = strip_header(clean(r['caption']), old)
        score = (1 if matched else 0, len(cap))
        if best is None or score > best[0]:
            best = (score, cap, matched, r, dname)
    score, cap, matched, r, dname = best
    chosen_from[dname] = chosen_from.get(dname, 0) + 1
    q['캡션'] = cap; q['글자수'] = len(cap)
    q['좋아요'] = num(r.get('likes')); q['댓글수'] = num(r.get('comments'))
    q['게시시각_utc'] = r.get('time') or None
    if '�' in cap:
        broken += 1; q['캡션상태'] = '인스타 제공 한계까지(약 1,070자에서 잘림)'
    elif not matched:
        # 캡션이 아니라 댓글 등 다른 글이 잡힌 것 → 옛 캡션(80자)을 그대로 두고 표시만
        nomatch += 1; q['캡션'] = old; q['글자수'] = len(old)
        q['캡션상태'] = '전문 못 받음(댓글 등 다른 글이 잡힘 → 재수집 필요, 옛 80자 유지)'
    else:
        q['캡션상태'] = '전문'
    ok += 1; out.append(q)

L = [x['글자수'] for x in out if '글자수' in x]
print(f"게시물 {len(posts)} / 합침 {ok} / 미수신 {miss} / 잘림 {broken} / 앞부분 불일치 {nomatch}")
if L:
    print(f"글자수 최소 {min(L)} 최대 {max(L)} 평균 {sum(L)//len(L)}  (300자 초과 {sum(1 for n in L if n>300)}개 → 설계서 수집 검증 ① {'통과' if max(L)>300 else '잘림 의심'})")
print("수신 폴더별 채택:", chosen_from)
print("미수신 순서:", [x['순서'] for x in out if x.get('캡션상태') == '미수신'])
print("전문 못 받음(재수집 필요) 순서:", [x['순서'] for x in out if x.get('캡션상태', '').startswith('전문 못')])
print("잘림 순서:", [x['순서'] for x in out if x.get('캡션상태', '').startswith('인스타')])

if write:
    today = datetime.date.today().isoformat()
    bak = src / f'{today}_게시물목록_이전(80자).json'
    if not bak.exists():
        shutil.copy(src / '게시물목록.json', bak)
    json.dump(out, open(src / '게시물목록.json', 'w'), ensure_ascii=False, indent=1)
    print('썼음:', src / '게시물목록.json', '/ 백업:', bak.name)
else:
    print('(검증만 했음. 실제로 쓰려면 --write)')
