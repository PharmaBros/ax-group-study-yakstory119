"""사진재료 — 약사님 폴더의 "글자 없는 본인 사진"이 몇 장인지 세어, 4단계 사진 재료가 충분한지 본다.

쓰기: python3 도구/사진재료.py <약사님폴더> [--필요 N]
- 01_*/사진_태그.json 에서 본인얼굴 true · 글자없음 true · 다른사람얼굴 false 인 사진을 센다.
- 대표 슬라이드 중 본인 사진 바탕 장(사진메모.json 의 사진[].본인얼굴 true)도 센다.
- --필요 N: 글자 없는 본인 사진이 N장 미만이면 [재료 부족] 줄을 내고 끝 코드 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402


def 글자없는_본인사진(태그: dict) -> list[str]:
    return [p["파일"] for p in 태그.get("사진", [])
            if p.get("본인얼굴") and p.get("글자없음") and not p.get("다른사람얼굴")]


def 본인바탕_장수(정보: dict) -> int:
    """대표 슬라이드 중 사진메모.json 에서 본인 얼굴이 든 장 수."""
    폴더02 = 정보.get("02")
    슬라이드 = 공통.파일_찾기(폴더02, "슬라이드") if 폴더02 else None
    if 슬라이드 is None:
        return 0
    n = 0
    for 편 in sorted(슬라이드.iterdir()):
        메모 = 공통.파일_찾기(편, "사진메모.json") if 편.is_dir() else None
        if 메모 is None:
            continue
        for 장 in json.loads(메모.read_text(encoding="utf-8")):
            n += any(p.get("본인얼굴") for p in 장.get("사진", []))
    return n


def main(argv=None) -> int:
    ap = 공통.한글ArgumentParser(description="글자 없는 본인 사진 수와 본인 사진 바탕 대표 슬라이드 수를 센다.")
    ap.add_argument("약사님폴더", help="01_수집이 있는 약사님 폴더")
    ap.add_argument("--필요", type=int, default=0, metavar="N", help="글자 없는 본인 사진이 N장 미만이면 [재료 부족]·끝 코드 1(기본 0)")
    a = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(a.약사님폴더)
    태그경로 = 공통.파일_찾기(정보["01"], "사진_태그.json") if 정보["01"] else None
    if 태그경로 is None:
        공통.실패("01_수집/사진_태그.json 이 없습니다(사진 태그 단계를 먼저 하세요)")
    try:
        태그 = json.loads(태그경로.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        공통.실패(f"사진_태그.json 을 읽지 못했습니다(JSON 오류): {e}")
    목록 = 글자없는_본인사진(태그)
    print(f"글자 없는 본인 사진: {len(목록)}장 (전체 태그 {len(태그.get('사진', []))}장)")
    for f in 목록:
        print(f"  - {f}")
    print(f"본인 사진 바탕 대표 슬라이드: {본인바탕_장수(정보)}장")
    if len(목록) < a.필요:
        print(f"[재료 부족] 글자 없는 본인 사진 {len(목록)}장 < 필요 {a.필요}장")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
