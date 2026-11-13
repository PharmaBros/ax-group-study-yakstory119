"""만든 장과 원본 장을 같은 높이로 나란히 붙인 비교 그림을 만든다(4단계 비교·수정용).

사용: python3 -I 6_도구/나란히보기.py <만든 그림> <원본 그림> <출력.jpg> [--폭 1080]
  예) python3 -I 6_도구/나란히보기.py 7_결과/기록/그림/NumberList.png 7_결과/기록/근거1080/NumberList.png 7_결과/기록/비교/NumberList_1회.jpg
- 원본은 가로를 --폭(기본 1080)에 맞춰 줄이고 늘린다(1:1 원본이면 1080×1080).
- 두 그림은 위끝을 맞춰 왼쪽 = 만든 것, 오른쪽 = 원본으로 붙이고, 위에 'MADE / ORIGINAL' 글을 단다(왼쪽 = 만든 것).
- 결과 그림은 Read로 열어 눈으로 본다.
"""
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow가 없습니다. `python3 -m pip install --user Pillow`로 설치해 주세요.")

인자 = sys.argv[1:]
폭 = 1080
if "--폭" in 인자:
    i = 인자.index("--폭"); 폭 = int(인자[i + 1]); del 인자[i:i + 2]
if len(인자) != 3:
    print(__doc__); sys.exit(2)
만든, 원본, 출력 = (Path(x) for x in 인자)


def 맞추기(p: Path) -> Image.Image:
    im = Image.open(p).convert("RGB")
    return im.resize((폭, round(im.height * 폭 / im.width)), Image.LANCZOS)


a, b = 맞추기(만든), 맞추기(원본)
머리 = 60
판 = Image.new("RGB", (폭 * 2 + 30, max(a.height, b.height) + 머리), "white")
판.paste(a, (0, 머리)); 판.paste(b, (폭 + 30, 머리))
d = ImageDraw.Draw(판)
for x, 글 in ((10, "MADE (left)"), (폭 + 40, "ORIGINAL (right)")):
    d.text((x, 15), 글, fill="black")
출력.parent.mkdir(parents=True, exist_ok=True)
판.save(출력, quality=90)
print("비교 그림:", 출력)
