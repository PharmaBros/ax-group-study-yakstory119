"""장마다 판정한 모양(부품·계열)을 모아 모양표를 만든다.

대표 슬라이드 각 편 `사진메모.json`의 장별 `부품`·`계열`·`모양`과 `02_대표슬라이드/분류.md`의 종류를 읽어
부품마다 편 수·장 수·쓰인 종류·편 안 자리·근거 장·견본 장 후보를 센다. 2편 이상 쓰인 것은 "부품", 1편뿐이면 "드묾".
`부품`이 없는(판정 전) 장이 있으면 맨 위에 경고한다.

사용
  python3 -I 도구/모양표집계.py <약사님폴더>            # 화면에만 보여 줌
  python3 -I 도구/모양표집계.py <약사님폴더> --write    # 03_분석/{오늘}_모양표.md 로 저장
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

캡처바탕 = "영상·자료 캡처"
바탕이름 = {"사진 바탕": "사진", "그래픽·단색 바탕": "그래픽·단색", 캡처바탕: "캡처"}
종류모름 = "(종류 모름)"


def 편_읽기(정보: dict) -> list[dict]:
    """편마다 {이름, 종류, 장: [{장, 부품, 계열, 모양, 바탕}]}. 사진메모.json이 없는 편은 그림 수만큼 판정 전 장으로 센다."""
    종류들 = 공통.분류_읽기(정보)
    편들 = []
    for 편 in 공통.편_목록(정보):
        종류 = 종류들["편"].get(편["이름"]) or 종류들["아이디"].get(편["이름"].split("_", 1)[-1]) or 종류모름
        메모 = 공통.파일_찾기(편["경로"], "사진메모.json")
        if 메모 is None:
            장들 = [{"장": n, "부품": None, "계열": None, "모양": None, "바탕": None} for n, _ in 편["이미지"]]
        else:
            try:
                원본 = json.loads(메모.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                공통.실패(f"{편['이름']} 사진메모.json을 읽지 못했습니다(JSON 오류): {e}")
            장들 = [{"장": x.get("장"), "부품": x.get("부품") or None, "계열": x.get("계열"),
                    "모양": x.get("모양"), "바탕": x.get("바탕")} for x in 원본]
        편들.append({"이름": 편["이름"], "종류": 종류, "장": 장들})
    return 편들


def 집계(편들: list[dict]) -> dict:
    부품 = {}
    바탕 = defaultdict(Counter)
    순서 = defaultdict(list)
    판정전 = 0
    for 편 in 편들:
        마지막 = max((x["장"] for x in 편["장"] if isinstance(x["장"], int)), default=0)
        for x in 편["장"]:
            바탕[편["종류"]][바탕이름.get(x["바탕"], "기타")] += 1
            캡처 = not x["부품"] and (x["모양"] or "").strip() == "캡처"  # 절차서 1단계 9: 캡처 장은 부품 null
            순서[편["종류"]].append((편["이름"], x["부품"] or ("캡처" if 캡처 else "?")))
            if not x["부품"]:
                판정전 += 0 if 캡처 else 1
                continue
            p = 부품.setdefault(x["부품"], {"편": set(), "장": [], "종류": Counter(), "계열": x["계열"], "마지막": []})
            p["편"].add(편["이름"])
            p["장"].append((편["이름"], x["장"], 편["종류"], x["바탕"]))
            p["종류"][편["종류"]] += 1
            p["마지막"].append(x["장"] == 마지막)
    return {"부품": 부품, "바탕": 바탕, "순서": 순서, "판정전": 판정전}


def 자리(p: dict) -> str:
    번호 = [n for _, n, _, _ in p["장"]]
    분포 = ", ".join(f"{n}장×{c}" for n, c in sorted(Counter(번호).items(), key=lambda t: (t[0] is None, t[0])))
    if all(n == 1 for n in 번호):
        이름 = "1장만"
    elif all(p["마지막"]):
        이름 = "마지막 장만"
    else:
        이름 = "중간"
    return f"{이름} ({분포})"


def 견본후보(p: dict) -> str:
    """가장 많이 쓰인 종류 안에서, 영상·자료 캡처가 아닌 첫 장."""
    종류 = sorted(p["종류"].items(), key=lambda t: (-t[1], t[0]))[0][0]
    for 편, n, k, 바탕 in sorted(p["장"], key=lambda t: (t[0], t[1] or 0)):
        if k == 종류 and 바탕 != 캡처바탕:
            return f"{편}/{n}장"
    return "-"


def 보고서(정보: dict, 편들: list[dict]) -> str:
    g = 집계(편들)
    줄 = [f"# 모양표 — {정보['표시이름']} ({정보['계정']})", ""]
    if g["판정전"]:
        줄 += [f"> **경고: 부품 판정 전 장 {g['판정전']}개** — 사진메모.json의 `부품` 칸이 비어 있음. 판정 뒤 다시 돌리세요.", ""]
    장수 = sum(len(e["장"]) for e in 편들)
    반복 = [k for k, p in g["부품"].items() if len(p["편"]) >= 2]
    줄 += [f"편 {len(편들)} · 장 {장수} · 판정된 부품 {len(g['부품'])}개(2편 이상 {len(반복)}개 / 드묾 {len(g['부품']) - len(반복)}개)", ""]
    행 = []
    for 이름, p in sorted(g["부품"].items(), key=lambda t: (-len(t[1]["편"]), -len(t[1]["장"]), t[0])):
        행.append([이름, "부품" if len(p["편"]) >= 2 else "드묾", len(p["편"]), len(p["장"]), p["계열"] or "",
                 ", ".join(f"{k}({c})" for k, c in sorted(p["종류"].items(), key=lambda t: (-t[1], t[0]))),
                 자리(p), ", ".join(f"{e}/{n}장" for e, n, _, _ in p["장"]), 견본후보(p)])
    줄 += ["## 부품별", "", 공통.마크다운표(["부품", "구분", "편 수", "장 수", "계열", "쓰인 종류(장)", "편 안 자리", "근거 장", "견본 장 후보"], 행), ""]
    행 = []
    for 종류, c in sorted(g["바탕"].items()):
        합 = sum(c.values())
        행.append([종류, 합] + [f"{c[k]} ({c[k] / 합:.0%})" for k in ("사진", "그래픽·단색", "캡처")])
    줄 += ["## 종류별 바탕 비율", "", 공통.마크다운표(["종류", "장 수", "사진", "그래픽·단색", "캡처"], 행), ""]
    줄 += ["## 종류별 장 순서 예 (편마다 부품 이름, ? = 판정 전)", ""]
    for 종류, 목록 in sorted(g["순서"].items()):
        줄.append(f"### {종류}")
        편별 = defaultdict(list)
        for 편, 부품 in 목록:
            편별[편].append(부품)
        줄 += [f"- {편}: " + " → ".join(v) for 편, v in 편별.items()]
        줄.append("")
    return "\n".join(줄)


def main(argv=None) -> int:
    ap = 공통.한글ArgumentParser(description="장마다 판정한 모양(부품)을 모아 모양표를 만든다. 기본은 화면만 보여 준다.")
    ap.add_argument("약사님폴더", help="예: 홍길동약사_hong_yaksa (작업 폴더 기준)")
    ap.add_argument("--write", action="store_true", help="03_분석/{오늘}_모양표.md 로 저장")
    a = ap.parse_args(argv)
    정보 = 공통.약사님폴더_검사(a.약사님폴더)
    편들 = 편_읽기(정보)
    if not 편들:
        공통.실패("02_대표슬라이드/슬라이드 안에 편 폴더가 없습니다.")
    글 = 보고서(정보, 편들)
    print(글)
    if a.write:
        print(f"저장: {공통.결과_저장(정보, 공통.오늘() + '_모양표.md', 글)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
