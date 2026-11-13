"""장 크기(출력_크기_기본·견본.json 크기)를 따르는지. 실행: python3 -m unittest discover 도구/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

도구 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(도구))
sys.path.insert(0, str(도구 / '부품'))

import lib  # noqa: E402
import 블라인드  # noqa: E402
import 캐러셀아티팩트  # noqa: E402
import 비슷한장검사  # noqa: E402
import 편블라인드  # noqa: E402
from test_편도구 import 가짜편, 그림, 실행  # noqa: E402
from PIL import Image  # noqa: E402

크롬 = os.path.exists(lib.CHROME)


class 장_크기_테스트(unittest.TestCase):
    def test_환산과_기본값(self):
        self.assertEqual(lib.장_크기({'출력_크기_기본': [1080, 1440]}), (1080, 1440))
        self.assertEqual(lib.장_크기({'출력_크기_기본': [1440, 1920]}), (1080, 1440))
        self.assertEqual(lib.장_크기({'크기': [1080, 1440]}), (1080, 1440))
        for 없음 in (None, {}, {'출력_크기_기본': None}, {'출력_크기_기본': 'x'}, {'출력_크기_기본': [0, 5]}):
            self.assertEqual(lib.장_크기(없음), (1080, 1350))

    def test_json_경로와_없는_파일(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); (t / 'a.json').write_text(json.dumps({'출력_크기_기본': [1080, 1440]}), encoding='utf-8')
            (t / 'bad.json').write_text('{', encoding='utf-8')
            self.assertEqual(lib.장_크기(t / 'a.json'), (1080, 1440))
            self.assertEqual(lib.장_크기(str(t / 'a.json')), (1080, 1440))
            self.assertEqual(lib.장_크기(t / 'bad.json'), (1080, 1350))
            self.assertEqual(lib.장_크기(t / '없음.json'), (1080, 1350))
            self.assertEqual(lib.견본_높이(t), 1350)

    def test_계정_높이(self):
        with tempfile.TemporaryDirectory() as t:
            약사 = Path(t) / '시험약사'; (약사 / '04_설계서').mkdir(parents=True)
            self.assertEqual(lib.계정_높이(약사), 1350)
            (약사 / '04_설계서' / '디자인시스템.json').write_text(json.dumps({'출력_크기_기본': [1080, 1440]}), encoding='utf-8')
            self.assertEqual(lib.계정_높이(약사), 1440)

    def test_장_열기는_높이까지만(self):
        with tempfile.TemporaryDirectory() as t:
            Image.new('RGB', (1080, 2000)).save(Path(t) / 'a.png')
            self.assertEqual(lib.장_열기(Path(t) / 'a.png').size, (1080, 1350))
            self.assertEqual(lib.장_열기(Path(t) / 'a.png', 1440).size, (1080, 1440))

    def test_블라인드_도구_높이(self):
        self.assertEqual(블라인드.재압축(Image.new('RGB', (1080, 1440)), 1440).size, (1080, 1440))
        self.assertEqual(블라인드.재압축(Image.new('RGB', (1080, 1350))).size, (1080, 1350))
        self.assertEqual(편블라인드.맞추기(Image.new('RGB', (2000, 3000)), 1440).size, (1080, 1440))


class 캐러셀_크기_테스트(unittest.TestCase):
    def test_편_크기를_따른다_1440(self):
        with tempfile.TemporaryDirectory() as t:
            편 = 가짜편(Path(t), ['A', 'B'], 크기=(1080, 1440))
            코드, 출력 = 실행(캐러셀아티팩트.main, 편)
            self.assertEqual(코드, 0, 출력)
            self.assertEqual(Image.open(편 / '아티팩트' / 's' / '1.jpg').size, (1080, 1440))
            문서 = (편 / '아티팩트' / '캐러셀.html').read_text(encoding='utf-8')
            self.assertIn('height="1440"', 문서); self.assertIn('1080×1440', 문서); self.assertNotIn('1350', 문서)

    def test_1350_편은_계정_기본이_1440이어도_통과(self):
        with tempfile.TemporaryDirectory() as t:
            약사 = Path(t) / '약사'; (약사 / '04_설계서').mkdir(parents=True)
            (약사 / '04_설계서' / '디자인시스템.json').write_text(json.dumps({'출력_크기_기본': [1080, 1440]}), encoding='utf-8')
            편 = 가짜편(약사 / '06_캐러셀', ['A', 'B'])  # 편 폴더 두 단계 위 = 약사님 폴더
            코드, 출력 = 실행(캐러셀아티팩트.main, 편)
            self.assertEqual(코드, 0, 출력)
            self.assertIn('1080×1350', (편 / '아티팩트' / '캐러셀.html').read_text(encoding='utf-8'))

    def test_섞인_크기는_실패(self):
        with tempfile.TemporaryDirectory() as t:
            편 = 가짜편(Path(t), ['A', 'B'])
            그림(편 / 's' / '02_B' / 'render.png', 5, (1080, 1440))
            코드, 출력 = 실행(캐러셀아티팩트.main, 편)
            self.assertEqual(코드, 1)
            self.assertIn('한 편 안 크기가 다름: 2장', 출력)
            self.assertFalse((편 / '아티팩트' / '캐러셀.html').exists())


class 섞인_부품_크기_테스트(unittest.TestCase):
    def 부품들(self, 상위, 크기들):
        for 이름, 크기 in 크기들.items():
            (상위 / 이름).mkdir(parents=True)
            견 = {'요소': []}
            if 크기: 견['크기'] = [1080, 크기]
            (상위 / 이름 / '견본.json').write_text(json.dumps(견), encoding='utf-8')
            (상위 / 이름 / 'README.md').write_text('# %s\n\n## 모양 계열\n\n㉠ %s계열 — 같은 계열: %s.\n' % (이름, 이름, 이름), encoding='utf-8')

    @unittest.skipUnless(크롬, '크롬 없음')
    def test_장만들기_섞이면_시작_전_실패(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); 상위 = t / '약사' / '05_디자인시스템' / '부품'
            self.부품들(상위, {'A': None, 'B': 1440})
            (t / '장.json').write_text(json.dumps([{'장': 1, '부품': 'A'}, {'장': 2, '부품': 'B'}]), encoding='utf-8')
            r = subprocess.run([sys.executable, str(도구 / '장만들기.py'), str(t / '약사'), str(t / '편'), '--장', str(t / '장.json')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn('한 편 안 부품 크기가 다름: A 1350 / B 1440', r.stderr)
            self.assertFalse((t / '편' / 's').exists())

    def test_비슷한장검사_크기_섞임은_코드_1(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); 상위 = t / '부품'
            self.부품들(상위, {'A': None, 'B': 1440, 'C': 1440})
            for 이름, 부품 in (('섞임', ['A', 'B']), ('같음', ['B', 'C'])):
                (t / f'{이름}.json').write_text(json.dumps({'편': 이름, '날짜': '2026-11-13', '부품': 부품}), encoding='utf-8')
            코드, 출력 = 실행(비슷한장검사.main, str(상위), str(t / '섞임.json'))
            self.assertEqual(코드, 1); self.assertIn('한 편 안 부품 크기가 다름: A 1350 / B 1440', 출력)
            코드, 출력 = 실행(lambda a: 비슷한장검사.main(a), str(상위), str(t / '같음.json'))
            self.assertEqual(코드, 0, 출력)


@unittest.skipUnless(크롬, '크롬 없음')
class 견본_크기_테스트(unittest.TestCase):
    def test_1440_견본에서_장까지(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            Image.new('RGB', (1080, 1350), 'white').save(t / '장.jpg')
            (t / '요소.json').write_text(json.dumps({'json_자리': '부품.시험.견본', '화면': 'Test', '편_안_자리': '1장', '글_자리': {}, '크기': [1080, 1440], '요소': [
                {'종류': '바탕', '색': '#FFFFFF'},
                {'종류': '다각형', '점': [[0, 1400], [100, 1440], [0, 1440]], '색': '#FF0000'}]}), encoding='utf-8')
            p = t / '약사' / '05_디자인시스템' / '부품' / 'Test'
            r = subprocess.run([sys.executable, str(도구 / '부품' / '견본만들기.py'), str(t / '요소.json'), str(t / '장.jpg'), str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Image.open(p / 'render.png').size, (1080, 1440))
            self.assertEqual(Image.open(p / 'cmp.jpg').size, (2160 + 20, 1440))
            self.assertEqual(json.loads((p / '견본.json').read_text(encoding='utf-8'))['크기'], [1080, 1440])
            self.assertIn('viewBox="0 0 1080 1440"', (p / 'preview.html').read_text(encoding='utf-8'))
            self.assertEqual(Image.open(p / 'render.png').getpixel((2, 1438)), (255, 0, 0))  # 아래 끝까지 그려짐
            (t / '장.json').write_text(json.dumps([{'장': 1, '부품': 'Test'}]), encoding='utf-8')  # 약사님 폴더에 크기 없음 → 견본 크기
            r = subprocess.run([sys.executable, str(도구 / '장만들기.py'), str(t / '약사'), str(t / '편'), '--장', str(t / '장.json')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Image.open(t / '편' / 's' / '01_Test' / 'render.png').size, (1080, 1440))


if __name__ == '__main__':
    unittest.main()
