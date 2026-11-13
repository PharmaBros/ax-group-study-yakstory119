#!/usr/bin/env python3
"""캡션 통계 — 게시물목록.json의 캡션에서 글 버릇을 셉니다(작업 절차서 부록 B 설계서 '말투(캡션)' 칸 기준).

사용법:  python3 -I 도구/캡션통계.py <약사님폴더> [--캡션파일 X.json] [--제외 종류] [--포함개인일상] [--write]

  --캡션파일 X   캡션 전문이 다른 파일에 있을 때만(키 `캡션전문`, id로 맞춤). 캡션합치기로 게시물목록.json에 합쳤으면 필요 없음
  --제외 종류    기본값 "개인·일상"(개인 일상 게시물은 뺀다). 다른 종류를 더 빼려면 쉼표로 적는다.
  --포함개인일상 개인 일상도 센다.
  --write        결과를 03_분석/{오늘}_캡션통계.md 로 저장

세는 것: 캡션 수·글자수·줄 수 / 끝맺음 어미 / 존댓말·반말(캡션) / 1인칭 / 이모지(불릿 제외) / 줄 구분 / 불릿 / 해시태그 / 멘션 / CTA /
광고·공구 표시 / 자주 쓰는 표현(2~4어절) / 첫 줄 모양 / 끝맺음 구조(마지막 줄 모양) / 종류별 캡션 수.
캡션 원문은 출력하지 않습니다(통계만).
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

# ──────────────────────────── 사전 ────────────────────────────

어미사전 = sorted([
    "해요", "에요", "예요", "거든요", "세요", "합니다", "습니다", "네요", "죠", "까요", "래요", "데요",
    "잖아요", "더라고요", "드려요", "주세요", "보세요", "하세요", "드릴게요", "할게요", "을게요", "ㄹ게요",
    "됩니다", "입니다", "었어요", "았어요", "했어요", "어요", "아요",
    "나요", "돼요", "안돼요", "줘요", "해줘요", "져요", "워요", "라요", "라구요", "려요", "여요", "켜요", "시켜요",
    "가요", "나가요", "구요", "볼게요", "줄게요", "있나요", "달라요", "커요", "봐요", "와요", "이에요", "예요", "거예요",
    "게요", "데요", "세용", "니당", "셔요", "써요",
], key=len, reverse=True)  # 단독 '요'는 두지 않는다('중요'·'필요' 같은 명사 오탐). 매칭은 긴 어미부터.

존댓말끝 = re.compile(r"(요|니다|세요|죠|용|당)$")
# 반말은 화이트리스트만 인정한다(미토콘드리아·방지·~는데·에게 같은 명사·연결 어미는 반말이 아님).
# ㄴ다·ㄹ게는 받침이라 글자 분해로 따로 판정한다(_받침_어미). 있어·없어는 시험 요구로 추가.
반말끝 = re.compile(r"(는다|ㄴ다|있다|없다|이다|하다|겠다|았다|었다|였다|았어|었어|했어|있어|없어|거야|거지|잖아|더라고|더라|할게|을게|ㄹ게|냐|했니|있니|없니|하자|보자)$")

일인칭_정확 = {"저는", "제가", "저도", "저", "제", "제게", "저를", "저한테", "저에게", "저의", "저랑", "저와"}
일인칭_접두 = ("저희",)
일인칭_구절 = ["약사인 저", "약사로서"]

CTA패턴 = {
    "저장": re.compile(r"저장해|저장하|저장 해|북마크|\[\s*저장\s*\]"),  # "[저장]" 대괄호 표기도 셈(검수 2026-11-02)
    "DM": re.compile(r"DM|디엠|메시지 주|(?<!전)문의", re.I),
    "댓글": re.compile(r"댓글"),
    "프로필": re.compile(r"프로필|링크\s*(?:클릭|타고|눌러|확인)"),
    "공유": re.compile(r"공유해|공유하|공유 부탁|공유 해|\[\s*공유\s*\]"),
    "팔로우": re.compile(r"팔로우|팔로잉"),
}
광고패턴 = re.compile(r"유료광고|공동구매|#광고|\*광고\*|광고|협찬|공구")

불릿기호 = set("✔✅📍▫▪•·◆■🔹✓☑◇○●▶‣※▶️➡→★☆🔸🔺🔻💡❗❕①②③④⑤⑥⑦⑧⑨⑩-–—")
구분선 = re.compile(r"^[─—–\-=_·.ㅡ•*~]{3,}$")
점자공백 = "⠀"

불용어 = set("이 그 저 것 수 등 및 더 좀 또 잘 꼭 너무 정말 진짜 그리고 그래서 하지만 근데 그냥 바로 다 안 못 왜 뭐 때 중 후 전 위 아래 요 네 아 오 음 어 응 은 는 을 를 가 에 의 로 과 와 도 만 한 두 세 번 개 분 명 년 월 일 시 하는 있는 없는 있어요 없어요 합니다 입니다 해요 되는 된 될 한다 이런 저런 그런 여기 거기 저기 또는 혹은".split())
해시태그 = re.compile(r"#[\w가-힣ㄱ-ㅎㅏ-ㅣ_]+")
멘션 = re.compile(r"(?<![\w가-힣])@[\w.]+")
URL = re.compile(r"https?://\S+")


# ──────────────────────────── 핵심 함수(테스트 대상) ────────────────────────────

def 문장_나누기(캡션: str) -> list[str]:
    """줄바꿈·. ! ? : 로 문장을 나눈다. ':)' ':D' 스마일은 끊지 않는다."""
    결과 = []
    for 줄 in 캡션.splitlines():
        조각 = re.split(r"(?:[.!?]+|:(?![)D]))", 줄)
        for s in 조각:
            s = s.strip()
            if s:
                결과.append(s)
    return 결과


_꼬리기호 = re.compile(r"[\s~♡♥♪☆★\"'”’)\]…·,.!?<>ㄱ-ㅎㅏ-ㅣ]+$")


def _꼬리_제거(문장: str) -> tuple[str, bool]:
    """문장 끝의 스마일·이모지·기호(~ ! ? < > ㅠㅠ ㅎㅎ ㅋㅋ …)를 떼고 (남은 글, 스마일 여부)를 돌려준다."""
    s = 문장.strip()
    스마일 = False
    if re.search(r":\)|:D|\^\^|:-\)", s[-4:]):
        스마일 = True
        s = re.sub(r"(:\)|:D|\^\^|:-\))\s*$", "", s)
    for e in 공통.이모지_추출(s[-8:]):
        s = s.replace(e, " ")
    return _꼬리기호.sub("", s).rstrip(), 스마일


def _받침_어미(어절: str) -> str | None:
    """'한다·간다'(ㄴ다)·'할게·갈게'(ㄹ게)를 글자 분해로 알아본다. 맞으면 '~ㄴ다'/'~ㄹ게' 용 어미, 아니면 None."""
    if len(어절) < 2:
        return None
    마지막, 앞 = 어절[-1], 어절[-2]
    if not ("가" <= 앞 <= "힣"):
        return None
    종성 = (ord(앞) - 0xAC00) % 28
    if 마지막 == "다" and 종성 == 4:      # ㄴ
        return "ㄴ다"
    if 마지막 == "게" and 종성 == 8:      # ㄹ
        return "ㄹ게"
    return None


def 끝맺음_어미(문장: str) -> str | None:
    """문장 마지막 어절의 끝 어미를 돌려준다. 어미사전(존댓말) 또는 반말 화이트리스트에 있을 때만 돌려주고, 아니면 None.
    ':)' 로 끝났으면 ' :)' 를 붙인다. 예: '~해요 :)'
    """
    s, 스마일 = _꼬리_제거(문장)
    if not s:
        return None
    어절 = s.split()[-1]
    어절 = re.sub(r"^[#@(\[\"'“‘]+", "", 어절)
    if 어절.startswith("#") or 어절.startswith("@") or not 어절:
        return None
    if not re.search(r"[가-힣]$", 어절):
        return None
    if len(어절) == 1:  # 한글 1글자 어절("(아!" 등)은 어미 후보가 아니다
        return None
    어미 = None
    for 후보 in 어미사전:
        if 어절.endswith(후보) and len(어절) >= len(후보):
            어미 = 후보
            break
    if 어미 is None and 어절.endswith("니다"):
        어미 = "ㅂ니다"
    if 어미 is None:
        m = 반말끝.search(어절)
        if m and m.group(1) not in ("ㄴ다", "ㄹ게"):
            # 할게는 ㄹ게 묶음보다 구체적이라 그대로 둔다
            어미 = m.group(1)
        else:
            어미 = _받침_어미(어절)
    if 어미 is None:
        return None
    라벨 = "~" + 어미
    if 스마일:
        라벨 += " :)"
    return 라벨


def 존댓말_판정(문장: str) -> str | None:
    """문장 끝으로 '존댓말' / '반말' / None(판정 불가: 어미사전·반말 화이트리스트에 없음)."""
    어미 = 끝맺음_어미(문장)
    if 어미 is None:
        return None
    어절 = re.sub(r" :\)$", "", 어미)[1:]
    if 존댓말끝.search(어절):
        return "존댓말"
    return "반말"


def 일인칭_세기(캡션: str) -> Counter:
    c = Counter()
    본문 = 해시태그.sub(" ", 캡션)
    for 구절 in 일인칭_구절:
        n = 본문.count(구절)
        if n:
            c[구절] += n
    for 어절 in 본문.split():
        w = 어절.strip("()[]\"'“”‘’,.!?~:")
        if w in 일인칭_정확:
            c[w] += 1
        elif w.startswith(일인칭_접두):
            c["저희~"] += 1
    return c


def 해시태그_위치(캡션: str) -> str | None:
    """'끝 줄 몰림' / '본문 안' / '섞임' / None(해시태그 없음)."""
    줄들 = [l for l in 캡션.splitlines() if l.strip() and set(l.strip()) != {점자공백}]
    태그줄 = [bool(해시태그.search(l)) for l in 줄들]
    if not any(태그줄):
        return None
    # 끝에서부터 연속으로 해시태그가 든 줄 수
    끝몰림 = 0
    for 있다 in reversed(태그줄):
        if 있다:
            끝몰림 += 1
        else:
            break
    본문안 = sum(태그줄[: len(태그줄) - 끝몰림])
    if 끝몰림 and not 본문안:
        return "끝 줄 몰림"
    if 본문안 and not 끝몰림:
        return "본문 안"
    return "섞임"


def 광고_위치(캡션: str) -> str | None:
    줄들 = [l for l in 캡션.splitlines() if l.strip() and set(l.strip()) != {점자공백}]
    위치 = set()
    n = len(줄들)
    for i, l in enumerate(줄들):
        if 광고패턴.search(l):
            if i < 3:
                위치.add("첫 3줄")
            elif i >= n - 3:
                위치.add("끝 3줄")
            else:
                위치.add("중간")
    if not 위치:
        return None
    return "·".join(sorted(위치, key=["첫 3줄", "중간", "끝 3줄"].index))


def 토큰화(캡션: str) -> list[list[str]]:
    """n-gram용: 줄마다 어절 목록. 해시태그·멘션·URL·이모지·기호만인 어절은 줄을 끊는 경계가 된다."""
    줄결과 = []
    for 줄 in 캡션.splitlines():
        줄 = URL.sub(" ", 줄)
        현재 = []
        for 어절 in 줄.split():
            w = 어절
            for e in 공통.이모지_추출(w):
                w = w.replace(e, "")
            w = w.strip("()[]\"'“”‘’,.!?~:;·⠀-▫▪•✔✅✓☑")
            if not w or w.startswith("#") or w.startswith("@") or not re.search(r"[가-힣A-Za-z0-9]", w):
                if 현재:
                    줄결과.append(현재)
                    현재 = []
                continue
            현재.append(w)
        if 현재:
            줄결과.append(현재)
    return 줄결과


def 엔그램_세기(캡션들: list[str], 최소=3, 상위=20) -> list[tuple[str, int]]:
    c = Counter()
    for 캡 in 캡션들:
        본편 = set()
        for 토큰들 in 토큰화(캡):
            for n in (2, 3, 4):
                for i in range(len(토큰들) - n + 1):
                    g = 토큰들[i:i + n]
                    if g[0] in 불용어 or g[-1] in 불용어:
                        continue
                    if any(len(t) == 1 for t in g):
                        continue
                    본편.add(" ".join(g))
        for g in 본편:
            c[g] += 1  # 캡션 단위로 센다(한 캡션에서 반복돼도 1)
    항목 = [(g, n) for g, n in c.items() if n >= 최소]
    항목.sort(key=lambda t: (-t[1], -len(t[0]), t[0]))
    # 더 긴 n-gram에 완전히 포함되고 횟수가 같은 짧은 것은 뺀다
    결과 = []
    for g, n in 항목:
        if any(g in g2 and g != g2 and n2 == n for g2, n2 in 항목):
            continue
        결과.append((g, n))
    return 결과[:상위]


def 첫줄(캡션: str) -> str:
    for l in 캡션.splitlines():
        if l.strip() and set(l.strip()) != {점자공백}:
            return l.strip()
    return ""


불릿이모지 = {"✔", "✅", "📍", "🔹", "🔸", "💡", "❗", "❕", "▫", "▪", "☑", "✓", "➡", "▶", "⭐", "🔺", "🔻", "✨", "👉", "📌", "💊", "🎈", "🧡", "💛", "❤", "🤍", "✍", "🔥"}
글자불릿 = set("•·◆■◇○●‣※★☆①②③④⑤⑥⑦⑧⑨⑩▫▪✓☑✔")


def 불릿_기호(줄: str) -> str | None:
    """줄 첫 글자가 불릿 기호면 그 기호(변형 선택자 제거)를, 아니면 None."""
    첫 = 줄.lstrip(점자공백 + " \t")
    if not 첫:
        return None
    es = 공통.이모지_추출(첫[:4])
    if es and 첫.startswith(es[0]):
        기호 = 공통.이모지_정규화(es[0])
        if 기호 in 불릿이모지 or re.match(r"^[0-9#*]\uFE0F?\u20E3$", 기호):
            return 기호
        return None
    ch = 첫[0]
    if ch in "-–—":
        return ch if len(첫) > 1 and 첫[1] == " " else None
    if ch in 글자불릿:
        return ch
    if re.match(r"^\d+[.)]\s", 첫):
        return "1."
    return None


def 제목형인가(줄: str) -> bool:
    s = 줄
    for e in 공통.이모지_추출(s):
        s = s.replace(e, "")
    s = s.strip()
    return bool(s) and "." not in s and len(s) <= 20


# ──────────────────────────── 집계 ────────────────────────────

설계서5종 = {"제품소개", "공구안내", "영양제트렌드", "건강정보", "개인일상"}


def 종류_출처(항목: dict, 분류: dict) -> tuple[str, str]:
    """(종류, 출처). 출처: '분류.md'(설계서 5종에 드는 것) / '게시물목록'(옛 분류 또는 5종 밖의 값)."""
    아이디 = 항목.get("id") or ""
    if 아이디 in 분류["아이디"]:
        종류 = 분류["아이디"][아이디]
        if 공통.종류_키(종류) in 설계서5종:
            return 종류, "분류.md"
        return 종류, "게시물목록"
    return (공통.종류_정리(항목.get("분류") or "미분류") or "미분류"), "게시물목록"


def 종류_정하기(항목: dict, 분류: dict) -> str:
    return 종류_출처(항목, 분류)[0]


def 마지막줄_모양(캡션: str) -> str | None:
    """마지막 비어 있지 않은 줄(점자 공백 줄 제외)의 모양: CTA 문구/멘션/해시태그/이모지만/인사말/기타. 줄이 없으면 None."""
    줄들 = [l.strip() for l in 캡션.splitlines() if l.strip() and set(l.strip()) > set() and not set(l.strip()) <= {점자공백, " "}]
    if not 줄들:
        return None
    줄 = 줄들[-1]
    남김 = URL.sub(" ", 줄)
    for e in 공통.이모지_추출(남김):
        남김 = 남김.replace(e, " ")
    글자없음 = not re.search(r"[가-힣A-Za-z0-9]", 해시태그.sub(" ", 멘션.sub(" ", 남김)))
    if not re.search(r"[가-힣A-Za-z0-9#@]", 남김):
        return "이모지만"
    if 줄.startswith("#") or (해시태그.search(줄) and 글자없음):
        return "해시태그"
    if any(p.search(줄) for p in CTA패턴.values()):
        return "CTA 문구"
    if 멘션.search(줄):
        return "멘션"
    꼬리없음, _ = _꼬리_제거(줄)
    if re.search(r"(세요|습니다|해요)$", 꼬리없음):
        return "인사말"
    return "기타"


_연결어미끝 = re.compile(r"(는데|인데|은데|한데|거나|까지|위해|니까|으니|면서|지만|어서|아서|면|다면|라면|시면|으나|해서|하고|이라)$")


def 판정불가_종류(문장: str) -> str:
    """종결어미를 못 찾은 문장이 왜 그런지: '불릿 항목' / '연결어미 끝' / '숫자·영어' / '명사·구 끝'."""
    if 불릿_기호(문장.strip()):
        return "불릿 항목"
    s, _ = _꼬리_제거(문장)
    if _연결어미끝.search(s):
        return "연결어미 끝"
    if re.search(r"[0-9A-Za-z%]$", s):
        return "숫자·영어"
    return "명사·구 끝"


def _내용_문장인가(문장: str) -> bool:
    """해시태그·멘션·URL·이모지·기호만 있는 조각은 판정 불가 문장 수에서 뺀다."""
    t = URL.sub(" ", 멘션.sub(" ", 해시태그.sub(" ", 문장)))
    for e in 공통.이모지_추출(t):
        t = t.replace(e, " ")
    return bool(re.search(r"[가-힣A-Za-z0-9]", t))


def 게시_날짜(항목: dict):
    """게시일 → 게시일_og(한국 날짜) → 게시시각_utc(+9시간, 한국 날짜로) 순으로 읽는다. 없으면 None."""
    import datetime as _dt
    for 키 in ("게시일", "게시일_og"):
        try:
            return _dt.date.fromisoformat(str(항목.get(키) or "")[:10])
        except ValueError:
            continue
    utc = str(항목.get("게시시각_utc") or "")
    try:
        return (_dt.datetime.fromisoformat(utc[:19]) + _dt.timedelta(hours=9)).date()
    except ValueError:
        return None


def 주당_편수(목록: list[dict], 최근=60) -> dict | None:
    """격자 순서 기준 최근 N편의 주당 편 수(릴스·개인 일상 포함).

    고정 게시물(`고정` 참)은 뺀다. 표시가 없어도 격자 앞 3자리 안에서 뒤 게시물보다 날짜가 이른 것은
    고정 의심으로 뺀다(이틀 이상 이를 때만 — 하루 차이는 시차일 수 있음). 의심한 편 아이디는 보고서에 적는다. 날짜가 빠진 게시물도 편 수에는 들어간다(격자에서 맨 앞·맨 뒤 날짜 있는 편 사이를 센다).
    날짜 있는 편이 2편 미만이면 None.
    """
    목록 = sorted(목록, key=lambda x: x.get("순서") or 0) if all(isinstance(x.get("순서"), int) for x in 목록) else list(목록)
    남은 = [x for x in 목록 if not x.get("고정")]
    날짜 = [게시_날짜(x) for x in 남은]
    의심 = set()
    for k in range(min(3, len(남은))):
        뒤 = [d for d in 날짜[k + 1:k + 11] if d]
        if 날짜[k] and 뒤 and (max(뒤) - 날짜[k]).days >= 2:
            의심.add(k)
    창 = [(x, d) for k, (x, d) in enumerate(zip(남은, 날짜)) if k not in 의심][:최근]
    있는 = [n for n, (_, d) in enumerate(창) if d]
    if len(있는) < 2:
        return None
    처음, 끝 = 있는[0], 있는[-1]
    최신, 오래 = 창[처음][1], 창[끝][1]
    일수 = max(1, (최신 - 오래).days)
    편수 = 끝 - 처음 + 1
    return {"편수": 편수, "시작": 오래.isoformat(), "끝": 최신.isoformat(), "일수": 일수,
            "주당": round((편수 - 1) / 일수 * 7, 1), "날짜없음": 편수 - len(있는),
            "고정": sum(1 for x in 목록 if x.get("고정")), "고정의심": len(의심),
            "고정의심_id": [str(남은[k].get("id") or 남은[k].get("순서")) for k in sorted(의심)]}


def 집계(목록: list[dict], 분류: dict, 제외: list[str], 포함개인일상: bool) -> dict:
    대상 = []
    제외수 = Counter()   # 종류_키 → 개수(표기만 다른 같은 종류는 합친다)
    제외이름: dict = {}
    제외키 = {공통.종류_키(x) for x in 제외}
    for 항목 in 목록:
        종류, 출처 = 종류_출처(항목, 분류)
        k = 공통.종류_키(종류)
        if (not 포함개인일상 and 공통.개인일상인가(종류)) or k in 제외키:
            제외수[k] += 1
            제외이름.setdefault(k, 종류)
            continue
        if not str(항목.get("캡션") or "").strip():
            제외수["(빈 캡션)"] += 1
            제외이름.setdefault("(빈 캡션)", "(빈 캡션)")
            continue
        대상.append((종류, 출처, str(항목["캡션"])))

    캡션들 = [c for _, _, c in 대상]
    R: dict = {"주당": 주당_편수(목록), "캡션수": len(캡션들), "제외": Counter({제외이름[k]: n for k, n in 제외수.items()}), "전문수": sum(1 for x in 목록 if x.get("캡션출처") == "전문")}
    if not 캡션들:
        return R
    길이 = [len(c) for c in 캡션들]
    줄수 = [len([l for l in c.splitlines() if l.strip()]) for c in 캡션들]
    R["글자수"] = {"최소": min(길이), "최대": max(길이), "중앙값": round(statistics.median(길이), 1), "평균": round(statistics.mean(길이), 1)}
    R["줄수평균"] = round(statistics.mean(줄수), 1)

    어미 = Counter(); 존반 = Counter(); 일인칭 = Counter()
    이모지 = Counter(); 이모지합 = 0; 첫이모지 = Counter(); 첫이모지수 = 0
    빈줄 = 점자줄 = 구분선수 = 0
    불릿 = Counter()
    태그수 = []; 태그위치 = Counter(); 태그 = Counter(); 멘션들 = Counter()
    CTA = Counter(); CTA캡션 = Counter()
    광고수 = 0; 광고위치 = Counter()
    첫줄길이 = []; 첫줄이모지 = 0; 첫줄제목형 = 0
    종류별 = {}; 종류별_옛 = {}; 표시이름 = {}
    이모지불릿합 = 0; 판정불가 = 0; 판정불가_세부 = Counter(); 끝구조 = Counter()

    for 종류, 출처, 캡 in 대상:
        for 문장 in 문장_나누기(캡):
            e = 끝맺음_어미(문장)
            if e:
                어미[e] += 1
            j = 존댓말_판정(문장)
            if j:
                존반[j] += 1
            elif _내용_문장인가(문장):
                판정불가 += 1
                판정불가_세부[판정불가_종류(문장)] += 1
        일인칭.update(일인칭_세기(캡))
        # 줄 첫 글자로 쓰인 이모지(불릿으로 잡힌 것)는 이모지 표에서 뺀다
        for 줄 in 캡.splitlines():
            es_줄 = 공통.이모지_추출(줄)
            b0 = 불릿_기호(줄.strip())
            if es_줄 and b0 and (공통.이모지인가(b0[0]) or 공통._키캡 in b0):
                이모지불릿합 += 1
                es_줄 = es_줄[1:]
            이모지합 += len(es_줄)
            이모지.update(공통.이모지_정규화(e) for e in es_줄)
        m끝 = 마지막줄_모양(캡)
        if m끝:
            끝구조[m끝] += 1
        s = 캡.lstrip()
        es0 = 공통.이모지_추출(s[:4])
        if es0 and s.startswith(es0[0]):
            첫이모지수 += 1
            첫이모지[공통.이모지_정규화(es0[0])] += 1
        for 줄 in 캡.splitlines():
            t = 줄.strip()
            if not t:
                빈줄 += 1
            elif set(t) <= {점자공백, " "}:
                점자줄 += 1
            elif 구분선.match(t):
                구분선수 += 1
            else:
                b = 불릿_기호(t)
                if b:
                    불릿[b] += 1
        ts = 해시태그.findall(캡)
        태그수.append(len(ts))
        태그.update(t.lower() for t in ts)
        p = 해시태그_위치(캡)
        if p:
            태그위치[p] += 1
        멘션들.update(m.lower() for m in 멘션.findall(캡))
        for 이름, 패턴 in CTA패턴.items():
            n = len(패턴.findall(캡))
            if n:
                CTA[이름] += n
                CTA캡션[이름] += 1
        gp = 광고_위치(캡)
        if gp:
            광고수 += 1
            광고위치[gp] += 1
        f = 첫줄(캡)
        첫줄길이.append(len(f))
        if 공통.이모지_추출(f):
            첫줄이모지 += 1
        if 제목형인가(f):
            첫줄제목형 += 1
        키 = 공통.종류_키(종류)
        표시이름.setdefault(키, 종류)
        (종류별 if 출처 == "분류.md" else 종류별_옛).setdefault(키, []).append(len(캡))

    R.update({
        "어미": 어미.most_common(10), "존반": 존반, "일인칭": 일인칭.most_common(),
        "이모지": 이모지.most_common(15), "이모지평균": round(이모지합 / len(캡션들), 1),
        "이모지평균_불릿포함": round((이모지합 + 이모지불릿합) / len(캡션들), 1), "불릿이모지수": 이모지불릿합,
        "판정불가": 판정불가, "판정불가_세부": 판정불가_세부, "끝구조": 끝구조,
        "첫이모지비율": round(첫이모지수 / len(캡션들) * 100), "첫이모지": 첫이모지.most_common(5),
        "빈줄": 빈줄, "점자줄": 점자줄, "구분선": 구분선수, "불릿": 불릿.most_common(),
        "태그평균": round(statistics.mean(태그수), 1), "태그위치": 태그위치, "태그": 태그.most_common(15),
        "태그있는캡션": sum(1 for n in 태그수 if n),
        "멘션": 멘션들.most_common(10), "CTA": CTA, "CTA캡션": CTA캡션,
        "광고수": 광고수, "광고위치": 광고위치, "엔그램": 엔그램_세기(캡션들),
        "첫줄길이평균": round(statistics.mean(첫줄길이), 1),
        "첫줄이모지비율": round(첫줄이모지 / len(캡션들) * 100), "첫줄제목형비율": round(첫줄제목형 / len(캡션들) * 100),
        "종류별": {표시이름[k]: (len(v), round(statistics.mean(v), 1)) for k, v in sorted(종류별.items())},
        "종류별_옛분류": {표시이름[k]: (len(v), round(statistics.mean(v), 1)) for k, v in sorted(종류별_옛.items())},
    })
    return R


def 보고서(정보: dict, R: dict, 캡션파일: str | None, 분류열: str | None) -> str:
    표 = 공통.마크다운표
    L = [f"# {정보['이름']} 캡션 통계 ({공통.오늘()})", ""]
    근거 = "01/게시물목록.json 캡션"
    if 캡션파일:
        근거 += f" + 전문 파일 `{Path(캡션파일).name}`(id 일치 {R.get('전문수', 0)}개 바꿈)"
    import datetime as _dt
    L.append(f"실행: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · 입력: 캡션 {R.get('캡션수', '?')}개(제외 뒤) — [도구] 칸에 옮길 때 이 실행 시각을 함께 적는다.")
    L.append(f"근거: {근거}. 종류는 02/분류.md(`{분류열 or '없음'}` 열) → 없으면 게시물목록의 `분류`. 제외: " +
             (", ".join(f"{k} {v}개" for k, v in R["제외"].items()) or "없음") + ". 캡션 원문은 싣지 않음.")
    L.append("")
    if not R["종류별"]:
        L += ["⚠ 02/분류.md가 설계서 5종으로 재분류되지 않아 5종 표가 비어 있음 — 작업 절차서 부록 A-1 판정표로 재분류한 뒤 다시 돌릴 것", ""]
    if not R.get("글자수"):
        L.append("**셀 캡션이 없습니다.**")
        return "\n".join(L)
    g = R["글자수"]
    L += ["## 분석 게시물 수 · 문장 길이", 표(["항목", "값"], [
        ["캡션 수", R["캡션수"]], ["글자수 최소/최대", f"{g['최소']} / {g['최대']}"],
        ["글자수 중앙값/평균", f"{g['중앙값']} / {g['평균']}"], ["줄 수 평균(빈 줄 제외)", R["줄수평균"]]]), ""]
    if g["최대"] <= 300:
        L += ["> ⚠ 최장 캡션이 300자 이하 — 캡션이 잘렸을 수 있습니다. 끝맺음·CTA·해시태그 수치는 참고값입니다.", ""]
    종결수 = sum(R["존반"].values())
    세부 = R["판정불가_세부"]
    L += ["## 캡션 글투(존댓말/반말)", "설계서 '말투(슬라이드)'는 글.md 기준. 여기는 캡션.", "",
          표(["구분", "문장 수", f"비율(종결어미가 있는 문장 {종결수}개 기준)"], [
              *[[k, v, f"{round(v / max(1, 종결수) * 100)}%"] for k, v in R["존반"].most_common()],
              [f"판정 불가 {R['판정불가']}문장 = 불릿 항목 {세부['불릿 항목']} / 명사·구 끝 {세부['명사·구 끝']} / "
               f"숫자·영어 {세부['숫자·영어']} / 연결어미 끝 {세부['연결어미 끝']}", R["판정불가"], "-"]]), ""]
    L += ["## 끝맺음(자주 쓰는 어미, 횟수)", 표(["어미", "횟수"], [[k, v] for k, v in R["어미"]]), ""]
    L += ["## 1인칭 표현(저/제가/약사인 저 등)", 표(["표현", "횟수"], [[k, v] for k, v in R["일인칭"]]), ""]
    L += ["## 이모지 버릇 — 캡션(쓰는 것·캡션당 개수, 줄 첫 글자 불릿 이모지는 뺌)",
          표(["항목", "값"], [["캡션당 평균(불릿 제외)", R["이모지평균"]], ["캡션당 평균(불릿 포함)", R["이모지평균_불릿포함"]],
                           ["불릿으로 쓴 이모지 수(표에서 뺌)", R["불릿이모지수"]], ["첫 글자가 이모지인 캡션", f"{R['첫이모지비율']}%"]]),
          "", 표(["이모지(상위 15)", "횟수"], [[k, v] for k, v in R["이모지"]]),
          "", 표(["첫 글자 이모지(상위 5)", "캡션 수"], [[k, v] for k, v in R["첫이모지"]]), ""]
    L += ["## 자주 쓰는 표현(2~4어절, 3회 이상 캡션, 상위 20)", 표(["표현", "캡션 수"], [[k, v] for k, v in R["엔그램"]]), ""]
    L += ["## 캡션 버릇(첫 줄 모양)", 표(["항목", "값"], [
        ["첫 줄 글자수 평균", R["첫줄길이평균"]], ["첫 줄에 이모지 있는 캡션", f"{R['첫줄이모지비율']}%"],
        ["첫 줄이 제목형(마침표 없음·20자 이하)", f"{R['첫줄제목형비율']}%"]]), ""]
    L += ["## CTA 문구 버릇", 표(["CTA", "횟수", "들어 있는 캡션 수"], [[k, R["CTA"][k], R["CTA캡션"][k]] for k in CTA패턴 if R["CTA"][k]]), ""]
    L += ["## 줄 구분 방식(빈 줄/공백 문자/구분선)", 표(["방식", "줄 수"], [["빈 줄", R["빈줄"]], ["점자 공백 ⠀(U+2800) 줄", R["점자줄"]], ["구분선(─·—·--- 등)", R["구분선"]]]), ""]
    L += ["## 불릿 기호와 자리(줄 첫 글자)", 표(["기호", "줄 수"], [[k, v] for k, v in R["불릿"]]), ""]
    L += ["## 해시태그(평균 개수, 위치, 고정 태그)", 표(["항목", "값"], [
        ["캡션당 평균 개수", R["태그평균"]], ["해시태그 있는 캡션", R["태그있는캡션"]],
        *[[f"위치: {k}", f"{v}개 캡션"] for k, v in R["태그위치"].most_common()]]),
          "", 표(["해시태그(상위 15)", "캡션 수"], [[k, v] for k, v in R["태그"]]), ""]
    L += ["## 멘션(@계정, 상위 10)", 표(["계정", "횟수"], [[k, v] for k, v in R["멘션"]]), ""]
    L += ["## 광고·공구 표시 방식(문구·위치)", 표(["항목", "값"], [
        ["광고·협찬·공구 표시가 든 캡션", R["광고수"]],
        *[[f"위치: {k}", f"{v}개 캡션"] for k, v in R["광고위치"].most_common()]]), ""]
    L += ["## 끝맺음 구조(마지막 줄 모양)", 표(["마지막 줄 모양", "캡션 수"], [[k, R["끝구조"][k]] for k in ["CTA 문구", "멘션", "해시태그", "이모지만", "인사말", "기타"]]), ""]
    주 = R.get("주당")
    L += ["## 주당 편 수(격자 최근 60편, 릴스·개인 일상 포함, 고정 게시물 제외)",
          표(["항목", "값"], [["주당 편 수", 주["주당"]], ["센 범위", f"최근 {주['편수']}편 · {주['시작']} ~ {주['끝']} ({주['일수']}일)"],
                           ["그 사이 날짜 빠진 게시물(편 수에는 셈)", 주["날짜없음"]],
                           ["뺀 고정 게시물(표시 있음 / 앞자리 날짜로 의심)", f"{주['고정']} / {주['고정의심']}" + (f" ({', '.join(주['고정의심_id'])} — 사람이 확인)" if 주['고정의심_id'] else "")],
                           ["계산", "(편 수 − 1) ÷ 기간 일수 × 7"]]) if 주 else "측정 불가(게시일이 있는 게시물이 2편 미만)", ""]
    L += ["## 종류 비율 — 분류.md 기준(설계서 5종)", 표(["종류", "캡션 수", "평균 글자수"], [[k, n, m] for k, (n, m) in R["종류별"].items()]), ""]
    L += ["## 종류 비율 — 게시물목록 기준(옛 분류·참고)", 표(["종류", "캡션 수", "평균 글자수"], [[k, n, m] for k, (n, m) in R["종류별_옛분류"].items()]), ""]
    return "\n".join(L)


def main(argv=None):
    ap = 공통.한글ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    ap.add_argument("약사님폴더")
    ap.add_argument("--캡션파일", default=None, help="캡션 전문 json(키 캡션전문)")
    ap.add_argument("--제외", default="개인·일상", help="뺄 종류(쉼표 구분). 기본 개인·일상")
    ap.add_argument("--포함개인일상", action="store_true", help="개인 일상 캡션도 센다")
    ap.add_argument("--write", action="store_true", help="03_분석/{오늘}_캡션통계.md 로 저장")
    ap.add_argument("-h", "--help", action="help", help="이 도움말")
    args = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(args.약사님폴더)
    목록 = 공통.게시물목록_읽기(정보, args.캡션파일)
    분류 = 공통.분류_읽기(정보)
    제외 = [x for x in args.제외.split(",") if x.strip()] if not args.포함개인일상 else [x for x in args.제외.split(",") if x.strip() and not 공통.개인일상인가(x)]
    R = 집계(목록, 분류, 제외, args.포함개인일상)
    본문 = 보고서(정보, R, args.캡션파일, 분류["열이름"])
    print(본문)
    if args.write:
        p = 공통.결과_저장(정보, f"{공통.오늘()}_캡션통계.md", 본문 + "\n")
        print(f"\n저장했습니다: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
