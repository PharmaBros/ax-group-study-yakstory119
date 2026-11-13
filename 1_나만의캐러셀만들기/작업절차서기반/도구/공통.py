"""약사님 계정 분석 스크립트 5개가 함께 쓰는 공용 함수.

- NFC 경로 처리(iCloud 한글 파일명은 NFD일 수 있음)
- 약사님 폴더 검사(01~06 하위 폴더 찾기)
- 분류.md 종류 읽기, 게시물목록.json 읽기
- 마크다운 표 만들기
- 이모지 판정
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# ──────────────────────────── 문자열 · 경로 ────────────────────────────

def nfc(s: str) -> str:
    """한글 문자열을 NFC(완성형)로 맞춘다. iCloud 파일명 비교에 쓴다."""
    return unicodedata.normalize("NFC", s)


작업폴더 = Path(__file__).resolve().parents[1]


def 작업폴더_경로(경로문자: str) -> Path:
    """상대 경로(예: 홍길동약사_hong_yaksa, 홍길동약사_hong_yaksa/04_설계서)를 작업 폴더 기준으로 바꾼다. 절대 경로는 그대로 둔다."""
    p = Path(nfc(경로문자)).expanduser()
    return p if p.is_absolute() else 작업폴더 / p


def 오늘() -> str:
    return _dt.date.today().strftime("%Y-%m-%d")


def 실패(메시지: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[실패] {메시지}", file=sys.stderr)
    sys.exit(code)


class 한글ArgumentParser(argparse.ArgumentParser):
    """argparse 오류 메시지를 한국어로 바꾼 파서."""

    def error(self, message: str) -> "NoReturn":  # type: ignore[name-defined]
        m = re.search(r"required: (.+)$", message)
        if m:
            print(f"[실패] 필요한 값이 빠졌습니다: {m.group(1)} — 사용법은 --help", file=sys.stderr)
        else:
            print(f"[실패] 옵션이 올바르지 않습니다: {message} — 사용법은 --help", file=sys.stderr)
        sys.exit(2)


def 하위폴더_찾기(상위: Path, 접두: str) -> Path | None:
    """`01_` 처럼 번호 접두로 시작하는 하위 폴더를 NFC 기준으로 찾는다."""
    if not 상위.is_dir():
        return None
    for 이름 in sorted(os.listdir(상위)):
        if nfc(이름).startswith(접두):
            p = 상위 / 이름
            if p.is_dir():
                return p
    return None


def 파일_찾기(폴더: Path, 이름: str) -> Path | None:
    """폴더 안에서 NFC 기준으로 같은 이름의 파일·폴더를 찾는다."""
    if not 폴더.is_dir():
        return None
    목표 = nfc(이름)
    for 항목 in os.listdir(폴더):
        if nfc(항목) == 목표:
            return 폴더 / 항목
    return None


def 약사님폴더_검사(경로문자: str) -> dict:
    """약사님 폴더를 검사해 하위 폴더 경로를 돌려준다.

    돌려주는 dict 키: 루트, 이름, 계정, 표시이름, 01 … 06 (없으면 None)
    """
    루트 = 작업폴더_경로(경로문자)
    if not 루트.exists():
        # NFD로 저장된 경우를 대비해 부모에서 다시 찾는다
        부모 = 루트.parent
        후보 = 파일_찾기(부모, 루트.name) if 부모.exists() else None
        if 후보 is None:
            실패(f"약사님 폴더를 찾을 수 없습니다: {경로문자}")
        루트 = 후보
    if not 루트.is_dir():
        실패(f"폴더가 아닙니다: {루트}")
    이름 = nfc(루트.name)
    if "_" in 이름:
        표시이름, 계정 = 이름.split("_", 1)
    else:
        표시이름, 계정 = 이름, 이름
    정보 = {"루트": 루트, "이름": 이름, "표시이름": 표시이름, "계정": 계정}
    for n in range(1, 7):
        정보[f"0{n}"] = 하위폴더_찾기(루트, f"0{n}_")
    if 정보["01"] is None and 정보["02"] is None:
        실패(
            f"'{이름}' 안에 01_수집 / 02_대표슬라이드 폴더가 없습니다. "
            "약사님 폴더(예: 홍길동약사_hong_yaksa)를 지정했는지 확인하세요."
        )
    return 정보


# ──────────────────────────── 게시물목록 · 분류 ────────────────────────────

def 게시물목록_읽기(정보: dict, 캡션파일: str | None = None) -> list[dict]:
    """01/게시물목록.json을 읽는다. `캡션파일`을 주면 그 파일의 `캡션전문`으로 캡션을 바꾼다."""
    폴더01 = 정보.get("01")
    if 폴더01 is None:
        실패("01_수집 폴더가 없습니다.")
    경로 = 파일_찾기(폴더01, "게시물목록.json")
    if 경로 is None:
        실패(f"게시물목록.json이 없습니다: {폴더01}")
    try:
        목록 = json.loads(경로.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        실패(f"게시물목록.json을 읽지 못했습니다(JSON 오류): {e}")
    if not isinstance(목록, list):
        실패("게시물목록.json은 리스트여야 합니다.")
    for 항목 in 목록:
        항목.setdefault("캡션", "")
        if 항목["캡션"] is None:
            항목["캡션"] = ""
    if 캡션파일:
        p = 작업폴더_경로(캡션파일)
        if not Path(캡션파일).is_absolute() and not p.exists():
            후보 = 파일_찾기(폴더01, 캡션파일)
            if 후보 is not None:
                p = 후보
        if not p.exists():
            실패(f"캡션 파일이 없습니다: {캡션파일}")
        try:
            전문목록 = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            실패(f"캡션 파일을 읽지 못했습니다(JSON 오류): {e}")
        전문 = {}
        for 항목 in 전문목록:
            캡 = 항목.get("캡션전문")
            if 캡 is None:
                캡 = 항목.get("캡션")
            if 항목.get("id") and 캡:
                전문[항목["id"]] = 캡
        바꾼수 = 0
        for 항목 in 목록:
            if 항목.get("id") in 전문:
                항목["캡션"] = 전문[항목["id"]]
                항목["캡션출처"] = "전문"
                바꾼수 += 1
        정보["캡션전문_바꾼수"] = 바꾼수
    return 목록


_원문자 = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩\d]+[.)]?\s*")


def 종류_정리(값: str) -> str:
    """'**공구 안내**', '① 정보형' 같은 표 셀을 종류 이름만 남긴다."""
    v = nfc(값 or "").strip().replace("**", "").strip()
    v = _원문자.sub("", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()


def 종류_키(값: str) -> str:
    """종류 이름을 비교용 키로: 정리 후 공백·`·` 제거, 소문자. '월간 일정'='월간일정', '개인·일상'='개인 일상'."""
    return 종류_정리(값).replace(" ", "").replace("\u00a0", "").replace("·", "").lower()


def 개인일상인가(종류: str) -> bool:
    s = 종류_키(종류)
    return "개인일상" in s or s.startswith("개인") or s.startswith("일상")


def 마크다운표_파싱(본문: str) -> list[dict]:
    """마크다운 안의 표를 모두 찾아 [{'헤더': [...], '행': [[...], ...]}] 로 돌려준다."""
    표들 = []
    줄들 = 본문.splitlines()
    i = 0
    while i < len(줄들):
        줄 = 줄들[i].strip()
        if 줄.startswith("|") and i + 1 < len(줄들) and re.match(r"^\|?\s*:?-{2,}", 줄들[i + 1].strip()):
            헤더 = _셀나누기(줄)
            i += 2
            행 = []
            while i < len(줄들) and 줄들[i].strip().startswith("|"):
                행.append(_셀나누기(줄들[i].strip()))
                i += 1
            표들.append({"헤더": 헤더, "행": 행})
        else:
            i += 1
    return 표들


def _셀나누기(줄: str) -> list[str]:
    s = 줄.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def 분류_읽기(정보: dict) -> dict:
    """02/분류.md의 표에서 편(게시일_아이디) → 종류 를 읽는다.

    돌려주는 dict: {"편": {편폴더명: 종류}, "아이디": {아이디: 종류}, "열이름": 쓴 열 이름}
    '종류' 열이 있으면 그것을, 없으면 '분류' 열을 쓴다. 표가 여럿이면 종류 열이 있는 표를, 그중에서도
    행이 많은 표(게시물별 전체 판정표)를 우선한다 — 대표 편 표나 결정 전 기록 표의 옛 종류가 이기지 않게.
    """
    결과 = {"편": {}, "아이디": {}, "열이름": None}
    폴더02 = 정보.get("02")
    if 폴더02 is None:
        return 결과
    경로 = 파일_찾기(폴더02, "분류.md")
    if 경로 is None:
        return 결과
    표들 = 마크다운표_파싱(nfc(경로.read_text(encoding="utf-8")))
    후보 = []
    for 표 in 표들:
        헤더 = [nfc(h) for h in 표["헤더"]]
        편열 = next((k for k, h in enumerate(헤더) if "게시일" in h or "폴더" in h), None)
        종류열 = next((k for k, h in enumerate(헤더) if "종류" in h), None)
        우선 = 1 if 종류열 is not None else 0
        if 종류열 is None:
            종류열 = next((k for k, h in enumerate(헤더) if "분류" in h and "이전" not in h), None)
        if 편열 is None or 종류열 is None:
            continue
        후보.append((우선, 표, 편열, 종류열, 헤더[종류열]))
    후보.sort(key=lambda t: (-t[0], -len(t[1]["행"])))
    for 우선, 표, 편열, 종류열, 열이름 in 후보:
        for 행 in 표["행"]:
            if len(행) <= max(편열, 종류열):
                continue
            편 = nfc(행[편열]).strip().strip("`")
            종류 = 종류_정리(행[종류열])
            if not 편 or not 종류:
                continue
            if 편 in 결과["편"]:
                continue  # 우선 표의 값을 유지
            결과["편"][편] = 종류
            아이디 = 편.split("_", 1)[1] if "_" in 편 else 편
            결과["아이디"].setdefault(아이디, 종류)
        if 결과["열이름"] is None:
            결과["열이름"] = 열이름
    return 결과


_이미지확장 = {".jpg", ".jpeg", ".png", ".webp"}


def 편_목록(정보: dict) -> list[dict]:
    """02/슬라이드/{편}/ 폴더마다 {'이름', '경로', '이미지': [(번호, Path), ...], '출처': Path|None}."""
    폴더02 = 정보.get("02")
    if 폴더02 is None:
        실패("02_대표슬라이드 폴더가 없습니다.")
    슬라이드 = 파일_찾기(폴더02, "슬라이드")
    if 슬라이드 is None:
        실패(f"02 안에 '슬라이드' 폴더가 없습니다: {폴더02}")
    결과 = []
    for 이름 in sorted(os.listdir(슬라이드), key=nfc):
        p = 슬라이드 / 이름
        if not p.is_dir() or 이름.startswith("."):
            continue
        이미지, 기타 = [], []
        for f in os.listdir(p):
            fp = p / f
            if f.startswith("."):
                continue
            if fp.suffix.lower() in _이미지확장 and fp.stem.isdigit():
                이미지.append((int(fp.stem), fp))
            elif nfc(f) not in ("출처.json", "글.md"):
                기타.append(nfc(f))
        이미지.sort(key=lambda t: t[0])
        결과.append({
            "이름": nfc(이름),
            "경로": p,
            "이미지": 이미지,      # 슬라이드 장: 이름이 숫자만인 그림(1.jpg, 2.jpg …)
            "기타": sorted(기타),  # 그 밖의 파일(예: 1_디자인시스템.jpg) — 장 수에 세지 않음
            "출처": 파일_찾기(p, "출처.json"),
        })
    return 결과


# ──────────────────────────── 마크다운 표 ────────────────────────────

def 셀(값) -> str:
    s = "" if 값 is None else str(값)
    return s.replace("|", "｜").replace("\n", " ")


def 마크다운표(헤더: list[str], 행들: list[list]) -> str:
    줄 = ["| " + " | ".join(셀(h) for h in 헤더) + " |",
          "|" + "---|" * len(헤더)]
    for 행 in 행들:
        줄.append("| " + " | ".join(셀(c) for c in 행) + " |")
    if not 행들:
        줄.append("| " + " | ".join(["(없음)"] + [""] * (len(헤더) - 1)) + " |")
    return "\n".join(줄)


def 결과_저장(정보: dict, 파일이름: str, 본문: str) -> Path:
    """03_분석/{파일이름} 으로 저장한다(폴더가 없으면 만든다)."""
    폴더03 = 정보.get("03")
    if 폴더03 is None:
        폴더03 = 정보["루트"] / "03_분석"
        폴더03.mkdir(parents=True, exist_ok=True)
        정보["03"] = 폴더03
    경로 = 폴더03 / 파일이름
    경로.write_text(본문, encoding="utf-8")
    return 경로


# ──────────────────────────── 이모지 ────────────────────────────

_이모지범위 = [
    (0x2600, 0x26FF),    # Misc Symbols
    (0x2700, 0x27BF),    # Dingbats
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    (0x1F1E6, 0x1F1FF),  # 국기 글자
    (0x2B00, 0x2BFF),    # ⭐ ⬇ 등
    (0x2300, 0x23FF),    # ⏰ ⌚ 등
    (0x25AA, 0x25AB), (0x25B6, 0x25B6), (0x25C0, 0x25C0), (0x25FB, 0x25FE),
    (0x2194, 0x2199), (0x21A9, 0x21AA),  # 화살표 가운데 이모지인 것(↔ ↗ ↩ 등)
    (0x2934, 0x2935), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297), (0x3299, 0x3299),
    (0x203C, 0x203C), (0x2049, 0x2049), (0x2122, 0x2122), (0x2139, 0x2139), (0x24C2, 0x24C2),
]
_변형선택자 = "️"
_결합자 = "‍"
_키캡 = "⃣"
_피부색 = range(0x1F3FB, 0x1F3FF + 1)


def 이모지인가(ch: str) -> bool:
    """글자 하나가 이모지 범위에 드는지. ⠀(U+2800)은 이모지가 아니다."""
    if not ch:
        return False
    cp = ord(ch[0])
    if cp == 0x2800:
        return False
    return any(a <= cp <= b for a, b in _이모지범위)


def 이모지_추출(text: str) -> list[str]:
    """문자열에서 이모지 목록을 뽑는다. FE0F·ZWJ·피부색·키캡(1️⃣)을 한 덩어리로 묶는다."""
    결과 = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        # 키캡: 숫자/#/* + (FE0F) + 20E3
        if ch in "0123456789#*" and i + 1 < n:
            j = i + 1
            if text[j] == _변형선택자:
                j += 1
            if j < n and text[j] == _키캡:
                결과.append(text[i:j + 1])
                i = j + 1
                continue
        if 이모지인가(ch):
            j = i + 1
            while j < n:
                nx = text[j]
                if nx == _변형선택자 or nx == _키캡 or ord(nx) in _피부색:
                    j += 1
                elif nx == _결합자 and j + 1 < n and 이모지인가(text[j + 1]):
                    j += 2
                else:
                    break
            결과.append(text[i:j])
            i = j
            continue
        i += 1
    return 결과


def 이모지_정규화(e: str) -> str:
    """통계용: 변형 선택자만 떼어 같은 이모지로 묶는다(✔️ 와 ✔). 키캡(1️⃣)은 보기 좋게 FE0F를 남긴다."""
    if _키캡 in e:
        return e[0] + _변형선택자 + _키캡
    return e.replace(_변형선택자, "")


if __name__ == "__main__":
    print("이 파일은 다른 스크립트가 불러 쓰는 공용 함수 모음입니다. 직접 실행할 일은 없습니다.")
