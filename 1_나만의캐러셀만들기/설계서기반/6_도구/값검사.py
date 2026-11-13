"""값검사 — 부품 견본 preview.html의 '장 안' 값이 최종 json에 있는지 대조한다.

쓰는 법: python3 -I 6_도구/값검사.py <project/components 폴더> <디자인시스템_최종.json>
  예) python3 -I 6_도구/값검사.py 7_결과/디자인시스템화면/project/components 2_커스텀설계서/디자인시스템_최종.json
- 장 안 = class="slide" 요소와 그 안쪽 모든 요소의 style 속성(장 밖 카드 설명·배율 .wrap/.scale·<style> 블록은 제외).
  → 장 안 값은 꼭 style="..." 속성에 적는다(<style> 블록에 적으면 검사가 못 본다).
- 모은 값: px 숫자(calc() 안 포함), hex 색(#RGB/#RRGGBB), font-family 이름.
- 대조: px 숫자 → json 안 모든 숫자 값(목록 안 포함), hex → json 문자열 어디든 나온 hex(대소문자 무시),
  글꼴 → json `글씨` 칸 문자열(글꼴·대체·보조)에 그 이름이 들어 있는지. CSS 이름 'Pretendard'=프리텐다드 등은 아래 표로 바꿔 찾는다.
  serif·sans-serif·cursive 같은 일반 이름은 글꼴이 아니라 건너뜀.
- 없는 값을 파일별로 출력하고, 0건이면 '없는 값 0건'. 0건이면 끝 코드 0, 있으면 1.
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

일반이름 = {"serif", "sans-serif", "cursive", "monospace", "fantasy", "system-ui"}
CSS이름 = {"nanummyeongjo": "나눔명조", "pretendard": "프리텐다드", "nanumsquareround": "나눔스퀘어라운드",
          "single day": "싱글데이", "do hyeon": "도현", "jalnan2": "잘난체2"}

class 장안스타일(HTMLParser):
    def __init__(self):
        super().__init__(); self.깊이 = 0; self.스타일 = []
    빈태그 = {"img", "br", "hr", "input", "meta", "link"}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.깊이 == 0 and "slide" in (a.get("class") or "").split():
            self.깊이 = 1
            if a.get("style"): self.스타일.append(a["style"])
            return
        if self.깊이 > 0:
            if a.get("style"): self.스타일.append(a["style"])
            if tag not in self.빈태그: self.깊이 += 1
    def handle_endtag(self, tag):
        if self.깊이 > 0 and tag not in self.빈태그: self.깊이 -= 1

def json_값(값, 숫자, 글):
    if isinstance(값, dict):
        for v in 값.values(): json_값(v, 숫자, 글)
    elif isinstance(값, list):
        for v in 값: json_값(v, 숫자, 글)
    elif isinstance(값, bool): pass
    elif isinstance(값, (int, float)): 숫자.add(float(값))
    elif isinstance(값, str): 글.append(값)

def main(폴더, 최종):
    d = json.loads(Path(최종).read_text(encoding="utf-8"))
    숫자, 글 = set(), []
    json_값(d, 숫자, 글)
    hex들 = {h.upper() for s in 글 for h in re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", s)}
    글씨글 = []
    json_값(d.get("글씨", {}), set(), 글씨글)
    글씨글 = " ".join(글씨글).lower()
    없음 = 0
    for f in sorted(Path(폴더).glob("*/preview.html")):
        p = 장안스타일(); p.feed(f.read_text(encoding="utf-8"))
        if not p.스타일: continue
        css = ";".join(p.스타일)
        빠짐 = []
        for n in re.findall(r"(-?\d+(?:\.\d+)?)px", css):
            if float(n) not in 숫자: 빠짐.append(f"{n}px")
        for h in re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", css):
            if h.upper() not in hex들: 빠짐.append(h)
        for 묶음 in re.findall(r"font-family:([^;]+)", css):
            for 이름 in 묶음.split(","):
                이름 = 이름.strip().strip("'\"")
                if not 이름 or 이름.lower() in 일반이름: continue
                찾을 = CSS이름.get(이름.lower(), 이름).lower()
                if 찾을 not in 글씨글: 빠짐.append(f"글꼴 {이름}")
        모은 = len(set(re.findall(r"(-?\d+(?:\.\d+)?)px", css))) , len(set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b", css)))
        print(f"{f.parent.name}: px {모은[0]}종 · hex {모은[1]}종 · 없는 값 {len(set(빠짐))}건" + (" — " + ", ".join(sorted(set(빠짐))) if 빠짐 else ""))
        없음 += len(set(빠짐))
    print(f"합계: 없는 값 {없음}건")
    return 1 if 없음 else 0

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
