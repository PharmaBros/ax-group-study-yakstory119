"""부품 도구 공용 — 잉크 상자 재기, 글 줄 훑기, 글꼴에 글자가 있는지, 크롬으로 글꼴 크기 맞추기, 렌더, 원본과 나란히 붙이기.

출처: R/2026-11-10_디자인시스템/도구/_tools_B/lib.py(7000px 창·dotspan 반영본) + scan.py + glyph.py, 2026-11-10 판.
ponytail: 겹침(IoU)은 잉크 상자 왼쪽 위를 맞춰 계산한 근사. 누끼·원형 오리기·선그림 추출은 이 파일에 없다(다른 도구 몫).

명령줄(작은 확인용):
  lib.py scan <장.jpg> x0 y0 x1 y1 [--gap 14] [--thr 100]   영역 안 글 줄·덩어리의 잉크 상자·색
  lib.py glyph <글꼴 이름> <글>                              그 글꼴에 없는 글자 찾기 (예: '강원교육모두 Bold' '·')
"""
import os, sys, json, re, tempfile, subprocess, functools
from pathlib import Path
import numpy as np
from PIL import Image

_도구 = Path(__file__).resolve().parents[1]
if str(_도구) not in sys.path: sys.path.insert(0, str(_도구))
from 공통 import 실패, 한글ArgumentParser, 하위폴더_찾기  # noqa: E402

FONT = _도구 / '글꼴'
CHROME = os.environ.get('CHROME') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# 글꼴 이름표(FAM) — 이 파일 한 곳에서만 정한다. 이름 앞부분이 키, 뒤 단어가 굵기. 값 = (CSS 글꼴 이름, {단어: 굵기})
FAM = {'프리텐다드': ('Pretendard', {'Light': 300, 'Regular': 400, 'Bold': 700, 'Black': 900}),
       '강원교육모두': ('강원교육모두', {'Bold': 700, 'Light': 300, 'Regular': 300}),
       '카페24 당당해': ('카페24 당당해', {'Regular': 400}),
       '나눔스퀘어라운드': ('나눔스퀘어라운드', {'Regular': 400, 'Bold': 700, 'ExtraBold': 800}),
       '싱글데이': ('싱글데이', {'Regular': 400}), '도현': ('도현', {'Regular': 400}),
       '카페24 서라운드에어': ('카페24 서라운드에어', {'Regular': 300}),
       '지마켓': ('지마켓', {'Bold': 700, 'Medium': 500, 'Regular': 500})}
FACES = [  # (CSS 글꼴 이름, 굵기, 파일) — 파일은 도구/글꼴/ 안
    ('Pretendard', 300, 'Pretendard-Light.woff2'), ('Pretendard', 400, 'Pretendard-Regular.woff2'), ('Pretendard', 700, 'Pretendard-Bold.woff2'),
    ('Pretendard', 900, 'Pretendard-Black.woff2'),
    ('강원교육모두', 700, 'GangwonEduAll-Bold.woff'), ('강원교육모두', 300, 'GangwonEduAll-Light.woff'),
    ('카페24 당당해', 400, 'Cafe24Dangdanghae-v2.0.woff2'),
    ('나눔스퀘어라운드', 400, 'NanumSquareRoundR.ttf'), ('나눔스퀘어라운드', 700, 'NanumSquareRoundB.ttf'),
    ('나눔스퀘어라운드', 800, 'NanumSquareRoundEB.ttf'),
    ('싱글데이', 400, 'SingleDay-Regular.ttf'), ('도현', 400, 'DoHyeon-Regular.ttf'),
    ('카페24 서라운드에어', 300, 'Cafe24SsurroundAir-v1.1.ttf'),
    ('지마켓', 700, 'GmarketSansTTFBold.ttf'), ('지마켓', 500, 'GmarketSansTTFMedium.ttf'),
]
# 이 글꼴에서 빠진 글자는 프리텐다드로 그린다(dotspan)
기본글꼴 = 'Pretendard'
글자검사_글꼴 = {'강원교육모두'}


def fam(name):
    """'강원교육모두 Bold' -> ('강원교육모두', 700). 모르는 이름이면 KeyError"""
    for k, (f, ws) in FAM.items():
        if name.startswith(k):
            return f, ws.get(name[len(k):].strip() or 'Regular', 400)
    raise KeyError(name)


def 글꼴_파일(css이름, 굵기):
    """CSS 글꼴 이름·굵기에 가장 가까운 글꼴 파일 경로"""
    c = [(abs(w - 굵기), p) for f, w, p in FACES if f == css이름]
    if not c: raise KeyError(css이름)
    return FONT / min(c)[1]


def font_css():
    return ''.join("@font-face{font-family:'%s';font-weight:%d;src:url('%s')}" % (f, w, (FONT / p).as_uri()) for f, w, p in FACES)


@functools.lru_cache(maxsize=None)
def has_glyph(path, ch):
    """PIL로 그려 .notdef(U+FFFF 자리)와 같으면 글자 없음. 글꼴을 못 열면 있다고 본다."""
    from PIL import ImageFont, ImageDraw
    try: f = ImageFont.truetype(str(path), 60)
    except OSError: return True
    def r(c):
        im = Image.new('L', (120, 120), 0); ImageDraw.Draw(im).text((10, 10), c, font=f, fill=255); return np.asarray(im)
    return not np.array_equal(r(ch), r('￿'))


def 없는_글자(css이름, 굵기, 글):
    """그 글꼴에 없는 글자 목록(공백 제외, 겹치지 않게 순서대로)"""
    p = 글꼴_파일(css이름, 굵기)
    return list(dict.fromkeys(c for c in 글 if not c.isspace() and not has_glyph(p, c)))


def dotspan(famname, 글, 굵기=700):
    """원본 글(이스케이프 전)을 HTML로 바꾸되, 강원교육모두에 없는 글자(· > < = 등)만 프리텐다드 span으로 감싼다."""
    import html as H
    miss = set(없는_글자(famname, 굵기, 글)) if famname in 글자검사_글꼴 else set()
    return ''.join("<span style=\"font-family:'%s'\">%s</span>" % (기본글꼴, H.escape(c)) if c in miss else H.escape(c) for c in 글)


# ---- 장 크기 · 장 열기 · 잉크 재기 ----
기본_높이 = 1350  # 장 크기를 못 읽을 때의 높이(너비는 늘 1080) — 1350 하드코딩은 여기 한 곳만


def 장_크기(src=None):
    """(1080, 높이). src = json 경로 | dict | None. `출력_크기_기본`(디자인시스템.json) 또는 `크기`(견본.json)의 [W, H]를 너비 1080 기준으로 환산. 없거나 못 읽으면 (1080, 기본_높이)."""
    try:
        if isinstance(src, (str, Path)): src = json.loads(Path(src).read_text(encoding='utf-8'))
        w, h = (src.get('출력_크기_기본') or src['크기'])[:2]
        return (1080, round(h * 1080 / w)) if w > 0 and h > 0 else (1080, 기본_높이)
    except Exception: return (1080, 기본_높이)  # ponytail: 어떤 오류든 기본값 — 모양이 틀린 json도 기존 동작 유지


def 견본_높이(part):
    """부품 폴더 견본.json의 `크기` 높이(없으면 기본_높이)"""
    return 장_크기(Path(part) / '견본.json')[1]


def 크기_섞임(높이들):
    """{부품: 높이}에 서로 다른 높이가 섞였으면 한 줄 메시지, 아니면 None (한 편 안 장은 모두 같은 크기)."""
    return '한 편 안 부품 크기가 다름: ' + ' / '.join('%s %d' % kv for kv in 높이들.items()) if len(set(높이들.values())) > 1 else None


def 계정_높이(약사님폴더):
    """약사님 폴더 04_설계서/디자인시스템.json의 `출력_크기_기본` 높이(없으면 기본_높이). 폴더는 Path."""
    d = 하위폴더_찾기(Path(약사님폴더), '04_')
    return 장_크기(d / '디자인시스템.json' if d else None)[1]


def 장_열기(path, h=기본_높이):
    """장 그림을 너비 1080으로 맞춰 열기(비율 유지). h보다 길면 위쪽 h만 쓴다."""
    im = Image.open(path).convert('RGB')
    if im.width != 1080: im = im.resize((1080, round(im.height * 1080 / im.width)))
    return im.crop((0, 0, 1080, h)) if im.height > h else im


def mode_color(a):
    q = (a.reshape(-1, 3) // 4)
    k = q[:, 0].astype(int) * 4096 + q[:, 1] * 64 + q[:, 2]
    u, c = np.unique(k, return_counts=True)
    v = u[c.argmax()]
    return np.array([(v // 4096) * 4 + 2, ((v // 64) % 64) * 4 + 2, (v % 64) * 4 + 2])


def hexc(c): return '#%02X%02X%02X' % tuple(int(x) for x in c)


def ink(im, box, thr=60, bg=None):
    """box=(x0,y0,x1,y1) 안에서 바탕과 다른 잉크 -> dict(왼쪽,위,오른쪽,아래,색,바탕,mask,off). 잉크 없으면 None"""
    x0, y0, x1, y1 = box
    a = np.asarray(im.crop(box)).astype(int)
    b = mode_color(a) if bg is None else np.array(bg)
    d = np.abs(a - b).sum(2)
    m = d > thr
    if not m.any(): return None
    ys, xs = np.where(m)
    mx = d[m].max()
    core = a[(d > 0.8 * mx)]
    col = np.median(core, 0) if len(core) else a[m].mean(0)
    return dict(왼쪽=int(xs.min() + x0), 위=int(ys.min() + y0), 오른쪽=int(xs.max() + x0 + 1), 아래=int(ys.max() + y0 + 1),
                색=hexc(col), 바탕=hexc(b), mask=m, off=(x0, y0))


def scan(im, box, gap=14, thr=100, bg=None, rowgap=3):
    """영역 안 글 줄·덩어리 훑기. 줄마다 [(왼쪽,위,오른쪽,아래,색), ...] 목록"""
    x0, y0, x1, y1 = box
    a = np.asarray(im.crop(box)).astype(int)
    b = mode_color(a) if bg is None else np.array(bg)
    m = np.abs(a - b).sum(2) > thr
    rows = np.where(m.any(1))[0]
    out = []
    if not len(rows): return out
    ls = []; s = p = rows[0]
    for r in rows[1:]:
        if r - p > rowgap: ls.append((s, p)); s = r
        p = r
    ls.append((s, p))
    for ys, ye in ls:
        cols = np.where(m[ys:ye + 1].any(0))[0]
        cs = []; s = p = cols[0]
        for c in cols[1:]:
            if c - p > gap: cs.append((s, p)); s = c
            p = c
        cs.append((s, p))
        row = []
        for cs_, ce in cs:
            yy, xx = np.where(m[ys:ye + 1, cs_:ce + 1])
            ay0 = ys + yy.min(); ay1 = ys + yy.max() + 1
            seg = a[ay0:ay1, cs_:ce + 1]
            d = np.abs(seg - b).sum(2)
            row.append((int(cs_ + x0), int(ay0 + y0), int(ce + x0 + 1), int(ay1 + y0), hexc(np.median(seg[d > 0.8 * d.max()], 0))))
        out.append(row)
    return out


# ---- 크롬 ----
def 크롬_확인():
    if not os.path.exists(CHROME):
        실패("크롬을 찾을 수 없습니다 — 환경변수 CHROME에 크롬 실행 파일 경로를 주세요 (기본: %s)" % CHROME)


def chrome_shot(html_path, out, w, h):
    크롬_확인()
    try:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                        '--default-background-color=FFFFFFFF', '--virtual-time-budget=3000',
                        '--window-size=%d,%d' % (w, h), '--screenshot=' + str(out), Path(html_path).as_uri()],
                       check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        실패("크롬 화면 찍기에 실패했습니다: %s" % (getattr(e, 'stderr', b'') or b'')[-200:].decode('utf-8', 'ignore'))


def html_shot(html, out, w=1080, h=기본_높이, 창_높이=None):
    """html 글을 임시 파일로 찍어 w×h로 자른 png를 out에 저장. 창 높이를 넉넉히(기본 h+150) 잡아 아래가 잘리지 않게 한다."""
    with tempfile.TemporaryDirectory() as t:
        hp = Path(t) / 'x.html'; hp.write_text(html, encoding='utf-8')
        chrome_shot(hp, out, w, 창_높이 or h + 150)
    Image.open(out).convert('RGB').crop((0, 0, w, h)).save(out)
    return out


def fit_fonts(items, tmp):
    """items: [{글,글꼴(CSS 이름),굵기,기울임,목표:(w,h),마스크?,조각?}] -> 각 항목에 크기·위_보정·폭_비·글자높이·겹침 채움. 한 줄 글만."""
    import html as H
    S = 120
    # 기울인 글은 위아래로 더 차지하니 띠를 넓히고 가운데에 둔다(기울기 = 시계 방향 도, CSS rotate와 같음)
    자리 = []; y = 0
    for it in items:
        기 = bool(it.get('기울기')); 자리.append((y, 720 if 기 else 220, 280 if 기 else 30, 240 if 기 else 40)); y += 자리[-1][1]
    parts = []
    for i, it in enumerate(items):
        if it.get('조각'):
            t = ''.join('<span style="font-weight:%d">%s</span>' % (w_, H.escape(x_)) for x_, w_ in it['조각'])
        else:
            t = dotspan(it['글꼴'], it['글'], it.get('굵기', 400))
        y0, _, 위틈, 왼틈 = 자리[i]
        parts.append("<div style=\"position:absolute;left:%dpx;top:%dpx;font-family:'%s',sans-serif;font-weight:%d;font-size:%dpx;line-height:1;white-space:pre;color:#000;font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0;%s%s\">%s</div>"
                     % (왼틈, y0 + 위틈, it['글꼴'], it.get('굵기', 400), S, 'font-style:italic;' if it.get('기울임') else '',
                        'transform:rotate(%gdeg);transform-origin:50%% 50%%;' % it['기울기'] if it.get('기울기') else '', t))
    html = '<!doctype html><meta charset=utf-8><style>body{margin:0;background:#fff}%s</style>%s' % (font_css(), ''.join(parts))
    hp = Path(tmp) / 'fit.html'; hp.write_text(html, encoding='utf-8')
    out = Path(tmp) / 'fit.png'
    chrome_shot(hp, out, 7000, y + 60)
    im = np.asarray(Image.open(out).convert('L'))
    for i, it in enumerate(items):
        y0, band, 위틈, 왼틈 = 자리[i]
        m = im[y0:y0 + band] < 140
        if not m.any(): it['크기'] = None; continue
        ys, xs = np.where(m)
        iw, ih = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        tw, th = it['목표']
        it['크기'] = round(tw / iw * S)
        sc = it['크기'] / S
        it['위_보정'] = -round((ys.min() - 위틈) * sc)
        it['왼쪽_보정'] = -round((xs.min() - 왼틈) * sc)
        it['폭_비'] = round(tw / (iw * sc), 2)
        it['글자높이'] = round(ih * sc)
        # 겹침: 같은 크기로 줄인 마스크와 원본 마스크를 왼쪽 위 기준으로 겹침
        rm = Image.fromarray((m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype('uint8')).resize((max(1, tw), max(1, round(ih * sc))))
        rm = np.asarray(rm) > 127
        sm = it.get('마스크')
        if sm is not None:
            h = min(rm.shape[0], sm.shape[0]); w = min(rm.shape[1], sm.shape[1])
            a = rm[:h, :w]; b = sm[:h, :w]
            it['겹침'] = round(float((a & b).sum() / max(1, (a | b).sum())), 3)
            it['잉크_비'] = round(float(b.sum() / max(1, a.sum())), 2)  # 원본 잉크 / 그린 잉크 — 1보다 크면 원본 획이 더 굵다
    return items


def underline_split(im, box, thr=150):
    """글+밑줄 영역: 밑줄 줄(가로로 길게 이어진 잉크)을 떼어 글 상자와 밑줄 상자를 돌려줌"""
    r = ink(im, box, thr)
    m = r['mask']; wid = r['오른쪽'] - r['왼쪽']
    ul = [i for i, v in enumerate(m.sum(1)) if v > 0.8 * wid]
    if not ul: return r, None
    y0 = min(ul) + r['off'][1]; y1 = max(ul) + r['off'][1] + 1
    t = ink(im, (box[0], box[1], box[2], y0 - 1), thr)
    xs = np.where(m[min(ul)])[0]
    return t, dict(위=y0, 두께=y1 - y0, 왼쪽=int(xs.min() + r['off'][0]), 오른쪽=int(xs.max() + r['off'][0] + 1), 색=r['색'])


def text_items(im, specs, tmp, thr=150):
    """specs: [{이름,글,box,fam(CSS 이름),w(숫자),글꼴(표시 이름),역할,맞춤?,색?,기울임?,밑줄?,thr?,bg?,조각?,외곽?,획?,색조각?}]
    -> 글 요소 dict 목록(+ 밑줄이면 바로 뒤에 선 요소). 잉크가 없는 글은 KeyError 대신 실패."""
    out = []; fits = []
    for s in specs:
        if s.get('밑줄'): r, ul = underline_split(im, s['box'], thr)
        else: r = ink(im, s['box'], s.get('thr', thr), s.get('bg')); ul = None
        if r is None: 실패("글 '%s' 상자 %s 안에서 잉크를 찾지 못했습니다(상자·thr 확인)" % (s['글'], list(s['box'])))
        s['_r'] = r; s['_ul'] = ul
        w = r['오른쪽'] - r['왼쪽']; h = r['아래'] - r['위']
        x0 = r['왼쪽'] - r['off'][0]; y0 = r['위'] - r['off'][1]
        fits.append(dict(글=s['글'], 글꼴=s['fam'], 굵기=s['w'], 기울임=s.get('기울임'), 기울기=s.get('기울기'), 목표=(w, h),
                         마스크=r['mask'][y0:y0 + h, x0:x0 + w], 조각=s.get('조각')))
    fit_fonts(fits, tmp)
    for s, f in zip(specs, fits):
        r = s['_r']
        if f['크기'] is None: 실패("글 '%s' 를 크롬이 그리지 못했습니다(글꼴 확인)" % s['글'])
        e = dict(종류='글', 이름=s['이름'], 글=s['글'], 글꼴=s['글꼴'], 글꼴크기=f['크기'], 위_보정=f['위_보정'], 색=s.get('색') or r['색'],
                 위=r['위'], 왼쪽=r['왼쪽'], 오른쪽=r['오른쪽'], 글자높이=r['아래'] - r['위'], 맞춤=s.get('맞춤', '왼쪽'),
                 겹침=f.get('겹침'), 폭_비=f['폭_비'], 잉크_비=f.get('잉크_비'), 역할=s['역할'])
        if s.get('기울임'): e['기울임'] = True
        if s.get('기울기'): e['기울기'] = s['기울기']; e['왼쪽_보정'] = f['왼쪽_보정']
        if s.get('조각'): e['조각'] = [[x_, w_] for x_, w_ in s['조각']]
        if s.get('외곽'): e['외곽'] = s['외곽']
        if s.get('획'): e['획'] = s['획']
        if s.get('색조각'): e['색조각'] = [[t_, c_] for t_, c_ in s['색조각']]
        out.append(e)
        if s['_ul']:
            u = s['_ul']
            out.append(dict(종류='선', 이름=s['이름'] + ' 밑줄', 선=[u['왼쪽'], u['위'], u['오른쪽'], u['위']], 두께=u['두께'], 색=s.get('색') or u['색']))
    return out


# ---- 렌더 · 나란히 붙이기 ----
def render(part):
    """부품 폴더의 preview.html 사본(__BLOB__ 그림을 부품 폴더 파일로, @font-face 삽입, 장만 1080×견본 높이)을 찍어 part/render.png"""
    d = Path(part); H = 견본_높이(d)
    h = (d / 'preview.html').read_text(encoding='utf-8')
    h = re.sub(r'__BLOB__(.+?)__', lambda m: (d / m.group(1)).resolve().as_uri(), h)
    h = h.replace('</style>', font_css() + '.wrap{width:1080px!important;height:%dpx!important}.scale{transform:none!important}</style>' % H, 1)
    return html_shot(h, d / 'render.png', h=H)


def cmp(part, orig, 가림=None):
    """왼쪽 원본(장_열기 규칙)·오른쪽 렌더를 붙여 part/cmp.jpg. 가림 = 원본 쪽에서 평균색으로 덮을 상자 [[x0,y0,x1,y1],..](실명·이름표·남의 아이디 — 교훈 12)"""
    d = Path(part); H = 견본_높이(d)
    a = 장_열기(orig, H)
    if a.height != H:
        c = Image.new('RGB', (1080, H), (128, 128, 128)); c.paste(a, (0, 0)); a = c
    for x0, y0, x1, y1 in 가림 or []:
        box = (max(0, int(x0)), max(0, int(y0)), min(a.width, int(x1)), min(a.height, int(y1)))
        if box[2] > box[0] and box[3] > box[1]:
            a.paste(a.crop(box).resize((1, 1), Image.BOX).resize((box[2] - box[0], box[3] - box[1])), box)  # 평균색 한 색으로 덮음(흐림은 글자 윤곽이 남음)
    b = Image.open(d / 'render.png').convert('RGB')
    c = Image.new('RGB', (2160 + 20, H), (128, 128, 128))
    c.paste(a, (0, 0)); c.paste(b, (1100, 0))
    c.save(d / 'cmp.jpg', quality=88)
    return d / 'cmp.jpg'


def main(argv=None):
    p = 한글ArgumentParser(description=__doc__.split('\n\n')[0] + ' — 작은 확인용 명령줄(scan, glyph). 나머지는 함수로 쓴다.')
    sp = p.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('scan', help='장 그림의 영역 안 글 줄·덩어리 훑기')
    a.add_argument('장'); a.add_argument('box', nargs=4, type=int, metavar=('x0', 'y0', 'x1', 'y1'))
    a.add_argument('--gap', type=int, default=14); a.add_argument('--thr', type=int, default=100)
    g = sp.add_parser('glyph', help='글꼴에 없는 글자 찾기')
    g.add_argument('글꼴', help="예: '강원교육모두 Bold'"); g.add_argument('글')
    o = p.parse_args(argv)
    if o.cmd == 'scan':
        if not Path(o.장).exists(): 실패("장 그림이 없습니다: %s" % o.장)
        for i, row in enumerate(scan(장_열기(o.장), tuple(o.box), gap=o.gap, thr=o.thr)):
            print('줄%d y%d-%d' % (i, min(r[1] for r in row), max(r[3] for r in row)), ' | '.join('%d-%d(높이%d)%s' % (r[0], r[2], r[3] - r[1], r[4]) for r in row))
    else:
        try: f, w = fam(o.글꼴)
        except KeyError: 실패("모르는 글꼴 이름입니다: %s (예: %s)" % (o.글꼴, ', '.join(FAM)))
        print('없는 글자:', 없는_글자(f, w, o.글) or '없음')


if __name__ == '__main__':
    main()
