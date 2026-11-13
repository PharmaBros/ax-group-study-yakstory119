"""부품 폴더의 견본.json으로 README.md를 만든다.

절: 첫 줄 요약 / 근거 원본 장 / `## 모양 계열` / `## 편 안 자리` / `## 글 자리` / `## 고정 / 바꿔 끼우는 자리` /
`## 깔개·그림 처리` / `## 원본과 아직 다른 점`.
`## 모양 계열` 첫 줄은 `㉠ 이름 — 같은 계열: …` 꼴(비슷한장검사.py가 이 줄을 읽음). 같은 계열 부품은
부품 폴더와 나란히 있는 폴더들의 견본.json `모양_계열`이 같은 것으로 찾는다.
견본.json 칸: 화면 · 모양_계열 · 근거 · 근거_편 · 고정 · 바꿔_끼우는_자리 · 편_안_자리 · 글_자리 · 요소 · json_자리,
그리고 있으면 쓰는 칸: 요약 · 깔개_그림_처리 · 원본과_다른_점.

사용
  python3 -I 도구/부품/부품README.py <부품 폴더> [--모양표 <모양표.md>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import 공통  # noqa: E402

없음 = "(견본.json에 `{}` 없음 — 아직 적지 않음)"


def 줄들(값, 칸: str) -> list[str]:
    """문자열·리스트·dict를 '- ' 줄 목록으로."""
    if not 값:
        return ["- " + 없음.format(칸)]
    if isinstance(값, dict):
        return [f"- {k}: {v}" for k, v in 값.items()]
    if isinstance(값, list):
        return [f"- {v}" for v in 값]
    return [f"- {값}"]


def 같은계열(부품폴더: Path, 계열: str, 화면: str) -> list[str]:
    이름들 = {화면}
    for 형제 in 부품폴더.parent.glob("*/견본.json"):
        try:
            d = json.loads(형제.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if 공통.nfc(str(d.get("모양_계열", ""))).strip() == 계열:
            이름들.add(d.get("화면") or 형제.parent.name)
    return sorted(이름들)


def 모양표_줄(모양표: Path | None, 화면: str) -> str | None:
    """모양표집계.py가 만든 모양표.md의 부품별 표에서 이 부품 행을 한 줄로."""
    if 모양표 is None:
        return None
    for 표 in 공통.마크다운표_파싱(모양표.read_text(encoding="utf-8")):
        if "부품" in 표["헤더"] and "편 안 자리" in 표["헤더"]:
            열 = {h: i for i, h in enumerate(표["헤더"])}
            for 행 in 표["행"]:
                if 행[0] == 화면:
                    return (f"모양표: {행[열['구분']]} — {행[열['편 수']]}편 {행[열['장 수']]}장, "
                            f"편 안 자리 {행[열['편 안 자리']]}, 근거 장 {행[열['근거 장']]}")
    return f"모양표에 '{화면}' 행이 없음"


def 편당_최대(모양표: Path | None, 계열: str) -> int:
    """모양표 근거 장에서 이 계열 장이 한 편에 가장 많이 나온 수(모양표가 없거나 계열 행이 없으면 1)."""
    if 모양표 is None:
        return 1
    편별: dict[str, int] = {}
    for 표 in 공통.마크다운표_파싱(모양표.read_text(encoding="utf-8")):
        if "부품" in 표["헤더"] and "근거 장" in 표["헤더"] and "계열" in 표["헤더"]:
            열 = {h: i for i, h in enumerate(표["헤더"])}
            for 행 in 표["행"]:
                if 공통.nfc(행[열["계열"]]).strip() == 계열 and 행[열["구분"]] == "부품":
                    for 장 in 행[열["근거 장"]].split(","):
                        편 = 장.strip().rsplit("/", 1)[0]
                        if 편:
                            편별[편] = 편별.get(편, 0) + 1
    return max(편별.values(), default=1)


def 그림_줄(d: dict) -> list[str]:
    결과 = []
    for e in d.get("요소", []):
        if e.get("종류") in ("바탕", "그림"):
            이름 = e.get("이름") or e.get("종류")
            내용 = e.get("파일") or e.get("색") or ""
            결과.append(f"- {e['종류']} {이름}: {내용}" + (f" — {e['메모']}" if e.get("메모") else ""))
    return 결과 + (줄들(d["깔개_그림_처리"], "깔개_그림_처리") if d.get("깔개_그림_처리") else [])


def 만들기(부품폴더: Path, 모양표: Path | None = None) -> str:
    경로 = 부품폴더 / "견본.json"
    if not 경로.is_file():
        공통.실패(f"견본.json이 없습니다: {부품폴더}")
    try:
        d = json.loads(경로.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        공통.실패(f"견본.json을 읽지 못했습니다(JSON 오류): {e}")
    화면 = d.get("화면") or 부품폴더.name
    계열 = 공통.nfc(str(d.get("모양_계열", ""))).strip()
    if not 계열:
        공통.실패(f"견본.json에 `모양_계열`이 없습니다: {경로}")
    t = [f"# {화면}", "", d.get("요약") or f"{화면} — {d.get('고정', '')}", "",
         f"근거 원본 장: {d.get('근거_편') or d.get('근거', '')}", "",
         "## 모양 계열",
         f"{계열} — 같은 계열: {' · '.join(같은계열(부품폴더, 계열, 화면))}. " + (
             "한 편에 이 계열은 1장만." if (최대 := 편당_최대(모양표, 계열)) <= 1 else f"한 편에 이 계열은 최대 {최대}장(원본 편당 최대 {최대}장 — 모양표)."), "",
         "## 편 안 자리", ""]
    t += 줄들(d.get("편_안_자리"), "편_안_자리")
    표줄 = 모양표_줄(모양표, 화면)
    if 표줄:
        t.append(f"- {표줄}")
    t += ["", "## 글 자리", ""] + 줄들(d.get("글_자리"), "글_자리")
    t += ["", "## 고정 / 바꿔 끼우는 자리", "", f"- **고정**: {d.get('고정', '')}", "- **바꿔 끼우는 자리**:"]
    바 = d.get("바꿔_끼우는_자리")
    t += [f"  - {v}" for v in (바 if isinstance(바, list) else [바 or ""])]
    t += ["", "## 깔개·그림 처리", ""] + (그림_줄(d) or ["- (그림·바탕 요소 없음)"])
    t += ["", "## 원본과 아직 다른 점", ""] + 줄들(d.get("원본과_다른_점"), "원본과_다른_점")
    return "\n".join(t) + "\n"


def main(argv=None) -> int:
    ap = 공통.한글ArgumentParser(description="부품 폴더의 견본.json으로 README.md를 만든다(같은 폴더에 저장).")
    ap.add_argument("부품폴더", help="견본.json이 있는 부품 폴더 (작업 폴더 기준)")
    ap.add_argument("--모양표", help="모양표집계.py가 만든 모양표.md (있으면 편 안 자리에 모양표 숫자를 넣음)")
    a = ap.parse_args(argv)
    폴더 = 공통.작업폴더_경로(a.부품폴더)
    if not 폴더.is_dir():
        공통.실패(f"부품 폴더를 찾을 수 없습니다: {a.부품폴더}")
    표 = None
    if a.모양표:
        표 = 공통.작업폴더_경로(a.모양표)
        if not 표.is_file():
            공통.실패(f"모양표 파일을 찾을 수 없습니다: {a.모양표}")
    글 = 만들기(폴더, 표)
    (폴더 / "README.md").write_text(글, encoding="utf-8")
    print(f"저장: {폴더 / 'README.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
