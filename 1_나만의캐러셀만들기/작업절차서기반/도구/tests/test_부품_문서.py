"""모양표집계·값검사·부품README·견본넣기·구성샘플 테스트. 실행: python3 -m unittest discover 도구/tests"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "부품"))

import 공통  # noqa: E402
import 모양표집계  # noqa: E402
import 비슷한장검사  # noqa: E402
import 견본넣기  # noqa: E402
import 구성샘플  # noqa: E402
import 부품README  # noqa: E402

from PIL import Image  # noqa: E402


def 메모(*장들):
    return json.dumps([{"장": i + 1, "바탕": b, "글자없음": False, "사진": [], "부품": p, "계열": c, "모양": "m"}
                     for i, (p, c, b) in enumerate(장들)], ensure_ascii=False)


def 가짜약사(루트: Path) -> Path:
    A = 루트 / "시험약사_test_yaksa"
    S = A / "02_대표슬라이드" / "슬라이드"
    for 편, 장들 in {
        "2026-01-01_AAA": [("Cover", "㉠ 표지", "영상·자료 캡처"), ("Table", "㉡ 표", "사진 바탕"), ("Cta", "㉢ 끝", "그래픽·단색 바탕")],
        "2026-01-02_BBB": [("Cover", "㉠ 표지", "사진 바탕"), ("Table", "㉡ 표", "사진 바탕"), ("Solo", "㉣ 혼자", "사진 바탕"), ("Cta", "㉢ 끝", "그래픽·단색 바탕")],
    }.items():
        (S / 편).mkdir(parents=True)
        (S / 편 / "사진메모.json").write_text(메모(*장들), encoding="utf-8")
        for i in range(len(장들)):
            Image.new("RGB", (10, 10)).save(S / 편 / f"{i + 1}.jpg")
    (A / "01_수집").mkdir()
    (A / "02_대표슬라이드" / "분류.md").write_text(
        "| 종류 | 게시일_아이디 |\n|---|---|\n| 건강 정보 | 2026-01-01_AAA |\n| 건강 정보 | 2026-01-02_BBB |\n", encoding="utf-8")
    return A


class 모양표집계_테스트(unittest.TestCase):
    def test_숫자(self):
        with tempfile.TemporaryDirectory() as t:
            A = 가짜약사(Path(t))
            정보 = 공통.약사님폴더_검사(str(A))
            편들 = 모양표집계.편_읽기(정보)
            g = 모양표집계.집계(편들)
            self.assertEqual(g["판정전"], 0)
            self.assertEqual(len(g["부품"]["Cover"]["편"]), 2)
            self.assertEqual(len(g["부품"]["Solo"]["편"]), 1)
            self.assertTrue(모양표집계.자리(g["부품"]["Cover"]).startswith("1장만"))
            self.assertTrue(모양표집계.자리(g["부품"]["Cta"]).startswith("마지막 장만"))
            self.assertTrue(모양표집계.자리(g["부품"]["Table"]).startswith("중간"))
            # 견본 후보: 첫 편 1장은 영상·자료 캡처라 건너뜀
            self.assertEqual(모양표집계.견본후보(g["부품"]["Cover"]), "2026-01-02_BBB/1장")
            글 = 모양표집계.보고서(정보, 편들)
            self.assertNotIn("경고", 글)
            self.assertIn("| Solo | 드묾 | 1 | 1 |", 글)
            self.assertIn("| Cover | 부품 | 2 | 2 |", 글)
            self.assertIn("Cover → Table → Cta", 글)
            self.assertIn("건강 정보 | 7 |", 글)

    def test_판정전_경고와_저장(self):
        with tempfile.TemporaryDirectory() as t:
            A = 가짜약사(Path(t))
            (A / "02_대표슬라이드/슬라이드/2026-01-01_AAA/사진메모.json").write_text(메모((None, None, "사진 바탕")) , encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(모양표집계.main([str(A), "--write"]), 0)
            self.assertIn("부품 판정 전 장 1개", out.getvalue())
            저장 = list((A / "03_분석").glob("*_모양표.md"))
            self.assertEqual(len(저장), 1)
            self.assertIn("경고", 저장[0].read_text(encoding="utf-8"))


class 값검사_테스트(unittest.TestCase):
    def test_있는값_없는값(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "d.json").write_text(json.dumps({"a": 40, "c": "#AABBCC"}), encoding="utf-8")
            html = '<div class="slide"><i style="left:40px;color:#aabbcc"></i></div>'
            (t / "ok.html").write_text(html, encoding="utf-8")
            (t / "bad.html").write_text(html.replace("40px", "41px"), encoding="utf-8")
            run = lambda h: subprocess.run([sys.executable, "-I", str(TOOLS / "값검사.py"), str(t / h), str(t / "d.json")],
                                           capture_output=True, text=True)
            self.assertEqual(run("ok.html").returncode, 0)
            r = run("bad.html")
            self.assertEqual(r.returncode, 1)
            self.assertIn("41px", r.stdout)


def 견본(화면, 계열, 자리, **더):
    return {"json_자리": 자리, "화면": 화면, "모양_계열": 계열, "근거": "근거", "근거_편": "편 1장",
            "고정": "고정 문구", "바꿔_끼우는_자리": "바뀌는 문구", "편_안_자리": "1장 전용",
            "글_자리": {"제목": "한 줄 5~14자 · 1~2줄"}, "요소": [{"종류": "바탕", "색": "#FFFFFF"}], **더}


def 부품만들기(상위: Path, 목록):
    for 이름, d in 목록:
        (상위 / 이름).mkdir(parents=True, exist_ok=True)
        (상위 / 이름 / "견본.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


class 부품README_테스트(unittest.TestCase):
    def test_계열줄을_비슷한장검사가_읽음(self):
        with tempfile.TemporaryDirectory() as t:
            상위 = Path(t) / "부품"
            부품만들기(상위, [("GridTable", 견본("GridTable", "㉤ 격자 표", "a.b")), ("TwoTable", 견본("TwoTable", "㉤ 격자 표", "a.c")),
                           ("Cta", 견본("Cta", "㉧ 끝 장", "a.d"))])
            모양표 = Path(t) / "모양표.md"
            모양표.write_text("| 부품 | 구분 | 편 수 | 장 수 | 계열 | 쓰인 종류(장) | 편 안 자리 | 근거 장 | 견본 장 후보 |\n"
                          "|---|---|---|---|---|---|---|---|---|\n| GridTable | 부품 | 3 | 3 | x | y | 중간 (4장×3) | e/4장 | e/4장 |\n", encoding="utf-8")
            for 이름 in ("GridTable", "TwoTable", "Cta"):
                with contextlib.redirect_stdout(io.StringIO()):
                    부품README.main([str(상위 / 이름), "--모양표", str(모양표)])
            글 = (상위 / "GridTable" / "README.md").read_text(encoding="utf-8")
            for 절 in ("## 모양 계열", "## 편 안 자리", "## 글 자리", "## 고정 / 바꿔 끼우는 자리", "## 깔개·그림 처리", "## 원본과 아직 다른 점"):
                self.assertIn(절, 글)
            self.assertIn("㉤ 격자 표 — 같은 계열: GridTable · TwoTable", 글)
            self.assertIn("모양표: 부품 — 3편 3장", 글)
            self.assertEqual(비슷한장검사.계열_읽기(상위), {"GridTable": "격자 표", "TwoTable": "격자 표", "Cta": "끝 장"})


class 견본넣기_테스트(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.상위 = Path(self.t.name) / "부품"
        self.대상 = Path(self.t.name) / "ds.json"
        self.대상.write_text(json.dumps({"부품": {"표": {"정의": "x"}}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.원본 = self.대상.read_text(encoding="utf-8")

    def tearDown(self):
        self.t.cleanup()

    def 실행(self, *인자):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            return 견본넣기.main([str(self.상위), str(self.대상), *인자]), out.getvalue()

    def test_dryrun_write(self):
        부품만들기(self.상위, [("A", 견본("A", "㉠ a", "부품.표.견본")), ("B", 견본("B", "㉡ b", "마지막장.견본_한글"))])
        코드, 글 = self.실행()
        self.assertEqual(코드, 0)
        self.assertIn("부품.표.견본", 글)
        self.assertEqual(self.대상.read_text(encoding="utf-8"), self.원본)  # 기본은 안 씀
        self.실행("--write")
        d = json.loads(self.대상.read_text(encoding="utf-8"))
        self.assertEqual(d["부품"]["표"]["정의"], "x")
        self.assertEqual(d["부품"]["표"]["견본"]["화면"], "A")
        self.assertNotIn("json_자리", d["부품"]["표"]["견본"])
        self.assertIn("견본_한글", self.대상.read_text(encoding="utf-8"))
        self.assertTrue(self.대상.read_text(encoding="utf-8").endswith("\n"))

    def test_겹치면_실패(self):
        부품만들기(self.상위, [("A", 견본("A", "㉠ a", "부품.표.견본")), ("B", 견본("B", "㉡ b", "부품.표.견본"))])
        with self.assertRaises(SystemExit) as e, contextlib.redirect_stderr(io.StringIO()) as err:
            self.실행("--write")
        self.assertEqual(e.exception.code, 1)
        self.assertIn("[실패] 같은 자리에 겹칩니다", err.getvalue())
        self.assertEqual(self.대상.read_text(encoding="utf-8"), self.원본)


class 구성샘플_테스트(unittest.TestCase):
    def test_그림_크기(self):
        with tempfile.TemporaryDirectory() as t:
            상위 = Path(t) / "부품"
            (상위 / "A").mkdir(parents=True)
            (상위 / "B").mkdir()
            Image.new("RGB", (1080, 1350), (200, 0, 0)).save(상위 / "A" / "render.png")
            Image.new("RGB", (2160, 1350), (0, 0, 200)).save(상위 / "B" / "cmp.jpg")  # 오른쪽 절반만 씀
            출력 = Path(t) / "out" / "s.jpg"
            with contextlib.redirect_stdout(io.StringIO()):
                구성샘플.main([str(상위), "A", "B", "--출력", str(출력)])
            im = Image.open(출력)
            self.assertEqual(im.size, (360 * 2 + 12, 450 + 40))
            self.assertTrue(im.getpixel((10, 10))[0] > 150)       # A: 빨강
            self.assertTrue(im.getpixel((380, 10))[2] > 150)      # B: 파랑


if __name__ == "__main__":
    unittest.main()


class 한도시험(unittest.TestCase):
    """README '최대 N장'이 적힌 계열은 한 편에 N장까지(비슷한장검사), cmp 원본 가림"""
    def test_계열_한도(self):
        import 비슷한장검사
        계열 = {"A": "실사+자막", "C": "표지"}
        편 = {"편": "x", "날짜": "2026-01-01", "부품": ["C", "A", "A", "A"], "사진": []}
        self.assertTrue(비슷한장검사.검사(편, [], 계열))                       # 한도 없으면 걸림
        self.assertFalse(비슷한장검사.검사(편, [], 계열, {"실사+자막": 3}))      # 3장까지 통과
        self.assertTrue(비슷한장검사.검사(편, [], 계열, {"실사+자막": 2}))

    def test_cmp_원본_가림(self):
        import lib
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); a = Image.new("RGB", (1080, 1350), "white"); ImageDraw.Draw(a).text((100, 100), "NAME", fill="black")
            a.save(t / "o.jpg"); Image.new("RGB", (1080, 1350), "white").save(t / "render.png")
            검정 = lambda p: sum(1 for v in Image.open(p).convert("L").crop((90, 90, 200, 130)).getdata() if v < 80)
            lib.cmp(t, t / "o.jpg"); 전 = 검정(t / "cmp.jpg")
            lib.cmp(t, t / "o.jpg", [[90, 90, 200, 130]]); 후 = 검정(t / "cmp.jpg")
            self.assertGreater(전, 0); self.assertEqual(후, 0)
