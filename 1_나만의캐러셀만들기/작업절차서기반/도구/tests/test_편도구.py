"""편 도구 4개(사진재료·사진준비·편블라인드·캐러셀아티팩트)와 비슷한장검사 같은 컷 검사 테스트. 실행: python3 -m unittest discover -s tests
사진준비는 OpenCV가 있어야 돈다(.venv-cv/bin/python -m unittest tests/test_편도구.py, 없으면 skip).
"""
from __future__ import annotations

import contextlib
import html
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "부품"))

from PIL import Image, ImageDraw  # noqa: E402

import 비슷한장검사  # noqa: E402
import 사진재료  # noqa: E402
import 사진준비  # noqa: E402
import 캐러셀아티팩트  # noqa: E402
import 편블라인드  # noqa: E402


def 실행(main, *인자):
    """(끝 코드, 출력). main 이 SystemExit 로 끝나도 코드로 돌려준다."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            코드 = main(list(map(str, 인자)))
        except SystemExit as e:
            코드 = e.code
    return (코드 or 0), out.getvalue()


def 그림(경로: Path, 씨앗: int, 크기=(1080, 1350)):
    """씨앗마다 모양이 다른(상관 낮은) 잡음 그림."""
    r = random.Random(씨앗)
    im = Image.new("RGB", (8, 8))
    im.putdata([(r.randrange(40, 215),) * 3 for _ in range(64)])
    경로.parent.mkdir(parents=True, exist_ok=True)
    im.resize(크기, Image.BICUBIC).save(경로, "JPEG", quality=92)


def 가짜약사님(루트: Path, 메모: dict[str, list[dict]], 태그: list[dict] | None = None) -> Path:
    A = 루트 / "시험약사_test_yaksa"
    (A / "01_수집").mkdir(parents=True)
    if 태그 is not None:
        (A / "01_수집" / "사진_태그.json").write_text(json.dumps({"사진": 태그}, ensure_ascii=False), encoding="utf-8")
    for 편, 장들 in 메모.items():
        d = A / "02_대표슬라이드" / "슬라이드" / 편
        d.mkdir(parents=True)
        (d / "사진메모.json").write_text(json.dumps(장들, ensure_ascii=False), encoding="utf-8")
        for e in 장들:
            그림(d / f"{e['장']}.jpg", sum(map(ord, 편)) * 100 + e["장"])
    return A


class 사진재료_테스트(unittest.TestCase):
    def test_수_세기와_필요_끝코드(self):
        with tempfile.TemporaryDirectory() as t:
            태그 = [{"파일": "a.jpg", "본인얼굴": True, "글자없음": True, "다른사람얼굴": False},
                  {"파일": "b.jpg", "본인얼굴": True, "글자없음": False, "다른사람얼굴": False},
                  {"파일": "c.jpg", "본인얼굴": True, "글자없음": True, "다른사람얼굴": True},
                  {"파일": "d.jpg", "본인얼굴": True, "글자없음": True, "다른사람얼굴": False}]
            메모 = {"편1": [{"장": 1, "사진": [{"본인얼굴": True}]}, {"장": 2, "사진": [{"본인얼굴": False}]}]}
            A = 가짜약사님(Path(t), 메모, 태그)
            코드, 출력 = 실행(사진재료.main, A)
            self.assertEqual(코드, 0)
            self.assertIn("2장", 출력.splitlines()[0])
            self.assertIn("a.jpg", 출력)
            self.assertNotIn("b.jpg", 출력)
            self.assertIn("본인 사진 바탕 대표 슬라이드: 1장", 출력)
            self.assertEqual(실행(사진재료.main, A, "--필요", 2)[0], 0)
            코드, 출력 = 실행(사진재료.main, A, "--필요", 3)
            self.assertEqual(코드, 1)
            self.assertIn("[재료 부족]", 출력)

    def test_태그_없으면_실패(self):
        with tempfile.TemporaryDirectory() as t:
            코드, 출력 = 실행(사진재료.main, 가짜약사님(Path(t), {}))
            self.assertEqual(코드, 1)
            self.assertIn("[실패]", 출력)


def 가짜편(루트: Path, 부품들: list[str], 캡션="첫 줄\n⠀\n<둘째> & 줄", 크기=(1080, 1350)) -> Path:
    편 = 루트 / "편"
    for i, 부품 in enumerate(부품들, 1):
        그림(편 / "s" / f"{i:02d}_{부품}" / "render.png", 100 + i, 크기)
    (편 / "brief.md").write_text(f"# brief — 2026-11-12_시험편\n\n## 캡션 완성본 (그대로)\n\n```\n{캡션}\n```\n\n```\n다른 블록\n```\n", encoding="utf-8")
    return 편


class 편블라인드_테스트(unittest.TestCase):
    def test_만든_실제_같은_수_쓴사진과_제외는_안_뽑힘(self):
        with tempfile.TemporaryDirectory() as t:
            루트 = Path(t)
            A = 가짜약사님(루트, {"편A": [{"장": n, "부품": "PhotoCaption", "바탕": "사진 바탕"} for n in range(1, 7)]})
            편 = 가짜편(루트, ["PhotoCaption"] * 4)
            (편 / "구성.json").write_text(json.dumps({"사진": ["편A/1"]}), encoding="utf-8")
            이전 = 루트 / "이전판"
            이전.mkdir()
            (이전 / "정답.json").write_text(json.dumps({"A": {"정답": "실제", "출처": "편A/2.jpg"}, "B": {"정답": "만든", "출처": "01_PhotoCaption/render.png"}}), encoding="utf-8")
            코드, 출력 = 실행(편블라인드.main, A, 편, "--출력", 루트 / "판", "--제외", 이전)
            self.assertEqual(코드, 0, 출력)
            정답 = json.loads((루트 / "판" / "정답.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(정답), list("ABCDEFGH"))
            만든 = [v for v in 정답.values() if v["정답"] == "만든"]
            실제 = [v["출처"] for v in 정답.values() if v["정답"] == "실제"]
            self.assertEqual((len(만든), len(실제)), (4, 4))
            self.assertEqual(sorted(실제), [f"편A/{n}.jpg" for n in (3, 4, 5, 6)])  # 1(구성.json)·2(--제외)는 빠짐
            for g in 정답:
                with Image.open(루트 / "판" / f"{g}.jpg") as im:
                    self.assertEqual(im.size, (1080, 1350))
            지시 = (루트 / "판" / "판정_지시문.md").read_text(encoding="utf-8")
            self.assertIn("A~H", 지시)
            self.assertIn("판정.md", 지시)

    def test_원본_모자라면_있는_만큼(self):
        with tempfile.TemporaryDirectory() as t:
            루트 = Path(t)
            A = 가짜약사님(루트, {"편A": [{"장": 1, "부품": "PhotoCaption", "바탕": "사진 바탕"}]})
            편 = 가짜편(루트, ["PhotoCaption"] * 2)
            코드, 출력 = 실행(편블라인드.main, A, 편, "--출력", 루트 / "판")
            self.assertEqual(코드, 0, 출력)
            self.assertIn("[알림]", 출력)
            정답 = json.loads((루트 / "판" / "정답.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(v["정답"] for v in 정답.values()), ["만든", "만든", "실제"])


class 캐러셀아티팩트_테스트(unittest.TestCase):
    def test_figure_수와_캡션과_지울_번호(self):
        with tempfile.TemporaryDirectory() as t:
            편 = 가짜편(Path(t), ["CoverX", "PhotoCaption", "Note"])
            (편 / "아티팩트" / "s").mkdir(parents=True)
            (편 / "아티팩트" / "s" / "9.jpg").write_bytes(b"x")
            코드, 출력 = 실행(캐러셀아티팩트.main, 편, "--제목", "내 제목", "--메모", "첫 메모", "--메모", "둘째 <메모>")
            self.assertEqual(코드, 0, 출력)
            문서 = (편 / "아티팩트" / "캐러셀.html").read_text(encoding="utf-8")
            self.assertEqual(문서.count("<figure>"), 3)
            self.assertIn("<title>2026-11-12_시험편</title>", 문서)
            self.assertIn("<h1>내 제목</h1>", 문서)
            self.assertEqual(문서.count("<li>"), 2)
            self.assertEqual(html.unescape(문서.split('<pre id="caption">')[1].split("</pre>")[0]), "첫 줄\n⠀\n<둘째> & 줄")
            for n in (1, 2, 3):
                with Image.open(편 / "아티팩트" / "s" / f"{n}.jpg") as im:
                    self.assertEqual(im.size, (1080, 1350))
            self.assertIn("s/9.jpg", 출력.split("지울 파일")[1])

    def test_메모_없으면_절을_뺌(self):
        with tempfile.TemporaryDirectory() as t:
            편 = 가짜편(Path(t), ["A"])
            실행(캐러셀아티팩트.main, 편)
            self.assertNotIn("보기 전에", (편 / "아티팩트" / "캐러셀.html").read_text(encoding="utf-8"))

    def test_크기_틀리면_실패(self):
        with tempfile.TemporaryDirectory() as t:
            편 = 가짜편(Path(t), ["A", "B"])
            그림(편 / "s" / "02_B" / "render.png", 5, (1080, 1080))
            코드, 출력 = 실행(캐러셀아티팩트.main, 편)
            self.assertEqual(코드, 1)
            self.assertIn("1080×1350", 출력)
            self.assertFalse((편 / "아티팩트" / "캐러셀.html").exists())


class 같은컷_테스트(unittest.TestCase):
    def 준비(self, t):
        A = 가짜약사님(Path(t), {"편1": [{"장": 1, "부품": "P"}, {"장": 2, "부품": "P"}]})
        슬 = A / "02_대표슬라이드" / "슬라이드"
        (슬 / "편2").mkdir()
        (슬 / "편2" / "7.jpg").write_bytes((슬 / "편1" / "1.jpg").read_bytes())  # 이름만 다른 같은 그림
        부품 = Path(t) / "부품" / "X"
        부품.mkdir(parents=True)
        (부품 / "README.md").write_text("# X\n\n## 모양 계열\n㉠ 표지 — 같은 계열: X\n", encoding="utf-8")
        새 = Path(t) / "새.json"
        return A, 부품.parent, 새

    def test_같은_그림_두_이름은_걸림_약사님폴더_없으면_기존_동작(self):
        with tempfile.TemporaryDirectory() as t:
            A, 부품, 새 = self.준비(t)
            새.write_text(json.dumps({"편": "n", "부품": ["X"], "사진": ["편1/1", "편2/7", "편1/2"]}), encoding="utf-8")
            코드, 출력 = 실행(비슷한장검사.main, 부품, 새, "--약사님폴더", A)
            self.assertEqual(코드, 1)
            self.assertIn("[같은 컷]", 출력)
            self.assertEqual(출력.count("[같은 컷]"), 1)  # 편1/2 는 다른 그림
            코드, 출력 = 실행(비슷한장검사.main, 부품, 새)
            self.assertEqual(코드, 0)
            self.assertIn("그림 견주기 건너뜀", 출력)

    def test_최근_편과_같은_컷(self):
        with tempfile.TemporaryDirectory() as t:
            A, 부품, 새 = self.준비(t)
            새.write_text(json.dumps({"편": "n", "부품": ["X"], "사진": ["편2/7"]}), encoding="utf-8")
            지난 = Path(t) / "지난.json"
            지난.write_text(json.dumps({"편": "old", "날짜": "2026-11-01", "부품": ["Y"], "사진": ["편1/1"]}), encoding="utf-8")
            코드, 출력 = 실행(비슷한장검사.main, 부품, 새, 지난, "--약사님폴더", A)
            self.assertEqual(코드, 1)
            self.assertIn("최근 편 'old'", 출력)


@unittest.skipUnless(사진준비.cv2, "OpenCV 없음")
class 사진준비_테스트(unittest.TestCase):
    def test_상자_글_메운_뒤_상자_색(self):
        with tempfile.TemporaryDirectory() as t:
            im = Image.new("RGB", (1080, 400), (90, 120, 150))
            d = ImageDraw.Draw(im)
            d.rectangle([100, 100, 599, 259], fill=(255, 255, 255))
            d.rectangle([200, 170, 240, 176], fill=(20, 20, 20))  # 상자 안 "글"
            im.save(Path(t) / "원.png")
            (Path(t) / "일.json").write_text(json.dumps({"시험": {"원본": str(Path(t) / "원.png"), "상자글": [[100, 100, 500, 160, "흰"]]}}), encoding="utf-8")
            코드, 출력 = 실행(사진준비.main, Path(t) / "일.json", "--출력", Path(t) / "끝")
            self.assertEqual(코드, 0, 출력)
            self.assertIn("#FFFFFF", 출력)
            결과 = Image.open(Path(t) / "끝" / "시험_보정.jpg").convert("RGB")
            self.assertTrue(all(v > 240 for v in 결과.getpixel((220, 173))))


if __name__ == "__main__":
    unittest.main()
