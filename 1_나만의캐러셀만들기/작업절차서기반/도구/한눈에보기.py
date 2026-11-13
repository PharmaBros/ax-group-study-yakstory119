#!/usr/bin/env python3
"""한눈에보기 — 02/슬라이드 편마다 모든 장을 한 장의 그림으로 모아 02/한눈에보기/{편}.jpg 로 만듭니다(모든 계정 같은 규격).

사용법:  python3 -I 도구/한눈에보기.py <약사님폴더> [--덮어쓰기] [--편 N] [--출력 폴더]

규격: 가로 5장 × 장당 360px 너비(높이는 비율 유지 — 4:5면 450px), 5장이 넘으면 줄을 더 만들고, 각 장 아래에 번호를 작게 적습니다.
  --덮어쓰기   이미 있는 파일은 `{편}_이전.jpg` 로 이름을 바꿔 남기고 새로 만듭니다(지우지 않음). 이 옵션이 없으면 있는 편은 건너뜁니다.
  --편 N       앞에서부터 N편만(시험용)
  --출력 폴더  02/한눈에보기 대신 다른 폴더에 만듭니다(시험용)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    공통.실패("Pillow가 설치돼 있지 않습니다. 터미널에서 `python3 -m pip install Pillow` 를 실행해 주세요.")

장너비 = 360
줄당장수 = 5
여백 = 8
번호높이 = 22
배경색 = (255, 255, 255)


def _글꼴(크기=14):
    try:
        return ImageFont.load_default(size=크기)
    except TypeError:  # 오래된 Pillow
        return ImageFont.load_default()


# ──────────────────────────── 핵심 함수(테스트 대상) ────────────────────────────

def 배치_계산(크기들: list[tuple[int, int]]) -> dict:
    """각 장의 (w,h) 목록 → 줄별 높이와 전체 캔버스 크기, 장별 위치."""
    위치 = []
    줄높이 = []
    for i in range(0, len(크기들), 줄당장수):
        줄 = 크기들[i:i + 줄당장수]
        높이들 = [round(장너비 * h / w) if w else 장너비 for w, h in 줄]
        줄높이.append(max(높이들) if 높이들 else 0)
    y = 여백
    for r, i in enumerate(range(0, len(크기들), 줄당장수)):
        줄 = 크기들[i:i + 줄당장수]
        for c, (w, h) in enumerate(줄):
            nh = round(장너비 * h / w) if w else 장너비
            x = 여백 + c * (장너비 + 여백)
            위치.append((x, y, 장너비, nh))
        y += 줄높이[r] + 번호높이 + 여백
    열수 = min(줄당장수, len(크기들)) or 1
    캔버스 = (여백 + 열수 * (장너비 + 여백), y)
    return {"위치": 위치, "캔버스": 캔버스, "줄수": len(줄높이)}


def 한눈에보기_만들기(이미지경로들: list[Path], 저장경로: Path) -> tuple[int, int]:
    크기들 = []
    열린 = []
    for p in 이미지경로들:
        im = Image.open(p)
        im = im.convert("RGB")
        크기들.append(im.size)
        열린.append(im)
    배치 = 배치_계산(크기들)
    캔버스 = Image.new("RGB", 배치["캔버스"], 배경색)
    그리기 = ImageDraw.Draw(캔버스)
    글꼴 = _글꼴(14)
    for 번호, (im, (x, y, w, h)) in enumerate(zip(열린, 배치["위치"]), start=1):
        캔버스.paste(im.resize((w, h), Image.LANCZOS), (x, y))
        그리기.text((x + w // 2 - 4, y + h + 3), str(번호), fill=(90, 90, 90), font=글꼴)
        im.close()
    저장경로.parent.mkdir(parents=True, exist_ok=True)
    캔버스.save(저장경로, "JPEG", quality=85)
    return 캔버스.size


def 이전이름(경로: Path) -> Path:
    """기존 파일을 보존할 이름. `{편}_이전.jpg`, 이미 있으면 시각을 덧붙인다."""
    후보 = 경로.with_name(f"{경로.stem}_이전{경로.suffix}")
    if 후보.exists():
        후보 = 경로.with_name(f"{경로.stem}_이전_{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}{경로.suffix}")
    return 후보


# ──────────────────────────── 본체 ────────────────────────────

def main(argv=None):
    ap = 공통.한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    ap.add_argument("약사님폴더")
    ap.add_argument("--덮어쓰기", action="store_true", help="있는 파일을 _이전 으로 남기고 새로 만든다")
    ap.add_argument("--편", type=int, default=None, help="앞에서부터 N편만")
    ap.add_argument("--출력", default=None, help="결과를 둘 폴더(기본 02/한눈에보기)")
    ap.add_argument("-h", "--help", action="help", help="이 도움말")
    args = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(args.약사님폴더)
    편들 = 공통.편_목록(정보)
    if args.편:
        편들 = 편들[:args.편]
    if args.출력:
        출력폴더 = 공통.작업폴더_경로(args.출력)
    else:
        출력폴더 = 공통.파일_찾기(정보["02"], "한눈에보기") or (정보["02"] / "한눈에보기")
    출력폴더.mkdir(parents=True, exist_ok=True)

    행 = []
    만든수 = 건너뜀 = 보존 = 0
    for 편 in 편들:
        if not 편["이미지"]:
            행.append([편["이름"], 0, "건너뜀(그림 없음)", ""])
            continue
        목표 = 출력폴더 / f"{편['이름']}.jpg"
        기존 = 공통.파일_찾기(출력폴더, 목표.name)
        if 기존 is not None and not args.덮어쓰기:
            건너뜀 += 1
            행.append([편["이름"], len(편["이미지"]), "건너뜀(이미 있음)", ""])
            continue
        보존이름 = ""
        if 기존 is not None:
            새이름 = 이전이름(기존)
            기존.rename(새이름)
            보존 += 1
            보존이름 = 새이름.name
        try:
            크기 = 한눈에보기_만들기([p for _, p in 편["이미지"]], 목표)
        except Exception:
            행.append([편["이름"], len(편["이미지"]), "실패: 그림 파일을 열 수 없음(깨짐 또는 iCloud 미다운로드)", 보존이름])
            continue
        만든수 += 1
        행.append([편["이름"], len(편["이미지"]), f"만듦 {크기[0]}×{크기[1]}", 보존이름])

    print(f"# {정보['이름']} 한눈에보기 ({공통.오늘()})\n")
    print(f"출력 폴더: `{출력폴더}`\n")
    print(공통.마크다운표(["편", "장 수", "결과", "보존한 이전 파일"], 행))
    print(f"\n**만듦 {만든수}편 · 건너뜀 {건너뜀}편 · 이전 파일 보존 {보존}개**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
