"""원본 장 하나에서 부품 견본 만들기: 요소.json -> 견본.json · preview.html · render.png · cmp.jpg, 끝에 글 위치 확인.

출처: R/2026-11-10_디자인시스템/도구/_tools_B/build.py + rc.py + chkpos.py, 2026-11-10 판.

사용: 견본만들기.py <요소.json> <원본 장 jpg> <부품 폴더>

요소.json = 견본.json에서 렌더 결과만 빠진 입력. 맨 위 칸은 견본.json 그대로 통과한다:
  json_자리(예 "부품.표.견본"), 화면(부품 영문 이름), 모양_계열, 근거, 근거_편, 고정, 바꿔_끼우는_자리,
  편_안_자리(예 "1장 전용"), 글_자리(글 자리마다 한 줄 글자 수·줄 수 범위)  — 빠지면 빈 값으로 두고 경고.
  원본_가림: [[x0,y0,x1,y1],..] — cmp.jpg 원본 쪽에서 흐릴 자리(실명·이름표·남의 아이디, 교훈 12). 렌더 쪽은 깔개·조각 그림에서 가린다.
  크기: [1080, H](선택, 없으면 [1080, 1350]) — 장 높이. 견본.json에도 그대로 남아 render·장만들기·블라인드가 읽는다.
  요소: 위에서 아래로 그릴 목록. 좌표는 모두 1080×H 장 기준(H 기본 1350).
  {"종류":"바탕","색":"#FFF"}                  (세로_번짐 [[y,색],..] · 원형_번짐 {중심,반지름,색} 선택)
  {"종류":"상자","이름":..,"상자":[x,y,w,h],"색":..,"모서리":..,"테두리":[두께,색],"기울기":도}
  {"종류":"선","선":[x0,y0,x1,y1],"두께":..,"색":..,"점선":[획,틈]}
  {"종류":"다각형","점":[[x,y],..],"색":..}
  {"종류":"그림","상자":[x,y,w,h],"파일":"부품 폴더 안 파일 이름","모서리":..}   (파일은 렌더 때만 실제 경로로 바뀜)
  {"종류":"글","이름":..,"글":"한 줄","글꼴":"강원교육모두 Bold","잴_상자":[x0,y0,x1,y1],"역할":..,
   "맞춤":"왼쪽|가운데|오른쪽","색":(생략하면 잰 값),"기울임":true,"기울기":도(시계 방향, 글 줄이 기운 각도 — 잴_상자는 기운 글 전체를 감싸게),"밑줄":true,"조각":[[글,굵기],..],"색조각":[[글,색],..],"외곽":..,"획":..}
   글은 잴_상자 안 잉크를 재서 위·왼쪽·오른쪽·글자높이·글꼴크기·위_보정·폭_비·겹침·잉크_비를 채운다(글꼴 이름은 lib.FAM의 것).
   잉크_비 = 원본 잉크 넓이 / 그린 잉크 넓이. 0.8~1.25 밖이면 획 굵기가 다르다(겹침만으로는 안 잡힘) — 끝에 [굵기] 경고.
   이미 잰 글(글꼴크기·위·왼쪽·오른쪽·글자높이·위_보정이 다 있으면 잴_상자 없이)은 그대로 쓴다.
글꼴에 없는 글자(강원교육모두의 · 등)는 그 글자만 프리텐다드로 그려진다.
"""
import sys, json, html as H, tempfile, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import *  # noqa: E402,F401
from lib import fam, ink, 장_열기, text_items, render, cmp, 실패, 한글ArgumentParser, dotspan, 크롬_확인, 기본_높이, 장_크기  # noqa: E402

필수칸 = ('json_자리', '편_안_자리', '글_자리')
잰값 = ('글꼴크기', '위', '왼쪽', '오른쪽', '글자높이', '위_보정')


def n(v):  # 숫자 -> 글자 (정수면 .0 없이)
    return '%g' % v


def draw(e, 높이=기본_높이):
    k = e['종류']
    if k == '바탕':
        return None
    if k == '글':
        f, w = fam(e['글꼴'])
        st = "position:absolute;top:calc(%spx + (%spx));" % (n(e['위']), n(e['위_보정']))
        al = e.get('맞춤', '왼쪽')
        if e.get('기울기'): st += "left:calc(%spx + (%spx));transform:rotate(%sdeg);transform-origin:50%% 50%%;" % (n(e['왼쪽']), n(e.get('왼쪽_보정', 0)), n(e['기울기']))
        elif al == '가운데': st += "left:calc((%spx + %spx) / 2);transform:translateX(-50%%);" % (n(e['왼쪽']), n(e['오른쪽']))
        elif al == '오른쪽': st += "left:%spx;transform:translateX(-100%%);" % n(e['오른쪽'])
        else: st += "left:%spx;" % n(e['왼쪽'])
        st += "font-family:'%s', sans-serif;font-size:%spx;font-weight:%d;line-height:1;color:%s;white-space:pre;font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0;" % (f, n(e['글꼴크기']), w, e['색'])
        if e.get('기울임'): st += 'font-style:italic;'
        if e.get('자간'): st += 'letter-spacing:%spx;' % n(e['자간'])
        if e.get('획'): st += '-webkit-text-stroke:%spx %s;' % (n(e['획'][0]), e['획'][1])
        if e.get('외곽'): st += 'text-shadow:' + ','.join('%spx %spx %spx %s' % (n(a_), n(b_), n(c_), d_) for a_, b_, c_, d_ in e['외곽']) + ';'
        if e.get('조각'):
            body = ''.join('<span style="font-weight:%d">%s</span>' % (w_, H.escape(x_)) for x_, w_ in e['조각'])
        elif e.get('색조각'):
            body = ''.join('<span style="color:%s">%s</span>' % (c_, dotspan(f, t_, w)) for t_, c_ in e['색조각'])
        else: body = dotspan(f, e['글'], w)
        return '<div style="%s">%s</div>' % (st, body)
    if k == '상자':
        x, y, w, h = e['상자']
        st = "position:absolute;left:%spx;top:%spx;width:%spx;height:%spx;box-sizing:border-box;" % (n(x), n(y), n(w), n(h))
        if e.get('색'): st += 'background:%s;' % e['색']
        if e.get('모서리'): st += 'border-radius:%spx;' % n(e['모서리'])
        if e.get('테두리'): st += 'border:%spx solid %s;' % (n(e['테두리'][0]), e['테두리'][1])
        if e.get('기울기'): st += 'transform:rotate(%sdeg);' % n(e['기울기'])
        return '<div style="%s"></div>' % st
    if k == '선':
        x0, y0, x1, y1 = e['선']; t = e['두께']
        if y0 == y1 or e.get('가로'):
            st = "position:absolute;left:%spx;top:%spx;width:calc(%spx - %spx);height:%spx;" % (n(x0), n(y0), n(x1), n(x0), n(t)); ang = '90deg'
        else:
            st = "position:absolute;left:%spx;top:%spx;width:%spx;height:calc(%spx - %spx);" % (n(x0), n(y0), n(t), n(y1), n(y0)); ang = '180deg'
        if e.get('점선'):
            d, g = e['점선']
            st += "background:repeating-linear-gradient(%s,%s 0 %spx,transparent %spx %spx);" % (ang, e['색'], n(d), n(d), n(d + g))
        else: st += 'background:%s;' % e['색']
        return '<div style="%s"></div>' % st
    if k == '다각형':  # 화살표 머리 등: 점은 장 좌표
        pts = ' '.join('%s,%s' % (n(x), n(y)) for x, y in e['점'])
        fill = ('fill="%s"' % e['색']) if e.get('색') else 'fill="none"'
        stk = ('stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (e['테두리'][1], n(e['테두리'][0]))) if e.get('테두리') else ''
        return '<svg width="1080" height="%d" style="position:absolute;left:0;top:0" viewBox="0 0 1080 %d"><polygon points="%s" %s %s/></svg>' % (높이, 높이, pts, fill, stk)
    if k == '그림':
        x, y, w, h = e['상자']
        st = "position:absolute;left:%spx;top:%spx;width:%spx;height:%spx;object-fit:%s;" % (n(x), n(y), n(w), n(h), e.get('맞춤_방식', 'cover'))
        if e.get('모서리'): st += 'border-radius:%spx;' % n(e['모서리'])
        return '<img src="__BLOB__%s__" alt="" style="%s">' % (e['파일'], st)
    실패("모르는 요소 종류입니다: %s" % k)


def 글_재기(im, 요소):
    """요소 목록의 글 중 잴_상자가 있고 값이 덜 찬 것을 재서 채운다. 밑줄이면 선 요소를 바로 뒤에 끼운다."""
    todo = [(i, e) for i, e in enumerate(요소) if e['종류'] == '글' and not all(k in e for k in 잰값)]
    if not todo: return 요소
    for i, e in todo:
        if not e.get('잴_상자'): 실패("글 '%s' 에 잴_상자가 없습니다(잰 값도 없음)" % e.get('글', '?'))
    res = {}
    for j in range(0, len(todo), 16):  # 크롬 한 번에 16개씩
        sub = todo[j:j + 16]
        specs = []
        for _, e in sub:
            try: f, w = fam(e['글꼴'])
            except KeyError: 실패("모르는 글꼴 이름입니다: %s" % e['글꼴'])
            specs.append(dict(e, box=tuple(e['잴_상자']), fam=f, w=w, 역할=e.get('역할', e.get('이름', '글'))))
        with tempfile.TemporaryDirectory() as t:
            els = text_items(im, specs, t)
        it = iter(sub); cur = None
        for el in els:
            if el['종류'] == '글': cur = next(it)[0]; res.setdefault(cur, []).append(el)
            else: res[cur].append(el)
    out = []
    for i, e in enumerate(요소):
        if i not in res: out.append(e); continue
        g = res[i][0]
        keep = {k: v for k, v in e.items() if k != '잴_상자'}
        keep.update({k: g[k] for k in g if k not in e or k in 잰값 + ('겹침', '폭_비', '잉크_비', '왼쪽_보정') or (k == '색' and not e.get('색'))})
        keep.setdefault('역할', g['역할'])
        out.append(keep); out.extend(res[i][1:])
    return out


def write_part(d, spec, 요소):
    """견본.json·preview.html 쓰기. spec = 요소 빼고 나머지 칸"""
    spec = dict(spec); spec['요소'] = [{k: v for k, v in e.items() if not k.startswith('_') and k != '마스크'} for e in 요소]
    (d / '견본.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
    b0 = next((e for e in 요소 if e['종류'] == '바탕'), None)
    if b0 is None: 실패("요소에 종류 '바탕'이 없습니다")
    bg = b0['색']
    if b0.get('세로_번짐'):
        bg = 'linear-gradient(180deg,' + ','.join('%s %spx' % (c, n(y)) for y, c in b0['세로_번짐']) + ')'
    if b0.get('원형_번짐'):
        o = b0['원형_번짐']
        bg = 'radial-gradient(circle %spx at %spx %spx,%s,transparent),' % (n(o['반지름']), n(o['중심'][0]), n(o['중심'][1]), o['색']) + bg
    높이 = 장_크기(spec)[1]
    body = ''.join(x for x in (draw(e, 높이) for e in 요소) if x)
    쓴글꼴 = sorted({fam(e['글꼴'])[0] for e in 요소 if e['종류'] == '글'})
    화면 = spec.get('화면', d.name)
    meta = ' · '.join(str(spec[k]) for k in ('모양_계열', '근거', '편_안_자리') if spec.get(k))
    h = '''<!-- @dsCard group="%s" height=760 subtitle="%s" -->
<!doctype html>
<html><head><meta charset="utf-8"><title>%s</title>
<style>
body{margin:0;color:#222}
.wrap{width:480px;height:600px;overflow:hidden;position:relative}
.scale{position:absolute;left:0;top:0;width:1080px;height:%dpx;transform:scale(0.444444);transform-origin:0 0}
.meta{font:12px/1.5 sans-serif;color:#555;margin:8px 0 0;max-width:480px}
.flag{font:12px/1.4 sans-serif;color:#a40;margin:4px 0 0;max-width:480px}
</style></head>
<body>
<div class="wrap"><div class="scale"><div class="slide" style="position:relative;width:1080px;height:%dpx;overflow:hidden;background:%s">%s</div></div></div>
<p class="meta">%s</p>
<script>(function(){var 쓴=%s;if(!document.fonts)return;document.fonts.ready.then(function(){var 있음={};document.fonts.forEach(function(f){if(f.status==='loaded')있음[f.family.replace(/["']/g,'')]=1;});쓴.forEach(function(f){if(!있음[f]){var p=document.createElement('p');p.className='flag';p.textContent='글꼴 못 부름 — '+f+'(기본 고딕으로 그림)';document.body.appendChild(p);}});});})();</script>
</body></html>
''' % (H.escape('부품 — ' + 화면, True), H.escape(meta, True), H.escape(화면), 높이, 높이, bg, body, H.escape(meta), json.dumps(쓴글꼴, ensure_ascii=False))
    (d / 'preview.html').write_text(h, encoding='utf-8')


def chkpos(원본, render_png, 요소, 허용=6, 높이=기본_높이):
    """글마다 원본과 렌더의 잉크 상자를 비교해 어긋남(px)을 출력. 어긋난 글 수를 돌려줌"""
    b = Image.open(render_png).convert('RGB')
    bad = 0
    for e in 요소:
        if e['종류'] != '글': continue
        pad = 14
        box = (max(0, e['왼쪽'] - pad), max(0, e['위'] - pad), min(1080, e['오른쪽'] + pad), min(높이, e['위'] + e['글자높이'] + pad))
        ra = ink(원본, box, 150); rb = ink(b, box, 150)
        if not ra or not rb: print('? 잉크를 못 찾음:', e['글']); continue
        dx0 = rb['왼쪽'] - ra['왼쪽']; dx1 = rb['오른쪽'] - ra['오른쪽']; dy = rb['위'] - ra['위']
        if max(abs(dx0), abs(dx1), abs(dy)) > 허용:
            bad += 1; print('어긋남 %s dx0 %d dx1 %d dy %d' % (e['글'][:14], dx0, dx1, dy))
    print('글 위치 확인: 어긋남(>%dpx) %d개 / 글 %d개' % (허용, bad, sum(e['종류'] == '글' for e in 요소)))
    for e in 요소:
        v = e.get('잉크_비') if e['종류'] == '글' else None
        if v and not 0.8 <= v <= 1.25: print('[굵기] %s: 원본이 %s(잉크_비 %.2f, 글꼴 %s) — 다른 굵기 후보로 다시 재기' % (e['글'][:14], '더 굵음' if v > 1 else '더 가늚', v, e['글꼴']))
    return bad


def main(argv=None):
    p = 한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('요소json', help='요소.json 경로'); p.add_argument('장', help='원본 장 jpg'); p.add_argument('부품폴더', help='결과를 쓸 부품 폴더(없으면 만듦)')
    o = p.parse_args(argv)
    for f in (o.요소json, o.장):
        if not Path(f).is_file(): 실패("파일이 없습니다: %s" % f)
    크롬_확인()
    try: spec = json.loads(Path(o.요소json).read_text(encoding='utf-8'))
    except json.JSONDecodeError as e: 실패("요소.json을 읽지 못했습니다(JSON 오류): %s" % e)
    if not isinstance(spec.get('요소'), list): 실패("요소.json에 '요소' 목록이 없습니다")
    요소 = spec.pop('요소')
    for k in 필수칸:
        if k not in spec:
            spec[k] = ''; print('[경고] 요소.json에 %s 칸이 없어 빈 값으로 둡니다' % k, file=sys.stderr)
    d = Path(o.부품폴더); d.mkdir(parents=True, exist_ok=True)
    높이 = 장_크기(spec)[1]
    im = 장_열기(o.장, 높이)
    요소 = 글_재기(im, 요소)
    write_part(d, spec, 요소)
    render(d); cmp(d, o.장, spec.get('원본_가림'))
    for f in ('견본.json', 'preview.html', 'render.png', 'cmp.jpg'): print('쓴 파일:', d / f)
    chkpos(im, d / 'render.png', 요소, 높이=높이)


if __name__ == '__main__':
    main()
