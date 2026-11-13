"""부품 견본 preview의 `__BLOB__<파일>__`을 사진아이디.json의 주소(`/_blob/<id>` 등)로 바꾼 게시용 사본을 만든다.

사용: python3 -I 6_도구/게시준비.py <디자인시스템화면 폴더> <네임스페이스> 부품1 부품2 ...
  예) python3 -I 6_도구/게시준비.py 7_결과/디자인시스템화면 YaksaName NumberList PhotoCover ...
- <디자인시스템화면 폴더> 안에 `사진아이디.json`과 `project/components/<부품>/{preview.html,README.md}`가 있어야 한다.
- `사진아이디.json` = {"파일이름.jpg": "/_blob/아이디", ...} — 그림을 아티팩트 자산으로 올린 뒤 받은 주소를 적는다.
- 부품 이름을 적은 순서가 화면 카드 순서가 된다.
- 결과: <폴더>/게시용/project/components/<부품>/{preview.html,README.md} + bundle.js.
  예전 `게시용/`이 있으면 지우지 않고 `게시용_이전_<날짜시각>/`으로 이름을 바꿔 둔다.
- 아이디가 빈 그림이 있으면 멈추고 그 그림 이름을 알려 준다(먼저 올리고 아이디를 채운다).
"""
import datetime
import json
import re
import sys
from pathlib import Path

if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(2)
폴더 = Path(sys.argv[1])
이름공간 = sys.argv[2]
부품들 = sys.argv[3:]
if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", 이름공간):
    sys.exit("네임스페이스는 영문·숫자만(첫 글자 영문) — 예: YaksaName")
아이디파일 = 폴더 / "사진아이디.json"
if not 아이디파일.exists():
    sys.exit(f"사진아이디.json이 없습니다: {아이디파일}")
아이디 = json.loads(아이디파일.read_text(encoding="utf-8"))
없는부품 = [b for b in 부품들 if not (폴더 / "project/components" / b / "preview.html").exists()]
if 없는부품:
    sys.exit("preview.html이 없는 부품: " + ", ".join(없는부품))

게시 = 폴더 / "게시용"
if 게시.exists():
    옛 = 폴더 / f"게시용_이전_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    게시.rename(옛)
    print("예전 게시용은 이름만 바꿔 둠:", 옛.name)
없음 = set()
for 부품 in 부품들:
    (게시 / "project/components" / 부품).mkdir(parents=True)
    for 파일 in ("preview.html", "README.md"):
        원본 = 폴더 / "project/components" / 부품 / 파일
        if not 원본.exists():
            continue
        글 = 원본.read_text(encoding="utf-8")

        def 바꾸기(m):
            주소 = 아이디.get(m.group(1), "")
            if not 주소:
                없음.add(m.group(1))
            return 주소 or m.group(0)

        (게시 / "project/components" / 부품 / 파일).write_text(re.sub(r"__BLOB__(.+?)__", 바꾸기, 글), encoding="utf-8")
if 없음:
    sys.exit("아이디 없는 그림(먼저 올리고 사진아이디.json을 채우세요): " + ", ".join(sorted(없음)))
머리 = json.dumps({"format": 4, "namespace": 이름공간, "components": [{"name": b} for b in 부품들]}, ensure_ascii=False)
(게시 / "project/components/bundle.js").write_text(
    f"/* @ds-bundle: {머리} */\n// 부품 견본은 preview.html의 HTML로 그린다(부품 코드 없음).\nwindow.{이름공간} = {{}};\n",
    encoding="utf-8")
print("게시용 준비 끝:", 게시)
