"""공통 디자인 시스템 json과 약사님 커스텀 json을 합쳐 `디자인시스템_최종.json`을 만든다.

공통 json이 기본값, 커스텀 json은 덮어쓰는 값만, 둘을 합친 최종 json이 그 약사님의 디자인 시스템이다.
최종 json은 이 도구가 만든다 — 손으로 고치지 말고, 커스텀 json을 고친 뒤 이 도구를 다시 돌린다.

합치는 규칙
1. 사전(칸 묶음)은 칸마다 들어가 합친다. 커스텀에 없는 칸은 공통 값이 그대로 남는다.
2. 배열·글자·숫자는 커스텀 값이 공통 값을 통째로 덮는다(배열도 덮어쓰기, 이어 붙이지 않음).
3. 커스텀이 `X`를 덮었는데 `X_권고`·`X_근거`는 적지 않았으면, 공통의 `X_권고`·`X_근거`는 버린다.
4. `_`로 시작하는 메모 칸은 커스텀에 적힌 자리 그대로 둔다. 공통 머리 칸(`_안내`·`판`·`기준일`·`설명`)은
   최종 파일 머리 `_합친_정보`로 옮긴다.

사용(이 묶음 안에서 — 경로는 어디서 돌려도 됨)
  python3 -I 6_도구/합치기.py 2_커스텀설계서                 # 화면에 보고만(파일 안 바뀜)
  python3 -I 6_도구/합치기.py 2_커스텀설계서 --write         # 2_커스텀설계서/디자인시스템_최종.json 저장
  python3 -I 6_도구/합치기.py 2_커스텀설계서 --출력 다른곳/최종.json   # 다른 곳에 저장(시험용)

- 폴더에는 `디자인시스템_커스텀.json`이 있어야 한다.
- 공통 json은 `--공통`으로 줄 수 있다. 안 주면 ① 같은 폴더의 `디자인시스템_공통.json` ② 이 도구 옆
  `../2_커스텀설계서/디자인시스템_공통.json` 순서로 찾는다.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import unicodedata
from pathlib import Path

공통_머리 = ("_안내", "판", "기준일", "설명")
딸린_칸 = ("_권고", "_근거")


# ── 작은 도우미 ──────────────────────────────────────────────

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def 오늘() -> str:
    return _dt.date.today().strftime("%Y-%m-%d")


def 실패(메시지: str, code: int = 1):
    print(f"[실패] {메시지}", file=sys.stderr)
    sys.exit(code)


class 한글ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str):
        m = re.search(r"required: (.+)$", message)
        if m:
            print(f"[실패] 필요한 값이 빠졌습니다: {m.group(1)} — 사용법은 --help", file=sys.stderr)
        else:
            print(f"[실패] 옵션이 올바르지 않습니다: {message} — 사용법은 --help", file=sys.stderr)
        sys.exit(2)


# ── 합치기 ──────────────────────────────────────────────────

def 메모칸(이름: str) -> bool:
    return 이름.startswith("_")


def 선택지칸(이름: str) -> bool:
    return 이름 == "선택지" or 이름.endswith("_선택지")


def 합치기(공통값: dict, 커스텀값: dict, 경로: str = "", 기록: dict | None = None) -> dict:
    if 기록 is None:
        기록 = {"덮음": [], "새칸": [], "모양바뀜": [], "버림": [], "같은값": []}
    결과: dict = {}
    버릴: set[str] = set()
    for 키, 값 in 커스텀값.items():
        if 메모칸(키) or 키 not in 공통값:
            continue
        for 꼬리 in 딸린_칸:
            if not 키.endswith(꼬리) and 키 + 꼬리 in 공통값 and 키 + 꼬리 not in 커스텀값:
                버릴.add(키 + 꼬리)
    for 키, 값 in 공통값.items():
        if 키 in 버릴:
            기록["버림"].append(f"{경로}{키}")
            continue
        if 키 not in 커스텀값:
            결과[키] = 값
            continue
        새값 = 커스텀값[키]
        if isinstance(값, dict) and isinstance(새값, dict):
            결과[키] = 합치기(값, 새값, f"{경로}{키}.", 기록)
            continue
        결과[키] = 새값
        if 새값 == 값:
            if not any(키.endswith(꼬리) and 키[: -len(꼬리)] in 커스텀값 for 꼬리 in 딸린_칸):
                기록["같은값"].append(f"{경로}{키}")
        else:
            기록["덮음"].append(f"{경로}{키}")
            고르기 = 선택지칸(키) or (isinstance(값, str) and 값.startswith("선택지"))
            if type(새값) is not type(값) and not 고르기:
                기록["모양바뀜"].append(f"{경로}{키}: {type(값).__name__} → {type(새값).__name__}")
    for 키, 값 in 커스텀값.items():
        if 키 in 공통값:
            continue
        결과[키] = 값
        if not 메모칸(키) and not any(메모칸(조각) for 조각 in 경로.split(".") if 조각):
            기록["새칸"].append(f"{경로}{키}")
    return 결과


def 남은_선택지(공통값, 최종값, 경로: str = "") -> list[str]:
    남음: list[str] = []
    if not isinstance(공통값, dict) or not isinstance(최종값, dict):
        return 남음
    for 키, 값 in 공통값.items():
        if 키 not in 최종값 or 메모칸(키):
            continue
        최종 = 최종값[키]
        if 키 == "선택지" and isinstance(최종값.get("대체"), str) and 최종값.get("대체") != 공통값.get("대체") \
                and not 최종값["대체"].startswith("선택지"):
            continue
        본칸 = 키[: -len("_선택지")] if 키.endswith("_선택지") else None
        if 본칸 and 본칸 in 공통값 and 최종값.get(본칸) != 공통값[본칸]:
            continue
        if isinstance(값, dict):
            남음 += 남은_선택지(값, 최종, f"{경로}{키}.")
        elif 최종 == 값 and (
            (선택지칸(키) and isinstance(값, list) and len(값) > 1)
            or (isinstance(값, str) and 값.startswith("선택지") and not isinstance(최종값.get("선택지"), str))
        ):
            남음.append(f"{경로}{키}")
    return 남음


def 확인전_칸(값, 경로: str = "") -> list[str]:
    칸: list[str] = []
    if not isinstance(값, dict):
        return 칸
    for 키, 속 in 값.items():
        if "확인전" in 키:
            if isinstance(속, dict) and 속:
                칸 += [f"{경로}{키}.{작은키}" for 작은키 in 속]
            else:
                칸.append(f"{경로}{키}")
        else:
            칸 += 확인전_칸(속, f"{경로}{키}.")
    return 칸


def 최종_만들기(공통값: dict, 커스텀값: dict) -> tuple[dict, dict]:
    기록: dict = {"덮음": [], "새칸": [], "모양바뀜": [], "버림": [], "같은값": []}
    몸통 = 합치기({k: v for k, v in 공통값.items() if k not in 공통_머리}, 커스텀값, "", 기록)
    머리 = {
        "_합친_정보": {
            "안내": "도구(디자인시스템합치기.py)가 만든 파일 — 직접 고치지 말고 커스텀 json을 고친 뒤 다시 돌린다",
            "계정": 커스텀값.get("_계정", ""),
            "공통_판": 공통값.get("판", ""),
            "공통_기준일": 공통값.get("기준일", ""),
            "커스텀_기준_공통판": 커스텀값.get("_기준_공통판", ""),
            "커스텀_작성일": 커스텀값.get("_작성일", ""),
            "만든_날": 오늘(),
        }
    }
    최종 = {**머리, **{k: v for k, v in 몸통.items() if k not in 머리}}
    기록["남은선택지"] = 남은_선택지(공통값, 최종)
    기록["확인전"] = 확인전_칸(커스텀값)
    if 커스텀값.get("_기준_공통판") and 커스텀값.get("_기준_공통판") != 공통값.get("판"):
        기록["판다름"] = f"커스텀은 공통 {커스텀값.get('_기준_공통판')} 기준, 지금 공통은 {공통값.get('판')}"
    return 최종, 기록


def json_읽기(경로: Path) -> dict:
    try:
        return json.loads(경로.read_text(encoding="utf-8"))
    except FileNotFoundError:
        실패(f"파일이 없습니다: {경로}")
    except json.JSONDecodeError as e:
        실패(f"json 모양이 잘못됐습니다: {경로} ({e})")


def 공통_찾기(폴더: Path, 준것: str | None) -> Path:
    if 준것:
        return Path(준것)
    후보 = [폴더 / "디자인시스템_공통.json",
          Path(__file__).resolve().parent.parent / "2_커스텀설계서" / "디자인시스템_공통.json"]
    for p in 후보:
        if p.exists():
            return p
    실패("공통 json을 못 찾았습니다. --공통 <경로>로 알려 주세요.")


def main(argv: list[str] | None = None) -> int:
    p = 한글ArgumentParser(description="공통 json + 커스텀 json → 디자인시스템_최종.json")
    p.add_argument("폴더", help="디자인시스템_커스텀.json이 있는 폴더(이 묶음에서는 2_커스텀설계서)")
    p.add_argument("--공통", default=None, help="공통 json 경로(안 주면 같은 폴더의 디자인시스템_공통.json)")
    p.add_argument("--write", action="store_true", help="폴더의 디자인시스템_최종.json에 저장")
    p.add_argument("--출력", default=None, help="저장할 다른 경로(시험용 — 이걸 주면 그곳에 저장)")
    a = p.parse_args(argv)

    폴더 = Path(a.폴더)
    if not (폴더 / "디자인시스템_커스텀.json").exists():
        실패(f"{폴더} 안에 디자인시스템_커스텀.json이 없습니다.")
    공통경로 = 공통_찾기(폴더, a.공통)
    공통값 = json_읽기(공통경로)
    커스텀값 = json_읽기(폴더 / "디자인시스템_커스텀.json")
    최종, 기록 = 최종_만들기(공통값, 커스텀값)

    줄 = [f"# 디자인 시스템 합치기 — 공통 {공통값.get('판', '?')}({공통값.get('기준일', '?')})", "",
         f"## {nfc(폴더.resolve().name)}", "",
         f"- 덮은 칸 {len(기록['덮음'])} · 새 칸 {len(기록['새칸'])} · 버린 권고·근거 {len(기록['버림'])}"
         f" · 남은 선택지 {len(기록['남은선택지'])} · 확인 전 {len(기록['확인전'])}"]
    if 기록.get("판다름"):
        줄.append(f"- 주의: {기록['판다름']}")
    for 제목, 키 in (("모양 바뀜", "모양바뀜"), ("버린 권고·근거", "버림"),
                    ("아직 고르지 않은 선택지", "남은선택지"), ("확인 전", "확인전")):
        if 기록[키]:
            줄.append(f"- {제목}: " + " · ".join(f"`{x}`" for x in 기록[키]))
    저장 = Path(a.출력) if a.출력 else (폴더 / "디자인시스템_최종.json" if a.write else None)
    if 저장:
        저장.parent.mkdir(parents=True, exist_ok=True)
        저장.write_text(json.dumps(최종, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        줄.append(f"- 저장: {저장}")
    else:
        줄.append("(화면만 — 저장하려면 --write)")
    print("\n".join(줄))
    return 0


if __name__ == "__main__":
    sys.exit(main())
