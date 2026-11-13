"""블라인드 — 만든 장과 원본 장을 섞은 판정용 판(흐림 모아보기 A · 낱장 B)과 정답표를 만든다. PIL만 쓴다.

출처: R/새방식_공용도구/블라인드/setup.py·setup2.py, R/2026-11-10_디자인시스템/블라인드/setup.py·setup2.py (2026-11-10 판)를 일반화.
쓰기: python3 도구/부품/블라인드.py <약사님폴더> <부품 상위 폴더> --출력 <폴더> [--회차 N] [--재압축] [--대조 <부품>] [--씨앗 N]
부품 폴더(render.png·견본.json 있는 곳)를 이름순으로 회차마다 4개씩 쓴다. 원본은 대표 슬라이드 사진메모.json 에서 같은 `부품`으로 판정된 장.
"""
from __future__ import annotations

import io
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402
from lib import 기본_높이, 견본_높이  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

회차당_부품 = 4

지시문 = """# 블라인드 판정 지시 ({종류})

아래 {n}장 중 **실제 인스타그램 게시물에서 가져온 장**과 **디자인 도구로 만든 장**을 가려 주세요.
{입력}

- 장마다 `실제` 또는 `만든 것` 중 하나로 답하고, 이유를 한 줄로 적습니다.
- 글의 주제·내용·계정 분위기를 단서로 쓰지 마세요. 모양·질감·글자 모양과 번짐·사진 처리·여백만 보고 판단합니다.
- 확신이 없어도 반드시 하나를 고르고, 이유 칸에 `애매함`이라고 적습니다.
- 다른 파일(정답표 등)은 열지 않습니다.

답 형식: `<번호>: 실제|만든 것 — 이유 한 줄`
"""


# ─────────── 원본 장 모으기 ───────────
def 해시(im):
    """작은 썸네일(8x8 흑백) 평균 해시 — 같은 그림 재사용 판단용."""
    t = im.convert("L").resize((8, 8), Image.BILINEAR)
    px = list(t.tobytes())
    m = sum(px) / 64
    return sum(1 << i for i, v in enumerate(px) if v > m)


def 같은그림(a, b):
    return bin(a ^ b).count("1") <= 6


def 장_모으기(슬라이드):
    """슬라이드/<편>/사진메모.json 의 장 항목 → [{편, 장, 경로, 부품, 바탕}]"""
    out = []
    for 편 in sorted(슬라이드.iterdir()):
        메모 = 공통.파일_찾기(편, "사진메모.json")
        if not 편.is_dir() or 메모 is None:
            continue
        for e in json.loads(메모.read_text(encoding="utf-8")):
            p = 편 / f"{e['장']}.jpg"
            if p.exists():
                out.append({"편": 공통.nfc(편.name), "장": int(e["장"]), "경로": p,
                            "부품": e.get("부품"), "바탕": e.get("바탕") or ""})
    return out


def 근거_장(부품폴더):
    """견본.json 근거·근거_편 글에서 `<11자 게시물 id> 1·2장` 꼴을 읽어 {(id, 장)}."""
    f = 공통.파일_찾기(부품폴더, "견본.json")
    if f is None:
        return set()
    d = json.loads(f.read_text(encoding="utf-8"))
    글 = f"{d.get('근거_편', '')} {d.get('근거', '')}"
    out = set()
    for m in re.finditer(r"(?<![A-Za-z0-9_-])(?=[A-Za-z0-9_-]*[A-Za-z])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])\s*((?:\d+\s*[장·,]?\s*)+)", 글):
        out |= {(m[1], int(n)) for n in re.findall(r"\d+", m[2])}
    return out


def 편_id(편):
    return 편.split("_", 1)[-1]


def 이전_회차_사용(출력, 회차):
    """출력 폴더의 이전 회차(r1…r{회차-1}) 정답표에서 쓴 원본 장 {(편, 장)}."""
    used = set()
    for d in 출력.glob("r*/정답.json") if 출력.is_dir() else []:
        m = re.match(r"r(\d+)(?:_|$)", d.parent.name)
        if m and int(m[1]) < 회차:
            for t in json.loads(d.read_text(encoding="utf-8"))["tile"].values():
                if t["답"] == "원본":
                    used.add((t["편"], t["장"]))
    return used


def 후보(장들, 부품, 제외, 제외해시, 이미뽑힌해시, 높이=기본_높이):
    """같은 부품 + 영상·자료 캡처 아님 + 그 부품 비율(1080×높이, 기본 4:5) + 제외 장 아님 + 같은 그림 아님."""
    out = []
    for s in 장들:
        if 부품 is not None and s["부품"] != 부품:
            continue
        if not s["부품"] or "영상" in s["바탕"] or "캡처" in s["바탕"] or (s["편"], s["장"]) in 제외 \
                or (편_id(s["편"]), s["장"]) in 제외:
            continue
        im = Image.open(s["경로"])
        if abs(im.width / im.height - 1080 / 높이) > 0.01:
            continue
        h = 해시(im)
        if any(같은그림(h, x) for x in 제외해시 | 이미뽑힌해시):
            continue
        out.append((s, im.convert("RGB"), h))
    return out


# ─────────── 그림 ───────────
def 재압축(im, h=기본_높이):
    """1440×(h×4/3) → JPEG q78·4:2:0 → 1080×h (인스타 재압축 흉내, 교훈 16-1). h=1350이면 1440×1800."""
    buf = io.BytesIO()
    im.convert("RGB").resize((1440, round(h * 4 / 3)), Image.LANCZOS).save(buf, "JPEG", quality=78, subsampling=2)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB").resize((1080, h), Image.LANCZOS)


def 판_저장(items, 폴더, 회차, 씨앗, 재압축쓰나, 대조=None):
    """장마다 items[i]["h"](없으면 기본_높이)로 맞추고, 높이가 섞이면 칸은 가장 큰 높이로 — 작은 장은 위 맞춤 + 회색 채움."""
    (폴더 / "A").mkdir(parents=True, exist_ok=True)
    (폴더 / "B").mkdir(parents=True, exist_ok=True)
    n = len(items)
    cols, rows = min(n, 4), (n + 3) // 4
    h = max(it.get("h", 기본_높이) for it in items)
    칸 = round(h / 3)  # 360 너비 칸의 높이(1350이면 450)
    grid = Image.new("RGB", (360 * cols, 칸 * rows), "white")
    tile = {}
    for k, it in enumerate(items, 1):
        im = it["img"].convert("RGB").resize((1080, it.get("h", 기본_높이)))
        if im.height != h:
            c = Image.new("RGB", (1080, h), (128, 128, 128)); c.paste(im, (0, 0)); im = c
        im.resize((540, round(h / 2)), Image.LANCZOS).save(폴더 / "B" / f"tile_{k}.jpg", quality=92)
        t = im.resize((180, round(h / 6)), Image.BILINEAR).resize((360, 칸), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.5))
        grid.paste(t, ((k - 1) % 4 * 360, (k - 1) // 4 * 칸))
        tile[f"tile_{k}"] = {x: v for x, v in it.items() if x not in ("img", "h")}
    grid.save(폴더 / "A" / "grid.jpg", quality=92)
    (폴더 / "정답.json").write_text(json.dumps(
        {"회차": 회차, "씨앗": 씨앗, "재압축": 재압축쓰나, "대조": 대조, "tile": tile}, ensure_ascii=False, indent=1), encoding="utf-8")
    (폴더 / "판정_지시.md").write_text(
        지시문.format(종류="A 흐림 모아보기", n=n, 입력="`A/grid.jpg` 한 장(왼쪽 위부터 1번, 한 줄 4칸)을 봅니다.")
        + "\n---\n\n" + 지시문.format(종류="B 낱장", n=n, 입력="`B/tile_1.jpg` … `tile_%d.jpg` 를 한 장씩 봅니다." % n),
        encoding="utf-8")


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="블라인드 판정용 판(A 흐림 모아보기·B 낱장)과 정답표를 만든다. 정답.json 은 판정자에게 주지 않는다.")
    ap.add_argument("약사님폴더", help="02_대표슬라이드가 있는 약사님 폴더")
    ap.add_argument("부품폴더", help="부품 상위 폴더(<부품>/render.png·견본.json 이 든 폴더들의 상위, 예: 05_디자인시스템/부품)")
    ap.add_argument("--출력", required=True, help="판을 만들 폴더(회차마다 r<N>/ 하위 폴더)")
    ap.add_argument("--회차", type=int, default=1, help="회차 N: 부품을 이름순으로 4개씩 끊어 N번째 묶음을 씀(기본 1)")
    ap.add_argument("--재압축", action="store_true", help="만든 장을 1440×1800 → JPEG q78·4:2:0 → 1080 으로 재압축(교훈 16-1)")
    ap.add_argument("--대조", metavar="부품", help="그 부품의 만든 장 자리에 견본 원본 장을 넣은 판도 r<N>_대조_<부품>/ 에 만듦(교훈 14)")
    ap.add_argument("--씨앗", type=int, default=1, help="무작위 씨앗(기본 1)")
    a = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(a.약사님폴더)
    슬라이드 = 공통.파일_찾기(정보["02"], "슬라이드") if 정보["02"] else None
    if 슬라이드 is None:
        공통.실패("02_대표슬라이드/슬라이드 폴더가 없습니다")
    상위 = 공통.작업폴더_경로(a.부품폴더)
    부품들 = sorted((d for d in 상위.iterdir() if (d / "render.png").exists()), key=lambda d: d.name) if 상위.is_dir() else []
    쓸 = 부품들[(a.회차 - 1) * 회차당_부품: a.회차 * 회차당_부품]
    if not 쓸:
        공통.실패(f"회차 {a.회차}에 쓸 부품이 없습니다(render.png 있는 부품 {len(부품들)}개, 회차당 {회차당_부품}개): {상위}")
    출력 = 공통.작업폴더_경로(a.출력)

    장들 = 장_모으기(슬라이드)
    제외 = 이전_회차_사용(출력, a.회차)
    근거 = {p.name: 근거_장(p) for p in 부품들}
    for s in 근거.values():
        제외 |= s
    by = {(편_id(s["편"]), s["장"]): s for s in 장들} | {(s["편"], s["장"]): s for s in 장들}
    제외해시 = {해시(Image.open(by[k]["경로"])) for k in 제외 if k in by}
    rng = random.Random(f"{a.씨앗}-{a.회차}")
    뽑힌 = set()
    items = []
    for p in 쓸:
        높이 = 견본_높이(p)  # 부품마다 그 견본.json `크기`
        made = Image.open(p / "render.png").convert("RGB").resize((1080, 높이))
        items.append({"답": "만든", "무엇": p.name, "부품": p.name, "h": 높이, "img": 재압축(made, 높이) if a.재압축 else made})
        c = 후보(장들, p.name, 제외, 제외해시, 뽑힌, 높이) or 후보(장들, None, 제외, 제외해시, 뽑힌, 높이)  # 없으면 다른 부품 장
        if not c:
            공통.실패(f"원본 장 후보가 없습니다: {p.name} (같은 부품 판정 장·4:5·제외 조건 확인)")
        s, im, h = rng.choice(c)
        뽑힌.add(h)
        items.append({"답": "원본", "무엇": f"{s['편']} {s['장']}장", "편": s["편"], "장": s["장"], "h": 높이, "img": im})
    rng.shuffle(items)

    판_저장(items, 출력 / f"r{a.회차}", a.회차, a.씨앗, a.재압축)
    print(f"[완료] r{a.회차}: 만든 {len(쓸)} + 원본 {len(쓸)} → {출력 / f'r{a.회차}'}")
    if a.대조:
        idx = next((i for i, it in enumerate(items) if it["답"] == "만든" and it["부품"] == a.대조), None)
        if idx is None:
            공통.실패(f"--대조 부품이 이 회차에 없습니다: {a.대조} (이 회차 부품: {', '.join(p.name for p in 쓸)})")
        if not 근거.get(a.대조):
            공통.실패(f"{a.대조}/견본.json 에서 근거 장(`<게시물 id> 1장` 꼴)을 읽지 못했습니다")
        편id, n = sorted(근거[a.대조])[0]
        s = by.get((편id, n))
        if s is None:
            공통.실패(f"근거 장 원본이 없습니다: {편id} {n}장")
        items[idx] = {"답": "원본", "무엇": f"견본 원본 {s['편']} {s['장']}장", "편": s["편"], "장": s["장"],
                      "대조": a.대조, "h": items[idx]["h"], "img": Image.open(s["경로"]).convert("RGB")}
        판_저장(items, 출력 / f"r{a.회차}_대조_{a.대조}", a.회차, a.씨앗, a.재압축, a.대조)
        print(f"[완료] 대조: {a.대조}의 만든 장 → 견본 원본 {s['편']} {s['장']}장")


if __name__ == "__main__":
    main()
