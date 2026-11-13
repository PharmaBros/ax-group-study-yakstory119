"""편블라인드 — 한 편에서 만든 사진 바탕 장과, 같은 부품의 대표 슬라이드 원본 장을 섞은 낱장 블라인드 판을 만든다. PIL만 쓴다.

쓰기: python3 도구/편블라인드.py <약사님폴더> <편 폴더> --출력 <폴더> [--씨앗 N] [--장 2,3,4,6] [--제외 <이전 판 폴더> …]
- 편 폴더 s/<nn>_<부품>/render.png 중 사진 바탕 부품 장에서 최대 4장(장 번호순, --장 으로 지정 가능)
- 같은 부품의 원본 장을 같은 수만큼. 뺄 것: 그 편이 쓴 사진(구성.json "사진" = <편>/<장>) · 만든 장과 같은 그림 · --제외 폴더 정답.json 의 원본
- 모두 1080×H(H = 만든 장 render.png 높이)로 맞추고(세로가 길면 위에서부터 자름) 같은 품질로 재압축해 A.jpg … 로 섞어 저장
- 정답.json(판정자에게 주지 않음)·판정_지시문.md 도 만든다. 원본이 모자라면 있는 만큼 쓰고 알린다.
"""
from __future__ import annotations

import json
import random
import re
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "부품"))
import 공통  # noqa: E402
import 블라인드  # noqa: E402
from lib import 기본_높이  # noqa: E402
from PIL import Image  # noqa: E402

최대_장수 = 4

지시문 = """# 블라인드 판정 지시

{글자}, 총 {n}장의 그림을 봅니다. 이 중 **실제 인스타그램 게시물에서 가져온 장**과 **디자인 도구로 만든 장**이 섞여 있습니다.

- 폴더에서 {글자} 그림 파일만 엽니다. `정답.json` 은 열지 않습니다.
- 모든 장은 같은 높이로 맞췄습니다(원본 비율이 다르면 덮도록 줄인 뒤 위쪽 기준으로 잘림).
- 글의 주제·내용이 아니라 모양(질감·글자 모양과 번짐·사진 처리·여백)만 보고 판단합니다.
- 장마다 `실제` 또는 `만든 것` 중 하나를 고르고, 확신(높음·보통·낮음)과 단서를 한 줄로 적습니다.
- 확신이 없어도 반드시 하나를 고릅니다.
- 결과는 `판정.md` 에 `<글자>: 실제|만든 것 — 확신 — 단서` 줄로 적습니다.
"""


def 장_읽기(편폴더: Path) -> list[tuple[int, str, Path]]:
    """s/<nn>_<부품>/render.png → [(장 번호, 부품, 경로)] 장 번호순."""
    out = []
    for p in (편폴더 / "s").glob("*/render.png"):
        m = re.match(r"(\d+)_(.+)$", 공통.nfc(p.parent.name))
        if m:
            out.append((int(m[1]), m[2], p))
    return sorted(out)


def 사진바탕_부품(장들: list[dict]) -> set[str]:
    # TODO(advisor): "사진 바탕 부품"의 기준이 스펙에 없음 — 대표 슬라이드 사진메모.json 에서 바탕이 "사진"을 포함하는 장의 부품으로 정함
    return {s["부품"] for s in 장들 if s["부품"] and "사진" in s["바탕"]}


def 제외_원본(폴더들: list[str]) -> set[tuple[str, int]]:
    """이전 판 정답.json 에서 쓴 원본 {(편, 장)}. `{"A": {"정답": "실제", "출처": "<편>/<장>.jpg"}}` 꼴."""
    out = set()
    for f in 폴더들:
        경로 = 공통.작업폴더_경로(f) / "정답.json"
        if not 경로.is_file():
            공통.실패(f"--제외 폴더에 정답.json 이 없습니다: {f}")
        for e in json.loads(경로.read_text(encoding="utf-8")).values():
            m = re.match(r"(.+)/(\d+)(?:\.\w+)?$", 공통.nfc(e.get("출처", ""))) if e.get("정답") == "실제" else None
            if m:
                out.add((m[1], int(m[2])))
    return out


def 맞추기(im: Image.Image, h: int = 기본_높이) -> Image.Image:
    """1080×h 로: 덮도록 줄이고 위에서부터(가로는 가운데) 자른다."""
    k = max(1080 / im.width, h / im.height)
    im = im.convert("RGB").resize((max(1080, round(im.width * k)), max(h, round(im.height * k))), Image.LANCZOS)
    x0 = (im.width - 1080) // 2
    return im.crop((x0, 0, x0 + 1080, h))


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="편의 만든 사진 장과 같은 부품 원본 장을 섞은 블라인드 판(A.jpg…)과 정답.json 을 만든다.")
    ap.add_argument("약사님폴더", help="02_대표슬라이드가 있는 약사님 폴더")
    ap.add_argument("편폴더", help="s/<nn>_<부품>/render.png 와 구성.json 이 있는 편 폴더")
    ap.add_argument("--출력", required=True, help="판을 만들 폴더")
    ap.add_argument("--씨앗", type=int, default=1, help="무작위 씨앗(기본 1)")
    ap.add_argument("--장", help="쓸 장 번호(쉼표, 예: 2,3,4,6). 없으면 사진 바탕 부품 장 중 앞에서 4장")
    ap.add_argument("--제외", nargs="+", default=[], metavar="폴더", help="이전 판 폴더(정답.json 에 나온 원본은 뺌)")
    a = ap.parse_args(argv)

    정보 = 공통.약사님폴더_검사(a.약사님폴더)
    슬라이드 = 공통.파일_찾기(정보["02"], "슬라이드") if 정보["02"] else None
    if 슬라이드 is None:
        공통.실패("02_대표슬라이드/슬라이드 폴더가 없습니다")
    편폴더 = 공통.작업폴더_경로(a.편폴더)
    구성경로 = 편폴더 / "구성.json"
    구성 = json.loads(구성경로.read_text(encoding="utf-8")) if 구성경로.is_file() else {}
    쓴사진 = set()
    for s in 구성.get("사진", []):
        m = re.match(r"(.+)/(\d+)$", 공통.nfc(s))
        if m:
            쓴사진.add((m[1], int(m[2])))

    원본장들 = 블라인드.장_모으기(슬라이드)
    사진부품 = 사진바탕_부품(원본장들)
    전체 = 장_읽기(편폴더)
    if a.장:
        고름 = {int(n) for n in a.장.split(",")}
        만든장들 = [t for t in 전체 if t[0] in 고름]
    else:
        만든장들 = [t for t in 전체 if t[1] in 사진부품][:최대_장수]
    if not 만든장들:
        공통.실패(f"블라인드에 쓸 만든 장이 없습니다(사진 바탕 부품 장 못 찾음): {편폴더 / 's'}")

    rng = random.Random(a.씨앗)
    제외 = 쓴사진 | 제외_원본(a.제외)
    H = Image.open(만든장들[0][2]).height  # 만든 장 높이(한 편은 같은 크기)
    만든그림 = [(n, 부품, 맞추기(Image.open(p), H)) for n, 부품, p in 만든장들]
    제외해시 = {블라인드.해시(im) for _, _, im in 만든그림}
    items = [{"정답": "만든", "출처": f"{p.parent.name}/render.png", "img": im} for (n, 부품, im), (_, _, p) in zip(만든그림, 만든장들)]
    모자람 = 0
    for n, 부품, _ in 만든그림:
        후보 = [s for s in 원본장들 if s["부품"] == 부품 and (s["편"], s["장"]) not in 제외]
        rng.shuffle(후보)
        for s in 후보:
            im = 맞추기(Image.open(s["경로"]), H)
            h = 블라인드.해시(im)
            if any(블라인드.같은그림(h, x) for x in 제외해시):
                continue
            제외해시.add(h)
            제외.add((s["편"], s["장"]))
            items.append({"정답": "실제", "출처": f"{s['편']}/{s['장']}.jpg", "img": im})
            break
        else:
            모자람 += 1
            print(f"[알림] {n}장 {부품}: 쓸 수 있는 원본 장이 없습니다")
    rng.shuffle(items)

    출력 = 공통.작업폴더_경로(a.출력)
    출력.mkdir(parents=True, exist_ok=True)
    글자 = string.ascii_uppercase[:len(items)]
    정답 = {}
    for g, it in zip(글자, items):
        블라인드.재압축(it["img"], H).save(출력 / f"{g}.jpg", "JPEG", quality=95)
        정답[g] = {"정답": it["정답"], "출처": it["출처"]}
    (출력 / "정답.json").write_text(json.dumps(정답, ensure_ascii=False, indent=1), encoding="utf-8")
    (출력 / "판정_지시문.md").write_text(지시문.format(글자=f"{글자[0]}~{글자[-1]}", n=len(items)), encoding="utf-8")
    print(f"[완료] 만든 {len(만든그림)} + 실제 {len(만든그림) - 모자람} → {출력}")
    if 모자람:
        print(f"[알림] 원본이 모자라 실제 {모자람}장이 빠졌습니다(만든 {len(만든그림)}장 ≠ 실제 {len(만든그림) - 모자람}장)")


if __name__ == "__main__":
    main()
