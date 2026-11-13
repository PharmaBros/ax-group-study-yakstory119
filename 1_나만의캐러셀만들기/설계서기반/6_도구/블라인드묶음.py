"""블라인드 검수 묶음을 만든다 — 만든 장 4장 + 원본 장 4장을 섞어 번호만 붙인다.

사용: python3 -I 6_도구/블라인드묶음.py --만든 a.png b.png c.png d.png --원본 1.jpg 2.jpg 3.jpg 4.jpg --출력 <폴더> [--씨앗 숫자]
  예) python3 -I 6_도구/블라인드묶음.py --만든 7_결과/기록/그림/NumberList.png ... \
        --원본 7_결과/게시물/<날짜>_<원본 편 아이디>/2.jpg ... --출력 7_결과/블라인드/1회차

만드는 것(<출력> 안)
- g/tile_1.jpg ~ g/tile_8.jpg — 판정자 B(선명)용 낱장, 540×675
- g/blur.jpg — 판정자 A(흐림)용 4×2 모아보기. 칸 360×450: 1080×1350을 180×225로 LANCZOS로 줄였다가
  BILINEAR로 360×450으로 키운 뒤 GaussianBlur(1.5). 칸 위에 번호 1~8.
- key.json — 정답(번호 → 만든 것/원본, 원래 파일 이름). **판정자에게 보여 주지 않는다.** g/ 밖에 둔다.
- 질문.txt — 판정자에게 줄 질문 문장(A용·B용).

원본 그림 규칙
- 세로 4:5(가로:세로 = 0.8, ±3%)만 그대로 1080×1350으로 맞춘다.
- 3:4(0.75)는 위아래를 똑같이 조금 잘라 4:5로 만든 뒤 맞춘다(잘랐다고 화면에 알림).
- 정사각(1:1)·가로형은 늘리면 일그러져 불공평하므로 받지 않는다 — 다른 원본을 고른다.
- 만든 장은 1080×1350이어야 한다(아니면 맞춰 줄이고 알림).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.exit("Pillow가 없습니다. `python3 -m pip install --user Pillow`로 설치해 주세요.")

질문 = ("인스타그램 약사 계정(한국어 건강·영양제·공구 게시물) 캐러셀 장 8장{보기}. "
      "일부는 그 계정이 실제로 올린 장이고, 일부는 다른 사람이 그 계정 스타일을 흉내 내 만든 장이다. "
      "몇 장이 만든 것인지는 알려 주지 않는다. {파일} 이 그림만 Read로 보고 다른 파일은 열지 마라. "
      "각 칸마다: 실제/만든 것, 확신(낮음/중간/높음), 이유 한 줄. 표로.")


def 인자_읽기(argv: list[str]) -> dict:
    a = {"만든": [], "원본": [], "출력": None, "씨앗": None}
    지금 = None
    for x in argv:
        if x in ("--만든", "--원본", "--출력", "--씨앗"):
            지금 = x[2:]; continue
        if 지금 in ("만든", "원본"):
            a[지금].append(Path(x))
        elif 지금 in ("출력", "씨앗"):
            a[지금] = x
    return a


def 원본_맞추기(p: Path) -> tuple[Image.Image, str]:
    im = Image.open(p).convert("RGB")
    비 = im.width / im.height
    if abs(비 - 0.8) <= 0.8 * 0.03:
        return im.resize((1080, 1350), Image.LANCZOS), ""
    if abs(비 - 0.75) <= 0.75 * 0.03:
        새높이 = round(im.width / 0.8)
        위 = (im.height - 새높이) // 2
        return im.crop((0, 위, im.width, 위 + 새높이)).resize((1080, 1350), Image.LANCZOS), "3:4 → 위아래 잘라 4:5"
    sys.exit(f"받지 않는 비율({im.width}×{im.height}): {p} — 세로 4:5(또는 3:4) 원본만 씁니다. 다른 장을 고르세요.")


def 만든_맞추기(p: Path) -> tuple[Image.Image, str]:
    im = Image.open(p).convert("RGB")
    if im.size == (1080, 1350):
        return im, ""
    return im.resize((1080, 1350), Image.LANCZOS), f"{im.width}×{im.height} → 1080×1350으로 맞춤"


def main(argv: list[str]) -> int:
    a = 인자_읽기(argv)
    if len(a["만든"]) != 4 or len(a["원본"]) != 4 or not a["출력"]:
        print(__doc__); return 2
    for p in a["만든"] + a["원본"]:
        if not p.exists():
            sys.exit(f"그림이 없습니다: {p}")
    출력 = Path(a["출력"]); g = 출력 / "g"
    if g.exists() and any(g.iterdir()):
        sys.exit(f"{g}에 이미 그림이 있습니다. 회차마다 새 폴더를 쓰세요(예: 블라인드/2회차).")
    장들 = []
    for p in a["만든"]:
        im, 알림 = 만든_맞추기(p); 장들.append(("만든 것", p.name, im, 알림))
    for p in a["원본"]:
        im, 알림 = 원본_맞추기(p); 장들.append(("원본", f"{p.parent.name}/{p.name}", im, 알림))
    g.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(int(a["씨앗"]) if a["씨앗"] else None)
    rnd.shuffle(장들)

    칸w, 칸h, 틈, 머리 = 360, 450, 12, 34
    판 = Image.new("RGB", (4 * 칸w + 5 * 틈, 2 * (칸h + 머리) + 3 * 틈), "white")
    d = ImageDraw.Draw(판)
    답 = {}
    for i, (종류, 이름, im, 알림) in enumerate(장들, 1):
        im.resize((540, 675), Image.LANCZOS).save(g / f"tile_{i}.jpg", quality=90)
        작게 = im.resize((180, 225), Image.LANCZOS).resize((칸w, 칸h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.5))
        행, 열 = divmod(i - 1, 4)
        x = 틈 + 열 * (칸w + 틈); y = 틈 + 행 * (칸h + 머리 + 틈)
        d.text((x + 4, y + 8), str(i), fill="black")
        판.paste(작게, (x, y + 머리))
        답[str(i)] = {"정답": 종류, "파일": 이름}
        if 알림:
            print(f"{i}번 {이름}: {알림}")
    판.save(g / "blur.jpg", quality=90)
    (출력 / "key.json").write_text(json.dumps(답, ensure_ascii=False, indent=1), encoding="utf-8")
    (출력 / "질문.txt").write_text(
        "[판정자 A — 흐림]\n" + 질문.format(보기="을 4×2로 모은 흐린 그림이다(칸 위 숫자가 번호)",
                                         파일=f"그림: {(g / 'blur.jpg').resolve()}") + "\n\n"
        "[판정자 B — 선명]\n" + 질문.format(보기="이다(폰 크기 낱장 8장, 파일 이름의 숫자가 번호)",
                                         파일="그림: " + ", ".join(str((g / f'tile_{i}.jpg').resolve()) for i in range(1, 9))) + "\n",
        encoding="utf-8")
    print("블라인드 묶음:", 출력, "— 정답 key.json은 판정이 끝날 때까지 열지 않는다")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
