"""AI 그림 티 검사 묶음 만들기 (작업 설계서 2.6판 2단계 7 ①).

한 편에 쓴 `_AI생성` 그림과 같은 계정 원본의 실사·원본 그림 조각을 섞어,
번호만 붙은 낱개 그림 판(격자 1장 + 낱장)과 정답 파일, 판정자 질문 문장을 만든다.

사용:
  python3 -I AI그림검사묶음.py --편 <편 폴더> --출력 <출력 폴더> [--원본 <조각 파일 ...>] [--씨앗 7]

- AI 그림: 편 폴더 img/ 아래 이름에 `_AI생성`이 들어간 그림을 모두 쓴다(그 편 index.html이 실제로 쓰는 것만).
- 원본 조각: --원본으로 준 파일. 안 주면 편 폴더 img/ 아래 `_AI생성`이 아닌 그림 중
  사진 바탕(가로·세로 모두 900px 넘는 것)과 글꼴·종이 같은 바탕을 뺀 조각을 쓴다.
  AI 그림 수와 비슷한 수(최소 3개)가 되도록 고른다.
- 투명 배경 그림은 회색(#E9E9E9) 위에 얹어 모두 같은 바탕으로 보이게 한다.
- 결과: 출력/grid.jpg(4열 격자, 칸 번호), 출력/tile_N.jpg, 출력/key.json(번호 → 파일·AI 여부), 출력/질문.txt
"""
import argparse, json, random, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument("--편", required=True)
p.add_argument("--출력", required=True)
p.add_argument("--원본", nargs="*", default=[])
p.add_argument("--씨앗", type=int, default=7)
a = p.parse_args()

편 = Path(a.편)
html = (편 / "index.html").read_text(encoding="utf-8") if (편 / "index.html").exists() else ""
쓰는것 = set(re.findall(r"img/([^\"')\s>]+)", html))
그림들 = [q for q in sorted((편 / "img").glob("*")) if q.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
if 쓰는것:
    그림들 = [q for q in 그림들 if q.name in 쓰는것]

ai = [q for q in 그림들 if "_AI생성" in q.name]
if a.원본:
    원본 = [Path(x) for x in a.원본]
else:
    후보 = []
    for q in 그림들:
        if "_AI생성" in q.name or re.search(r"paper|bg|종이|바탕", q.name):
            continue
        w, h = Image.open(q).size
        if w > 900 and h > 900:
            continue
        후보.append(q)
    random.Random(a.씨앗).shuffle(후보)
    원본 = 후보[: max(3, len(ai))]

if not ai:
    raise SystemExit("이 편에는 _AI생성 그림이 없습니다 — 그림 검사 해당 없음.")

칸 = 360
def 판(q):
    im = Image.open(q).convert("RGBA")
    im.thumbnail((칸 - 40, 칸 - 40), Image.LANCZOS)
    bg = Image.new("RGB", (칸, 칸), (233, 233, 233))
    bg.paste(im, ((칸 - im.width) // 2, (칸 - im.height) // 2), im)
    return bg

목록 = [(q, True) for q in ai] + [(q, False) for q in 원본]
random.Random(a.씨앗).shuffle(목록)
출력 = Path(a.출력); 출력.mkdir(parents=True, exist_ok=True)
열 = 4; 행 = (len(목록) + 열 - 1) // 열
grid = Image.new("RGB", (열 * 칸, 행 * (칸 + 30)), "white")
d = ImageDraw.Draw(grid)
try:
    f = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 22)
except Exception:
    f = ImageFont.load_default()
key = {}
for i, (q, isai) in enumerate(목록, 1):
    t = 판(q); t.save(출력 / f"tile_{i}.jpg", quality=90)
    x, y = ((i - 1) % 열) * 칸, ((i - 1) // 열) * (칸 + 30)
    d.text((x + 8, y + 4), str(i), fill="black", font=f)
    grid.paste(t, (x, y + 30))
    key[i] = {"파일": q.name, "AI": isai}
grid.save(출력 / "grid.jpg", quality=88)
(출력 / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
(출력 / "질문.txt").write_text(
    f"인스타그램 약사 계정 게시물에 쓰인 그림 조각 {len(목록)}개가 번호와 함께 한 그림(grid.jpg)에 있다. "
    "일부는 실제 사진이나 사람이 만든 그림이고, 일부는 AI가 생성한 그림이다. 몇 개가 AI인지는 알려 주지 않는다. "
    "이 그림만 보고 다른 파일은 열지 마라. 번호마다: 실제/AI 생성, 확신(낮음/중간/높음), 이유 한 줄. 표로 답하라.",
    encoding="utf-8")
print(f"묶음 완료: AI {len(ai)}개 + 원본 {len(원본)}개 → {출력}")
