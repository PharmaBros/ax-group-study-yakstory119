"""캐러셀아티팩트 — 편의 장 그림과 캡션을 한 페이지(아티팩트/캐러셀.html)로 묶는다. PIL만 쓴다.

쓰기: python3 도구/캐러셀아티팩트.py <편 폴더> [--안 <이름>] [--제목 <제목>] [--메모 "<줄>" …]
- s/*/render.png 를 장 번호순으로 아티팩트/s/<n>.jpg(q90)로 내보낸다. 가로 1080 이 아니거나 첫 장과 크기가 다르면 "한 편 안 크기가 다름" 실패(한 편은 모두 같은 크기, H = 첫 장 높이).
- brief.md 의 "## 캡션 완성본" 아래 첫 코드 블록을 캡션으로 읽는다(그대로).
- 끝에 올릴 파일 목록과, 이전에 있던 s/<n>.jpg 중 이번에 없어진 번호(아티팩트에서 지울 것)를 알린다.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402
from PIL import Image  # noqa: E402

# 틀: 처음 만든 편의 캐러셀.html 그대로(@@…@@ 자리만 채움)
틀 = """<title>@@제목태그@@</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* 장을 순서대로 놓은 격자 + 아래 캡션. 꾸밈 없이 장이 주인공. */
:root { --bg:#F6F4F1; --fg:#1E1B18; --muted:#6B645C; --line:#DDD7CF; --card:#FFFFFF; --accent:#F85028;
  --sans: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#191715; --fg:#EEEAE4; --muted:#A39B91; --line:#38332E; --card:#24211E; --accent:#FF7A55; color-scheme: dark } }
:root[data-theme="dark"] { --bg:#191715; --fg:#EEEAE4; --muted:#A39B91; --line:#38332E; --card:#24211E; --accent:#FF7A55; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--sans); font-size: 15px; line-height: 1.6;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 28px 56px; }
main { max-width: 1240px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px; }
h1 { font-size: 24px; margin: 0; text-wrap: balance; }
h2 { font-size: 16px; margin: 0; }
.meta { color: var(--muted); margin: 4px 0 0; max-width: 70ch; }
.note { border-left: 3px solid var(--accent); padding: 2px 0 2px 14px; max-width: 75ch; }
.note ul { margin: 6px 0 0; padding-left: 18px; }
.slides { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }
figure { margin: 0; display: flex; flex-direction: column; gap: 6px; }
figure img { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); }
figcaption { color: var(--muted); font-size: 13px; }
figcaption b { color: var(--fg); font-variant-numeric: tabular-nums; margin-right: 6px; }
.cap { display: flex; flex-direction: column; gap: 10px; max-width: 640px; }
.caphead { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
pre { margin: 0; white-space: pre-wrap; word-break: keep-all; font: inherit; background: var(--card); border: 1px solid var(--line); padding: 18px; }
button { font: inherit; font-size: 13px; padding: 6px 12px; border: 1px solid var(--line); background: var(--card); color: var(--fg); cursor: pointer; }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
<main>
<header>
<h1>@@제목@@</h1>
<p class="meta">@@메타@@</p>
</header>
@@메모@@<section class="slides" aria-label="장">
@@장@@
</section>
<section class="cap">
<div class="caphead"><h2>캡션</h2><button id="copy" type="button">캡션 복사</button></div>
<pre id="caption">@@캡션@@</pre>
</section>
</main>
<script>
document.getElementById('copy').addEventListener('click', function () {
  var b = this, t = document.getElementById('caption');
  navigator.clipboard.writeText(t.textContent).then(function () { b.textContent = '복사됨'; }, function () {
    var r = document.createRange(); r.selectNodeContents(t); var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = '선택됨 — 직접 복사하세요';
  });
});
</script>
"""


def 캡션_읽기(brief: Path) -> tuple[str, str]:
    """brief.md → (편 이름, 캡션). 편 이름은 첫 제목 줄, 캡션은 '## 캡션 완성본' 아래 첫 코드 블록."""
    줄들 = brief.read_text(encoding="utf-8").splitlines()
    제목 = next((l for l in 줄들 if l.startswith("# ")), "")
    편 = re.sub(r"^#\s*(?:brief\s*[—-]\s*)?", "", 제목).strip()
    i = next((k for k, l in enumerate(줄들) if l.startswith("## 캡션 완성본")), None)
    if i is None:
        공통.실패("brief.md 에 '## 캡션 완성본' 절이 없습니다")
    시작 = next((k for k in range(i + 1, len(줄들)) if 줄들[k].startswith("```")), None)
    끝 = next((k for k in range(시작 + 1, len(줄들)) if 줄들[k].startswith("```")), None) if 시작 is not None else None
    if 끝 is None:
        공통.실패("'## 캡션 완성본' 아래에 코드 블록(```)이 없습니다")
    return 편, "\n".join(줄들[시작 + 1:끝])


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="편의 장 그림(s/*/render.png)과 brief.md 캡션을 아티팩트/캐러셀.html 로 묶는다.")
    ap.add_argument("편폴더", help="s/<nn>_<부품>/render.png 와 brief.md 가 있는 편 폴더")
    # TODO(advisor): --안 의 쓰임이 스펙에 없음 — 위쪽 설명 줄에 이름만 적고, 다른 폴더·파일을 고르지는 않음
    ap.add_argument("--안", default="", help="몇 안인지 이름(예: 3안) — 위쪽 설명 줄에 적음")
    ap.add_argument("--제목", help="페이지 제목 <h1>(없으면 편 이름)")
    ap.add_argument("--메모", action="append", default=[], metavar="줄", help="'보기 전에' 목록 한 줄(여러 번 가능, 없으면 그 절을 뺌)")
    a = ap.parse_args(argv)

    편폴더 = 공통.작업폴더_경로(a.편폴더)
    brief = 편폴더 / "brief.md"
    if not brief.is_file():
        공통.실패(f"brief.md 가 없습니다: {brief}")
    편, 캡션 = 캡션_읽기(brief)
    장들 = []
    for p in (편폴더 / "s").glob("*/render.png"):
        m = re.match(r"(\d+)_(.+)$", 공통.nfc(p.parent.name))
        if m:
            장들.append((int(m[1]), m[2], p))
    장들.sort()
    if not 장들:
        공통.실패(f"장 그림이 없습니다: {편폴더 / 's'}/<nn>_<부품>/render.png")
    첫크기 = Image.open(장들[0][2]).size  # 첫 장 크기가 이 편의 크기
    H = 첫크기[1]
    그림들 = {}
    for n, 부품, p in 장들:
        im = Image.open(p)
        if im.width != 1080 or im.size != 첫크기:
            공통.실패(f"한 편 안 크기가 다름: {n}장({p.parent.name}) {im.width}×{im.height} — 가로 1080, 첫 장 {첫크기[0]}×{첫크기[1]} 와 같아야 합니다")
        그림들[n] = im.convert("RGB")

    아티팩트 = 편폴더 / "아티팩트"
    (아티팩트 / "s").mkdir(parents=True, exist_ok=True)
    이전 = {int(f.stem) for f in (아티팩트 / "s").glob("*.jpg") if f.stem.isdigit()}
    for n, im in 그림들.items():
        im.save(아티팩트 / "s" / f"{n}.jpg", "JPEG", quality=90)
    esc = lambda s: html.escape(s, quote=False)
    메모 = ('<section class="note">\n<h2>보기 전에</h2>\n<ul>\n' + "".join(f"<li>{esc(m)}</li>\n" for m in a.메모) + "</ul>\n</section>\n") if a.메모 else ""
    메타 = " · ".join([f"{len(장들)}장", f"1080×{H}"] + ([a.안] if a.안 else []) + [공통.오늘()])
    figure = "\n".join(
        f'<figure><img src="s/{n}.jpg" width="1080" height="{H}" alt="{n}장 {html.escape(부품)}" loading="lazy">'
        f'<figcaption><b>{n}</b> {esc(부품)}</figcaption></figure>' for n, 부품, _ in 장들)
    # ponytail: 틀의 @@ 자리 치환은 한 번에(캡션 안의 @@ 가 다시 바뀌지 않게)
    값 = {"제목태그": esc(편), "제목": esc(a.제목 or 편), "메타": esc(메타), "메모": 메모, "장": figure, "캡션": esc(캡션)}
    (아티팩트 / "캐러셀.html").write_text(re.sub(r"@@(\w+)@@", lambda m: 값[m[1]], 틀), encoding="utf-8")

    올릴 = ["캐러셀.html"] + [f"s/{n}.jpg" for n in 그림들]
    print(f"[완료] {아티팩트 / '캐러셀.html'} (장 {len(장들)}개)")
    print("올릴 파일: " + ", ".join(올릴))
    없어진 = sorted(이전 - set(그림들))
    if 없어진:
        print("[알림] 아티팩트에서 지울 파일: " + ", ".join(f"s/{n}.jpg" for n in 없어진))


if __name__ == "__main__":
    main()
