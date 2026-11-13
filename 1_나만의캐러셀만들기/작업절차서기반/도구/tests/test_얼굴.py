"""얼굴 겹침 검사(부품/얼굴.py). 실행: python3 -m unittest discover 도구/tests
겹침 판정은 가짜 얼굴 상자로, macOS Vision은 swift가 있을 때 그린 얼굴 없는 그림에서 [] 인지만."""
import shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "부품"))
from PIL import Image, ImageDraw  # noqa: E402
import 얼굴  # noqa: E402


class 얼굴겹침시험(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.t)
        Image.new("RGB", (1080, 1350), (200, 200, 200)).save(self.t / "a.png")

    def 글(self, 이름, 상자):
        im = Image.new("RGB", (1080, 1350), (200, 200, 200)); ImageDraw.Draw(im).rectangle(상자, fill=0); im.save(self.t / 이름)
        return self.t / 이름

    def test_겹침(self):
        원래 = 얼굴.얼굴_찾기; 얼굴.얼굴_찾기 = lambda p: [(400, 400, 200, 200)]  # 검사상자 (380,320)-(620,620)
        self.addCleanup(setattr, 얼굴, "얼굴_찾기", 원래)
        r = 얼굴.검사(self.t / "a.png", self.글("b.png", (300, 605, 700, 640)), self.t / "확인.jpg")  # 턱 아래 5px
        self.assertTrue(r[0]["겹침"]); self.assertTrue((self.t / "확인.jpg").is_file())
        self.assertFalse(얼굴.검사(self.t / "a.png", self.글("c.png", (300, 660, 700, 700)))[0]["겹침"])  # 턱 아래 60px

    @unittest.skipUnless(shutil.which("swift"), "swift 없음(macOS 아님)")
    def test_Vision_얼굴없음(self):
        self.assertEqual(얼굴.얼굴_찾기(self.t / "a.png"), [])


if __name__ == "__main__":
    unittest.main()
