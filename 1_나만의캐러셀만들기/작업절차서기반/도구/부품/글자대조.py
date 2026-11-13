"""견본·장 안 글을 글.md와 줄마다 대조해 오타 잡기.

사용: 글자대조.py <견본.json 또는 장.html> <글.md>
- 견본.json: 요소 중 종류 '글'의 `글`(여러 줄이면 줄마다). 장.html: 태그·script·style·주석을 뺀 텍스트 줄.
- 줄마다 글.md 전체에서 찾는다(공백·줄바꿈 차이는 무시, 글자 하나 차이는 잡는다).
  없으면 그 줄과 글.md에서 가장 비슷한 줄(difflib)을 나란히 보여 준다.
- 끝 코드 0 = 모두 있음, 1 = 없는 줄 있음(또는 파일 오류).
출처: 새로 작성(2026-11-11).
"""
import sys, re, json, html as H, difflib, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 공통 import 실패, 한글ArgumentParser  # noqa: E402


def 정규(s):
    """NFC로 맞추고 모든 공백 제거"""
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', s))


def 줄_뽑기(path):
    t = Path(path).read_text(encoding='utf-8')
    if Path(path).suffix.lower() == '.json':
        try: d = json.loads(t)
        except json.JSONDecodeError as e: 실패("견본.json을 읽지 못했습니다(JSON 오류): %s" % e)
        return [l for e in d.get('요소', []) if e.get('종류') == '글' for l in str(e.get('글', '')).split('\n') if l.strip()]
    t = re.sub(r'(?is)<(script|style)\b.*?</\1>|<!--.*?-->', '', t)
    t = re.sub(r'(?i)<br\s*/?>|</(div|p|li|h\d|tr)>', '\n', t)
    return [l.strip() for l in H.unescape(re.sub(r'<[^>]+>', '', t)).split('\n') if l.strip()]


def 대조(줄들, 글md):
    """없는 줄마다 (줄, 가장 비슷한 글.md 줄, 비율) 목록"""
    md줄 = [l.strip() for l in 글md.split('\n') if l.strip()]
    전체 = 정규(글md)
    후보 = [(l, 정규(re.sub(r'^[-*#\s]*[^:：\s]{1,12}[:：]\s*', '', l))) for l in md줄]  # '- 제목:' 머리 뗀 꼴
    없음 = []
    for l in 줄들:
        n = 정규(l)
        if not n or n in 전체: continue
        best = max(후보, key=lambda c: difflib.SequenceMatcher(None, n, c[1]).ratio(), default=('', ''))
        없음.append((l, best[0], difflib.SequenceMatcher(None, n, best[1]).ratio(), best[1]))
    return 없음


def main(argv=None):
    p = 한글ArgumentParser(description=__doc__, formatter_class=__import__('argparse').RawDescriptionHelpFormatter)
    p.add_argument('대상', help='견본.json 또는 장.html'); p.add_argument('글md', help='글.md 경로')
    o = p.parse_args(argv)
    for f in (o.대상, o.글md):
        if not Path(f).is_file(): 실패("파일이 없습니다: %s" % f)
    줄들 = 줄_뽑기(o.대상)
    if not 줄들: 실패("대조할 글 줄이 없습니다: %s" % o.대상)
    없음 = 대조(줄들, Path(o.글md).read_text(encoding='utf-8'))
    for l, md, r, 뗀 in 없음:
        print('[없음] %s' % l)
        print('  글.md 가까운 줄(%.2f): %s' % (r, md))
        a, b = 정규(l), 뗀
        diffs = ['%s→%s' % (a[i1:i2] or '(없음)', b[j1:j2] or '(없음)') for t, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes() if t != 'equal']
        if r >= 0.5 and len(diffs) <= 4: print('  차이(견본→글.md): %s' % ', '.join(diffs))
    print('대조 %d줄 중 없는 줄 %d' % (len(줄들), len(없음)))
    sys.exit(1 if 없음 else 0)


if __name__ == '__main__':
    main()
