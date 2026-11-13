"""4단계 장 만들기: 부품 견본(견본.json·preview.html)을 틀로, 글·그림만 바꾼 장 html을 만들고 렌더한다.

출처: R/2026-11-10_캐러셀/도구/build.py(한 편 전용) 일반화 + R/2026-11-10_캐러셀2/make_slide1.py, 2026-11-10 판.

사용: 장만들기.py <약사님폴더> <편 폴더> --장 <장.json> [--부품 <부품 상위 폴더>]
  기본 부품 폴더 = <약사님폴더>/05_디자인시스템/부품
  장 높이 = 부품 견본.json `크기`, 없으면 <약사님폴더>/04_설계서/디자인시스템.json `출력_크기_기본`, 없으면 1350(너비는 늘 1080).

장.json = [{"장": 1, "부품": "PhotoCaption",
            "글": {"<요소 이름>": "새 글(줄바꿈 \\n)"},
            "그림": {"<그림 요소의 파일 이름>": "<새 그림 경로>"},
            "숨김": ["<요소 이름>"]}]
  요소 이름 = 견본.json 요소[].이름(글·상자·그림·선 어느 것이든 숨김 가능).
결과: <편 폴더>/s/<장:02d>_<부품>/slide.html(1080×장 높이 class="slide" 조각) + render.png + 그림 파일, 끝에 <편 폴더>/s/모아보기.jpg.

글 바꾸기(공통 교훈 22): 글 요소는 낱말 조각마다 원본 자리에 있으므로 새 글은 줄 단위로 다시 앉힌다.
  - 이름으로 고른 요소의 첫 조각 자리(위)·글꼴·크기·색·맞춤·자간은 견본 값. 가운데 맞춤은 줄마다 left 0·width 1080·가운데, 아니면 견본 왼쪽(오른쪽 맞춤은 오른쪽 끝).
  - 줄 간격 = 아래 같은 크기 글 요소와의 위 차이(견본 값). 없으면 글꼴크기x1.3(계산값 — 실행 때 표시).
  - 같은 줄의 다른 조각 요소는 "숨김"에 적는다(자동으로 지우지 않음).
  - 강조: **낱말** = 이름에 '굵게'·'강조'가 든 견본 글 요소의 굵기·색, ==낱말== = 이름에 '형광'이 든 견본 상자의 색(글 뒤 배경). 견본에 없으면 표기만 지운다.
  - 글꼴에 없는 글자는 프리텐다드로 그린다(dotspan). 글이 견본.json 글_자리 한도를 넘으면 경고(그래도 만든다).
장.json에 "요소"를 주면(사진에 원래 있던 상자 자리에 글을 앉힐 때 — 사진마다 상자·글 자리가 다를 때. 글꼴 크기·색은 디자인시스템.json 값만):
  {"장": 1, "부품": "PhotoCaption", "요소": [ {"종류": "바탕", ...}, {"종류": "그림", "이름": "사진", "상자": [x,y,w,h], "파일": "a.jpg"},
     {"종류": "상자", "상자": [x,y,w,h], "색": "#FFFFFF"}, {"종류": "글", "이름": "제목", "글": "...", "글꼴": "프리텐다드 Bold", "글꼴크기": 42, "색": "#000000",
      "맞춤": "가운데", "위": 100, "위_보정": 0, "왼쪽": 100, "오른쪽": 980} ]}
  견본.json의 요소 대신 이 목록으로 그린다(형식은 견본.json 요소와 같다. 위_보정 생략 = 0). "글"·"그림"·"숨김"은 이 목록에 대해 같은 뜻.
  그림 파일이 부품 폴더에 없으면 "그림"에 준 경로에서 찾는다. 글_자리 한도 경고는 하지 않는다(얼굴 겹침 검사는 그대로).
  글줄 줄임 꼴 = 상자 안 세로 가운데로 줄마다 글 요소("<이름> 1줄"…)를 만든다(상자는 그리지 않음 — "종류": "상자"를 따로):
  {"종류": "글줄", "이름": "흰 상자", "줄": ["가", "나"], "상자": [x,y,w,h], "글꼴": "프리텐다드 Regular", "글꼴크기": 42, "색": "#000000", "맞춤": "가운데", "줄간격": 50, "안쪽": 24}
  줄간격 생략 = round(글꼴크기 x1.19)([계산값] 알림). 맞춤 왼쪽이면 상자 x + 안쪽에서 시작.
얼굴 겹침 검사(공통 교훈 10): 그림이 든 장은 글 뺀 렌더에서 얼굴을 찾아 글이 머리 상자+20px 안이면 [얼굴] 경고하고
  <장 폴더>/얼굴확인.jpg(빨강 = 겹침)를 남긴다(부품/얼굴.py — macOS Vision). 못 찾는 얼굴이 있으니 사람도 render.png를 본다.
"""
import sys, re, json, shutil, html as H, argparse
from pathlib import Path
from urllib.parse import quote
_도구 = Path(__file__).resolve().parent
sys.path.insert(0, str(_도구)); sys.path.insert(0, str(_도구 / '부품'))
from 공통 import 작업폴더_경로, 하위폴더_찾기, 실패, 한글ArgumentParser  # noqa: E402
from lib import fam, dotspan, font_css, html_shot, 크롬_확인, 기본_높이, 장_크기, 계정_높이, 크기_섞임  # noqa: E402
from 견본만들기 import draw, n  # noqa: E402
from 얼굴 import 검사 as 얼굴검사  # noqa: E402
from PIL import Image  # noqa: E402


def 줄간격(요소, e):
    """(간격, 계산값인가). 견본에서 아래쪽 같은 크기 글 요소와의 위 차이, 없으면 글꼴크기x1.3"""
    s = e['글꼴크기']
    c = [x['위'] - e['위'] for x in 요소 if x['종류'] == '글' and x is not e and s * 0.5 < x['위'] - e['위'] <= s * 2.2 and abs(x['글꼴크기'] - s) <= s * 0.15]
    return (min(c), False) if c else (round(s * 1.3), True)


def 본문(e, 요소, 줄, 경고):
    """한 줄 글(**굵게**·==형광== 표기 포함) -> HTML"""
    f, w = fam(e['글꼴'])
    강조 = next((x for x in 요소 if x['종류'] == '글' and x is not e and re.search('굵게|강조', x.get('이름', ''))), None)
    형광 = next((x for x in 요소 if x['종류'] == '상자' and '형광' in x.get('이름', '') and x.get('색')), None)
    out = []
    for p in re.split(r'(\*\*.+?\*\*|==.+?==)', 줄):
        if p.startswith('**') and len(p) > 4:
            if 강조:
                bf, bw = fam(강조['글꼴'])
                out.append("<span style=\"font-family:'%s';font-weight:%d;color:%s\">%s</span>" % (bf, bw, 강조['색'], dotspan(bf, p[2:-2], bw)))
            else: 경고.append('견본에 굵게·강조 글 요소가 없어 **%s** 표기만 지웁니다' % p[2:-2]); out.append(dotspan(f, p[2:-2], w))
        elif p.startswith('==') and len(p) > 4:
            if 형광: out.append('<span style="background:%s">%s</span>' % (형광['색'], dotspan(f, p[2:-2], w)))
            else: 경고.append('견본에 형광 상자가 없어 ==%s== 표기만 지웁니다' % p[2:-2]); out.append(dotspan(f, p[2:-2], w))
        else: out.append(dotspan(f, p, w))
    return ''.join(out)


def 줄_div(e, y, body):
    f, w = fam(e['글꼴']); al = e.get('맞춤', '왼쪽')
    st = 'position:absolute;top:calc(%spx + (%spx));' % (n(y), n(e['위_보정']))
    # ponytail: 줄마다 제 가운데서 돌림 — 여러 줄이 한 덩어리로 기운 원본이면 줄 간격이 조금 다름
    tf = ('translateX(-50%) ' if al == '가운데' else '') + ('rotate(%sdeg)' % n(e['기울기']) if e.get('기울기') else '')
    if tf: st += 'transform:%s;transform-origin:50%% 50%%;' % tf.strip()
    if al == '가운데': st += 'left:calc((%spx + %spx) / 2);' % (n(e['왼쪽']), n(e['오른쪽']))  # 견본만들기 draw()와 같은 기준(글 자리 가운데)
    elif al == '오른쪽': st += 'left:0px;width:%spx;text-align:right;' % n(e['오른쪽'])
    else: st += 'left:%spx;' % n(e['왼쪽'])
    st += "font-family:'%s', sans-serif;font-size:%spx;font-weight:%d;line-height:1;color:%s;white-space:pre;font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0;" % (f, n(e['글꼴크기']), w, e['색'])
    if e.get('기울임'): st += 'font-style:italic;'
    if e.get('자간'): st += 'letter-spacing:%spx;' % n(e['자간'])
    if e.get('획'): st += '-webkit-text-stroke:%spx %s;' % (n(e['획'][0]), e['획'][1])
    if e.get('외곽'): st += 'text-shadow:' + ','.join('%spx %spx %spx %s' % (n(a), n(b), n(c), d) for a, b, c, d in e['외곽']) + ';'
    return '<div style="%s">%s</div>' % (st, body)


def 자리_경고(견본, 이름, 줄들):
    """견본.json 글_자리[이름] 문장에서 'N~M자'·'N~M줄' 한도를 읽어 넘으면 경고 목록(문장 모양이 다르면 건너뜀)"""
    자리 = 견본.get('글_자리'); t = 자리.get(이름) if isinstance(자리, dict) else None
    if not isinstance(t, str): return []
    out = []
    for 단위, 값 in (('자', max((len(re.sub(r'\*\*|==', '', x)) for x in 줄들), default=0)), ('줄', len(줄들))):
        m = re.search(r'(\d+)(?:\s*[~-]\s*(\d+))?\s*' + 단위, t)
        if m and 값 > int(m.group(2) or m.group(1)): out.append('글 자리 한도 초과: %s — %s 최대 %s%s인데 %d%s(자리: %s)' % (이름, '한 줄' if 단위 == '자' else '줄 수', m.group(2) or m.group(1), 단위, 값, 단위, t))
    return out


def 글줄_펼치기(요소, 장번호, 경고):
    """장.json "요소" 목록 복사본: 글은 위_보정 기본 0, "글줄" 도우미는 상자 안 세로 가운데 글 요소들로 펼친다"""
    out = []
    for e in 요소:
        if e.get('종류') == '글줄':
            줄들 = e['줄']; x, y, w, h = e['상자']; 크기 = e['글꼴크기']; 안 = e.get('안쪽', 0)
            gap = e.get('줄간격')
            if gap is None: gap = round(크기 * 1.19); 경고.append('[계산값] %s장 %s: 줄 간격 %d(글꼴크기 %s x1.19)' % (장번호, e['이름'], gap, 크기))
            위 = y + (h - ((len(줄들) - 1) * gap + 크기)) / 2  # line-height:1이라 글 상자 높이 = 글꼴크기
            for i, t in enumerate(줄들):
                out.append({'종류': '글', '이름': '%s %d줄' % (e['이름'], i + 1), '글': t, '글꼴': e['글꼴'], '글꼴크기': 크기, '색': e['색'], '맞춤': e.get('맞춤', '왼쪽'),
                            '위': 위 + i * gap, '위_보정': 0, '왼쪽': x + 안, '오른쪽': x + w - 안})
        else: out.append(dict(e, 위_보정=e.get('위_보정', 0)) if e.get('종류') == '글' else e)
    return out


def 장_조각(견본, 틀_html, 장, 경고, 글뺌=False, 높이=기본_높이):
    """견본 한 장의 slide 조각 html(그림은 __BLOB__파일__ 자리표시)과 쓸 그림 {파일이름: 원래 경로 또는 None}. 글뺌이면 글 요소 없이(얼굴 검사용)"""
    요소 = 글줄_펼치기(장['요소'], 장['장'], 경고) if '요소' in 장 else 견본['요소']; 이름 = {e.get('이름') for e in 요소}; 파일 = {e['파일'] for e in 요소 if e['종류'] == '그림'}
    글, 그림, 숨김 = 장.get('글') or {}, 장.get('그림') or {}, set(장.get('숨김') or [])
    for k in list(글) + list(숨김):
        if k not in 이름: 실패("%s장: 견본에 없는 요소 이름입니다: %s" % (장['장'], k))
    for k in 그림:
        if k not in 파일: 실패("%s장: 견본에 없는 그림 파일 이름입니다: %s (있는 것: %s)" % (장['장'], k, ', '.join(sorted(파일)) or '없음'))
    m = re.search(r'<div class="slide"[^>]*>', 틀_html)
    if not m: 실패('preview.html에 class="slide"가 없습니다')
    body = []; 쓸그림 = {}
    for e in 요소:
        if e['종류'] == '바탕' or e.get('이름') in 숨김 or (글뺌 and e['종류'] == '글'): continue
        if e['종류'] == '글' and e['이름'] in 글:
            줄들 = str(글[e['이름']]).split('\n'); gap, 계산 = 줄간격(요소, e)
            if 계산 and len(줄들) > 1: 경고.append('[계산값] %s장 %s: 줄 간격 %d(글꼴크기 %s x1.3)' % (장['장'], e['이름'], gap, e['글꼴크기']))
            if '요소' not in 장: 경고.extend(자리_경고(견본, e['이름'], 줄들))  # 요소를 준 장은 자리 이름이 달라 건너뜀
            body += [줄_div(e, e['위'] + i * gap, 본문(e, 요소, t, 경고)) for i, t in enumerate(줄들)]
        elif e['종류'] == '그림':
            새 = 그림.get(e['파일']); 이름_ = Path(새).name if 새 else e['파일']
            쓸그림[이름_] = 작업폴더_경로(새) if 새 else None
            body.append(draw(e, 높이).replace('__BLOB__%s__' % e['파일'], '__BLOB__%s__' % 이름_))
        else:
            x = draw(e, 높이)
            if x: body.append(x)
    return m.group(0) + ''.join(body) + '</div>', 쓸그림


def main(argv=None):
    p = 한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('약사님폴더', help='약사님 폴더(작업 폴더 기준 상대 경로 가능)'); p.add_argument('편폴더', help='편 폴더(없으면 만듦). 결과는 <편 폴더>/s/ 안')
    p.add_argument('--장', required=True, help='장.json 경로'); p.add_argument('--부품', help='부품 상위 폴더(기본: <약사님폴더>/05_디자인시스템/부품)')
    o = p.parse_args(argv)
    약사 = 작업폴더_경로(o.약사님폴더)
    if o.부품: 부품 = 작업폴더_경로(o.부품)
    else:
        디 = 하위폴더_찾기(약사, '05_'); 부품 = 디 / '부품' if 디 else None
    if not 부품 or not 부품.is_dir(): 실패("부품 폴더를 찾을 수 없습니다: %s (--부품으로 지정)" % (부품 or 약사))
    if not 작업폴더_경로(o.장).is_file(): 실패("장.json이 없습니다: %s" % o.장)
    try: 장들 = json.loads(작업폴더_경로(o.장).read_text(encoding='utf-8'))
    except json.JSONDecodeError as e: 실패("장.json을 읽지 못했습니다(JSON 오류): %s" % e)
    if not isinstance(장들, list) or not 장들: 실패("장.json은 장 목록([{...}, ...])이어야 합니다")
    크롬_확인()
    계정높이 = 계정_높이(약사); 높이들 = {}  # 부품별 장 높이 = 견본 `크기`, 없으면 계정 기본
    for 장 in 장들:
        f = 부품 / 장['부품'] / '견본.json'
        if f.is_file():
            견 = json.loads(f.read_text(encoding='utf-8')); 높이들[장['부품']] = 장_크기(견)[1] if 견.get('크기') else 계정높이
    섞임 = 크기_섞임(높이들)
    if 섞임: 실패(섞임)
    s = 작업폴더_경로(o.편폴더) / 's'; 경고 = []; 렌더 = []; 얼굴못함 = []; 얼굴없음 = []
    for 장 in sorted(장들, key=lambda x: x['장']):
        d = 부품 / 장['부품']
        if not (d / '견본.json').is_file() or not (d / 'preview.html').is_file(): 실패("%s장: 부품 폴더에 견본.json·preview.html이 없습니다: %s" % (장['장'], d))
        견본 = json.loads((d / '견본.json').read_text(encoding='utf-8'))
        높이 = 높이들[장['부품']]
        조각, 그림 = 장_조각(견본, (d / 'preview.html').read_text(encoding='utf-8'), 장, 경고, 높이=높이)
        out = s / ('%02d_%s' % (장['장'], 장['부품'])); out.mkdir(parents=True, exist_ok=True)
        for 이름, 원 in 그림.items():
            src = 원 or d / 이름
            if not src.is_file(): 실패("%s장: 그림 파일이 없습니다: %s" % (장['장'], src))
            if src.resolve() != (out / 이름).resolve(): shutil.copy2(src, out / 이름)
        (out / 'slide.html').write_text(re.sub(r'__BLOB__(.+?)__', lambda m: quote(m.group(1)), 조각) + '\n', encoding='utf-8')
        page = lambda x: '<!doctype html><meta charset="utf-8"><style>body{margin:0}%s</style>' % font_css() + re.sub(r'__BLOB__(.+?)__', lambda m: H.escape((out / m.group(1)).resolve().as_uri(), True), x)
        html_shot(page(조각), out / 'render.png', h=높이); 렌더.append(out / 'render.png')
        if 그림:
            뺌 = out / '_글뺌.png'; html_shot(page(장_조각(견본, (d / 'preview.html').read_text(encoding='utf-8'), 장, [], 글뺌=True, 높이=높이)[0]), 뺌, h=높이)
            r = 얼굴검사(뺌, out / 'render.png', out / '얼굴확인.jpg'); 뺌.unlink()
            if r is None: 얼굴못함.append(장['장'])
            elif not r: 얼굴없음.append(장['장'])
            for x in r or []:
                if x['겹침']: 경고.append('[얼굴] %s장: 글이 얼굴(머리 위~턱)+20px 안에 있습니다(글 픽셀 %d) — %s 확인, 교훈 10대로 사진·글 자리 옮기기' % (장['장'], x['글픽셀'], out / '얼굴확인.jpg'))
        print('쓴 장:', out / 'slide.html', '·', out / 'render.png')
    칸높이 = round(360 * Image.open(렌더[0]).height / 1080)  # 첫 장 기준(한 편은 같은 크기) — 1350이면 450
    sheet = Image.new('RGB', (360 * len(렌더), 칸높이), 'white')
    for i, r in enumerate(렌더): sheet.paste(Image.open(r).convert('RGB').resize((360, 칸높이)), (360 * i, 0))
    sheet.save(s / '모아보기.jpg', quality=88); print('쓴 파일:', s / '모아보기.jpg')
    for w in 경고: print(w if w.startswith('[') else '[경고] ' + w, file=sys.stderr)
    if 얼굴못함: print('[경고] 얼굴 검사 못 함(swift·macOS Vision 없음): %s장 — 사람이 render.png로 확인하세요.' % ', '.join(map(str, 얼굴못함)), file=sys.stderr)
    if 얼굴없음: print('얼굴을 찾지 못한 사진 장: %s장 — 가린·옆 얼굴은 못 찾을 수 있으니 render.png로 한 번 보세요.' % ', '.join(map(str, 얼굴없음)))


if __name__ == '__main__':
    main()
