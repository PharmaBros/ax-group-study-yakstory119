"""글 자리마다 후보 글꼴을 원본 잉크에 겹쳐(IoU) 재서 1위 고르기 + 역할별 평균 1위.

출처: R/2026-11-10_디자인시스템/도구/_tools_B/mh.py(measure·pick) + 글꼴겹침_fc.py + 새방식_공용도구/글꼴비교/run.py·report.py + _tools_B/swap.py, 2026-11-10 판.
ponytail: 겹침은 잉크 상자 왼쪽 위를 맞춰 크롬으로 그린 글과 원본 잉크 마스크를 견준 근사(글 한 줄 기준).

사용: 글꼴겹침.py <원본 장 jpg> <글자리.json> [--후보 이름 ...] [--표 결과.md] [--그림 비교.jpg]
글자리.json = [{"이름":"제목","상자":[x0,y0,x1,y1],"글":"한 줄 글","역할":"(생략하면 이름)"}]  — 상자는 1080 너비 기준 장 좌표
후보 이름은 lib.FAM 이름 ('강원교육모두 Bold' 등). 기본 후보 = 강원교육모두 Bold·Light, 싱글데이, 도현, 나눔스퀘어라운드 Regular·Bold·ExtraBold,
  카페24 당당해, 프리텐다드 Regular·Bold·Black, 지마켓 Medium.
결과 표(md)는 화면에 나오고, --표로 파일에도 쓴다. --그림은 글 자리마다 원본 | 1위 글꼴 렌더를 나란히 붙인 jpg.
"""
import sys, json, argparse, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from lib import fam, ink, 장_열기, text_items, html_shot, font_css, FONT, 크롬_확인, 실패, 한글ArgumentParser, 기본_높이  # noqa: E402
import 견본만들기  # noqa: E402

기본후보 = ['강원교육모두 Bold', '강원교육모두 Light', '싱글데이', '도현', '나눔스퀘어라운드 Regular', '나눔스퀘어라운드 Bold',
            '나눔스퀘어라운드 ExtraBold', '카페24 당당해', '프리텐다드 Light', '프리텐다드 Regular', '프리텐다드 Bold', '프리텐다드 Black', '지마켓 Medium']


def 재기(im, 자리, 후보, chunk=16):
    """후보마다 자리별 글 요소(겹침 포함) 목록 -> {후보: [요소...]}"""
    res = {}
    for nm in 후보:
        f, w = fam(nm)
        els = []
        for j in range(0, len(자리), chunk):
            sp = [dict(s, box=tuple(s['상자']), fam=f, w=w, 글꼴=nm, 역할=s.get('역할', s['이름'])) for s in 자리[j:j + chunk]]
            with tempfile.TemporaryDirectory() as t:
                els += [e for e in text_items(im, sp, t) if e['종류'] == '글']
        res[nm] = els
    return res


def 표_만들기(자리, 후보, res):
    ov = lambda nm, i: res[nm][i]['겹침'] or 0
    굵 = lambda nm, i: res[nm][i].get('잉크_비') or 0
    맞음 = lambda nm, i: 0.8 <= 굵(nm, i) <= 1.25
    L = ['## 글 자리마다 겹침(IoU)', '', '잉크_비 = 원본 잉크 / 그린 잉크(1보다 크면 원본 획이 더 굵음). 0.8~1.25 밖이면 겹침 1위라도 굵기가 다르니 "굵기 맞는 1위"를 쓴다.', '',
         '| 이름 | 글 | ' + ' | '.join(후보) + ' | 1위(잉크_비) | 굵기 맞는 1위 |', '|---|---|' + '---|' * (len(후보) + 2)]
    for i, s in enumerate(자리):
        top = max(후보, key=lambda nm: ov(nm, i))
        ok = [nm for nm in 후보 if 맞음(nm, i)]
        top2 = max(ok, key=lambda nm: ov(nm, i)) if ok else None
        L.append('| %s | %s | ' % (s['이름'], s['글'].replace('|', '\\|')) + ' | '.join('%.3f' % ov(nm, i) for nm in 후보)
                 + ' | %s (%.2f) | %s |' % (top, 굵(top, i), '같음' if top2 == top else ('%s (%.3f, %.2f)' % (top2, ov(top2, i), 굵(top2, i)) if top2 else '없음 — 후보를 넓히거나 원본 잉크 조각')))
    roles = {}
    for i, s in enumerate(자리): roles.setdefault(s.get('역할', s['이름']), []).append(i)
    L += ['', '## 역할별 평균 겹침', '', '| 역할 | 글 수 | 1위 | 평균 | 2위 | 평균 |', '|---|---|---|---|---|---|']
    for r, idx in roles.items():
        mean = sorted(((sum(ov(nm, i) for i in idx) / len(idx), nm) for nm in 후보), reverse=True)
        L.append('| %s | %d | ' % (r, len(idx)) + ' | '.join('%s | %.3f' % (m[1], m[0]) for m in mean[:2]) + ' |')
    return '\n'.join(L) + '\n'


def 그림_만들기(im, 자리, 후보, res, out, pad=20, 높이=기본_높이):
    """자리마다 [원본 | 자리별 1위 글꼴 렌더] 가로로 붙여 세로로 쌓는다. 렌더는 크롬 한 번(바탕 상자 위에 글)."""
    els = []; best = []
    for i, s in enumerate(자리):
        nm = max(후보, key=lambda n: res[n][i]['겹침'] or 0); best.append(nm)
        b = s['상자']; r = ink(im, tuple(b), 150)
        els.append({'종류': '상자', '상자': [b[0] - pad, b[1] - pad, b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad], '색': r['바탕'] if r else '#808080'})
        els.append(res[nm][i])
    body = ''.join(x for x in (견본만들기.draw(e) for e in els) if x)
    h = '<!doctype html><meta charset=utf-8><style>body{margin:0}%s</style><div style="position:relative;width:1080px;height:%dpx;background:#808080">%s</div>' % (font_css(), 높이, body)
    with tempfile.TemporaryDirectory() as t:
        rp = html_shot(h, Path(t) / 'r.png', h=높이)
        rim = Image.open(rp).convert('RGB')
    lab = ImageFont.truetype(str(FONT / 'NanumSquareRoundB.ttf'), 22)
    tiles = []
    for s, nm in zip(자리, best):
        b = s['상자']; box = (max(0, b[0] - pad), max(0, b[1] - pad), min(1080, b[2] + pad), min(높이, b[3] + pad))
        a = im.crop(box); c = rim.crop(box)
        t_ = Image.new('RGB', (a.width * 2 + 30, a.height + 36), 'white'); d = ImageDraw.Draw(t_)
        d.text((4, 6), '%s — 원본 | %s' % (s['이름'], nm), font=lab, fill=(200, 0, 0))
        t_.paste(a, (0, 36)); t_.paste(c, (a.width + 30, 36)); tiles.append(t_)
    W_ = max(t.width for t in tiles); can = Image.new('RGB', (W_, sum(t.height for t in tiles)), 'white'); y = 0
    for t in tiles: can.paste(t, (0, y)); y += t.height
    can.save(out, quality=90)


def main(argv=None):
    p = 한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('장', help='원본 장 jpg'); p.add_argument('글자리', help='글자리.json')
    p.add_argument('--후보', nargs='+', help='후보 글꼴 이름들(기본: 12개)'); p.add_argument('--표', help='표(md)를 쓸 파일'); p.add_argument('--그림', help='비교 그림(jpg)을 쓸 파일')
    p.add_argument('--높이', type=int, default=기본_높이, help='장 높이(기본 %d, 너비 1080)' % 기본_높이)
    o = p.parse_args(argv)
    for f in (o.장, o.글자리):
        if not Path(f).is_file(): 실패("파일이 없습니다: %s" % f)
    try: 자리 = json.loads(Path(o.글자리).read_text(encoding='utf-8'))
    except json.JSONDecodeError as e: 실패("글자리.json을 읽지 못했습니다(JSON 오류): %s" % e)
    if not isinstance(자리, list) or not 자리 or not all({'이름', '상자', '글'} <= set(s) and len(s['상자']) == 4 for s in 자리):
        실패('글자리.json은 [{"이름","상자":[x0,y0,x1,y1],"글"}, ...] 이어야 합니다')
    후보 = o.후보 or 기본후보
    for nm in 후보:
        try: fam(nm)
        except KeyError: 실패("모르는 글꼴 이름입니다: %s" % nm)
    크롬_확인()
    im = 장_열기(o.장, o.높이)
    res = 재기(im, 자리, 후보)
    표 = 표_만들기(자리, 후보, res)
    print(표)
    if o.표: Path(o.표).write_text(표, encoding='utf-8'); print('쓴 파일:', o.표)
    if o.그림: 그림_만들기(im, 자리, 후보, res, o.그림, 높이=o.높이); print('쓴 파일:', o.그림)


if __name__ == '__main__':
    main()
