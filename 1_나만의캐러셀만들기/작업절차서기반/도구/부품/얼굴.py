"""얼굴 겹침 검사(공통 교훈 10): 글 뺀 렌더에서 얼굴을 찾고, 글 넣은 렌더와의 차이(= 얹힌 글)가 머리 상자 + 20px 안에 있는지 본다.

얼굴은 위치만 잰다(macOS Vision, 얼굴찾기.swift — 내려받는 모델 없음). 얼굴을 만들거나 고치지 않는다.
못 찾는 얼굴(가린 얼굴·작은 얼굴·뒷모습)이 있으니 사람이 render.png로 다시 본다.

사용: python3 -I 도구/부품/얼굴.py <글뺀.png> <render.png> [--확인 <jpg>]
  -> JSON 한 줄: [{"얼굴":[x,y,w,h], "검사상자":[x0,y0,x1,y1], "글픽셀":n, "겹침":true|false}, ...]
  얼굴을 못 찾으면 [], swift가 없으면 끝 코드 2.
"""
import sys, json, shutil, argparse, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

여백 = 20       # 교훈 10: 얼굴과 20px 이상
글_차이 = 40    # 두 렌더의 픽셀 차이가 이보다 크면 글 픽셀
겹침_최소 = 30  # 글 픽셀이 이만큼 이상이면 겹침(글자 가장자리 번짐 몇 픽셀은 무시)
_swift = Path(__file__).resolve().parent / '얼굴찾기.swift'


def 얼굴_찾기(그림):
    """그림 경로 -> [(x,y,w,h)], swift(macOS)가 없으면 None"""
    if not shutil.which('swift'): return None
    r = subprocess.run(['swift', str(_swift), str(그림)], capture_output=True, text=True)
    if r.returncode: raise SystemExit('얼굴 찾기 실패: %s' % r.stderr.strip())
    return [tuple(b) for b in json.loads(r.stdout)]


def 머리상자(x, y, w, h, W, H):
    """Vision 얼굴 상자(이마~턱)를 머리 위까지 넓히고 사방 여백 20px"""
    return (max(0, x - 여백), max(0, y - int(.3 * h) - 여백), min(W, x + w + 여백), min(H, y + h + 여백))


def 검사(바탕, 렌더, 확인=None):
    """결과 목록, 얼굴 찾기를 못 돌리면 None"""
    a, b = (np.asarray(Image.open(p).convert('RGB')).astype(int) for p in (바탕, 렌더))
    if a.shape != b.shape: raise SystemExit('두 그림 크기가 다릅니다: %s, %s' % (바탕, 렌더))
    얼굴들 = 얼굴_찾기(바탕)
    if 얼굴들 is None: return None
    글 = np.abs(a - b).max(2) > 글_차이
    결과 = []
    for f in 얼굴들:
        x0, y0, x1, y1 = 머리상자(*f, a.shape[1], a.shape[0])
        n = int(글[y0:y1, x0:x1].sum())
        결과.append({'얼굴': list(f), '검사상자': [x0, y0, x1, y1], '글픽셀': n, '겹침': n >= 겹침_최소})
    if 확인 and 결과:
        c = Image.open(렌더).convert('RGB'); d = ImageDraw.Draw(c)
        for r in 결과: d.rectangle(r['검사상자'], outline=(255, 0, 0) if r['겹침'] else (0, 200, 0), width=4)
        c.save(확인, quality=85)
    return 결과


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('글뺀'); p.add_argument('렌더'); p.add_argument('--확인', help='검사 상자를 그린 확인 그림(빨강 = 겹침)')
    o = p.parse_args()
    r = 검사(o.글뺀, o.렌더, o.확인)
    if r is None:
        print('swift(macOS)가 없어 얼굴 검사를 못 했습니다', file=sys.stderr); sys.exit(2)
    print(json.dumps(r, ensure_ascii=False))
