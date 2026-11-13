"""캐러셀 한 편의 장 구성이 '비슷한 장 중복 금지' 규칙을 지키는지 확인한다.

작업 설계서 2.4판 2단계 2:
1. 한 편 안에서 같은 모양 계열 장은 1장만(부품 이름이 달라도 같은 계열이면 같은 것으로 센다).
2. 같은 약사님의 최근 3편과 표지 부품(첫 장)이 같지 않다.
3. 최근 3편과 장 모양 계열 순서가 똑같지 않다.
4. 최근 3편에 쓴 사진(바탕·본인·제품 사진)을 다시 쓰지 않는다(2단계 4 "최근 3편에 쓴 사진은 피한다").
5. 배경 이미지 중복 금지(작업 설계서 2.9판, 2026-11-12 결정): 한 편 안 두 장에 같은 배경 이미지를 깔지 않고,
   최근 3편에 깐 배경 이미지도 다시 쓰지 않는다(디자인 시스템 부품 견본 깔개 포함).
   배경 이미지 = 편 index.html이 쓰는 그림 중 가로·세로 모두 900px 이상인 그림(장 전체를 덮는 사진·종이·바탕 그림).
   구성.json 옆에 index.html이 있으면 도구가 장(`<section class="frame"`)마다 배경을 찾아 그림 내용으로 비교한다
   (파일 이름이 달라도 그림이 같거나 거의 같으면 — 16×16 밝기 지문 차이 10 이하 — 같은 배경으로 본다).

모양 계열은 그 약사님 디자인 시스템 화면 부품 README의 `## 모양 계열` 다음 줄에서 읽는다
(예: `㉡ 격자 표 — 같은 계열: CoverTableCombo · GridTable · DoseTableCheck. ...` → 계열 이름 "격자 표").

편 구성 파일(편 폴더 `구성.json`):
  {"편": "774-1", "날짜": "2026-11-04", "부품": ["CoverPhotoList", "NumberedHeading", ...],
   "사진": ["<원본 편 아이디> 2장", "<원본 편 아이디> 7장", ...]}
  `사진`은 쓴 사진의 출처(원본 편 아이디·장 또는 공식 이미지 주소)를 적는다. 같은 출처면 같은 사진으로 본다.

사용
  python3 -I 나만의캐러셀만들기/도구/비슷한장검사.py <부품폴더> <새 편 구성.json> [최근 편 구성.json ...]
  - <부품폴더>: iCloud `.../04_설계서검토/디자인시스템화면/project/components`
  - 최근 편은 날짜가 늦은 3편만 본다(더 주면 날짜순으로 3편만).
  통과하면 0, 걸리면 1로 끝난다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

최근_편수 = 3
배경_최소 = 900  # 가로·세로 모두 이 이상이면 배경 이미지
지문_허용 = 10  # 16×16 밝기 지문 비트 차이가 이 이하이면 같은 배경


def _지문(그림: Path) -> int | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(그림) as im:
        if im.width < 배경_최소 or im.height < 배경_최소:
            return None
        작은 = im.convert("L").resize((16, 16))
    값 = list(작은.getdata())
    평균 = sum(값) / len(값)
    return sum(1 << i for i, v in enumerate(값) if v > 평균)


def 배경_읽기(편폴더: Path) -> list[tuple[int, str, int]]:
    """편 index.html에서 장마다 배경 이미지 → [(장 번호, 파일 이름, 지문)]. index.html이 없으면 빈 목록."""
    html = 편폴더 / "index.html"
    if not html.exists():
        return []
    글 = html.read_text(encoding="utf-8")
    조각 = 글.split('<section class="frame"')
    장들 = 조각[1:] if len(조각) > 1 else [글]
    결과, 캐시 = [], {}
    for 번호, 장 in enumerate(장들, 1):
        본 = set()
        for 이름 in re.findall(r"img/([^\"')\s>]+)", 장):
            if 이름 in 본:
                continue
            본.add(이름)
            if 이름 not in 캐시:
                파일 = 편폴더 / "img" / 이름
                캐시[이름] = _지문(파일) if 파일.exists() else None
            if 캐시[이름] is not None:
                결과.append((번호, 이름, 캐시[이름]))
    return 결과


def _같은그림(가: int, 나: int) -> bool:
    return bin(가 ^ 나).count("1") <= 지문_허용


def 배경_검사(새배경: list, 최근배경: list[tuple[str, list]]) -> list[str]:
    """한 편 안 같은 배경, 최근 편과 같은 배경 → 걸린 까닭 목록."""
    문제 = []
    for i, (장1, 이름1, 지1) in enumerate(새배경):
        for 장2, 이름2, 지2 in 새배경[i + 1:]:
            if 장1 != 장2 and _같은그림(지1, 지2):
                문제.append(f"한 편 안 같은 배경: {장1}장 {이름1} = {장2}장 {이름2}")
    for 편이름, 지난배경 in 최근배경:
        for 장1, 이름1, 지1 in 새배경:
            같은 = next((이름2 for _, 이름2, 지2 in 지난배경 if _같은그림(지1, 지2)), None)
            if 같은:
                문제.append(f"최근 편 '{편이름}'과 같은 배경: {장1}장 {이름1} (지난 편 {같은})")
    return 문제


def 계열_읽기(부품폴더: Path) -> dict[str, str]:
    """부품 README의 `## 모양 계열` 다음 줄 → {부품: 계열 이름}. 줄이 없는 부품은 빠진다."""
    계열 = {}
    for readme in sorted(부품폴더.glob("*/README.md")):
        줄들 = readme.read_text(encoding="utf-8").splitlines()
        for i, 줄 in enumerate(줄들):
            if 줄.strip() == "## 모양 계열":
                뒤 = next((x for x in 줄들[i + 1:] if x.strip()), "")
                이름 = re.sub(r"^\W+", "", 뒤.split("—")[0]).strip()
                if 이름:
                    계열[readme.parent.name] = 이름
                break
    return 계열


def 검사(새편: dict, 최근: list[dict], 계열: dict[str, str]) -> list[str]:
    """걸린 까닭 목록(빈 목록이면 통과)."""
    문제 = []
    부품 = 새편["부품"]
    없음 = [b for b in 부품 if b not in 계열]
    if 없음:
        문제.append(f"모양 계열을 모르는 부품: {', '.join(없음)} (README에 '## 모양 계열' 줄 필요)")
    순서 = [계열.get(b, b) for b in 부품]
    본 = {}
    for 장, 이름 in enumerate(순서, 1):
        if 이름 in 본:
            문제.append(f"한 편 안 같은 계열: {본[이름]}장과 {장}장이 모두 '{이름}'")
        else:
            본[이름] = 장
    최근 = sorted(최근, key=lambda p: p.get("날짜", ""), reverse=True)[:최근_편수]
    for 지난 in 최근:
        지난부품 = 지난.get("부품") or []
        if 부품 and 지난부품 and 부품[0] == 지난부품[0]:
            문제.append(f"표지 부품이 최근 편 '{지난.get('편', '?')}'과 같음: {부품[0]}")
        if 순서 == [계열.get(b, b) for b in 지난부품]:
            문제.append(f"장 모양 계열 순서가 최근 편 '{지난.get('편', '?')}'과 똑같음")
        겹친사진 = sorted(set(새편.get("사진") or []) & set(지난.get("사진") or []))
        if 겹친사진:
            문제.append(f"최근 편 '{지난.get('편', '?')}'과 같은 사진: {', '.join(겹친사진)}")
    return 문제


def main(인자: list[str]) -> int:
    if len(인자) < 2:
        print(__doc__)
        return 2
    계열 = 계열_읽기(Path(인자[0]))
    읽기 = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    새편 = 읽기(인자[1])
    지난들 = [(p, 읽기(p)) for p in 인자[2:]]
    문제 = 검사(새편, [j for _, j in 지난들], 계열)
    새배경 = 배경_읽기(Path(인자[1]).parent)
    최근 = sorted(지난들, key=lambda x: x[1].get("날짜", ""), reverse=True)[:최근_편수]
    문제 += 배경_검사(새배경, [(j.get("편", "?"), 배경_읽기(Path(p).parent)) for p, j in 최근])
    print(f"편 '{새편.get('편', '?')}': " + " → ".join(f"{b}({계열.get(b, '?')})" for b in 새편["부품"]))
    if 문제:
        print("걸림:")
        for 줄 in 문제:
            print(" -", 줄)
        return 1
    print(f"통과: 비슷한 장 없음, 최근 편과 표지·순서·사진 겹침 없음, 배경 이미지 중복 없음(배경 {len(새배경)}개 확인)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
