"""부품 핵심 도구(lib·글자대조·견본만들기) 테스트. 실행: python3 -m unittest discover 도구/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

도구 = Path(__file__).resolve().parents[1]
부품 = 도구 / '부품'
sys.path.insert(0, str(부품))

import lib  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

크롬 = os.path.exists(lib.CHROME)


def 실행(script, *args):
    return subprocess.run([sys.executable, str(부품 / script), *map(str, args)], capture_output=True, text=True)


class 립(unittest.TestCase):
    def test_잉크_상자(self):
        im = Image.new('RGB', (200, 100), 'white')
        ImageDraw.Draw(im).rectangle((50, 20, 119, 39), fill=(255, 0, 0))
        r = lib.ink(im, (0, 0, 200, 100))
        self.assertEqual((r['왼쪽'], r['위'], r['오른쪽'], r['아래']), (50, 20, 120, 40))
        self.assertEqual(r['색'], '#FF0000')
        self.assertIsNone(lib.ink(Image.new('RGB', (20, 20), 'white'), (0, 0, 20, 20)))

    def test_가운뎃점은_강원교육모두에_없다(self):
        f, w = lib.fam('강원교육모두 Bold')
        self.assertEqual(lib.없는_글자(f, w, '가·나'), ['·'])
        self.assertEqual(lib.없는_글자(*lib.fam('프리텐다드 Bold'), '가·나'), [])
        self.assertIn('Pretendard', lib.dotspan(f, '가·나', w))
        self.assertNotIn('Pretendard', lib.dotspan(f, '가나', w))


class 글자대조(unittest.TestCase):
    def test_한글자_오타와_끝코드(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / '글.md').write_text('- 제목: 피부가 끊어져요\n  둘째 줄입니다\n', encoding='utf-8')
            ok = t / 'ok.json'; ok.write_text(json.dumps({'요소': [{'종류': '글', '글': '피부가  끊어져요'}, {'종류': '글', '글': '둘째\n줄입니다'}, {'종류': '상자'}]}), encoding='utf-8')
            bad = t / 'bad.json'; bad.write_text(json.dumps({'요소': [{'종류': '글', '글': '피부가 끓어져요'}]}), encoding='utf-8')
            self.assertEqual(실행('글자대조.py', ok, t / '글.md').returncode, 0)
            r = 실행('글자대조.py', bad, t / '글.md')
            self.assertEqual(r.returncode, 1)
            self.assertIn('끓→끊', r.stdout)
            h = t / '장.html'; h.write_text('<style>x{}</style><div>피부가 <b>끊어져요</b></div><!-- c --><p>없는줄</p>', encoding='utf-8')
            r = 실행('글자대조.py', h, t / '글.md')
            self.assertEqual(r.returncode, 1); self.assertIn('없는줄', r.stdout)


@unittest.skipUnless(크롬, '크롬 없음')
class 견본만들기(unittest.TestCase):
    def test_끝까지(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            im = Image.new('RGB', (1080, 1350), 'white'); d = ImageDraw.Draw(im)
            d.rectangle((60, 100, 700, 200), fill='black')
            d.text((90, 120), '안녕하세요 반가워요', font=ImageFont.truetype(str(lib.FONT / 'SingleDay-Regular.ttf'), 56), fill='white')
            d.text((90, 400), '두번째 글자', font=ImageFont.truetype(str(lib.FONT / 'SingleDay-Regular.ttf'), 56), fill='black')
            im.save(t / '장.jpg')
            (t / '요소.json').write_text(json.dumps({'json_자리': '부품.시험.견본', '화면': 'Test', '요소': [
                {'종류': '바탕', 'color': 'x', '색': '#FFFFFF'},
                {'종류': '상자', '이름': '라벨', '상자': [60, 100, 640, 100], '색': '#000000'},
                {'종류': '글', '이름': 'a', '글': '안녕하세요 반가워요', '글꼴': '싱글데이', '잴_상자': [70, 105, 690, 195], '역할': '라벨', 'thr': 300},
                {'종류': '글', '이름': 'b', '글': '두번째 글자', '글꼴': '프리텐다드 Bold', '잴_상자': [70, 380, 600, 480], '역할': '본문'}]}), encoding='utf-8')
            r = 실행('견본만들기.py', t / '요소.json', t / '장.jpg', t / '부품')
            self.assertEqual(r.returncode, 0, r.stderr)
            for f in ('견본.json', 'preview.html', 'render.png', 'cmp.jpg'):
                self.assertTrue((t / '부품' / f).is_file(), f)
            j = json.loads((t / '부품' / '견본.json').read_text(encoding='utf-8'))
            self.assertEqual(j['편_안_자리'], ''); self.assertIn('글꼴크기', j['요소'][2]); self.assertNotIn('잴_상자', j['요소'][2])
            self.assertIn('어긋남', r.stdout)


if __name__ == '__main__':
    unittest.main()
