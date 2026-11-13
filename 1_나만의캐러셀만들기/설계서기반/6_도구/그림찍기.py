"""부품 견본 preview.html의 장(.slide)만 떼어 크롬으로 1080×1350 PNG를 찍는다(비교·블라인드용).

사용: python3 -I 6_도구/그림찍기.py <디자인시스템화면 폴더> <출력 폴더> [부품 ...] [--글꼴 폴더 ...]
  예) python3 -I 6_도구/그림찍기.py 7_결과/디자인시스템화면 7_결과/기록/그림 NumberList PhotoCover
- <디자인시스템화면 폴더> 안: project/components/<부품>/preview.html, 그림은 올릴사진/<파일>
  (preview 안 `__BLOB__<파일>__`을 올릴사진/<파일>로 바꿔 찍는다).
- 부품을 안 적으면 장(.slide)이 있는 부품을 모두 찍는다.
- 글꼴: ① project/tokens.json의 type.fonts ② 글꼴표.json(기본: 이 도구 옆 ../5_글꼴/글꼴표.json)에 적힌 파일을
  project/fonts/ → --글꼴 폴더들 → ../5_글꼴/ 순서로 찾아 붙인다. 파일이 없는 글꼴은 이름을 알려 준다
  (그 글꼴 자리는 기본 고딕으로 찍혀 원본과 달라 보인다).
- 창을 1080×1500으로 찍고 위 1350만 자른다(1350으로 찍으면 아래 흰 띠가 생길 때가 있음).
- 크롬: 맥 기본 위치(/Applications/Google Chrome.app). 다른 곳이면 환경변수 CHROME에 경로를 넣는다.
- 결과: <출력>/<부품>.png (1080×1350) + <출력>/work/<부품>.html(찍은 장 html).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow가 없습니다. `python3 -m pip install --user Pillow`로 설치한 뒤 다시 돌려 주세요.")

여기 = Path(__file__).resolve().parent
기본글꼴 = 여기.parent / "5_글꼴"


def 크롬_찾기() -> str:
    후보 = [os.environ.get("CHROME", ""),
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
          "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in 후보:
        if c and Path(c).exists():
            return c
    sys.exit("크롬을 못 찾았습니다. 구글 크롬을 설치하거나(https://www.google.com/chrome/), "
             "환경변수 CHROME에 크롬 실행 파일 경로를 넣어 주세요.")


def 파일주소(p: Path) -> str:
    return "file://" + quote(str(p.resolve()))


def 인자_나누기(argv: list[str]):
    자리, 글꼴폴더 = [], []
    i = 0
    while i < len(argv):
        if argv[i] == "--글꼴":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                글꼴폴더.append(Path(argv[i])); i += 1
            continue
        자리.append(argv[i]); i += 1
    return 자리, 글꼴폴더


def 글꼴_모으기(project: Path, 글꼴폴더: list[Path]) -> tuple[str, list[str]]:
    항목 = []  # (family, file 이름 또는 상대 경로, weight)
    tok = project / "tokens.json"
    if tok.exists():
        try:
            for f in json.loads(tok.read_text(encoding="utf-8")).get("type", {}).get("fonts", []):
                항목.append((f["family"], f["file"], str(f.get("weight", "400"))))
        except (json.JSONDecodeError, KeyError, TypeError):
            print("주의: project/tokens.json을 읽지 못해 글꼴표.json만 씀")
    표후보 = [d / "글꼴표.json" for d in 글꼴폴더] + [기본글꼴 / "글꼴표.json"]
    for 표 in 표후보:
        if 표.exists():
            for f in json.loads(표.read_text(encoding="utf-8")).get("fonts", []):
                항목.append((f["family"], f["file"], str(f.get("weight", "400"))))
            break
    찾을곳 = [project, project / "fonts"] + 글꼴폴더 + [기본글꼴]
    본 = set(); 면 = []; 없음 = []
    for fam, 파일, 굵기 in 항목:
        if (fam, 굵기) in 본:
            continue
        경로 = next((d / 파일 for d in 찾을곳 if (d / 파일).exists()), None)
        if 경로 is None:
            경로 = next((d / Path(파일).name for d in 찾을곳 if (d / Path(파일).name).exists()), None)
        if 경로 is None:
            없음.append(f"{fam}({Path(파일).name})")
            continue
        본.add((fam, 굵기))
        면.append(f"@font-face{{font-family:'{fam}';src:url('{파일주소(경로)}');font-weight:{굵기}}}")
    return "".join(면), sorted(set(없음))


def 장_떼기(h: str) -> str | None:
    m = re.search(r'<div class="slide"', h)
    if not m:
        return None
    i = m.start(); k = i; 깊이 = 0
    for t in re.finditer(r"<div\b|</div>", h[i:]):
        깊이 += 1 if t.group(0).startswith("<div") else -1
        if 깊이 == 0:
            k = i + t.end(); break
    return h[i:k]


def main(argv: list[str]) -> int:
    자리, 글꼴폴더 = 인자_나누기(argv)
    if len(자리) < 2:
        print(__doc__); return 2
    화면 = Path(자리[0]); 출력 = Path(자리[1]); 부품들 = 자리[2:]
    comp = 화면 / "project" / "components"
    if not comp.is_dir():
        sys.exit(f"부품 폴더가 없습니다: {comp}")
    if not 부품들:
        부품들 = sorted(p.parent.name for p in comp.glob("*/preview.html")
                     if 'class="slide"' in p.read_text(encoding="utf-8"))
    크롬 = 크롬_찾기()
    면, 없음 = 글꼴_모으기(화면 / "project", 글꼴폴더)
    if 없음:
        print("글꼴 파일 없음(기본 고딕으로 찍힘):", ", ".join(없음))
    (출력 / "work").mkdir(parents=True, exist_ok=True)
    프로필 = 출력 / "work" / "chrome-profile"
    사진 = 화면 / "올릴사진"
    실패수 = 0
    for 이름 in 부품들:
        pv = comp / 이름 / "preview.html"
        if not pv.exists():
            print(이름, "— preview.html 없음"); 실패수 += 1; continue
        h = pv.read_text(encoding="utf-8")
        장 = 장_떼기(h)
        if 장 is None:
            print(이름, '— <div class="slide" ...> 장이 없음'); 실패수 += 1; continue
        빠진그림 = sorted({m for m in re.findall(r"__BLOB__(.+?)__", 장) if not (사진 / m).exists()})
        if 빠진그림:
            print(이름, "— 올릴사진에 없는 그림:", ", ".join(빠진그림))
        장 = re.sub(r"__BLOB__(.+?)__", lambda m: 파일주소(사진 / m.group(1)), 장)
        css = "".join(re.findall(r"<style>(.*?)</style>", h, re.S))
        쪽 = ("<!doctype html><html><head><meta charset='utf-8'><style>" + 면 + css +
             "body{margin:0;overflow:hidden;background:#000}"
             ".slide{transform:none!important;position:relative!important;left:0!important;top:0!important}"
             "</style></head><body>" + 장 + "</body></html>")
        hp = 출력 / "work" / f"{이름}.html"; hp.write_text(쪽, encoding="utf-8")
        png = 출력 / f"{이름}.png"
        시작 = png.stat().st_mtime if png.exists() else 0
        r =subprocess.run([크롬, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                            f"--user-data-dir={프로필}", "--virtual-time-budget=5000",
                            f"--screenshot={png}", "--window-size=1080,1500", 파일주소(hp)],
                           capture_output=True, text=True)
        if not png.exists() or png.stat().st_mtime == 시작:
            print(이름, "— 찍기 실패:", (r.stderr or "")[-300:]); 실패수 += 1; continue
        Image.open(png).convert("RGB").crop((0, 0, 1080, 1350)).save(png)
        print(이름, "ok →", png)
    return 1 if 실패수 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
