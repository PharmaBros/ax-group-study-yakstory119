"""preview.html 장(.slide) 안의 px 숫자·색이 json 파일(들)에 있는 값인지 본다.
쓰기: python3 -I 값검사.py <preview.html> <json> [<json> ...]   끝 코드 1 = 없는 값 있음
출처: R/새방식_공용도구/값검사.py, 2026-11-09 판 (--help·없는 파일 처리만 더함)
ponytail: 숫자 문자열 대조만 함(어느 칸 값인지는 안 봄). 0·1·100% 같은 기본값은 넘김."""
import json, os, re, sys

def json_values(o, out):
    if isinstance(o, dict):
        for v in o.values(): json_values(v, out)
    elif isinstance(o, list):
        for v in o: json_values(v, out)
    elif isinstance(o, bool):
        pass
    elif isinstance(o, (int, float)):
        out.add(float(o))
    elif isinstance(o, str):
        for c in re.findall(r'#[0-9A-Fa-f]{6}\b', o): out.add(c.upper())
        for n in re.findall(r'-?\d+(?:\.\d+)?', o): out.add(float(n))

def main(a):
    if not a or a[0] in ('-h', '--help'):
        print(__doc__); return 0 if a else 2
    for p in a:
        if not os.path.isfile(p): print('[실패] 파일이 없습니다: ' + p); return 1
    html = open(a[0], encoding='utf-8').read()
    i = html.find('class="slide"')
    if i < 0: print('[실패] class="slide" 없음'); return 2
    body = html[i:]
    vals = set()
    for p in a[1:]: json_values(json.load(open(p, encoding='utf-8')), vals)
    miss = []
    for c in sorted(set(c.upper() for c in re.findall(r'#[0-9A-Fa-f]{6}\b', body))):
        if c not in vals: miss.append(c)
    for n in sorted(set(re.findall(r'(-?\d+(?:\.\d+)?)px', body)), key=float):
        f = float(n)
        if f in (0, 1, 1080, 1350) or f in vals or -f in vals: continue
        miss.append(n + 'px')
    print('없는 값 %d건' % len(miss) + (': ' + ', '.join(miss) if miss else ''))
    return 1 if miss else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
