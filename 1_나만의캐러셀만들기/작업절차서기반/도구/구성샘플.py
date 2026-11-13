"""구성안 순서대로 부품 그림을 가로로 이어 붙여 한 장 샘플 그림을 만든다.

출처: R/2026-11-10_디자인시스템/도구/samples.py, 2026-11-10 판(부품 목록·출력 폴더를 인자로).
각 부품 폴더의 render.png(없으면 cmp.jpg 오른쪽 절반)를 장당 가로 360(세로 = 첫 부품 견본.json `크기` 비율, 없으면 1080×1350 → 450)으로 줄여 잇고 아래에 부품 이름을 적는다.

사용
  python3 -I 도구/구성샘플.py <부품 상위 폴더> <부품 이름 순서…> --출력 <jpg>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "부품"))
import 공통  # noqa: E402
from lib import 견본_높이  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

가로, 간격, 이름줄 = 360, 12, 40


def 장_그림(폴더: Path, 세로: int) -> Image.Image:
    render = 폴더 / "render.png"
    if render.is_file():
        im = Image.open(render).convert("RGB")
    else:
        cmp = 폴더 / "cmp.jpg"
        if not cmp.is_file():
            공통.실패(f"render.png도 cmp.jpg도 없습니다: {폴더}")
        im = Image.open(cmp).convert("RGB")
        im = im.crop((im.width // 2, 0, im.width, im.height))
    return im.resize((가로, 세로), Image.LANCZOS)


def 글꼴_열기(크기: int):
    # ponytail: 한글이 나오는 시스템 글꼴 하나만 찾음, 없으면 PIL 기본 글꼴(한글이 네모로 보일 수 있음)
    for 경로 in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        try:
            return ImageFont.truetype(경로, 크기)
        except OSError:
            pass
    return ImageFont.load_default()


def 이어붙이기(상위: Path, 이름들: list[str]) -> Image.Image:
    세로 = round(가로 * 견본_높이(상위 / 이름들[0]) / 1080)  # 첫 부품 기준(1350이면 450)
    판 = Image.new("RGB", (가로 * len(이름들) + 간격 * (len(이름들) - 1), 세로 + 이름줄), (230, 230, 230))
    글 = 글꼴_열기(22)
    펜 = ImageDraw.Draw(판)
    for k, 이름 in enumerate(이름들):
        폴더 = 상위 / 이름
        if not 폴더.is_dir():
            공통.실패(f"부품 폴더가 없습니다: {폴더}")
        x = k * (가로 + 간격)
        판.paste(장_그림(폴더, 세로), (x, 0))
        펜.text((x + 가로 // 2, 세로 + 이름줄 // 2), 이름, fill=(40, 40, 40), font=글, anchor="mm")
    return 판


def main(argv=None) -> int:
    ap = 공통.한글ArgumentParser(description="부품 그림(render.png 또는 cmp.jpg 오른쪽)을 구성안 순서대로 가로로 이어 붙인다.")
    ap.add_argument("상위폴더", help="부품 폴더들이 들어 있는 폴더 (작업 폴더 기준)")
    ap.add_argument("부품", nargs="+", help="부품 폴더 이름을 장 순서대로")
    ap.add_argument("--출력", required=True, help="저장할 jpg 경로")
    a = ap.parse_args(argv)
    상위 = 공통.작업폴더_경로(a.상위폴더)
    if not 상위.is_dir():
        공통.실패(f"부품 상위 폴더를 찾을 수 없습니다: {a.상위폴더}")
    출력 = 공통.작업폴더_경로(a.출력)
    출력.parent.mkdir(parents=True, exist_ok=True)
    그림 = 이어붙이기(상위, a.부품)
    그림.save(출력, quality=90)
    print(f"저장: {출력} ({그림.width}×{그림.height}, 장 {len(a.부품)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
