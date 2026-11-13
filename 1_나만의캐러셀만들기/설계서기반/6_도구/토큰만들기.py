"""최종 json + 글꼴표로 디자인 시스템 화면의 `project/tokens.json`(색·글씨·글꼴 파일·여백·모서리 견본)을 만든다.

사용: python3 -I 6_도구/토큰만들기.py <디자인시스템_최종.json> <project 폴더> [--이름 약들약_yakstory119] [--제목글꼴 <글꼴 이름>]
  예) python3 -I 6_도구/토큰만들기.py 2_커스텀설계서/디자인시스템_최종.json 7_결과/디자인시스템화면/project
- 값은 모두 최종 json에서 가져온다(이 도구가 새 숫자를 만들지 않는다). 글씨 크기는 json 범위의 작은 쪽.
- 글꼴 파일 목록(type.fonts)은 5_글꼴/글꼴표.json에서, 파일이 project/fonts/에 있는 것만 넣는다
  (없는 것은 화면에 알려 준다 — 5_글꼴의 파일을 project/fonts/로 먼저 복사).
- --제목글꼴: 제목 글꼴 이름(font-family). 안 주면 5_글꼴/글꼴표.json의 `제목글꼴`(없으면 잘난체2).
- 글씨 역할표(type.families)와 굵기: 글꼴표.json에 `families`·`굵기`가 있으면 그 값을 쓴다(계정마다 글꼴이 달라서).
  없으면 예전 기본값(잘난체2·지마켓 산스·Pretendard·싱글데이·나눔스퀘어라운드·도현·카페24 당당해).
- 이미 tokens.json이 있으면 지우지 않고 `tokens_이전_<날짜시각>.json`으로 이름을 바꿔 둔다.
- Design System 아티팩트 종류의 안내가 tokens.json 꼴을 다르게 말하면 그 안내가 우선이다.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def 인자(argv):
    자리, 옵션 = [], {"이름": None, "제목글꼴": None}
    i = 0
    while i < len(argv):
        if argv[i] in ("--이름", "--제목글꼴") and i + 1 < len(argv):
            옵션[argv[i][2:]] = argv[i + 1]; i += 2; continue
        자리.append(argv[i]); i += 1
    return 자리, 옵션


def hex들(v) -> list[str]:
    if isinstance(v, str):
        return [v.lower()] if HEX.match(v) else []
    if isinstance(v, list):
        return [x.lower() for x in v if isinstance(x, str) and HEX.match(x)]
    if isinstance(v, dict):
        for k in ("hex", "선택지", "값"):
            if k in v:
                return hex들(v[k])
    return []


def main(argv) -> int:
    자리, 옵션 = 인자(argv)
    if len(자리) != 2:
        print(__doc__); return 2
    최종 = json.loads(Path(자리[0]).read_text(encoding="utf-8"))
    project = Path(자리[1]); project.mkdir(parents=True, exist_ok=True)
    색 = 최종.get("색", {}); 보조 = 색.get("보조", {}) if isinstance(색.get("보조"), dict) else {}
    토큰 = []

    def 넣기(이름, 값들, 쓰는곳):
        if len(값들) == 1:
            토큰.append({"name": 이름, "value": 값들[0], "usage": 쓰는곳})
        else:
            for n, v in enumerate(값들, 1):
                토큰.append({"name": f"{이름}-{n}", "value": v, "usage": f"{쓰는곳} — {n}번째"})

    넣기("bg", hex들(색.get("바탕")), "장 바탕(색.바탕)")
    넣기("ink", hex들(색.get("본문")), "본문 글자(색.본문)")
    넣기("title", hex들(색.get("제목")), "제목 글자(색.제목)")
    넣기("ink-on-photo", hex들(색.get("본문_사진위")), "사진 위 글자(색.본문_사진위)")
    넣기("accent", hex들(색.get("강조")), "핵심 낱말 색글자(색.강조)")
    넣기("highlight", hex들(색.get("형광펜")), "형광·띠(색.형광펜)")
    넣기("orange", hex들(보조.get("주황_선택지")), "보조색(색.보조.주황_선택지)")
    넣기("blue", hex들(보조.get("파랑_선택지")), "보조색(색.보조.파랑_선택지)")
    초록 = hex들(보조.get("초록_선택지"))
    if len(초록) > 1:
        for n, v in enumerate(초록, 1):
            토큰.append({"name": f"green-choice-{n}", "value": v, "usage": f"고르기 전 — 후보 {n}. 보조색(색.보조.초록_선택지)"})
    else:
        넣기("green", 초록, "보조색(색.보조.초록_선택지)")
    if isinstance(색.get("바탕_선택지"), dict):
        넣기("cream", hex들(색["바탕_선택지"].get("미색")), "미색 바탕(색.바탕_선택지.미색)")

    글꼴표 = json.loads((여기.parent / "5_글꼴" / "글꼴표.json").read_text(encoding="utf-8"))
    표 = 글꼴표["fonts"]
    if not 옵션["제목글꼴"]:
        옵션["제목글꼴"] = 글꼴표.get("제목글꼴") or "잘난체2"
    fonts, 없음 = [], []
    for f in 표:
        if (project / "fonts" / f["file"]).exists():
            fonts.append({"family": f["family"], "file": f"fonts/{f['file']}", "weight": f["weight"]})
        else:
            없음.append(f"{f['family']}({f['file']})")
    families = {"title": f"\"{옵션['제목글꼴']}\", sans-serif", "subtitle": "\"지마켓 산스\", sans-serif",
                "body": "\"Pretendard\", sans-serif", "small": "\"Pretendard\", sans-serif",
                "hand": "\"싱글데이\", sans-serif", "round": "\"나눔스퀘어라운드\", sans-serif",
                "label-narrow": "\"도현\", sans-serif", "badge": "\"카페24 당당해\", sans-serif"}
    if isinstance(글꼴표.get("families"), dict):  # 계정 글꼴표에 역할표가 있으면 그것을 쓴다
        families = {"title": f"\"{옵션['제목글꼴']}\", sans-serif", **글꼴표["families"]}
        for 역할 in ("subtitle", "body", "small"):
            families.setdefault(역할, families["title"] if 역할 == "subtitle" else "\"Pretendard\", sans-serif")
    굵기표 = 글꼴표.get("굵기") if isinstance(글꼴표.get("굵기"), dict) else {}
    글씨 = 최종.get("글씨", {})
    styles = []
    for 역할, 칸, 굵기 in (("title", "제목", 400), ("subtitle", "소제목", 700), ("body", "본문", 400), ("small", "작은글씨", 400)):
        크기 = (글씨.get(칸) or {}).get("크기")
        if isinstance(크기, list) and 크기:
            styles.append({"name": 역할, "family": 역할, "fontSize": f"{min(크기)}px", "fontWeight": 굵기표.get(역할, 굵기),
                           "usage": f"대체 글꼴: {(글씨.get(칸) or {}).get('대체', '')} · 크기: 글씨.{칸}.크기 {크기[0]}~{크기[-1]} 중 작은 쪽 · 1080px 장 기준"})
    여백 = 최종.get("여백", {})
    spacing = []
    for 칸, 이름 in (("좌우", "margin-x"), ("위", "margin-top"), ("아래_계정표시까지", "margin-bottom")):
        v = 여백.get(칸)
        if isinstance(v, list) and len(v) >= 2 and all(isinstance(x, (int, float)) for x in v[:2]):
            spacing += [{"name": f"{이름}-min", "value": f"{v[0]}px", "usage": f"여백.{칸} 가장 좁게"},
                        {"name": f"{이름}-max", "value": f"{v[1]}px", "usage": f"여백.{칸} 가장 넓게"}]
    radius = []
    r = (최종.get("사진위글자") or {}).get("모서리px")
    if isinstance(r, (int, float)):
        radius.append({"name": "box", "value": f"{r}px", "usage": "사진 위 글 상자·바 모서리(사진위글자.모서리px)"})

    결과 = {"name": 옵션["이름"] or 최종.get("_계정", "") or "디자인 시스템", "version": 1,
          "color": {"themes": [{"id": "light", "name": "기본"}], "tokens": 토큰},
          "type": {"families": families, "groups": [{"name": "장 글씨", "family": "title", "styles": styles}], "fonts": fonts},
          "spacing": {"tokens": spacing}, "radius": {"tokens": radius}}
    out = project / "tokens.json"
    if out.exists():
        옛 = project / f"tokens_이전_{datetime.datetime.now():%Y%m%d-%H%M%S}.json"
        out.rename(옛); print("예전 tokens.json은 이름만 바꿔 둠:", 옛.name)
    out.write_text(json.dumps(결과, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"tokens.json 만듦: 색 {len(토큰)} · 글꼴 파일 {len(fonts)} · 여백 {len(spacing)} · 모서리 {len(radius)} → {out}")
    if 없음:
        print("project/fonts/에 없는 글꼴(화면에서 기본 고딕으로 보임):", ", ".join(없음))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
