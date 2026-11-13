"""디자인시스템변환기: 부품 합치기 시험(가짜 약사님 폴더, 크롬·OpenCV 없이)."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

도구 = Path(__file__).resolve().parents[1]
변환기 = 도구 / "디자인시스템변환기.py"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def 부품_만들기(루트: Path, 이름: str, 계열: str, 글꼴: str):
    d = 루트 / 이름
    d.mkdir(parents=True)
    (d / "견본.json").write_text(json.dumps({
        "화면": 이름, "모양_계열": 계열, "편_안_자리": "1장 전용", "근거": f"{이름} 시험 장 1장. 위치 = 잼.",
        "글_자리": {"제목": "한 줄 8~12자"}, "요소": [{"종류": "글", "글": "가", "글꼴": 글꼴}]}, ensure_ascii=False), encoding="utf-8")
    (d / "preview.html").write_text(
        f'<!-- @dsCard group="부품 — {계열}" height=760 subtitle="x" -->\n<img src="__BLOB__a.png__"><img src="__BLOB__none.png__">\n', encoding="utf-8")
    (d / "README.md").write_text(f"# {이름}\n", encoding="utf-8")
    (d / "a.png").write_bytes(PNG)
    (d / "cmp.jpg").write_bytes(PNG)


class 변환기부품시험(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        self.약 = self.t / "시험약사_test"
        슬라이드 = self.약 / "02_대표" / "슬라이드" / "편1"
        슬라이드.mkdir(parents=True)
        (슬라이드 / "글.md").write_text("## 1장\n", encoding="utf-8")
        self.디자인 = self.약 / "04_설계서"
        self.디자인.mkdir()
        shutil.copy(도구 / "디자인시스템_빈틀.json", self.디자인 / "디자인시스템.json")
        self.d05 = self.약 / "05_디자인시스템"
        self.d05.mkdir()
        (self.d05 / "재료.json").write_text(json.dumps({
            "표시이름": "시험", "핸들": "test", "대표편": "편1", "사진": [],
            "장": [{"부품": "SlideCover", "이름": "표지", "장": 1, "설명": "x", "글": []}]}, ensure_ascii=False), encoding="utf-8")
        부품 = self.d05 / "부품"
        부품_만들기(부품, "Alpha", "㉠ 가", "강원교육모두 Bold")
        부품_만들기(부품, "Beta", "㉡ 나", "프리텐다드 Regular")
        self.out = self.t / "out"
        self.out.mkdir()
        shutil.copy(self.d05 / "재료.json", self.out / "재료.json")

    def 돌리기(self, *추가):
        r = subprocess.run([sys.executable, "-I", str(변환기), str(self.디자인), str(self.약), "--출력", str(self.out), *추가],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_부품_합치기(self):
        # 1차: 아이디 없음 → 자리표시 유지·"올리기 전" 보고
        out1 = self.돌리기()
        proj = self.out / "project"
        self.assertIn("부품 2개 · 부품 그림 2장(아이디 있는 것 0)", out1)
        self.assertIn("올리기 전 4곳", out1)
        a = (proj / "components/Alpha/preview.html").read_text(encoding="utf-8")
        self.assertTrue(a.startswith("<!-- @dsCard group=\"부품 — ㉠ 가\""))
        self.assertIn("__BLOB__a.png__", a)
        self.assertTrue((self.out / "올릴사진/part-alpha-a.png").exists())
        self.assertNotIn("cmp.jpg", json.loads((self.out / "사진아이디.json").read_text(encoding="utf-8")))
        # 2차: 아이디 적고 다시 → 치환(없는 파일 자리는 그대로)
        아이디 = json.loads((self.out / "사진아이디.json").read_text(encoding="utf-8"))
        아이디["part-alpha-a.png"] = "/_blob/abc123"
        (self.out / "사진아이디.json").write_text(json.dumps(아이디), encoding="utf-8")
        out2 = self.돌리기()
        self.assertIn("아이디 있는 것 1)", out2)
        a = (proj / "components/Alpha/preview.html").read_text(encoding="utf-8")
        self.assertIn('src="/_blob/abc123"', a)
        self.assertIn("__BLOB__none.png__", a)
        self.assertIn("__BLOB__a.png__", (proj / "components/Beta/preview.html").read_text(encoding="utf-8"))
        self.assertTrue((proj / "components/Beta/README.md").exists())
        # 옛 카드 group, bundle 순서, Parts 묶음, README 부품 절, 글꼴
        self.assertIn('group="옛 방식(참고)"', (proj / "components/SlideCover/preview.html").read_text(encoding="utf-8"))
        머리 = json.loads(re.search(r"@ds-bundle: (\{.*?\}) \*/", (proj / "components/bundle.js").read_text(encoding="utf-8")).group(1))
        self.assertEqual([c["name"] for c in 머리["components"]], ["Alpha", "Beta", "SlideCover"])
        색인 = json.loads((proj / "design-system.json").read_text(encoding="utf-8"))
        self.assertIn("Parts", 색인["groups"])
        parts = 색인["assetGroups"]["Parts"]
        self.assertEqual((parts["tile"], parts["order"], list(parts["files"])), ("s", ["part-alpha-a.png"], ["part-alpha-a.png"]))  # order는 올린(기록 있는) 그림만
        self.assertEqual(parts["files"]["part-alpha-a.png"]["blob"], "abc123")
        readme = (proj / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 부품 견본", readme)
        self.assertIn("| Alpha | ㉠ 가 | 1장 전용 | Alpha 시험 장 1장. | 제목: 한 줄 8~12자 |", readme)
        self.assertTrue((proj / "fonts/GangwonEduAll-Bold.woff").exists())
        self.assertTrue((proj / "licenses/GangwonEduAll_License.txt").exists())  # 라이선스 글은 fonts/ 밖(화면이 글꼴 파일처럼 보여 주지 않게)
        tokens = json.loads((proj / "tokens.json").read_text(encoding="utf-8"))
        self.assertIn("GangwonEduAll", {f["family"] for f in tokens["type"]["fonts"]})

    def test_장_샘플_비우면_폴더도_빠진다(self):
        self.돌리기()
        proj = self.out / "project"
        self.assertTrue((proj / "components/SlideCover").exists())
        (self.out / "재료.json").write_text(json.dumps({"표시이름": "시험", "핸들": "test", "사진": [], "장": []}, ensure_ascii=False), encoding="utf-8")
        out = self.돌리기()  # 대표편 없이도 돈다
        self.assertIn("뺀 컴포넌트: SlideCover", out)
        self.assertEqual(sorted(d.name for d in (proj / "components").iterdir() if d.is_dir()), ["Alpha", "Beta", "Cover"])
        self.assertNotIn("SlideCover", (proj / "components/bundle.js").read_text(encoding="utf-8"))
        self.assertNotIn("## 장 샘플", (proj / "README.md").read_text(encoding="utf-8"))

    def test_부품_없으면_그대로(self):
        shutil.rmtree(self.d05 / "부품")
        self.돌리기()
        proj = self.out / "project"
        self.assertNotIn("부품 견본", (proj / "README.md").read_text(encoding="utf-8"))
        self.assertIn('group="장 샘플"', (proj / "components/SlideCover/preview.html").read_text(encoding="utf-8"))
        self.assertNotIn("Parts", json.loads((proj / "design-system.json").read_text(encoding="utf-8"))["groups"])


if __name__ == "__main__":
    unittest.main()


class 변환기이름시험(unittest.TestCase):
    """부품 preview 글꼴 이름을 화면 family로, 색인 기록 이름을 허용 글자로"""
    def test_글꼴_이름과_안전이름(self):
        import 디자인시스템변환기 as V
        h = V.부품_글꼴바꾸기("font-family:'강원교육모두', sans-serif;font-family:'지마켓';var 쓴=[\"싱글데이\",\"Pretendard\"]")
        self.assertIn("'GangwonEduAll'", h); self.assertIn("'지마켓 산스'", h); self.assertIn('"Single Day"', h); self.assertNotIn("강원교육모두", h)
        n = V.안전이름(["part-x-+ R2 오.png", "part-x-+ R2 왼.png", "part-x-bg_보정.jpg"])
        self.assertEqual(len(set(n.values())), 3)
        for v in n.values():
            self.assertRegex(v, r"^[A-Za-z0-9_.-]+$")
        self.assertEqual(V.부품_글꼴({"요소": [{"글꼴": "강원교육모두 Bold"}, {"글꼴": "지마켓 Medium"}]}) >= {"지마켓 산스", "Pretendard"}, True)
