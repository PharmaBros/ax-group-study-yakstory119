"""사진보정·누끼·블라인드 테스트. 실행: python3 -m unittest discover 도구/tests
사진보정·누끼는 OpenCV가 있어야 돈다: .venv-cv/bin/python -m unittest 도구/tests/test_부품_사진.py (없으면 skip)
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "부품"))

from PIL import Image  # noqa: E402

import 블라인드  # noqa: E402

try:
    import cv2
    import numpy as np
    import 누끼  # noqa: E402
    import 사진보정  # noqa: E402
except ImportError:
    cv2 = None


@unittest.skipUnless(cv2, "OpenCV 없음")
class 사진보정_테스트(unittest.TestCase):
    def test_판_방식_글_자리를_판_색으로_메우고_보호는_그대로(self):
        판 = (200, 210, 225)
        im = np.full((300, 400, 3), 판, np.uint8)
        im[100:140, 100:220] = 0  # 검정 글 사각형
        im[100:140, 260:300] = 0  # 보호 상자 안 검정(그대로여야 함)
        글, 보호 = (80, 80, 320, 160), (250, 90, 310, 150)
        out, n = 사진보정.보정(im, [글], [보호], "판")
        self.assertGreater(n, 4000)
        self.assertLessEqual(np.abs(out[100:140, 100:220].astype(int) - 판).max(), 10)
        self.assertTrue((out[90:150, 250:310] == im[90:150, 250:310]).all())

    def test_메움_방식도_글_자리를_채움(self):
        판 = (200, 210, 225)
        im = np.full((300, 400, 3), 판, np.uint8)
        im[100:140, 100:220] = 0
        out, _ = 사진보정.보정(im, [(80, 80, 320, 160)], [], "메움")
        self.assertLessEqual(np.abs(out[100:140, 100:220].astype(int) - 판).mean(), 12)  # 결 잡음이 있어 평균으로

    def test_질감_방식은_흰_글만_지움(self):
        rng = np.random.default_rng(0)
        im = np.clip(rng.normal(60, 5, (200, 300, 3)), 0, 255).astype(np.uint8)
        im[80:100, 100:200] = 255
        out, _ = 사진보정.보정(im, [(60, 60, 260, 140)], [], "질감")
        self.assertLess(out[82:98, 105:195].max(), 120)

    def test_누끼_알파_범위(self):
        im = np.full((200, 200, 3), 255, np.uint8)
        cv2.circle(im, (100, 100), 50, (30, 60, 200), -1)
        rgba, box = 누끼.cutout(im, (0, 0, 200, 200))
        self.assertEqual(rgba.shape[2], 4)
        self.assertEqual(rgba[0, 0, 3], 0)  # 모서리(바탕) 투명
        a = rgba[..., 3]
        self.assertEqual(a[a.shape[0] // 2, a.shape[1] // 2], 255)  # 한가운데 불투명
        self.assertTrue(40 <= box[0] <= 55 and 145 <= box[2] <= 160)


def 가짜약사님(루트: Path):
    """부품 A·B(render.png·견본.json)와 원본 장 8개(편 2개)가 든 가짜 폴더. 견본 근거 장 = AAAAAAAAAAA 1장."""
    약사 = 루트 / "시험약사_test_yaksa"
    (약사 / "01_수집").mkdir(parents=True)
    rng = random.Random(1)
    for 편, 부품, 이름 in [("2026-01-01_AAAAAAAAAAA", "A", "A"), ("2026-01-02_BBBBBBBBBBB", "B", "B")]:
        d = 약사 / "02_대표슬라이드" / "슬라이드" / 편
        d.mkdir(parents=True)
        메모 = []
        for n in range(1, 5):
            블록 = Image.new("RGB", (4, 5))
            블록.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(20)])
            블록.resize((400, 500), Image.NEAREST).save(d / f"{n}.jpg")
            메모.append({"장": n, "바탕": "사진 바탕", "부품": 부품})
        (d / "사진메모.json").write_text(json.dumps(메모, ensure_ascii=False), encoding="utf-8")
    부품들 = 루트 / "부품"
    for 이름 in "AB":
        (부품들 / 이름).mkdir(parents=True)
        Image.new("RGB", (1080, 1350), (240, 235, 230) if 이름 == "A" else (30, 40, 50)).save(부품들 / 이름 / "render.png")
        근거 = "AAAAAAAAAAA 1장(첫 장)" if 이름 == "A" else "BBBBBBBBBBB 2·3장"
        (부품들 / 이름 / "견본.json").write_text(json.dumps({"근거": "2026-10-14, 1440×1800 원본", "근거_편": 근거}, ensure_ascii=False), encoding="utf-8")
    return 약사, 부품들


class 블라인드_테스트(unittest.TestCase):
    def test_판_수_정답표_재압축(self):
        with tempfile.TemporaryDirectory() as t:
            약사, 부품들 = 가짜약사님(Path(t))
            out = Path(t) / "out"
            블라인드.main([str(약사), str(부품들), "--출력", str(out), "--재압축", "--대조", "A"])
            r1 = out / "r1"
            self.assertEqual(len(list((r1 / "B").glob("tile_*.jpg"))), 4)  # 만든 2 + 원본 2
            with Image.open(r1 / "A" / "grid.jpg") as g, Image.open(r1 / "B" / "tile_1.jpg") as b:
                self.assertEqual(g.size, (360 * 4, 450))
                self.assertEqual(b.size, (540, 675))
            tile = json.loads((r1 / "정답.json").read_text(encoding="utf-8"))["tile"]
            self.assertEqual(sorted(v["답"] for v in tile.values()), ["만든", "만든", "원본", "원본"])
            원본 = [(v["편"], v["장"]) for v in tile.values() if v["답"] == "원본"]
            self.assertNotIn(("2026-01-01_AAAAAAAAAAA", 1), 원본)  # 견본 근거 장은 뺌
            self.assertTrue((r1 / "판정_지시.md").exists())
            # 대조 판: 부품 A의 만든 장 자리가 견본 원본 장으로 바뀜 → 만든 장 1개
            대조 = json.loads((out / "r1_대조_A" / "정답.json").read_text(encoding="utf-8"))["tile"]
            self.assertEqual(sorted(v["답"] for v in 대조.values()), ["만든", "원본", "원본", "원본"])
            # 같은 장은 이전 회차에 못 씀 → 부품이 없는 회차 2는 실패
            with self.assertRaises(SystemExit) as e:
                블라인드.main([str(약사), str(부품들), "--출력", str(out), "--회차", "2"])
            self.assertEqual(e.exception.code, 1)

    def test_재압축_크기와_변화(self):
        rng = random.Random(2)
        im = Image.new("RGB", (1080, 1350))
        im.putdata([(rng.randrange(256),) * 3 for _ in range(1080 * 1350 // 64)] * 64)
        r = 블라인드.재압축(im)
        self.assertEqual(r.size, (1080, 1350))
        self.assertNotEqual(r.tobytes(), im.tobytes())


if __name__ == "__main__":
    unittest.main()

