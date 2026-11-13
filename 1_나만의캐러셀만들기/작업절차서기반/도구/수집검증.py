#!/usr/bin/env python3
"""수집 검증 — 약사님 폴더의 수집 결과가 설계서 기준(작업_설계서 4장 1단계 1 "수집 검증" ①~④)에 맞는지 확인합니다.

사용법:  python3 -I 도구/수집검증.py <약사님폴더> [--write]

확인하는 것
  ① 캡션 최장 길이가 300자를 넘는지(안 넘으면 "잘림 의심"), 깨진 글자(�) 개수
  ② 한 편 안에 같은 그림이 두 번 있는지(파일 내용 sha1 비교)
  ③ 표지(1.jpg 또는 가장 작은 번호) 가로가 1080 미만인 편
  ④ 출처.json이 없는 편
  "확인 필요" 건수는 ①~④만 셉니다. 아래는 "참고(건수에 안 셈)" 절에 따로 적습니다.
  · 01 하위 세트(프로필.md, 프로필/, 릴스/, 스토리/, 본인사진/, 개인게시물/, 사진_태그.json) 유무
  · 읽어주세요.md, 동의기록.md, 02/분류.md, 02/한눈에보기/ 유무(한눈에보기는 `한눈에보기.py`로 만든다)
  · 게시물목록.json 항목 수와 02 편 수
  ①: 항목의 `캡션상태`(전문/잘림 등)별 개수와 '전문'이 아닌 항목 아이디. 상태에 "잘림"이 든 항목의 �는 인스타 한계라 건수에서 뺍니다.
  ③: 편 출처.json의 "해상도"에 "낮음"이 적혀 있으면 "기록됨(통과)"으로 보고 건수에서 뺍니다.
  게시물목록.json이 없으면 멈추지 않고 ①에 "확인 필요 1건"으로 적고 계속합니다.

결과는 한국어 표로 화면에 보여 주고, --write 를 주면 03_분석/{오늘}_수집검증.md 로도 저장합니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    공통.실패("Pillow가 설치돼 있지 않습니다. 터미널에서 `python3 -m pip install Pillow` 를 실행해 주세요.")


# ──────────────────────────── 핵심 함수(테스트 대상) ────────────────────────────

def 캡션_검사(목록: list[dict]) -> dict:
    """캡션 최장 길이·300자 초과 여부·� 개수를 센다."""
    길이들 = [len(str(x.get("캡션") or "")) for x in 목록]
    최장 = max(길이들) if 길이들 else 0
    깨짐 = sum(str(x.get("캡션") or "").count("�") for x in 목록)
    return {
        "캡션수": len(목록),
        "최장": 최장,
        "300초과": 최장 > 300,
        "깨진글자": 깨짐,
        "빈캡션": sum(1 for l in 길이들 if l == 0),
    }


def 파일_sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for 덩어리 in iter(lambda: f.read(1 << 16), b""):
            h.update(덩어리)
    return h.hexdigest()


def 편내_중복(이미지: list[tuple[int, Path]]) -> list[list[str]]:
    """한 편 안에서 내용이 같은 그림 묶음을 돌려준다. 예: [['2.jpg','5.jpg']]"""
    묶음: dict[str, list[str]] = {}
    for _, p in 이미지:
        묶음.setdefault(파일_sha1(p), []).append(p.name)
    return [sorted(v) for v in 묶음.values() if len(v) > 1]


def 표지_크기(이미지: list[tuple[int, Path]]) -> tuple[int, int] | None:
    if not 이미지:
        return None
    try:
        with Image.open(이미지[0][1]) as im:
            return im.size
    except Exception:
        return None


def 하위세트_검사(폴더01: Path | None) -> list[tuple[str, bool]]:
    항목 = ["프로필.md", "프로필", "본인사진", "개인게시물", "사진_태그.json", "게시물목록.json", "게시물목록.md"]
    결과 = []
    for 이름 in 항목:
        있음 = 폴더01 is not None and 공통.파일_찾기(폴더01, 이름) is not None
        결과.append((이름, 있음))
    return 결과


# ──────────────────────────── 본체 ────────────────────────────

def 출처_해상도_낮음(편: dict) -> bool:
    """편 출처.json의 "해상도" 값에 '낮음'이 있으면 True(기록됨 → 통과)."""
    p = 편.get("출처")
    if p is None:
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(d, dict) and "낮음" in str(d.get("해상도", ""))


def 검증(정보: dict) -> tuple[str, int]:
    확인 = 0
    줄 = [f"# {정보['이름']} 수집 검증 ({공통.오늘()})", "",
          "건수에 세는 것은 설계서 ①~④뿐입니다. 하위 세트·읽어주세요·동의기록·분류.md·한눈에보기 유무는 아래 \"참고\"에만 적습니다.", ""]

    # ① 캡션
    목록 = []
    목록없음 = False
    if 정보.get("01") is not None and 공통.파일_찾기(정보["01"], "게시물목록.json") is not None:
        목록 = 공통.게시물목록_읽기(정보)
    else:
        목록없음 = True
    if 목록없음:
        확인 += 1
        줄 += ["## ① 캡션", 공통.마크다운표(["항목", "값", "판정"], [["게시물목록.json", "없음", "**게시물목록.json 없음 — 확인 필요 1건**"]]), ""]
    else:
        c = 캡션_검사(목록)
        잘림항목 = [x for x in 목록 if "잘림" in str(x.get("캡션상태") or "") and "�" in str(x.get("캡션") or "")]
        참고깨짐 = sum(str(x.get("캡션") or "").count("�") for x in 잘림항목)
        깨짐 = c["깨진글자"] - 참고깨짐
        캡션판정 = "통과(300자 넘는 캡션 있음)" if c["300초과"] else "**잘림 의심**(최장 300자 이하 → 게시물 페이지에서 전문을 다시 받는다)"
        if not c["300초과"]:
            확인 += 1
        if 깨짐:
            확인 += 1
        행 = [["캡션 수", c["캡션수"], ""],
              ["최장 길이", f"{c['최장']}자", 캡션판정],
              ["깨진 글자(�) 개수(인스타 한계 제외)", 깨짐, "통과" if 깨짐 == 0 else "**확인 필요**"]]
        if 참고깨짐:
            행.append(["깨진 글자(�) — 캡션상태 '잘림' 항목", 참고깨짐, "참고(인스타 한계, 건수에 안 셈)"])
        행.append(["빈 캡션(참고)", c["빈캡션"], "" if c["빈캡션"] == 0 else "참고(건수에 안 셈)"])
        줄 += ["## ① 캡션", 공통.마크다운표(["항목", "값", "판정"], 행), ""]
        깨진항목 = [[i + 1, x.get("id", "?"), str(x.get("캡션") or "").count("�")] for i, x in enumerate(목록) if "�" in str(x.get("캡션") or "")]
        if 깨진항목:
            줄 += ["### � 글자가 든 항목(순서·아이디·글자수 — 캡션 원문은 싣지 않음)", 공통.마크다운표(["순서", "아이디", "� 글자수"], 깨진항목), ""]
        상태 = Counter(str(x["캡션상태"]) for x in 목록 if x.get("캡션상태"))
        if 상태:
            줄 += ["### 캡션상태별 개수", 공통.마크다운표(["캡션상태", "개수"], [[k, v] for k, v in 상태.most_common()]), ""]
            전문아님 = [[x.get("id", "?"), x["캡션상태"]] for x in 목록 if x.get("캡션상태") and str(x["캡션상태"]) != "전문"]
            줄 += ["### 캡션상태가 '전문'이 아닌 항목", 공통.마크다운표(["아이디", "캡션상태"], 전문아님), ""]

    # ②③④ 편
    편들 = 공통.편_목록(정보) if 정보.get("02") else []
    중복행, 저해상도행, 출처없음, 기록됨행 = [], [], [], []
    for 편 in 편들:
        for 묶음 in 편내_중복(편["이미지"]):
            중복행.append([편["이름"], ", ".join(묶음)])
        크기 = 표지_크기(편["이미지"])
        낮음 = 크기 is None or 크기[0] < 1080
        if 낮음:
            표시 = "(표지 없음/못 읽음)" if 크기 is None else f"{크기[0]}×{크기[1]}"
            if 출처_해상도_낮음(편):
                기록됨행.append([편["이름"], 표시, len(편["이미지"]), "기록됨(통과)"])
            else:
                저해상도행.append([편["이름"], 표시, len(편["이미지"])])
        if 편["출처"] is None:
            출처없음.append([편["이름"], len(편["이미지"])])
    확인 += len(중복행) + len(저해상도행) + len(출처없음)
    기타행 = [[편["이름"], ", ".join(편["기타"])] for 편 in 편들 if 편["기타"]]
    줄 += ["## ② 편 안 같은 그림 두 번(sha1 비교)", 공통.마크다운표(["편", "같은 그림"], 중복행), ""]
    줄 += ["## ③ 표지 가로 1080 미만 편(출처.json에 \"해상도: 낮음\" 적고 글꼴 분석에서 뺀다)",
           공통.마크다운표(["편", "표지 크기", "장 수"], 저해상도행), ""]
    if 기록됨행:
        줄 += ["### ③ 출처.json에 \"해상도: 낮음\"이 기록된 편(통과, 건수에 안 셈)", 공통.마크다운표(["편", "표지 크기", "장 수", "판정"], 기록됨행), ""]
    줄 += ["## ④ 출처.json 없는 편", 공통.마크다운표(["편", "장 수"], 출처없음), ""]

    줄.append(f"**결과: {'통과' if 확인 == 0 else f'확인 필요 {확인}건'} (설계서 ①~④만 센 값)**")
    줄.append("")

    # 참고(건수에 안 셈)
    줄 += ["## 참고(건수에 안 셈)", ""]
    if 기타행:
        줄 += ["### 편 폴더 안 장 번호가 아닌 파일(장 수에 세지 않음)", 공통.마크다운표(["편", "파일"], 기타행), ""]
    세트행 = []
    for 이름, 있음 in 하위세트_검사(정보.get("01")):
        세트행.append([f"01/{이름}", "있음" if 있음 else "없음"])
    for 이름, 폴더 in [("읽어주세요.md", 정보["루트"]), ("동의기록.md", 정보["루트"]), ("02/분류.md", 정보.get("02")), ("02/한눈에보기/", 정보.get("02"))]:
        실제 = 이름.rstrip("/").split("/")[-1]
        있음 = 폴더 is not None and 공통.파일_찾기(폴더, 실제) is not None
        상태 = "있음" if 있음 else "없음"
        if 이름 == "02/한눈에보기/" and not 있음:
            상태 = "없음 — `한눈에보기.py`로 만든다"
        세트행.append([이름, 상태])
    줄 += ["### 폴더·파일 유무", 공통.마크다운표(["항목", "유무"], 세트행), ""]

    분류 = 공통.분류_읽기(정보)
    분류없는편 = [편["이름"] for 편 in 편들 if 편["이름"] not in 분류["편"]]
    줄 += ["### 개수", 공통.마크다운표(
        ["항목", "값"],
        [["게시물목록.json 항목 수", len(목록)],
         ["02/슬라이드 편 수", len(편들)],
         ["02/슬라이드 장 수 합계", sum(len(편["이미지"]) for 편 in 편들)],
         ["분류.md에 종류가 적힌 편 수", len([e for e in 편들 if e["이름"] in 분류["편"]])],
         ["분류.md에 없는 편", ", ".join(분류없는편) if 분류없는편 else "없음"]]), ""]
    return "\n".join(줄), 확인


def main(argv=None):
    ap = 공통.한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    ap.add_argument("약사님폴더", help="작업 폴더 아래 약사님 폴더 이름(예: 홍길동약사_hong_yaksa)")
    ap.add_argument("--write", action="store_true", help="결과를 03_분석/{오늘}_수집검증.md 로 저장")
    ap.add_argument("-h", "--help", action="help", help="이 도움말을 보여 줍니다")
    args = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(args.약사님폴더)
    본문, 확인 = 검증(정보)
    print(본문)
    if args.write:
        p = 공통.결과_저장(정보, f"{공통.오늘()}_수집검증.md", 본문 + "\n")
        print(f"\n저장했습니다: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
