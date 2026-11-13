"""캐러셀 한 편의 장 구성이 '비슷한 장 중복 금지' 규칙을 지키는지 확인한다.

작업 절차서 4단계 3:
1. 한 편 안에서 같은 모양 계열 장은 1장만(부품 이름이 달라도 같은 계열이면 같은 것으로 센다).
   부품 README `## 모양 계열` 줄에 '최대 N장'이 적힌 계열은 N장까지(원본이 한 편에 여러 장 쓰는 계열 — 부품README.py가 모양표에서 적는다).
2. 같은 약사님의 최근 3편과 표지 부품(첫 장)이 같지 않다.
3. 최근 3편과 장 모양 계열 순서가 똑같지 않다.
4. 최근 3편에 쓴 사진(바탕·본인·제품 사진)을 다시 쓰지 않는다(절차서 4단계 3 "편 사이 중복 금지").

모양 계열은 그 약사님 디자인 시스템 화면 부품 README의 `## 모양 계열` 다음 줄에서 읽는다
(예: `㉡ 격자 표 — 같은 계열: CoverTableCombo · GridTable · DoseTableCheck. ...` → 계열 이름 "격자 표").

편 구성 파일(편 폴더 `구성.json`):
  {"편": "774-1", "날짜": "2026-11-04", "부품": ["CoverPhotoList", "NumberedHeading", ...],
   "사진": ["AAAAAAAAAAA 2장", "BBBBBBBBBBB 7장", ...]}
  `사진`은 쓴 사진의 출처(원본 편 아이디·장 또는 공식 이미지 주소)를 적는다. 같은 출처면 같은 사진으로 본다.

사용
  python3 -I 도구/비슷한장검사.py <부품폴더> <새 편 구성.json> [최근 편 구성.json ...]
  - <부품폴더>: `<약사님폴더>/05_디자인시스템/부품` (부품마다 README.md가 있는 폴더)
  - 최근 편은 날짜가 늦은 3편만 본다(더 주면 날짜순으로 3편만).
  - `--약사님폴더 <폴더>`를 주면 `사진` 항목(`<편>/<장>`)을 `02_*/슬라이드/<편>/<장>.jpg`(또는 그대로 있는 경로)로 풀어
    그림을 읽어, 한 편 안과 최근 편 사이의 **같은 컷**(이름은 달라도 그림이 같음)도 `[같은 컷]` 으로 건다. 없으면 그림 견주기는 건너뛴다.
  통과하면 0, 걸리면 1로 끝난다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "부품"))
import 공통  # noqa: E402
from lib import 견본_높이, 크기_섞임  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

작업폴더 = Path(__file__).resolve().parents[1]  # 상대 경로는 작업 폴더 기준

최근_편수 = 3


def 한도_읽기(부품폴더: Path) -> dict[str, int]:
    """README `## 모양 계열` 줄의 '최대 N장' → {계열 이름: N}. 안 적힌 계열은 1장(같은 계열 부품 중 큰 값)."""
    한도: dict[str, int] = {}
    for readme in sorted(부품폴더.glob("*/README.md")):
        줄들 = readme.read_text(encoding="utf-8").splitlines()
        for i, 줄 in enumerate(줄들):
            if 줄.strip() == "## 모양 계열":
                뒤 = next((x for x in 줄들[i + 1:] if x.strip()), "")
                이름 = re.sub(r"^\W+", "", 뒤.split("—")[0]).strip()
                m = re.search(r"최대 (\d+)장", 뒤)
                if 이름:
                    한도[이름] = max(한도.get(이름, 1), int(m.group(1)) if m else 1)
                break
    return 한도


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


def 검사(새편: dict, 최근: list[dict], 계열: dict[str, str], 한도: dict[str, int] | None = None) -> list[str]:
    """걸린 까닭 목록(빈 목록이면 통과)."""
    문제 = []
    부품 = 새편["부품"]
    없음 = [b for b in 부품 if b not in 계열]
    if 없음:
        문제.append(f"모양 계열을 모르는 부품: {', '.join(없음)} (README에 '## 모양 계열' 줄 필요)")
    순서 = [계열.get(b, b) for b in 부품]
    본: dict[str, list[int]] = {}
    for 장, 이름 in enumerate(순서, 1):
        본.setdefault(이름, []).append(장)
    for 이름, 장들 in 본.items():
        최대 = (한도 or {}).get(이름, 1)
        if len(장들) > 최대:
            문제.append(f"한 편 안 같은 계열: {'·'.join(map(str, 장들))}장이 모두 '{이름}'(한도 {최대}장)")
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


def 그림_경로(항목: str, 슬라이드: Path | None) -> Path | None:
    """`사진` 항목 → 그림 파일. `<편>/<장>` 은 슬라이드 폴더에서, 아니면 그대로 있는 경로. 못 풀면 None."""
    항목 = 공통.nfc(항목).strip()
    후보 = [작업폴더 / Path(항목).expanduser()]
    if 슬라이드 is not None and (m := re.match(r"(.+)/(\d+)$", 항목)):
        편 = 공통.파일_찾기(슬라이드, m[1])
        후보.insert(0, 편 / f"{m[2]}.jpg" if 편 else 슬라이드 / "없음")
    return next((p for p in 후보 if p.is_file()), None)


def 컷_특징(경로: Path, 문턱밝음: int = 235, 문턱어둠: int = 25, 비율: float = 0.6, 칸: int = 32):
    """(회색 값 칸×칸 줄, 믿을 칸 줄). 4:5 보다 길면 위에서 4:5 로 자르고, 가운데 60%를 32×32 로 줄인다.
    아주 밝은(≥235)·아주 어두운(≤25) 곳(글 상자)은 5px 부풀려 믿을 칸에서 뺀다."""
    im = Image.open(경로).convert("L")
    w, h = im.size
    if w / h < 0.8:
        im = im.crop((0, 0, w, int(w / 0.8)))
        w, h = im.size
    im = im.crop((int(w * (1 - 비율) / 2), int(h * (1 - 비율) / 2), int(w * (1 + 비율) / 2), int(h * (1 + 비율) / 2)))
    글 = im.resize((칸 * 4, 칸 * 4), Image.BOX).point(lambda v: 255 if v >= 문턱밝음 or v <= 문턱어둠 else 0).filter(ImageFilter.MaxFilter(5))
    g = 글.load()
    믿음 = [not any(g[x * 4 + i, y * 4 + j] for i in range(4) for j in range(4)) for y in range(칸) for x in range(칸)]
    return list(im.resize((칸, 칸), Image.BOX).tobytes()), 믿음


def 같은컷인가(f, g, 문턱: float = 0.9) -> bool:
    # ponytail: 해시(블라인드.같은그림, 8×8 해시 거리 ≤6)는 같은 컷인데 크롭·글 상자가 다른 짝(실데이터 거리 11)을 못 잡아
    # 글 상자를 뺀 가운데 60% 32×32 회색 상관 ≥0.9 로 바꿈(실데이터: 같은 컷 0.939, 같은 촬영 다른 컷 0.00·0.26). 믿을 칸이 30% 미만이면 견주지 않음.
    # 머리 위치까지 같은 컷만 잡는다 — 컷 밖 이동·확대 맞춤은 안 함(필요하면 cv2 특징 맞춤으로).
    쌍 = [(a, b) for a, b, ok1, ok2 in zip(f[0], g[0], f[1], g[1]) if ok1 and ok2]
    if len(쌍) < 0.3 * len(f[0]):
        return False
    ma, mb = sum(a for a, _ in 쌍) / len(쌍), sum(b for _, b in 쌍) / len(쌍)
    cov = sum((a - ma) * (b - mb) for a, b in 쌍)
    va, vb = sum((a - ma) ** 2 for a, _ in 쌍), sum((b - mb) ** 2 for _, b in 쌍)
    return va > 0 and vb > 0 and cov / (va * vb) ** 0.5 >= 문턱


def 같은컷_검사(새편: dict, 최근: list[dict], 슬라이드: Path | None) -> list[str]:
    """한 편 안과 최근 편 사이에서 이름은 달라도 그림이 같은 사진 짝을 `[같은 컷]` 줄로 돌려준다."""
    최근 = sorted(최근, key=lambda p: p.get("날짜", ""), reverse=True)[:최근_편수]
    캐시: dict[str, tuple | None] = {}

    def 특징(항목):
        if 항목 not in 캐시:
            p = 그림_경로(항목, 슬라이드)
            캐시[항목] = 컷_특징(p) if p else None
        return 캐시[항목]

    def 같은가(a, b):
        return a != b and (fa := 특징(a)) and (fb := 특징(b)) and 같은컷인가(fa, fb)

    문제 = []
    안 = list(dict.fromkeys(새편.get("사진") or []))
    for i, a in enumerate(안):
        for b in 안[i + 1:]:
            if 같은가(a, b):
                문제.append(f"[같은 컷] 한 편 안: '{a}' = '{b}'")
    for 지난 in 최근:
        for a in 안:
            for b in dict.fromkeys(지난.get("사진") or []):
                if 같은가(a, b):
                    문제.append(f"[같은 컷] 최근 편 '{지난.get('편', '?')}'과: '{a}' = '{b}'")
    return 문제


def main(인자: list[str]) -> int:
    약사님 = None
    if "--약사님폴더" in 인자:
        k = 인자.index("--약사님폴더")
        if k + 1 >= len(인자):
            공통.실패("--약사님폴더 값이 빠졌습니다")
        약사님 = 인자[k + 1]
        인자 = 인자[:k] + 인자[k + 2:]
    if len(인자) < 2:
        print(__doc__)
        return 2
    계열 = 계열_읽기(작업폴더 / Path(인자[0]).expanduser())
    읽기 = lambda p: json.loads((작업폴더 / Path(p).expanduser()).read_text(encoding="utf-8"))
    새편 = 읽기(인자[1])
    문제 = 검사(새편, [읽기(p) for p in 인자[2:]], 계열, 한도_읽기(작업폴더 / Path(인자[0]).expanduser()))
    최근들 = [읽기(p) for p in 인자[2:]]
    크기문제 = 크기_섞임({b: 견본_높이(작업폴더 / Path(인자[0]).expanduser() / b) for b in dict.fromkeys(새편["부품"])})  # 견본.json 없으면 1350
    if 크기문제: 문제.append(크기문제)
    if 약사님:
        정보 = 공통.약사님폴더_검사(약사님)
        슬라이드 = 공통.파일_찾기(정보["02"], "슬라이드") if 정보["02"] else None
        문제 += 같은컷_검사(새편, 최근들, 슬라이드)
    else:
        print("그림 견주기 건너뜀(--약사님폴더 없음)")
    print(f"편 '{새편.get('편', '?')}': " + " → ".join(f"{b}({계열.get(b, '?')})" for b in 새편["부품"]))
    if 문제:
        print("걸림:")
        for 줄 in 문제:
            print(" -", 줄)
        return 1
    print("통과: 비슷한 장 없음, 최근 편과 표지·순서·사진 겹침 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
