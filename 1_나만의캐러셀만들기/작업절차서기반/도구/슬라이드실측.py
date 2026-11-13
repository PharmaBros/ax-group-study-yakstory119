#!/usr/bin/env python3
"""슬라이드 실측 — 02/슬라이드 편마다 표지 크기·비율·장 수·주요 색을 잽니다(작업 절차서 부록 B 설계서 "슬라이드 비율", "종류별 장 구성", "색" 칸의 숫자 근거).

사용법:  python3 -I 도구/슬라이드실측.py <약사님폴더> [--편 N] [--종류 X] [--포함개인일상] [--write]

  --편 N     앞에서부터 N편만(시험용)
  --종류 X   분류.md의 종류가 X인 편만(예: "공구 안내")
  --포함개인일상  개인 일상 종류 편도 잰다(기본은 뺀다)
  --write    03_분석/{오늘}_슬라이드실측.md 와 같은 이름의 .json(값)으로 저장

재는 것
  - 편마다: 표지 크기, 비율(1:1 / 4:5 / 3:4 / 9:16 / 기타, 오차 2%), 장 수, 해상도 낮음(가로 1080 미만),
    표지 밝기 평균, 배경이 사진인지(색 수·엣지 밀도로 추정 — "추정"이라고 표시), 주요 색 상위 6개(무채색은 하나로 묶고 유채색 5개)
  - 계정 전체: 비율 분포, 종류별 장 수 최소/최대/중앙값, 유채색 상위 10개(근거 편 수)
  - 720px 편(표지 가로 1080 미만)도 색 집계에 넣고, 표에는 "표지 가로 1080 미만"이라고만 표시합니다.
  - 면적 상위 색은 바탕색입니다(설계서 '색' 칸의 바탕).
  - 강조색 후보(양식 '강조 1~3')는 두 단계로 봅니다: (a) 배경이 "단색·그래픽(추정)"인 장만 골라 (b) 그 장들만 따로 480px 썸네일·16단위로 세어,
    채도 높은 색(HSV S≥0.45·V≥0.35, 피부·나무 띠 H 10~45°이면서 S<0.75 는 뺌) 가운데 픽셀 수 순 상위 5. 사진 장은 강조색 집계에서 뺍니다.
    얇은 글자색은 못 잡을 수 있어, 글자 강조색은 한눈에보기로 사람이 확정합니다.
  - 개인 일상 종류 편은 기본으로 뺍니다(--포함개인일상 으로 넣음).
  - 그림이 0장이거나 못 읽은 편은 "못 잰 편" 표로 따로 보여 주고 비율·장 수 집계에서 뺍니다.
글자 높이는 재지 않습니다(정확도가 낮아서).
"""
from __future__ import annotations

import argparse
import colorsys
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

try:
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    공통.실패("Pillow가 설치돼 있지 않습니다. 터미널에서 `python3 -m pip install Pillow` 를 실행해 주세요.")

비율표 = [("1:1", 1.0), ("4:5", 0.8), ("3:4", 0.75), ("9:16", 9 / 16), ("16:9", 16 / 9), ("1.91:1", 1.91)]
양자화단계 = 32   # 색을 32단위로 뭉친다(채널당 8단계)
강조_썸네일 = 480   # 강조색 후보용 썸네일 긴 변(px)
설계서5종 = {"제품소개", "공구안내", "영양제트렌드", "건강정보", "개인일상"}
강조_양자화 = 16    # 강조색 후보용 색 뭉침 단위


# ──────────────────────────── 핵심 함수(테스트 대상) ────────────────────────────

def 비율_판정(w: int, h: int, 오차=0.02) -> str:
    if not w or not h:
        return "기타"
    r = w / h
    for 이름, 기준 in 비율표:
        if abs(r - 기준) / 기준 <= 오차:
            return 이름
    return "기타"


def 무채색인가(r: int, g: int, b: int) -> bool:
    """흰·검·회색: 채널 차이가 작으면 무채색."""
    return max(r, g, b) - min(r, g, b) <= 24


def 강조색_후보인가(r: int, g: int, b: int) -> bool:
    """채도 S≥0.45 이고 명도 V≥0.35 인 색(HSV). 피부·나무 띠(색상 H 10~45°이면서 S<0.75)는 뺀다."""
    h, sat, val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if 10 <= h * 360 <= 45 and sat < 0.75:
        return False
    return sat >= 0.45 and val >= 0.35


def hex색(r: int, g: int, b: int) -> str:
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


def 색_세기(im: Image.Image, 최대변=160, 단계=None) -> dict:
    """그림의 색을 `단계`(기본 32)단위 칸으로 뭉쳐 센다. 칸 → [픽셀 수, R합, G합, B합] (대표색은 칸 안 실제 평균)."""
    단계 = 단계 or 양자화단계
    im = im.convert("RGB")
    im.thumbnail((최대변, 최대변))
    d: dict = {}
    for r, g, b in im.getdata():
        k = (r // 단계, g // 단계, b // 단계)
        v = d.get(k)
        if v is None:
            d[k] = [1, r, g, b]
        else:
            v[0] += 1; v[1] += r; v[2] += g; v[3] += b
    return d


def 색_합치기(전체: dict, 추가: dict) -> None:
    for k, v in 추가.items():
        t = 전체.get(k)
        if t is None:
            전체[k] = list(v)
        else:
            for i in range(4):
                t[i] += v[i]


def 대표색(v: list) -> tuple[int, int, int]:
    n = v[0] or 1
    return (round(v[1] / n), round(v[2] / n), round(v[3] / n))


def 주요색(d: dict, 유채색수=5) -> dict:
    """{'무채색비율': %, '유채색': [(hex, %, 칸), ...]} — 칸은 계정 전체 합산용 키."""
    전체 = sum(v[0] for v in d.values()) or 1
    무채 = 0
    유채 = []
    for k, v in sorted(d.items(), key=lambda t: -t[1][0]):
        rgb = 대표색(v)
        if 무채색인가(*rgb):
            무채 += v[0]
        else:
            유채.append((hex색(*rgb), round(v[0] / 전체 * 100, 1), "-".join(map(str, k))))
    return {"무채색비율": round(무채 / 전체 * 100, 1), "유채색": 유채[:유채색수]}


def 강조색_후보(d: dict, 상위=5) -> list:
    """단색·그래픽 장만 모아 센 칸(d)에서 강조색 조건을 통과하는 칸을 픽셀 수 순 상위로. [(hex, %, 칸), ...] (%는 그 장들 안 비율)"""
    전체 = sum(v[0] for v in d.values()) or 1
    결과 = []
    for k, v in sorted(d.items(), key=lambda t: -t[1][0]):
        rgb = 대표색(v)
        if 강조색_후보인가(*rgb):
            결과.append((hex색(*rgb), round(v[0] / 전체 * 100, 1), "-".join(map(str, k))))
    return 결과[:상위]


def 표지_특징(im: Image.Image) -> dict:
    """밝기 평균(0~255)과 배경이 사진인지 추정(16단위 색 가운데 상위 3색이 차지하는 비율이 55% 미만이면 사진)."""
    im = im.convert("RGB")
    im.thumbnail((160, 160))
    px = list(im.getdata())
    n = len(px) or 1
    밝기 = round(statistics.mean((r * 299 + g * 587 + b * 114) // 1000 for r, g, b in px), 1)
    c16 = Counter((r // 16, g // 16, b // 16) for r, g, b in px)
    상위3 = round(sum(cnt for _, cnt in c16.most_common(3)) / n * 100, 1)
    g = im.convert("L").filter(ImageFilter.FIND_EDGES)
    엣지밀도 = round(sum(1 for v in g.getdata() if v > 40) / n * 100, 1)
    사진 = 상위3 < 55
    return {"밝기": 밝기, "상위3색비율": 상위3, "엣지밀도": 엣지밀도, "배경추정": "사진(추정)" if 사진 else "단색·그래픽(추정)"}


# ──────────────────────────── 본체 ────────────────────────────

def 실측(정보: dict, 편수제한: int | None, 종류필터: str | None, 포함개인일상: bool = False) -> dict:
    분류 = 공통.분류_읽기(정보)
    편들 = 공통.편_목록(정보)
    if 종류필터:
        f = 공통.종류_키(종류필터)
        편들 = [e for e in 편들 if 공통.종류_키(분류["편"].get(e["이름"], "")) == f]
    제외개인 = []
    if not 포함개인일상:
        제외개인 = [e["이름"] for e in 편들 if 공통.개인일상인가(분류["편"].get(e["이름"], ""))]
        편들 = [e for e in 편들 if e["이름"] not in 제외개인]
    if 편수제한:
        편들 = 편들[:편수제한]
    결과 = {"계정": 정보["이름"], "날짜": 공통.오늘(), "편": [], "분류열": 분류["열이름"], "개인일상제외": 제외개인}
    for 편 in 편들:
        항 = {"편": 편["이름"], "종류": 분류["편"].get(편["이름"], "(분류 없음)"), "장수": len(편["이미지"])}
        if not 편["이미지"]:
            항.update({"표지": None, "비율": "기타", "저해상도": True, "오류": "그림 0장", "못잼": True})
            결과["편"].append(항)
            continue
        try:
            with Image.open(편["이미지"][0][1]) as im:
                w, h = im.size
                항["표지"] = f"{w}×{h}"
                항["가로"], 항["세로"] = w, h
                항["비율"] = 비율_판정(w, h)
                항["저해상도"] = w < 1080
                항.update(표지_특징(im))
            전체: dict = {}
            그래픽: dict = {}   # 배경이 단색·그래픽(추정)인 장만 따로(강조색 후보용)
            그래픽장 = 0
            for _, p in 편["이미지"]:
                with Image.open(p) as im2:
                    색_합치기(전체, 색_세기(im2))
                    if 표지_특징(im2)["배경추정"].startswith("단색"):
                        그래픽장 += 1
                        색_합치기(그래픽, 색_세기(im2, 강조_썸네일, 강조_양자화))
            항["색"] = 주요색(전체)
            항["색"]["강조색후보"] = 강조색_후보(그래픽)
            항["그래픽장수"] = 그래픽장
        except Exception as e:  # 깨진 그림 등
            항.update({"오류": "그림 파일을 열 수 없음(깨짐 또는 iCloud 미다운로드)", "비율": 항.get("비율", "기타"), "저해상도": True, "못잼": True})
            항.pop("표지", None)
        결과["편"].append(항)
    return 결과


def 보고서(R: dict) -> str:
    표 = 공통.마크다운표
    전체편 = R["편"]
    못잰 = [e for e in 전체편 if e.get("못잼")]
    편들 = [e for e in 전체편 if not e.get("못잼")]
    import datetime as _dt
    L = [f"# {R['계정']} 슬라이드 실측 ({R['날짜']})", "",
         f"실행: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · 입력: 편 {len(전체편)}(잰 편 {len(편들)}) — [도구] 칸에 옮길 때 이 실행 시각을 함께 적는다.",
         f"근거: 02/슬라이드 {len(전체편)}편(잰 편 {len(편들)} · 못 잰 편 {len(못잰)}), 표지는 번호가 가장 작은 장. 종류는 02/분류.md(`{R['분류열'] or '없음'}` 열). "
         "색은 모든 장을 32단위로 뭉쳐 센 값(대표 hex)이라 실제 디자인 색과 ±16 정도 차이가 날 수 있습니다. 배경 판정은 추정입니다. "
         f"면적 상위는 바탕색입니다. 강조색 후보는 배경이 단색·그래픽(추정)인 장만 {강조_썸네일}px 썸네일·16단위로 따로 세어 채도 높은 색을 뽑은 것이라 "
         "얇은 글자색은 못 잡을 수 있습니다(한눈에보기로 사람이 확정).", ""]
    if 편들 and not any(공통.종류_키(e["종류"]) in 설계서5종 for e in 편들):
        L += ["⚠ 02/분류.md가 설계서 5종으로 재분류되지 않아 5종 표가 비어 있음 — 작업 절차서 부록 A-1 판정표로 재분류한 뒤 다시 돌릴 것", ""]
    if R.get("개인일상제외"):
        L += [f"개인 일상 종류 {len(R['개인일상제외'])}편은 뺐습니다(`--포함개인일상` 으로 넣을 수 있음).", ""]

    # 편별
    L += ["## 편별 실측", 표(["편", "종류", "표지 크기", "비율", "장 수", "해상도", "표지 밝기", "배경(추정)"], [
        [e["편"], e["종류"], e.get("표지") or "-", e["비율"], e["장수"], "표지 가로 1080 미만" if e.get("저해상도") else "정상",
         e.get("밝기", "-"), e.get("배경추정", e.get("오류", "-"))] for e in 편들]), ""]

    # 비율 분포
    비율 = Counter(e["비율"] for e in 편들)
    크기 = defaultdict(Counter)
    for e in 편들:
        if e.get("표지"):
            크기[e["비율"]][e["표지"]] += 1
    L += ["## 슬라이드 비율 분포 → 양식 '슬라이드 비율'", 표(["비율", "편 수", "원본 크기(편 수)", "근거(편, 최대 6)"], [
        [k, v, " · ".join(f"{s}({n})" for s, n in 크기[k].most_common()),
         ", ".join([e["편"].split("_", 1)[-1] for e in 편들 if e["비율"] == k][:6]) + (" …" if v > 6 else "")]
        for k, v in 비율.most_common()]), ""]
    if 비율:
        L += [f"가장 많은 비율: **{비율.most_common(1)[0][0]}** ({비율.most_common(1)[0][1]}편 / {len(편들)}편)", ""]

    # 종류별 장 수
    종류장 = defaultdict(list)
    for e in 편들:
        종류장[e["종류"]].append(e["장수"])
    L += ["## 종류별 장 수 → 양식 '종류별 장 구성 > 장 수 범위'", 표(["종류", "편 수", "장 수 최소", "최대", "중앙값", "장 수 분포"], [
        [k, len(v), min(v), max(v), round(float(statistics.median(v)), 1), ", ".join(f"{n}장×{c}" for n, c in sorted(Counter(v).items()))]
        for k, v in sorted(종류장.items(), key=lambda t: -len(t[1]))]), ""]

    # 색(표지 가로 1080 미만 편도 포함)
    색편 = [e for e in 편들 if e.get("색")]
    L += ["## 편별 주요 색(유채색 상위 5 + 무채색 비율)", 표(["편", "종류", "해상도", "무채색(흰·검·회색) 비율", "유채색 1", "2", "3", "4", "5"], [
        [e["편"], e["종류"], "표지 가로 1080 미만" if e.get("저해상도") else "정상", f"{e['색']['무채색비율']}%",
         *[f"{h} {p}%" for h, p, _ in e["색"]["유채색"]], *[""] * (5 - len(e["색"]["유채색"]))]
        for e in 색편]), ""]
    L += ["## 편별 강조색 후보(단색·그래픽 장의 채도 높은 색 — 얇은 글자색은 못 잡을 수 있음, 한눈에보기로 사람이 확정; 배경 판정이 틀릴 때 제품 사진 색이 섞일 수 있음 — 계정 전체 표를 우선 본다) → 양식 '강조 1~3'",
          표(["편", "종류", "그래픽 장 수", "강조색 후보 1", "2", "3", "4", "5"], [
        [e["편"], e["종류"], f"{e.get('그래픽장수', 0)}/{e['장수']}", *[f"{h} {p}%" for h, p, _ in e["색"]["강조색후보"]], *[""] * (5 - len(e["색"]["강조색후보"]))]
        for e in 색편]), ""]

    def 모으기(키):
        합 = Counter(); 근거 = Counter(); 대표 = defaultdict(list)
        for e in 색편:
            for h, p, k in e["색"][키]:
                합[k] += p
                근거[k] += 1
                대표[k].append(h)
        return 합, 근거, 대표

    def 평균hex(hs):
        rs = [int(h[1:3], 16) for h in hs]; gs = [int(h[3:5], 16) for h in hs]; bs = [int(h[5:7], 16) for h in hs]
        return hex색(round(statistics.mean(rs)), round(statistics.mean(gs)), round(statistics.mean(bs)))

    합, 근거, 대표 = 모으기("유채색")
    상위 = sorted(합, key=lambda k: (-근거[k], -합[k]))[:10]
    L += ["## 계정 전체 유채색 상위 10(편별 상위 5에 든 색, 근거 편 수 순 — 면적 기준이라 바탕색 쪽) → 설계서 '색' 칸의 바탕", 표(["hex(근거 편 평균)", "근거 편 수", "비율 합(%)", "편당 평균(%)"], [
        [평균hex(대표[k]), 근거[k], round(합[k], 1), round(합[k] / 근거[k], 1)] for k in 상위]), ""]
    합2, 근거2, 대표2 = 모으기("강조색후보")
    상위2 = sorted(합2, key=lambda k: (-근거2[k], -합2[k]))[:5]
    L += ["## 계정 전체 강조색 후보(단색·그래픽 장의 채도 높은 색 — 얇은 글자색은 못 잡을 수 있음, 한눈에보기로 사람이 확정) 상위 5(편별 상위 5에 든 색, 근거 편 수 순) → 양식 '강조 1~3'", 표(["hex(근거 편 평균)", "근거 편 수", "비율 합(%)", "편당 평균(%)"], [
        [평균hex(대표2[k]), 근거2[k], round(합2[k], 1), round(합2[k] / 근거2[k], 1)] for k in 상위2]), ""]
    L += ["## 못 잰 편(그림 0장 또는 열 수 없음 — 비율·장 수 집계에서 뺌)", 표(["편", "종류", "장 수", "해상도", "사유"], [
        [e["편"], e["종류"], e["장수"], "-", e.get("오류", "-")] for e in 못잰]), ""]
    R["요약"] = {"비율": dict(비율), "종류별장수": {k: {"편수": len(v), "최소": min(v), "최대": max(v), "중앙값": round(float(statistics.median(v)), 1)} for k, v in 종류장.items()},
                "유채색상위": [{"hex": 평균hex(대표[k]), "근거편수": 근거[k], "비율합": round(합[k], 1)} for k in 상위],
                "강조색후보상위": [{"hex": 평균hex(대표2[k]), "근거편수": 근거2[k], "비율합": round(합2[k], 1)} for k in 상위2]}
    return "\n".join(L)


def main(argv=None):
    ap = 공통.한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    ap.add_argument("약사님폴더")
    ap.add_argument("--편", type=int, default=None, help="앞에서부터 N편만")
    ap.add_argument("--종류", default=None, help="이 종류의 편만")
    ap.add_argument("--포함개인일상", action="store_true", help="개인 일상 종류 편도 잰다")
    ap.add_argument("--write", action="store_true", help="03_분석/{오늘}_슬라이드실측.md 와 .json 으로 저장")
    ap.add_argument("-h", "--help", action="help", help="이 도움말")
    args = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(args.약사님폴더)
    R = 실측(정보, args.편, args.종류, args.포함개인일상)
    if not R["편"]:
        공통.실패("잴 편이 없습니다(02/슬라이드가 비어 있거나 --종류 조건에 맞는 편이 없음).")
    본문 = 보고서(R)
    print(본문)
    if args.write:
        p = 공통.결과_저장(정보, f"{공통.오늘()}_슬라이드실측.md", 본문 + "\n")
        pj = 공통.결과_저장(정보, f"{공통.오늘()}_슬라이드실측.json", json.dumps(R, ensure_ascii=False, indent=1))
        print(f"\n저장했습니다: {p}\n저장했습니다: {pj}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
