"""장만들기.py 테스트. 실행: python3 -m unittest discover 도구/tests (크롬 없으면 끝까지 시험은 건너뜀)"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

도구 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(도구)); sys.path.insert(0, str(도구 / '부품'))

import lib  # noqa: E402
import 장만들기  # noqa: E402
from PIL import Image  # noqa: E402

크롬 = os.path.exists(lib.CHROME)


def 글(이름, 문장, 위, 크기=60):  # 이미 잰 값이 다 있는 글 요소(견본만들기가 크롬 재기 없이 통과시킴)
    return {'종류': '글', '이름': 이름, '글': 문장, '글꼴': '프리텐다드 Bold', '글꼴크기': 크기, '위': 위, '왼쪽': 200, '오른쪽': 880,
            '글자높이': 50, '위_보정': -3, '색': '#111111', '맞춤': '가운데', '역할': '본문'}


class 줄간격_계산(unittest.TestCase):
    def test_견본_간격과_계산값(self):
        a, b = 글('a', 'x', 300), 글('b', 'y', 378)
        self.assertEqual(장만들기.줄간격([a, b], a), (78, False))
        self.assertEqual(장만들기.줄간격([a], a), (78, True))  # round(60*1.3)

    def test_글_자리_한도(self):
        견 = {'글_자리': {'제목': '한 줄 4~8자, 1~2줄'}}
        self.assertEqual(장만들기.자리_경고(견, '제목', ['가나다라마']), [])
        self.assertEqual(len(장만들기.자리_경고(견, '제목', ['가나다라마바사아자', 'b', 'c'])), 2)


틀 = '<div class="slide" style="width:1080px">'


class 요소_받기(unittest.TestCase):  # 크롬 없이 장_조각만 시험
    def test_가운데_맞춤은_글_자리_가운데(self):
        견 = {'요소': [글('제목', '옛', 300)]}
        h = 장만들기.장_조각(견, 틀, {'장': 1, '글': {'제목': '새'}}, [])[0]
        self.assertNotIn('left:0px;width:1080px', h); self.assertIn('left:calc((200px + 880px) / 2)', h); self.assertIn('translateX(-50%)', h)
        견['요소'][0]['기울기'] = 3  # 기울기가 있어도 translateX와 rotate가 한 transform에
        h = 장만들기.장_조각(견, 틀, {'장': 1, '글': {'제목': '새'}}, [])[0]
        self.assertIn('transform:translateX(-50%) rotate(3deg)', h)

    def test_요소를_주면_견본_요소_없이_그림(self):
        견 = {'요소': [글('제목', '견본글', 300)], '글_자리': {'제목': '한 줄 1~2자'}}
        요소 = [{'종류': '상자', '상자': [10, 20, 300, 100], '색': '#FF0000'}, 글('캡션', '캡션글', 400)]
        del 요소[1]['위_보정']  # 위_보정 없으면 0
        경고 = []
        h = 장만들기.장_조각(견, 틀, {'장': 1, '요소': 요소, '글': {'캡션': '바꾼 글자가 길다'}}, 경고)[0]
        self.assertIn('background:#FF0000', h); self.assertIn('바꾼 글자가 길다', h); self.assertNotIn('견본글', h)
        self.assertFalse([w for w in 경고 if '한도' in w])

    def test_글줄은_줄마다_세로_가운데(self):
        e = {'종류': '글줄', '이름': '흰 상자', '줄': ['가', '나'], '상자': [100, 500, 800, 200], '글꼴': '프리텐다드 Regular', '글꼴크기': 42, '색': '#000000', '맞춤': '가운데', '줄간격': 50, '안쪽': 24}
        r = 장만들기.글줄_펼치기([e], 1, [])
        self.assertEqual([x['이름'] for x in r], ['흰 상자 1줄', '흰 상자 2줄'])
        self.assertEqual([x['위'] for x in r], [554, 604])  # 500 + (200 - (50 + 42)) / 2
        self.assertEqual((r[0]['왼쪽'], r[0]['오른쪽'], r[0]['위_보정']), (124, 876, 0))
        경고 = []; 장만들기.글줄_펼치기([dict(e, 줄간격=None)], 1, 경고); self.assertIn('[계산값]', 경고[0])  # round(42*1.19)=50

    def test_요소_없는_장은_그대로(self):
        견 = {'요소': [글('제목', '옛', 300), {'종류': '상자', '상자': [0, 0, 5, 5], '색': '#123456'}]}
        h = 장만들기.장_조각(견, 틀, {'장': 1}, [])[0]
        self.assertIn('옛', h); self.assertIn('background:#123456', h)


@unittest.skipUnless(크롬, '크롬 없음')
class 끝까지(unittest.TestCase):
    def test_장_만들기(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); 부품 = t / '약사' / '05_디자인시스템' / '부품'; p = 부품 / 'Test'; p.mkdir(parents=True)
            Image.new('RGB', (40, 40), 'red').save(p / 'a.png'); Image.new('RGB', (40, 40), 'blue').save(t / 'b.png')
            Image.new('RGB', (1080, 1350), 'white').save(t / '장.jpg')
            (t / '요소.json').write_text(json.dumps({'json_자리': '부품.시험.견본', '화면': 'Test', '편_안_자리': '2장 이후', '글_자리': {'제목': '한 줄 4~10자, 1~2줄'}, '요소': [
                {'종류': '바탕', '색': '#FFFFFF'},
                {'종류': '그림', '이름': '사진', '상자': [100, 700, 400, 300], '파일': 'a.png'},
                글('제목', '옛 제목', 300), 글('부제', '옛 부제', 378)]}), encoding='utf-8')
            r = subprocess.run([sys.executable, str(도구 / '부품' / '견본만들기.py'), str(t / '요소.json'), str(t / '장.jpg'), str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            (t / '장.json').write_text(json.dumps([{'장': 1, '부품': 'Test', '글': {'제목': '새 줄 하나\n새 줄 둘'}, '그림': {'a.png': str(t / 'b.png')}, '숨김': ['부제']},
                                                {'장': 2, '부품': 'Test'}]), encoding='utf-8')
            r = subprocess.run([sys.executable, str(도구 / '장만들기.py'), str(t / '약사'), str(t / '편'), '--장', str(t / '장.json')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            d = t / '편' / 's' / '01_Test'; h = (d / 'slide.html').read_text(encoding='utf-8')
            self.assertIn('새 줄 하나', h); self.assertIn('새 줄 둘', h); self.assertIn('src="b.png"', h)
            self.assertNotIn('옛 ', h); self.assertNotIn('a.png', h); self.assertNotIn('<wrap', h)
            self.assertTrue((d / 'b.png').is_file())
            self.assertEqual(Image.open(d / 'render.png').size, (1080, 1350))
            self.assertEqual(Image.open(t / '편' / 's' / '모아보기.jpg').size, (720, 450))
            v = subprocess.run([sys.executable, '-I', str(도구 / '값검사.py'), str(d / 'slide.html'), str(p / '견본.json')], capture_output=True, text=True)
            self.assertEqual(v.returncode, 0, v.stdout)

    def test_없는_요소_이름은_실패(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); (t / 'x').mkdir()
            (t / 'x' / 'Test').mkdir(); (t / 'x' / 'Test' / '견본.json').write_text(json.dumps({'요소': [글('제목', 'a', 300)]}), encoding='utf-8')
            (t / 'x' / 'Test' / 'preview.html').write_text('<div class="slide" style="width:1080px">', encoding='utf-8')
            (t / '장.json').write_text(json.dumps([{'장': 1, '부품': 'Test', '글': {'없음': 'a'}}]), encoding='utf-8')
            r = subprocess.run([sys.executable, str(도구 / '장만들기.py'), str(t), str(t / '편'), '--장', str(t / '장.json'), '--부품', str(t / 'x')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1); self.assertIn('[실패]', r.stderr)


if __name__ == '__main__':
    unittest.main()
