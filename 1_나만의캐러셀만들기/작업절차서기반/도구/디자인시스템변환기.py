"""약사님 `디자인시스템.json`을 Claude "Design System" 아티팩트 파일(`project/…`)로 바꾼다.

`작업_절차서.md` 3단계. 같은 json·프로필·대표 편이면 언제 돌려도 같은 화면이 나온다.
값(색·글꼴·크기·여백·모서리·꾸밈)은 `디자인시스템.json`에서만 가져온다. 변환기가 계산해 만든 숫자는 쓰지 않는다.
json에 값이 없는 꾸밈은 그리지 않고 장 아래에 "설계서에 값 없음 — ○○"을 적는다. 장 샘플 글은 대표 편 `글.md`에 있는 글만 쓴다.

입력
- `{표시이름}_{계정}/04_설계서/디자인시스템.json` (빈 틀: `도구/디자인시스템_빈틀.json`)
- 작업 폴더 아래 약사님 폴더: `01/프로필.md`·프로필 사진, `05_디자인시스템/재료.json`(대표 편·장 샘플 배치·사진 자르기 — 부품 견본이 있으면 `장`·`사진`을 비우고 `대표편`은 없어도 된다),
  대표 편 `02/슬라이드/{편}/글.md`

재료.json의 장 샘플 글 한 덩이(값은 모두 json 경로로 가리킨다 — '꼴.'은 그 장이 쓰는 `사진위글자.꼴` 묶음)
  {"글": "...", "줄바꿈": " / ", "글꼴": "제목.보조.3", "굵기": "꼴.굵기", "크기": "꼴.글자높이px.자막바",
   "글자색": "꼴.바_글자색[1]", "배경": "꼴.바색", "안쪽여백": "꼴.안쪽여백px", "위": "꼴.위치px.자막바_위" | "이어서",
   "정렬": "가운데" | "왼쪽" | "오른쪽", "들여쓰기": "꼴.엇갈림_들여쓰기px", "오른쪽여백": "꼴.엇갈림_오른쪽여백px",
   "강조": {"낱말": "색.보조.초록_선택지[0]"}}

출력(`--출력`, 기본: 약사님 폴더 `05_디자인시스템/`)
- `올릴사진/` — 잘라 낸 장 샘플 사진·프로필 사진. 아티팩트 assets로 먼저 올린다.
- `사진아이디.json` — 올린 사진의 `/_blob/<id>`를 적는 곳(처음에는 빈 틀을 만든다).
- `project/` — design-system.json·tokens.json·README.md·components/*/preview.html·README.md·bundle.js.

사용
  python3 -I 도구/디자인시스템변환기.py 홍길동약사_hong_yaksa/04_설계서 홍길동약사_hong_yaksa
"""
from __future__ import annotations

import shutil
import base64
import datetime as _dt
import html
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 공통 import nfc, 한글ArgumentParser, 실패, 하위폴더_찾기, 작업폴더_경로  # noqa: E402

# 글꼴 이름(json `대체`) → (CSS family, 부르는 태그). 여기에 없거나 못 불러오면 기본 고딕 + "글꼴 못 부름" 표시.
글꼴표 = {
    "프리텐다드": ("Pretendard", ""),  # 외부 CSS는 화면 안에서 막혀 글꼴 파일을 fonts/에 넣는다(아래 글꼴파일)
    "나눔명조": ("NanumMyeongjo", ""),  # 파일로 넣음(아래 글꼴파일)
    "검은고딕": ("Black Han Sans", ""),  # 파일로 넣음(아래 글꼴파일)
    "나눔스퀘어라운드": ("NanumSquareRound", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-08 둥근 고딕 — 예전 CDN 링크는 화면 안에서 막힘)
    "지마켓 산스": ("지마켓 산스", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-03 결정 C)
    "카페24 써라운드 에어": ("카페24 써라운드 에어", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-03 결정 B)
    "카페24 당당해": ("카페24 당당해", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-08 시리즈 배지)
    "싱글데이": ("Single Day", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-08 손글씨 대체, OFL)
    "도현": ("Do Hyeon", ""),  # 파일로 넣음(아래 글꼴파일, 2026-11-08 좁은 굵은 고딕 라벨, OFL)
    "배민 연성": ("BMYEONSUNG", "<style>@font-face{font-family:'BMYEONSUNG';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/BMYEONSUNG.woff') format('woff')}</style>"),
}
# 화면에 파일로 넣는 글꼴(git `도구/글꼴/`, OFL — 같은 폴더 라이선스 파일). family → [(파일, 굵기)]
글꼴폴더 = Path(__file__).resolve().parent / "글꼴"
글꼴파일 = {"Pretendard": [("Pretendard-Light.woff2", "300"), ("Pretendard-Regular.woff2", "400"), ("Pretendard-Bold.woff2", "700"), ("Pretendard-Black.woff2", "900")],
          "NanumMyeongjo": [("NanumMyeongjo-Regular.ttf", "400"), ("NanumMyeongjo-Bold.ttf", "700"), ("NanumMyeongjo-ExtraBold.ttf", "800")],
          "Black Han Sans": [("BlackHanSans-Regular.ttf", "400")],
          "지마켓 산스": [("GmarketSansTTFMedium.ttf", "500"), ("GmarketSansTTFBold.ttf", "700")],
          "카페24 써라운드 에어": [("Cafe24SsurroundAir-v1.1.ttf", "400")],
          "NanumSquareRound": [("NanumSquareRoundR.ttf", "400"), ("NanumSquareRoundB.ttf", "700"), ("NanumSquareRoundEB.ttf", "800")],
          "카페24 당당해": [("Cafe24Dangdanghae-v2.0.woff2", "400")],
          "Single Day": [("SingleDay-Regular.ttf", "400")],
          "Do Hyeon": [("DoHyeon-Regular.ttf", "400")]}
# 꼴 칸의 한글 자리 이름 → 토큰 이름(Design System 토큰 이름은 영문·숫자만). 표에 없으면 로마자로 바꾼다.
자리이름 = {"머리말바": "head-bar", "자막바": "sub-bar", "미색상자": "cream-box", "흰상자": "white-box", "끝바": "end-bar",
          "상자_위": "box-top", "머리말바_위": "head-bar-top", "자막바_위": "sub-bar-top", "끝바_위": "end-bar-top",
          "위": "top", "아래": "bottom", "좌우": "x"}


_초 = "g kk n d tt r m b pp s ss  j jj ch k t p h".split(" ")
_중 = "a ae ya yae eo e yeo ye o wa wae oe yo u wo we wi yu eu ui i".split(" ")
_종 = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]


def 로마자(글: str) -> str:
    """한글 낱말 → 로마자(국어의 로마자 표기 바탕, 글자 단위). 같은 낱말은 늘 같은 이름이 된다."""
    나옴 = []
    for ch in 글:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            나옴.append(_초[o // 588] + _중[(o % 588) // 28] + _종[o % 28])
        elif re.fullmatch(r"[A-Za-z0-9]", ch):
            나옴.append(ch.lower())
        else:
            나옴.append("-")
    return re.sub(r"-+", "-", "".join(나옴)).strip("-")


def 영문(자리: str) -> str:
    """꼴 칸 자리 이름 → 토큰 이름 조각. 표에 있으면 표, 없으면 로마자(Design System 이름은 영문·숫자만)."""
    이름 = 자리이름.get(자리) or 로마자(자리)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", 이름 or ""):
        실패(f"토큰 이름으로 바꿀 수 없는 자리 이름입니다: '{자리}'")
    return 이름


# 굵기 낱말 → 숫자(단위 바꾸기 — 작업 절차서 3단계 5 — 고정 표)
굵기표 = {"thin": 100, "light": 300, "regular": 400, "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}
연락_무늬 = [
    r"https?://\S+", r"\b[\w.-]+@[\w.-]+\.\w+\b", r"(open|pf)\.kakao\.com\S*", r"band\.us\S*", r"linktr\.ee\S*",
    r"0\d{1,2}[- .]?\d{3,4}[- .]?\d{4}", r"(카톡|카카오톡|카카오|오픈채팅)\s*(아이디|ID|id)?\s*[:：]?\s*[A-Za-z0-9_.@-]{3,}",
    r"\S*kakao\.com\S*",
]


def 읽기(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        실패(f"파일이 없습니다: {p}")
    except json.JSONDecodeError as e:
        실패(f"json 모양이 잘못됐습니다: {p} ({e})")


def 경로(최종: dict, 길: str, 꼴: dict | None = None):
    """'색.본문'·'여백.좌우[0]'·'꼴.위치px.머리말바_위' 같은 json 경로의 값. 없으면 None."""
    if 길.startswith("꼴."):
        d, 길 = 꼴, 길[2:]
    else:
        d = 최종
    for 조각 in 길.split("."):
        m = re.fullmatch(r"(.+?)((?:\[\d+\])*)", 조각)
        if not isinstance(d, dict) or m.group(1) not in d:
            return None
        d = d[m.group(1)]
        for n in re.findall(r"\[(\d+)\]", m.group(2)):
            if not isinstance(d, list) or int(n) >= len(d):
                return None
            d = d[int(n)]
    return d


경로값 = 경로  # 예전 이름


def 하나(값):
    """선택지에서 고른 hex(글자) 또는 한 값짜리 목록. 고르기 전 목록이면 None."""
    if isinstance(값, str) and 값.startswith("#"):
        return 값
    if isinstance(값, list) and len(값) == 1:
        return 값[0]
    return None


def 굵기숫자(낱말) -> int | None:
    """'Bold~Black'·'Regular·Medium, 강조 Bold'처럼 적힌 굵기의 첫 낱말을 숫자로. 없으면 None."""
    if not isinstance(낱말, str):
        return None
    for 조각 in re.findall(r"[A-Za-z]+", 낱말):
        if 조각.lower() in 굵기표:
            return 굵기표[조각.lower()]
    return None


def 이름굵기(이름: str) -> int | None:
    """'프리텐다드 Black'처럼 글꼴 이름 뒤에 붙은 굵기만 읽는다. 'Black Han Sans'처럼 글꼴 이름의 일부인 낱말은 굵기가 아님."""
    if not isinstance(이름, str):
        return None
    남은 = 이름
    for 열쇠, (family, _) in 글꼴표.items():
        if 열쇠 in 남은 or family in 남은:
            남은 = 남은.replace(열쇠, " ").replace(family, " ")
            return 굵기숫자(남은)
    return None


def 크기(최종: dict, 역할: str) -> tuple[int | None, str]:
    """글씨 역할의 크기. 권고값이 있으면 그것, 없으면 범위의 작은 쪽(둘 다 json 값). (값, 설명)."""
    칸 = 최종["글씨"].get(역할) or {}
    if isinstance(칸.get("크기_권고"), (int, float)):
        return int(칸["크기_권고"]), f"글씨.{역할}.크기_권고"
    범위 = 칸.get("크기")
    if isinstance(범위, list) and len(범위) == 2:
        return int(범위[0]), f"글씨.{역할}.크기 {범위[0]}~{범위[1]} 중 작은 쪽(권고 없음)"
    return None, f"글씨.{역할}.크기 없음"


def 글꼴(최종: dict, 역할: str) -> tuple[str, str, str]:
    """역할('제목'·'본문'·'손글씨'·'제목.보조.N') → (대체 글꼴, 원본 추정 글꼴, 고른 상태)."""
    제목 = 최종["글씨"]["제목"]
    if 역할 == "제목":
        고름 = 제목.get("선택지")
        if isinstance(고름, str):
            return 고름, 고름, "고름"
        대체 = 제목.get("대체", "")
        if 대체 and not 대체.startswith("선택지"):  # 커스텀이 선택지 밖 글꼴을 `대체`로 정한 경우
            return 대체, 제목.get("글꼴", ""), "고름"
        return "", 제목.get("글꼴", ""), "고르기 전"
    if 역할.startswith("제목.보조."):
        n = int(역할.rsplit(".", 1)[1])
        보조 = 제목.get("보조") or []
        if len(보조) < n:
            실패(f"글씨.제목.보조에 {n}번째가 없습니다")
        return 보조[n - 1].get("대체", ""), 보조[n - 1].get("글꼴", ""), "고름"
    칸 = 최종["글씨"].get(역할) or {}
    return 칸.get("대체") or "", 칸.get("글꼴", ""), "고름"


def 웹글꼴(이름: str) -> tuple[str, str]:
    """대체 글꼴 이름 → (CSS family, 부르는 태그). 표에 없으면 ('', '')."""
    for 열쇠, 값 in 글꼴표.items():
        if 이름 and (열쇠 in 이름 or 값[0] in 이름):
            return 값
    return "", ""


def 프로필_읽기(약사님: Path) -> dict:
    """`01/프로필.md` 표 → {'게시물': …, '팔로워': …, '소개글': …}. 칸 이름은 낱말이 들어 있으면 찾는다."""
    p = 하위폴더_찾기(약사님, "01_")
    md = (p / "프로필.md") if p else None
    if not md or not md.exists():
        return {}
    표 = {}
    for 줄 in md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", 줄)
        if m and m.group(1) not in ("항목", "---"):
            표[m.group(1)] = m.group(2)
    찾기 = lambda 낱말: next((v for k, v in 표.items() if 낱말 in k and "팔로우" != k), "")  # noqa: E731
    return {"게시물": 찾기("게시물"), "팔로워": 찾기("팔로워"), "소개글": 찾기("소개")}


def 숫자(값) -> str:
    return f"{int(값):,}" if isinstance(값, str) and 값.isdigit() else (값 or "?")


def 연락_가리기(글: str) -> str:
    for 무늬 in 연락_무늬:
        글 = re.sub(무늬, "(연락 주소 가림)", 글)
    return 글


def 글_확인(글들: list[str], 글md: str) -> list[str]:
    """샘플 글의 줄마다 글.md에 그대로 있는지. 없는 줄 목록을 돌려준다(새 글을 지어 쓰지 않기)."""
    원문 = nfc(글md)
    return [줄 for 글 in 글들 for 줄 in 글.split("\n") if 줄.strip() and nfc(줄.strip()) not in 원문]


def json_숫자들(값) -> set:
    """json 안의 모든 숫자(시험·검수용: 장 샘플의 px가 모두 여기 있어야 한다)."""
    if isinstance(값, bool):
        return set()
    if isinstance(값, (int, float)):
        return {값}
    if isinstance(값, dict):
        return set().union(*[json_숫자들(v) for v in 값.values()]) if 값 else set()
    if isinstance(값, list):
        return set().union(*[json_숫자들(v) for v in 값]) if 값 else set()
    return set()


# ──────────────────────────── 토큰 ────────────────────────────

def 토큰_만들기(최종: dict, 남은: list[str]) -> dict:
    색 = 최종["색"]
    토큰 = []

    def 넣기(이름, 값, 쓰는곳):
        if isinstance(값, str) and re.fullmatch(r"#[0-9A-Fa-f]{3,8}", 값) and 이름 not in {t["name"] for t in 토큰}:
            토큰.append({"name": 이름, "value": 값.lower(), "usage": 쓰는곳})

    for i, v in enumerate(색.get("바탕") or [], 1):
        넣기(f"bg-{i}", v, "장 바탕(색.바탕). " + ("기본 바탕." if i == 1 else "편 갈래에 따라 쓰는 바탕."))
    넣기("ink", 색.get("본문"), "본문 글자(색.본문) — 흰·미색 바탕 위")
    넣기("title", 색.get("제목"), "제목 글자(색.제목)")
    넣기("ink-on-photo", 색.get("본문_사진위"), "사진 위 글자(색.본문_사진위)")
    for 키, 이름, 설명 in (("강조", "accent", "핵심 낱말 색글자(색.강조)"), ("형광펜", "highlight", "형광·띠(색.형광펜)")):
        칸 = 색.get(키) or {}
        고른 = 하나(칸.get("선택지"))
        if 고른:
            넣기(이름, 고른, 설명 + (" — " + 칸["역할"] if 칸.get("역할") else ""))
        else:
            for j, v in enumerate(칸.get("선택지") or [], 1):
                넣기(f"{이름}-choice-{j}", v, f"고르기 전 — 후보 {j}. {설명}")
    for 키, 이름 in (("주황_선택지", "orange"), ("파랑_선택지", "blue"), ("초록_선택지", "green")):
        값 = (색.get("보조") or {}).get(키)
        근거 = (색.get("보조") or {}).get(키.replace("_선택지", "_근거"), "")
        if isinstance(값, str):
            넣기(이름, 값, f"보조색(색.보조.{키})" + (f" — {근거}" if 근거 else ""))
        elif isinstance(값, list):
            고르기전 = f"색.보조.{키}" in 남은
            for j, v in enumerate(값, 1):
                넣기(f"{이름}-choice-{j}" if 고르기전 else f"{이름}-{j}", v,
                     (f"고르기 전 — 후보 {j}. " if 고르기전 else f"{j}번째 값(편마다 한 값). ") + f"보조색(색.보조.{키})")
    for 키, 값 in (색.get("보조") or {}).items():  # 위 세 이름 밖의 보조색(분홍 형광·노랑 글자 등)도 hex면 토큰으로
        if 키 not in ("주황_선택지", "파랑_선택지", "초록_선택지") and isinstance(값, str):
            넣기(f"sub-{영문(키)}", 값, f"보조색(색.보조.{키})")
    미색 =(색.get("바탕_선택지") or {}).get("미색")
    if isinstance(미색, str):
        넣기("cream", 미색, "미색 바탕(색.바탕_선택지.미색)")
    for n, 꼴 in enumerate((최종.get("사진위글자") or {}).get("꼴") or [], 1):
        앞 = f"style{n}"
        for 키, 값 in 꼴.items():  # 이름에 '색'이 든 칸(글자색·강조_글자색·바탕색 등) — 아래 고정 칸 말고 모두 토큰으로
            if "색" not in 키 or 키 in ("바색", "바_글자색", "상자색", "상자_글자색"):
                continue
            if isinstance(값, str):
                넣기(f"{앞}-{영문(키)}", 값, f"'{꼴.get('이름')}' {키}(사진위글자.꼴)")
            elif isinstance(값, dict):
                for 자리, v in 값.items():
                    넣기(f"{앞}-{영문(키)}-{영문(자리)}", v, f"'{꼴.get('이름')}' {키}.{자리}")
            elif isinstance(값, list):
                for j, v in enumerate(값, 1):
                    넣기(f"{앞}-{영문(키)}-{j}", v, f"'{꼴.get('이름')}' {키} {j}")
        넣기(f"{앞}-bar", 꼴.get("바색"), f"사진 위 글자 꼴 '{꼴.get('이름')}' — 바 색(사진위글자.꼴)")
        for j, v in enumerate(꼴.get("바_글자색") or [], 1):
            넣기(f"{앞}-bar-text-{j}", v, f"'{꼴.get('이름')}' 바 위 글자 {j}")
        for j, v in enumerate(꼴.get("상자색") or [], 1):
            넣기(f"{앞}-box-{j}", v, f"'{꼴.get('이름')}' 상자 {j}")
        넣기(f"{앞}-box-text", 꼴.get("상자_글자색"), f"'{꼴.get('이름')}' 상자 위 글자")

    글씨 = 최종["글씨"]
    가족: dict[str, str] = {}
    묶음 = []

    def 스타일(이름, 대체, 원본, 크기값, 크기설명, 굵기낱말, 덧말=""):
        family, _ = 웹글꼴(대체)
        가족[이름] = f'"{family}", sans-serif' if family else "sans-serif"
        부름 = family in 글꼴파일  # 화면 안에서는 fonts/ 파일로 넣은 글꼴만 불린다
        s = {"name": 이름, "family": 이름,
             "usage": f"대체 글꼴: {대체 or '없음(장 샘플 참고)'}" + ("" if 부름 or not 대체 else "(글꼴 못 부름 — 기본 고딕)")
                      + f" · 원본 추정: {원본 or '없음'} · 크기: {크기설명} · 1080px 장 기준" + 덧말}
        if 크기값:
            s["fontSize"] = f"{크기값}px"
        w = 이름굵기(대체) or 굵기숫자(굵기낱말)
        if w:
            s["fontWeight"] = w
        if 크기값:
            묶음.append(s)

    for 역할, 열쇠 in (("제목", "title"), ("소제목", "subtitle"), ("본문", "body"), ("작은글씨", "small"), ("손글씨", "hand")):
        칸 = 글씨.get(역할)
        if not isinstance(칸, dict):
            continue
        대체, 원본, 상태 = 글꼴(최종, "제목" if 역할 == "소제목" else 역할)
        값, 설명 = 크기(최종, 역할)
        스타일(열쇠, 대체, 원본, 값, 설명, 칸.get("굵기") or (글씨["제목"].get("굵기") if 역할 == "소제목" else None),
             "" if 상태 == "고름" else f" · {상태}")
    for n, 보조 in enumerate(글씨["제목"].get("보조") or [], 1):
        if isinstance(보조.get("크기"), (int, float)):  # 보조 글꼴에 크기가 적혀 있으면 그것
            값, 설명 = int(보조["크기"]), f"글씨.제목.보조[{n - 1}].크기"
        else:
            값, 설명 = 크기(최종, "제목")
            설명 += "(보조 글꼴은 크기 칸 없음 — 제목 값)"
        스타일(f"title-alt-{n}", 보조.get("대체", ""), 보조.get("글꼴", ""), 값, 설명, 보조.get("굵기"))
    본문칸 = 글씨.get("본문") if isinstance(글씨.get("본문"), dict) else {}
    for n, 보조 in enumerate(본문칸.get("보조") or [], 1):
        값, 설명 = 크기(최종, "본문")
        스타일(f"body-alt-{n}", 보조.get("대체", ""), 보조.get("글꼴", ""), 값, f"{설명}(보조 글꼴은 크기 칸 없음 — 본문 값)", 보조.get("굵기"))
    for n, 꼴 in enumerate((최종.get("사진위글자") or {}).get("꼴") or [], 1):
        글꼴크기 = 꼴.get("글꼴크기px") or {}
        for 자리, 높이 in (꼴.get("글자높이px") or {}).items():
            굵기 = 꼴.get("굵기")
            굵기 = 굵기.get(자리) if isinstance(굵기, dict) else 굵기  # 자리별로 적힌 굵기
            if isinstance(글꼴크기.get(자리), (int, float)):  # 원본 높이에 맞춘 글꼴 크기가 있으면 그것
                스타일(f"style{n}-{영문(자리)}", 꼴.get("대체", ""), "", 글꼴크기[자리],
                     f"사진위글자.꼴 '{꼴.get('이름')}' 글꼴 크기(글꼴크기px.{자리}, 원본 글자 높이 {높이}px에 맞춤)", 굵기)
            else:
                스타일(f"style{n}-{영문(자리)}", 꼴.get("대체", ""), "", 높이,
                     f"사진위글자.꼴 '{꼴.get('이름')}' 글자 높이(실측) — 글자 높이를 글꼴 크기로 그림", 굵기)
    type_ = {"families": 가족, "groups": [{"name": "장 글씨", "family": next(iter(가족), "body"), "styles": 묶음}]}
    쓰는 = {f for v in 가족.values() for f in 글꼴파일 if f'"{f}"' in v} | {"Pretendard"}  # 표지·소개도 프리텐다드
    type_["fonts"] = [{"family": f, "file": f"fonts/{파일}", "weight": 굵기}
                      for f in sorted(쓰는) for 파일, 굵기 in 글꼴파일[f] if (글꼴폴더 / 파일).exists()]

    여백 = 최종["여백"]
    간격 = []
    for 키, 이름, 설명 in (("좌우", "margin-x", "장 왼쪽·오른쪽 여백"), ("위", "margin-top", "장 위 여백"),
                         ("아래_계정표시까지", "margin-bottom", "장 아래(계정 표시까지) 여백")):
        범위 = 여백.get(키)
        if isinstance(범위, list) and len(범위) == 2 and all(isinstance(x, (int, float)) for x in 범위):
            간격.append({"name": f"{이름}-min", "value": f"{범위[0]}px", "usage": f"{설명} 가장 좁게(여백.{키})"})
            간격.append({"name": f"{이름}-max", "value": f"{범위[1]}px", "usage": f"{설명} 가장 넓게(여백.{키})"})
        if isinstance(여백.get(f"{키}_권고"), (int, float)):
            간격.append({"name": 이름, "value": f"{여백[f'{키}_권고']}px", "usage": f"{설명} 권고값(여백.{키}_권고)"})
        후보 = 여백.get(f"{키}_선택지")
        if isinstance(범위, str) and isinstance(후보, list):  # 고르기 전: 후보마다 토큰(1단계 7-2)
            for j, 쌍 in enumerate(후보, 1):
                if isinstance(쌍, list) and len(쌍) == 2:
                    간격.append({"name": f"{이름}-choice-{j}-min", "value": f"{쌍[0]}px", "usage": f"고르기 전 — 후보 {j}({쌍[0]}~{쌍[1]}) {설명}"})
                    간격.append({"name": f"{이름}-choice-{j}-max", "value": f"{쌍[1]}px", "usage": f"고르기 전 — 후보 {j}({쌍[0]}~{쌍[1]}) {설명}"})
    for n, 꼴 in enumerate((최종.get("사진위글자") or {}).get("꼴") or [], 1):
        for 묶음키, 이름 in (("안쪽여백px", "pad"), ("머리말바_안쪽여백px", "head-pad"), ("위치px", "top")):
            for 자리, v in (꼴.get(묶음키) or {}).items():
                if isinstance(v, (int, float)):
                    간격.append({"name": f"style{n}-{이름}-{영문(자리)}", "value": f"{v}px",
                               "usage": f"사진위글자.꼴 '{꼴.get('이름')}' {묶음키}.{자리}"})
    모서리 = []
    값 = (최종.get("사진위글자") or {}).get("모서리px")
    if isinstance(값, (int, float)):
        모서리.append({"name": "box", "value": f"{값}px", "usage": "사진 위 글 상자·바 모서리(사진위글자.모서리px)"})
    return {"name": 최종.get("_계정", ""), "version": 1,
            "color": {"themes": [{"id": "light", "name": "기본"}], "tokens": 토큰},
            "type": type_, "spacing": {"tokens": 간격}, "radius": {"tokens": 모서리}}


# ──────────────────────────── 장 샘플 ────────────────────────────

def 장_안쪽(최종: dict, 장: dict, 사진주소: dict) -> tuple[str, list[str], list[tuple[str, str, str]], set]:
    """장(1080 좌표) 안쪽 HTML. (html, 설계서에 값 없음 목록, 쓴 글꼴[(대체, family, 원본)], 부르는 태그)."""
    W, H = 최종.get("출력_크기_기본") or [1080, 1350]
    꼴들 = {k.get("이름"): k for k in (최종.get("사진위글자") or {}).get("꼴") or []}
    없음: list[str] = []
    쓴글꼴, 태그들 = [], set()
    좌우 = 경로(최종, "여백.좌우[0]")
    if not isinstance(좌우, (int, float)):
        없음.append("여백.좌우")
        좌우 = None
    무리: list[dict] = []
    for 글 in 장["글"]:
        꼴 = 꼴들.get(글.get("꼴")) if 글.get("꼴") else None
        if 글.get("꼴") and 꼴 is None:
            없음.append(f"사진위글자.꼴 '{글['꼴']}'")

        def 값(키, 종류=None):
            길 = 글.get(키)
            if not 길:
                return None
            v = 경로(최종, 길, 꼴)
            if v is None or (종류 and not isinstance(v, 종류)):
                없음.append(길)
                return None
            return v

        대체, 원본, _ = 글꼴(최종, 글["글꼴"])
        family, 태그 = 웹글꼴(대체)
        if 태그:
            태그들.add(태그)
        쓴글꼴.append((대체, family, 원본))
        크기px = 값("크기", (int, float))
        굵기 = 굵기숫자(값("굵기", str))
        if 글.get("굵기") and not 굵기:
            없음.append(f"{글['굵기']}(굵기 낱말)")
        글색 = 값("글자색", str)
        배경 = 값("배경", str)
        여백 = 값("안쪽여백", dict)
        본문 = html.escape(글["글"])
        for 낱말, 색길 in (글.get("강조") or {}).items():
            색 = 경로(최종, 색길)
            if isinstance(색, str):
                본문 = 본문.replace(html.escape(낱말), f'<span style="color:{색}">{html.escape(낱말)}</span>', 1)
            else:
                없음.append(색길)
        if 글.get("줄바꿈"):
            본문 = 본문.replace(html.escape(글["줄바꿈"]), "<br>")
        본문 = 본문.replace("\n", "<br>")
        css = [f"font-family:{chr(39) + family + chr(39) + ',' if family else ''}sans-serif", "line-height:normal"]
        if 크기px:
            css.append(f"font-size:{크기px}px")
        if 굵기:
            css.append(f"font-weight:{굵기}")
        if 글색:
            css.append(f"color:{글색}")
        if 배경:
            css.append(f"background:{배경}")
        if 여백:
            위, 아래, 옆 = 여백.get("위"), 여백.get("아래"), 여백.get("좌우")
            if all(isinstance(x, (int, float)) for x in (위, 아래, 옆)):
                css.append(f"padding:{위}px {옆}px {아래}px")
        모서리 = 경로(최종, "사진위글자.모서리px")
        if 배경 and isinstance(모서리, (int, float)):
            css.append(f"border-radius:{모서리}px")
        css.append("display:inline-block")
        줄css = [f"text-align:{ {'가운데': 'center', '오른쪽': 'right'}.get(글.get('정렬'), 'left') }"]
        들여 = 값("들여쓰기", (int, float))
        if 들여:
            줄css.append(f"padding-left:{들여}px")
        오른 = 값("오른쪽여백", (int, float))
        if 오른 is not None and 글.get("오른쪽여백"):
            줄css.append(f"padding-right:{오른}px")
        줄 = f'<div style="{";".join(줄css)}"><span style="{";".join(css)}">{본문}</span></div>'
        if 글.get("위") == "이어서" and 무리:
            무리[-1]["줄"].append(줄)
            if 글.get("오른쪽여백"):
                무리[-1]["오른쪽부터"] = True
        else:
            위치 = 값("위", (int, float))
            무리.append({"위": 위치, "줄": [줄], "붙음": 글.get("붙음")})
    if 장["글"]:
        없음.append("줄 간격(글꼴 기본으로 그림)")
    덩이 = []
    for m in 무리:
        왼 = 0 if m.get("붙음") == "왼쪽" else 좌우
        오 = 0 if m.get("붙음") == "오른쪽" or m.get("오른쪽부터") else 좌우  # 오른쪽여백px는 장 가장자리에서 잰 값
        자리 = [f"top:{m['위']}px" if m["위"] is not None else "top:0"]
        if 왼 is not None:
            자리.append(f"left:{왼}px")
        if 오 is not None:
            자리.append(f"right:{오}px")
        덩이.append(f'<div style="position:absolute;{";".join(자리)}">{"".join(m["줄"])}</div>')
    사진 = 사진주소.get(장["사진"]) if 장.get("사진") else None
    바탕색 = 경로(최종, 장["바탕색"]) if 장.get("바탕색") else None  # 사진 없는 단색 바탕 장(월간 달력형 등)
    if 장.get("바탕색") and not isinstance(바탕색, str):
        없음.append(장["바탕색"])
    if 바탕색 and not 장.get("사진"):
        바탕 = f'<div style="position:absolute;inset:0;background:{바탕색}"></div>'
    else:
        바탕 = (f'<img src="{사진}" alt="" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:{장.get("사진_위치", "center")}">'
              if 사진 else '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#ddd;color:#555;font-size:40px">사진 올리기 전</div>')
    안 = f'<div class="slide" style="width:{W}px;height:{H}px">{바탕}{"".join(덩이)}</div>'
    return 안, list(dict.fromkeys(없음)), 쓴글꼴, 태그들


def 장_그리기(최종: dict, 장: dict, 사진주소: dict, 사진출처: dict) -> tuple[str, list[str]]:
    """장 샘플 preview.html. 장 안은 1080 좌표 px를 json 값 그대로, 장 전체를 배율 하나로 줄인다."""
    W, H = 최종.get("출력_크기_기본") or [1080, 1350]
    안, 없음, 쓴글꼴, 태그들 = 장_안쪽(최종, 장, 사진주소)
    배율 = 480 / W
    못부름 = [대체 or 원본 or "?" for 대체, family, 원본 in 쓴글꼴 if not family]
    글꼴줄 = " · ".join(dict.fromkeys(f"대체 {대체 or '없음'}(원본 추정 {원본 or '없음'})" for 대체, family, 원본 in 쓴글꼴))
    알림 = "".join(f'<p class="flag">글꼴 못 부름 — {html.escape(x)}(기본 고딕으로 그림)</p>' for x in dict.fromkeys(못부름))
    알림 += "".join(f'<p class="flag">설계서에 값 없음 — {html.escape(x)}</p>' for x in 없음)
    families = sorted({f for _, f, _ in 쓴글꼴 if f})
    문서 = f"""<!-- @dsCard group="장 샘플" height={int(H * 배율) + 160} subtitle="{html.escape(장['이름'])} — 대표 편 {html.escape(장['편'])} {장['장']}장 글" -->
<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(장['이름'])}</title>
{''.join(sorted(태그들))}
<style>
body{{margin:0;color:#222}}
.wrap{{width:{int(W * 배율)}px;height:{int(H * 배율)}px;overflow:hidden;position:relative}}
.slide{{position:relative;overflow:hidden;transform:scale({배율:.6f});transform-origin:0 0}}
.meta{{font:12px/1.5 sans-serif;color:#555;margin:8px 0 0;max-width:480px}}
.flag{{font:12px/1.4 sans-serif;color:#c00;margin:4px 0 0}}
</style></head>
<body>
<div id="root">
<div class="wrap">{안}</div>
<p class="meta">{html.escape(장['설명'])}<br>글자 크기: 디자인시스템.json 값(px, 1080 기준) · 글꼴: {html.escape(글꼴줄)} · 사진: {html.escape(사진출처.get(장.get('사진'), '') or '없음')}</p>{알림}
</div>
<script>
(function(){{var 쓴={json.dumps(families, ensure_ascii=False)};if(!document.fonts)return;
document.fonts.ready.then(function(){{var 있음={{}};document.fonts.forEach(function(f){{if(f.status==='loaded')있음[f.family.replace(/["']/g,'')]=1;}});
쓴.forEach(function(f){{if(!있음[f]){{var p=document.createElement('p');p.className='flag';p.textContent='글꼴 못 부름 — '+f+'(기본 고딕으로 그림)';document.getElementById('root').appendChild(p);}}}});}});}})();
</script>
</body></html>
"""
    return 문서, 못부름


# ──────────────────────────── 소개서·표지 ────────────────────────────

def README_만들기(최종: dict, 재료: dict, 프로필: dict, 남은: list[str], 확인: list[str], 메모확인: list[str]) -> str:
    j = 최종
    줄 = []
    if 프로필.get("_사진_data"):  # README는 data: 그림만 보여 준다
        줄.append(f"![프로필 사진]({프로필['_사진_data']})\n")
    소개 = 연락_가리기(프로필.get("소개글", "")).replace(" / ", "  \n> ")
    줄 += [f"**{재료['표시이름']}** · @{재료['핸들']}", "",
           f"게시물 {숫자(프로필.get('게시물'))} · 팔로워 {숫자(프로필.get('팔로워'))}", ""]
    if 소개:
        줄 += [f"> {소개}", ""]
    줄 += ["이 페이지는 이 계정 카드뉴스의 디자인 규칙이다. 값은 모두 `디자인시스템.json`에서 왔다."
           " 고칠 값은 토큰을 바로 고치고, 고르기·확인 질문은 댓글로 답한다.", ""]
    줄 += ["## 한눈에", ""] + [f"- {p}" for p in j.get("표지_패턴", [])] + [""]
    줄 += ["## 색", "", "- 기본 바탕은 `bg-1`, 글자는 `ink`, 제목은 `title`. 사진 위 글자는 `ink-on-photo`.",
           "- 핵심 낱말은 `accent`(색글자) 또는 보조색(" + (" · ".join(
               f"`{ {'주황_선택지': 'orange', '파랑_선택지': 'blue', '초록_선택지': 'green'}.get(k) or 'sub-' + 영문(k)}`"
               for k, v in (j['색'].get('보조') or {}).items() if isinstance(v, str) and v.startswith('#')) or "없음")
           + "). 형광·띠는 `highlight`.",
           f"- 강조 장치는 한 장에 {j['꾸밈'].get('한_장당_개수', '?')}종까지: " + " · ".join(j["꾸밈"].get("강조_장치", [])), ""]
    줄 += ["## 글씨", "", f"- 한 장에 글꼴 {j['글씨'].get('한_장당_글꼴_수')}개(최대 {j['글씨'].get('한_장당_글꼴_수_최대')}개). 크기는 1080px 장 기준."]
    for 역할 in ("제목", "소제목", "본문", "작은글씨", "손글씨"):
        if isinstance(j["글씨"].get(역할), dict):
            대체, 원본, 상태 = 글꼴(j, "제목" if 역할 == "소제목" else 역할)
            값, 설명 = 크기(j, 역할)
            줄.append(f"- {역할}: 대체 글꼴 {대체 or '없음'} · 원본 추정 {원본 or '없음'} · 크기 {f'{값}px' if 값 else '없음'}({설명})"
                     + ("" if 상태 == "고름" else f" · {상태}"))
    for n, 보조 in enumerate(j["글씨"]["제목"].get("보조") or [], 1):
        줄.append(f"- 제목 보조 {n}: 대체 글꼴 {보조.get('대체', '')} · 원본 추정 {보조.get('글꼴', '')}")
    본문칸 = j["글씨"].get("본문") if isinstance(j["글씨"].get("본문"), dict) else {}
    for n, 보조 in enumerate(본문칸.get("보조") or [], 1):
        줄.append(f"- 본문 보조 {n}: 대체 글꼴 {보조.get('대체', '')} · 원본 추정 {보조.get('글꼴', '')}")
    사진처리 = j.get("사진_처리", {})
    줄 += ["", "## 사진", "", f"- 배치: {사진처리.get('배치', '')}", f"- 테두리 {사진처리.get('테두리', '')} · 그림자 {사진처리.get('그림자', '')}",
           f"- 사진 위 글자: {j.get('사진위글자', {}).get('방식', '')}"]
    for n, 꼴 in enumerate(j.get("사진위글자", {}).get("꼴") or [], 1):
        줄.append(f"- 꼴 {n} '{꼴.get('이름')}' (토큰 `style{n}-*`): " + " · ".join(
            f"{k} {v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)}" for k, v in 꼴.items() if k not in ("이름",) and not k.startswith("_")))
    줄 += ["", "## 종류별 장 구성", ""]
    for 종류, 칸 in j.get("장_구성", {}).items():
        장수 = 칸.get("장수")
        줄.append(f"**{종류}** — {장수 if isinstance(장수, str) else f'{장수[0]}~{장수[1]}장'}")
        줄 += [f"- {s}" for s in 칸.get("순서", [])] + [f"- 배경: {칸.get('배경', '')}", ""]
    줄 += ["## 부품", ""] + [f"- **{이름}** — {칸.get('쓰는_곳', '')}. {칸.get('정의', '')}" for 이름, 칸 in j.get("부품", {}).items()]
    줄 += ["", "## 쓰지 않는 것", ""] + [f"- {s}" for s in j.get("쓰지_않는_것", [])] + [""]
    말투 = j.get("말투", {})
    줄 += ["## 말투", ""] + [f"- {k}: {v if not isinstance(v, list) else ' · '.join(map(str, v))}" for k, v in 말투.items()] + [""]
    줄 += ["## 고르기·확인 전 목록", "", "아래는 아직 정하지 않은 칸이다. 페이지 댓글로 답하면 담당자가 설계서에 옮긴다.", ""]
    for 칸 in 남은:  # `X`와 `X_선택지`는 한 고르기로 보여 준다(6-2)
        if 칸.endswith("_선택지") and 칸[: -len("_선택지")] in 남은:
            continue
        후보칸 = 칸 + "_선택지" if 칸 + "_선택지" in 남은 else 칸
        값 = 경로(j, 후보칸)
        줄.append(f"- [고르기 전] `{칸}` — 후보: {값 if not isinstance(값, list) else ' / '.join(map(str, 값))}")
    for 칸 in 확인 + 메모확인:
        값 = 경로(j, 칸)
        if 값 is None and 칸.startswith("_확인전."):  # ponytail: `_확인전` 안 키에 점이 든 경우(설계서 칸 이름 그대로) — 점으로 쪼개지 않고 바로 꺼낸다
            값 = (j.get("_확인전") or {}).get(칸[len("_확인전."):])
        if isinstance(값, dict) and "값" in 값:
            값 = f"{값['값']} — {값.get('상태', '')}"
        줄.append(f"- [확인 전] `{칸}` — {값 if not isinstance(값, dict) else json.dumps(값, ensure_ascii=False)}")
    if not (남은 or 확인 or 메모확인):
        줄.append("- 없음")
    if 재료.get("장"):
        줄 += ["", "## 장 샘플", "", f"대표 편 `{재료['대표편']}`의 글(`글.md`)을 그대로 쓰고, 사진은 그 계정 실제 사진에서 글 없는 부분을 잘라 썼다.",
               "고른 기록:", ""] + [f"- {s}" for s in 재료.get("대표편_고른_기록", [])] + [""]
    return "\n".join(줄) + "\n"


def 표지_만들기(토큰: dict, 표시이름: str) -> str:
    """디자인 시스템 표지(cover.md). 색 블록은 이 계정 토큰 가운데 있는 것만 쓴다."""
    이름들 = [t["name"] for t in 토큰["color"]["tokens"] if "choice" not in t["name"]]
    후보 = [n for n in ("accent", "highlight", "green", "green-1", "green-2", "blue", "blue-1", "orange", "cream") if n in 이름들][:4]
    자리 = [(480, 0, 300, 288), (780, 0, 180, 150), (780, 150, 180, 138), (620, 200, 160, 88)]
    rect = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" style="fill:var(--{n})"/>' for n, (x, y, w, h) in zip(후보, 자리))
    return f"""<!-- @dsCard height=288 -->
<!doctype html>
<html><head><meta charset="utf-8"><title>표지</title>
<style>body{{margin:0}}.c{{position:relative;width:960px;height:288px;background:var(--bg-1)}}svg{{position:absolute;inset:0}}
.n{{position:absolute;left:40px;bottom:40px;max-width:440px;font:900 96px/.95 'Pretendard',sans-serif;color:var(--title)}}
.t{{font:500 14px/1.4 'Pretendard',sans-serif;color:var(--ink);margin-top:12px;opacity:.7}}</style></head>
<body><div class="c" id="root">
<svg viewBox="0 0 960 288" width="960" height="288" aria-hidden="true">
<!-- 블록: {' · '.join(후보)}(이 계정 색 토큰) / 배치: 오른쪽 위로 붙인 각진 판(사진위글자 모서리) / 무늬 없음 / 간격: 표지 기본 칸 -->
{rect}</svg>
<div class="n">{html.escape(표시이름)}<div class="t">카드뉴스 디자인 시스템 — 이 계정 게시물에서 잰 값</div></div>
</div></body></html>
"""


# ──────────────────────────── 고르기 전 · 확인 전 ────────────────────────────

def 남은_선택지(값, 경로: str = "") -> list[str]:
    """아직 고르지 않은 칸. ① `X_선택지`·`선택지` 목록(2개 이상)이 남았고 X를 정하지 않음
    ② 값이 "선택지…"로 적힌 칸(같은 묶음의 `선택지`를 골랐으면 끝). 글꼴은 `대체`를 정했으면 끝."""
    남음: list[str] = []
    if not isinstance(값, dict):
        return 남음
    대체 = 값.get("대체")
    글꼴정함 = isinstance(대체, str) and bool(대체) and not 대체.startswith("선택지")
    for 키, 속 in 값.items():
        if 키.startswith("_"):
            continue
        if isinstance(속, dict):
            남음 += 남은_선택지(속, f"{경로}{키}.")
        elif 키 == "선택지" or 키.endswith("_선택지"):
            if not (isinstance(속, list) and len(속) > 1) or (키 == "선택지" and 글꼴정함):
                continue
            본칸 = 키[: -len("_선택지")] if 키.endswith("_선택지") else None
            if 본칸 and 본칸 in 값 and not (isinstance(값[본칸], str) and 값[본칸].startswith("선택지")):
                continue  # X를 골랐으면 X_선택지 목록은 끝난 것
            남음.append(f"{경로}{키}")
        elif isinstance(속, str) and 속.startswith("선택지") and not isinstance(값.get("선택지"), str):
            남음.append(f"{경로}{키}")
    return 남음


def 확인전_칸(값, 경로: str = "") -> list[str]:
    """이름에 '확인전'이 든 칸(`_확인전` 묶음이면 그 안의 칸마다)."""
    칸: list[str] = []
    if not isinstance(값, dict):
        return 칸
    for 키, 속 in 값.items():
        if "확인전" in 키:
            if isinstance(속, dict):
                칸 += [f"{경로}{키}.{작은키}" for 작은키 in 속]
            elif 속:  # 빈 칸(빈 틀 그대로)은 묻지 않는다
                칸.append(f"{경로}{키}")
        else:
            칸 += 확인전_칸(속, f"{경로}{키}.")
    return 칸


# ──────────────────────────── 부품 ────────────────────────────

# 부품 견본이 있을 때만 이름표에 더하는 글꼴(없을 때는 지금 출력 그대로 — 강원교육모두는 원래 '못 부름')
부품_글꼴표 = {"강원교육모두": ("GangwonEduAll", "")}
# 부품 preview(도구/부품/lib.py FAM의 CSS 이름)가 쓰는 글꼴 이름 → 화면 tokens의 family 이름. 화면은 tokens.json fonts로만 글꼴을 부르므로 이름이 같아야 한다.
부품_글꼴이름 = {"강원교육모두": "GangwonEduAll", "나눔스퀘어라운드": "NanumSquareRound", "싱글데이": "Single Day", "도현": "Do Hyeon",
            "지마켓": "지마켓 산스", "카페24 서라운드에어": "카페24 써라운드 에어", "카페24 당당해": "카페24 당당해", "Pretendard": "Pretendard"}


def 부품_글꼴바꾸기(문서: str) -> str:
    """부품 preview 안의 글꼴 이름('이름'·"이름")을 화면 family 이름으로 바꾼다."""
    for 옛, 새 in 부품_글꼴이름.items():
        if 옛 != 새:
            문서 = 문서.replace(f"'{옛}'", f"'{새}'").replace(f'"{옛}"', f'"{새}"').replace(f"&quot;{옛}&quot;", f"&quot;{새}&quot;")
    return 문서


def 부품_설명줄이기(문서: str, 견본: dict) -> str:
    """부품 preview의 카드 머리줄(subtitle)과 아래 설명(.meta)을 짧게: 모양 계열 · 견본 장 · 편 안 자리 · 대체 글꼴. 긴 근거는 README·견본.json에 있다."""
    근거 = str(견본.get("근거_편") or 견본.get("근거") or "")
    m = re.match(r"\s*(?:\d{4}-\d{2}-\d{2}_)?([A-Za-z0-9_-]{6,}\s*\d+장)", 근거)
    글꼴 = sorted({e["글꼴"] for e in 견본.get("요소") or [] if isinstance(e, dict) and isinstance(e.get("글꼴"), str)})
    짧은 = " · ".join(x for x in (str(견본.get("모양_계열") or ""), f"견본 장 {m.group(1)}" if m else "", str(견본.get("편_안_자리") or ""),
                                 "대체 글꼴(원본 글에 겹쳐 고름): " + ", ".join(글꼴) if 글꼴 else "") if x)
    문서 = re.sub(r'subtitle="[^"]*"', lambda _: f'subtitle="{html.escape(짧은, True)}"', 문서, count=1)
    return re.sub(r'<p class="meta">.*?</p>', lambda _: f'<p class="meta">{html.escape(짧은)}</p>', 문서, count=1, flags=re.S)


def 안전이름(이름들: list[str]) -> dict[str, str]:
    """색인(assetGroups) 기록 이름: 허용 글자([A-Za-z0-9_.-])만 남기고, 겹치면 번호를 붙인다. {원래 이름: 안전한 이름}"""
    결과, 쓴 = {}, set()
    for f in 이름들:
        줄기, 점, 확장 = nfc(f).rpartition(".")
        기본 = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.-]", "_", 줄기)).strip("_") or "file"
        새, n = f"{기본}.{확장}", 1
        while 새 in 쓴:
            n += 1
            새 = f"{기본}-{n}.{확장}"
        쓴.add(새)
        결과[f] = 새
    return 결과
부품_글꼴파일 = {"GangwonEduAll": [("GangwonEduAll-Bold.woff", "700"), ("GangwonEduAll-Light.woff", "300")]}


def 부품_찾기(루트: Path) -> list[Path]:
    """`견본.json`이 있는 부품 폴더(이름순). 루트가 없으면 빈 목록."""
    if not 루트.is_dir():
        return []
    return [d for d in sorted(루트.iterdir(), key=lambda d: nfc(d.name)) if d.is_dir() and (d / "견본.json").exists()]


def 부품_글꼴(견본: dict) -> set:
    """견본 요소가 쓰는 글꼴 이름 → 글꼴파일에 있는 CSS family 모음."""
    이름들 = {e["글꼴"] for e in 견본.get("요소") or [] if isinstance(e, dict) and isinstance(e.get("글꼴"), str)}
    가족 = {next((새 for 옛, 새 in 부품_글꼴이름.items() if n.startswith(옛)), None) or 웹글꼴(n)[0] for n in 이름들} | {"Pretendard"}  # 없는 글자는 프리텐다드로 그린다
    return {f for f in 가족 if f in 글꼴파일}


def 부품_README절(견본들: list[dict]) -> str:
    """README `## 부품 견본` 표: 부품 | 모양 계열 | 편 안 자리 | 견본 장 | 글 자리."""
    def 칸(v):
        if isinstance(v, dict):
            v = "; ".join(f"{k}: {x}" for k, x in v.items())
        elif isinstance(v, list):
            v = "; ".join(map(str, v))
        return str(v or "").replace("|", "/").replace("\n", " ")

    # TODO(advisor): 브리프는 `## 부품`이지만 README_만들기에 설계서 부품 절 `## 부품`이 이미 있어 `## 부품 견본`으로 구별함 — 이름 확정 필요
    줄 = ["## 부품 견본", "", "| 부품 | 모양 계열 | 편 안 자리 | 견본 장 | 글 자리 |", "| --- | --- | --- | --- | --- |"]
    for k in 견본들:
        근거 = str(k.get("근거") or "")
        m = re.match(r"(.*?[.。])(?:\s|$)", 근거, re.S)
        줄.append("| " + " | ".join(칸(v) for v in (k.get("화면"), k.get("모양_계열"), k.get("편_안_자리"),
                                                   m.group(1) if m else 근거, k.get("글_자리"))) + " |")
    return "\n".join(줄) + "\n"


# ──────────────────────────── 실행 ────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = 한글ArgumentParser(description="디자인시스템.json → Claude Design System 아티팩트 파일")
    p.add_argument("계정폴더", help="<약사님폴더>/04_설계서 (디자인시스템.json이 있는 폴더)")
    p.add_argument("약사님폴더", help="작업 폴더 아래 약사님 폴더 이름(예: 홍길동약사_hong_yaksa)")
    p.add_argument("--출력", help="기본: <약사님폴더>/05_디자인시스템")
    p.add_argument("--부품", help="부품 폴더들이 든 곳(기본: <약사님폴더>/05_디자인시스템/부품). 상대 경로는 작업 폴더 기준")
    a = p.parse_args(argv)
    계정 = 작업폴더_경로(a.계정폴더)
    약사님 = 작업폴더_경로(a.약사님폴더)
    출력 = 작업폴더_경로(a.출력) if a.출력 else (하위폴더_찾기(약사님, "05_") or 약사님 / "05_디자인시스템")
    최종 = 읽기(계정 / "디자인시스템.json")
    기본05 = 하위폴더_찾기(약사님, "05_")
    부품들 = 부품_찾기(작업폴더_경로(a.부품) if a.부품 else 기본05 / "부품" if 기본05 else Path())
    if 부품들:
        글꼴표.update(부품_글꼴표)
        글꼴파일.update(부품_글꼴파일)
    부품견본 = {d.name: 읽기(d / "견본.json") for d in 부품들}
    기록 = {"남은선택지": 남은_선택지(최종), "확인전": 확인전_칸(최종)}
    메모확인 = []  # `_확인전` 밖의 메모 칸 가운데 '확인 전'·'확인 필요'라고 적힌 것(1단계 7-2)
    for k, v in 최종.items():
        if not k.startswith("_") or k in ("_확인전", "_안내", "_계정", "_작성일"):
            continue
        속 = v.items() if isinstance(v, dict) and not ("값" in v and "상태" in v) else [(None, v)]
        for 작은, 값 in 속:
            if re.search(r"확인 ?(전|필요)", json.dumps(값, ensure_ascii=False)):
                메모확인.append(f"{k}.{작은}" if 작은 else k)
    재료 = 읽기(출력 / "재료.json")
    재료.setdefault("장", [])  # 부품 견본이 있으면 장 샘플은 만들지 않는다(절차서 3단계 5) — 빈 목록이면 대표 편도 필요 없다
    편 = 재료.get("대표편", "")
    글md = ""
    if 재료["장"]:
        둘 = 하위폴더_찾기(약사님, "02_")
        if not 둘:
            실패(f"02_ 폴더가 없습니다: {약사님}")
        글md_경로 = 둘 / "슬라이드" / 편 / "글.md"
        if not 글md_경로.exists():
            실패(f"대표 편 글.md가 없습니다: {글md_경로} — 1단계 1 양식으로 먼저 받아 적으세요")
        글md = 글md_경로.read_text(encoding="utf-8")
    for 장 in 재료["장"]:  # 장마다 그 장 절 안에서 확인
        m = re.search(rf"## {장['장']}장[^\n]*\n(.*?)(?=\n## |\Z)", 글md, re.S)
        없는줄 = 글_확인([g["글"].replace(g.get("줄바꿈") or "\0", "\n") for g in 장["글"]], m.group(1) if m else "")
        if 없는줄:
            실패(f"글.md {장['장']}장에 없는 글이 샘플에 있습니다: " + " / ".join(없는줄))

    from PIL import Image, ImageFilter

    def 가리기(im, 상자들):
        """실명 이름표·연락처처럼 사진 속 글자를 흐리게 가린다(얼굴은 가리거나 고치지 않는다)."""
        for 상자 in 상자들 or []:
            im.paste(im.crop(tuple(상자)).filter(ImageFilter.GaussianBlur(8)), tuple(상자[:2]))
        return im

    올릴 = 출력 / "올릴사진"
    올릴.mkdir(parents=True, exist_ok=True)
    for s in 재료.get("사진", []):
        im = Image.open(약사님 / s["원본"]).convert("RGB")
        가리기(im, s.get("가림")).crop(tuple(s["상자"])).save(올릴 / s["파일"], quality=90)
    if 재료.get("프로필사진") and (약사님 / 재료["프로필사진"]).exists():
        im = Image.open(약사님 / 재료["프로필사진"]).convert("RGB")
        가리기(im, 재료.get("프로필사진_가림")).save(올릴 / "profile.jpg", quality=92)
    쓸파일 = {s["파일"] for s in 재료.get("사진", [])} | {"profile.jpg"}
    아이디파일 = 출력 / "사진아이디.json"
    사진주소 = 읽기(아이디파일) if 아이디파일.exists() else {}
    원래아이디 = dict(사진주소)
    빈틀 = {f: 사진주소.get(f, "") for f in sorted(쓸파일) if (올릴 / f).exists()}
    # 부품 견본이 쓰는 다른 그림의 아이디도 지우지 않고 그대로 둔다
    아이디파일.write_text(json.dumps({**사진주소, **빈틀}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    사진주소 = {k: v for k, v in 빈틀.items() if v}
    사진출처 = {s["파일"]: s["출처"] for s in 재료.get("사진", [])}
    # 부품 그림: preview.html이 __BLOB__<파일>__로 쓰는 것만 올릴사진/part-<부품 소문자>-<파일>로 복사(아이디는 기존 것 보존)
    부품문서, 부품빈틀 = {}, {}
    for d in 부품들:
        pv = d / "preview.html"
        if not pv.exists():
            실패(f"부품 preview.html이 없습니다: {pv}")
        부품문서[d.name] = pv.read_text(encoding="utf-8")
        for f in dict.fromkeys(re.findall(r"__BLOB__(.+?)__", 부품문서[d.name])):
            if (d / f).is_file() and f not in ("render.png", "cmp.jpg") and Path(f).suffix.lower() in (".jpg", ".jpeg", ".png"):
                이름 = f"part-{d.name.lower()}-{f}"
                (올릴 / 이름).write_bytes((d / f).read_bytes())
                부품빈틀[이름] = 원래아이디.get(이름, "")
    if 부품빈틀:
        아이디파일.write_text(json.dumps({**원래아이디, **빈틀, **부품빈틀}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    부품주소 = {k: v for k, v in 부품빈틀.items() if v}

    토큰 = 토큰_만들기(최종, 기록["남은선택지"])
    proj = 출력 / "project"
    (proj / "components").mkdir(parents=True, exist_ok=True)
    (proj / "fonts").mkdir(exist_ok=True)
    쓴가족 = {f["family"] for f in 토큰["type"].get("fonts", [])}
    for 가족 in sorted(set().union(*[부품_글꼴(k) for k in 부품견본.values()]) - 쓴가족):  # 부품 견본이 쓴 글꼴
        토큰["type"].setdefault("fonts", []).extend(
            {"family": 가족, "file": f"fonts/{파일}", "weight": 굵기} for 파일, 굵기 in 글꼴파일[가족] if (글꼴폴더 / 파일).exists())
        앞 = re.split(r"[-.]|TTF", 글꼴파일[가족][0][0])[0]
        for txt in 글꼴폴더.glob(f"{앞}_*.txt"):  # 라이선스 글은 fonts/ 밖에(fonts/ 안에 두면 화면이 글꼴 파일처럼 보여 줌)
            (proj / "licenses").mkdir(exist_ok=True)
            (proj / "licenses" / txt.name).write_bytes(txt.read_bytes())
            (proj / "fonts" / txt.name).unlink(missing_ok=True)
    (proj / "tokens.json").write_text(json.dumps(토큰, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for f in 토큰["type"].get("fonts", []):  # 글꼴 파일은 assets가 아니라 fonts/ 파일(Design System 형식)
        (proj / f["file"]).write_bytes((글꼴폴더 / Path(f["file"]).name).read_bytes())
    프로필 = 프로필_읽기(약사님)
    if not 프로필:
        print("- ⚠️ 01/프로필.md가 없습니다 — 프로필 머리가 비어 나옵니다(1단계 0부터 받으세요)")
    if (올릴 / "profile.jpg").exists():
        작은 = Image.open(올릴 / "profile.jpg").convert("RGB")
        작은.thumbnail((240, 240))
        버퍼 = io.BytesIO()
        작은.save(버퍼, "JPEG", quality=85)
        프로필["_사진_data"] = "data:image/jpeg;base64," + base64.b64encode(버퍼.getvalue()).decode()
    소개문 = README_만들기(최종, 재료, 프로필, 기록["남은선택지"], 기록["확인전"], 메모확인)
    if 부품들:
        소개문 += "\n" + 부품_README절(list(부품견본.values()))
    (proj / "README.md").write_text(소개문, encoding="utf-8")
    못부름_전체, 없음_전체 = [], []
    for 장 in 재료["장"]:
        장 = {**장, "편": 편}
        문서, 못부름 = 장_그리기(최종, 장, 사진주소, 사진출처)
        if 부품들:
            문서 = 문서.replace('group="장 샘플"', 'group="옛 방식(참고)"', 1)
        못부름_전체 += 못부름
        없음_전체 += 장_안쪽(최종, 장, 사진주소)[1]
        d = proj / "components" / 장["부품"]
        d.mkdir(exist_ok=True)
        (d / "preview.html").write_text(문서, encoding="utf-8")
        (d / "README.md").write_text(f"# {장['부품']}\n\n{'옛 방식(참고) — 부품 견본이 생기기 전의 장 샘플. ' if 부품들 else ''}{장['설명']}. 대표 편 {편} {장['장']}장 글을 그대로 썼다.\n", encoding="utf-8")
    아직 = 0  # 아이디 없어 자리표시로 남은 부품 그림 자리
    for d in 부품들:
        html_ = 부품문서[d.name]
        for f in dict.fromkeys(re.findall(r"__BLOB__(.+?)__", html_)):
            주소 = 부품주소.get(f"part-{d.name.lower()}-{f}")
            if 주소:
                html_ = html_.replace(f"__BLOB__{f}__", 주소)
        아직 += html_.count("__BLOB__")
        (proj / "components" / d.name).mkdir(exist_ok=True)
        (proj / "components" / d.name / "preview.html").write_text(부품_글꼴바꾸기(부품_설명줄이기(html_, 부품견본[d.name])), encoding="utf-8")
        if (d / "README.md").exists():
            (proj / "components" / d.name / "README.md").write_bytes((d / "README.md").read_bytes())
    이름공간 = re.sub(r"[^A-Za-z0-9]", "", 재료["핸들"].title()) or "DS"
    머리 = json.dumps({"format": 4, "namespace": 이름공간, "components": [{"name": d.name} for d in 부품들] + [{"name": 장["부품"]} for 장 in 재료["장"]]})
    (proj / "components" / "bundle.js").write_text(
        f"/* @ds-bundle: {머리} */\n// 부품·장 샘플은 preview.html의 HTML로 그린다(부품 코드 없음).\nwindow.{이름공간} = {{}};\n", encoding="utf-8")
    남길 = {d.name for d in 부품들} | {장["부품"] for 장 in 재료["장"]} | {"Cover"}
    for d in (proj / "components").iterdir():  # 목록에서 빠진 컴포넌트 폴더는 지운다(안 지우면 화면에 계속 남는다)
        if d.is_dir() and d.name not in 남길:
            shutil.rmtree(d)
            print(f"- 뺀 컴포넌트: {d.name} — 아티팩트에서도 project/components/{d.name}/ 파일을 지우세요")
    (proj / "components" / "Cover").mkdir(exist_ok=True)
    (proj / "components" / "Cover" / "preview.html").write_text(표지_만들기(토큰, 재료["표시이름"]), encoding="utf-8")

    그룹 = {"Profile": ["profile.jpg"], "Photos": [s["파일"] for s in 재료.get("사진", [])]}
    if 부품들:
        그룹["Parts"] = list(부품빈틀)
    if not 그룹["Photos"]:
        del 그룹["Photos"]  # 장 샘플 사진이 없으면 빈 묶음을 화면에 두지 않는다
    지금 = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:  # 이미 올린 시스템이면 만든 때 표식(createdOnFiles)을 그대로 둔다(Design System 형식 — 색인의 표식은 바꾸지 않는다)
        표식 = json.loads((proj / "design-system.json").read_text(encoding="utf-8"))["createdOnFiles"]
    except (OSError, ValueError, KeyError):
        표식 = {"v": 1, "at": 지금}
    색인 = {"v": 3, "layout": "files", "createdOnFiles": 표식, "title": f"{재료['표시이름']} 디자인 시스템",
          "namespace": 이름공간, "libraries": [], "sections": {},
          "groups": list(그룹), "assetGroups": {}, "blobs": {}, "docs": {"readme": "project/README.md", "sections": []},
          "lastChange": {"by": "Claude", "at": 지금, "via": "Claude Code · 디자인시스템변환기.py",
                         "note": "디자인시스템.json → 화면"}}
    for g, 파일들 in 그룹.items():
        기록들 = {}
        이름 = 안전이름(파일들)  # 한글·빈칸이 든 파일 이름은 색인 기록 이름으로 못 쓴다
        for f in 파일들:
            주소 = {**사진주소, **부품주소}.get(f, "")
            if 주소 and (올릴 / f).exists():
                기록들[이름[f]] = {"name": 이름[f], "blob": 주소.rsplit("/", 1)[-1], "size": (올릴 / f).stat().st_size,
                               "type": "image/png" if f.lower().endswith(".png") else "image/jpeg"}
        색인["assetGroups"][g] = {"name": g, "tile": "s" if g == "Parts" else "m", "order": list(기록들), "files": 기록들}
    (proj / "design-system.json").write_text(json.dumps(색인, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"# 디자인 시스템 변환 — {재료['표시이름']}")
    print(f"- 출력: {proj}")
    print(f"- 색 토큰 {len(토큰['color']['tokens'])} · 글씨 {len(토큰['type']['groups'][0]['styles'])} · 여백 {len(토큰['spacing']['tokens'])} · 모서리 {len(토큰['radius']['tokens'])}")
    print(f"- 장 샘플 {len(재료['장'])} · 고르기 전 {len(기록['남은선택지'])} · 확인 전 {len(기록['확인전']) + len(메모확인)}")
    print(f"- 사진 {len(빈틀)}장(올릴사진/) · 아이디 있는 사진 {len(사진주소)}")
    if 못부름_전체:
        print("- ⚠️ 글꼴 못 부름(표에 없음): " + " · ".join(dict.fromkeys(못부름_전체)))
    if 없음_전체:
        print("- 설계서에 값 없음: " + " · ".join(dict.fromkeys(없음_전체)))
    if 부품들:
        print(f"- 부품 {len(부품들)}개 · 부품 그림 {len(부품빈틀)}장(아이디 있는 것 {len(부품주소)})")
        if 아직:
            print(f"- 부품 사진 올리기 전 {아직}곳(preview에 __BLOB__ 자리표시가 남음)")
    if len(사진주소) < len(빈틀) or len(부품주소) < len(부품빈틀):
        print("- 사진을 아티팩트에 올리고 사진아이디.json에 /_blob/<id>를 적은 뒤 다시 돌리세요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
