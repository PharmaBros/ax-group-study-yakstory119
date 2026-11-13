"""gpt그림 테스트(실제 API는 부르지 않는다 — 부르기를 가짜로 바꾼다). 실행: python3 -m unittest discover -s tests"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "부품"))

from PIL import Image  # noqa: E402

import gpt그림  # noqa: E402

진짜_키체인 = gpt그림.키체인
mock.patch.object(gpt그림, "키체인", return_value=None).start()  # 시험은 이 컴퓨터 키체인을 보지 않는다

KEY = "sk-test-SECRET-123"


def 가짜응답(색=(255, 0, 0), 크기=(64, 64)):
    b = io.BytesIO()
    Image.new("RGB", 크기, 색).save(b, "PNG")
    return 200, json.dumps({"data": [{"b64_json": base64.b64encode(b.getvalue()).decode()}]})


def 실행(*인자, env=None, 폴더=None, 응답=None):
    """(끝 코드, 출력, 부르기 mock). 환경변수는 env 만 남긴다."""
    out = io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=True), mock.patch.object(gpt그림, "작업폴더", Path(폴더 or tempfile.gettempdir()) / "없는폴더"), \
            mock.patch.object(gpt그림, "부르기", return_value=응답 or 가짜응답()) as 부름, \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            코드 = gpt그림.main(list(map(str, 인자)))
        except SystemExit as e:
            코드 = e.code
    return (코드 or 0), out.getvalue(), 부름


class 고치기_테스트(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = {"OPENAI_API_KEY": KEY}

    def 원본(self, 크기=(1080, 1350)):
        p = self.d / "원본.png"
        im = Image.new("RGB", 크기)
        im.putdata([((x * 7) % 256, (y * 5) % 256, (x + y) % 256) for y in range(크기[1]) for x in range(크기[0])])
        im.save(p)
        return p, im

    def test_자리_밖은_원본과_같다(self):  # 2a
        p, im = self.원본()
        out = self.d / "결과_AI생성.png"
        코드, _, _ = 실행("고치기", p, out, "--자리", "200,300,600,700", "--프롬프트", "x", env=self.env)
        self.assertEqual(코드, 0)
        r = Image.open(out).convert("RGB")
        self.assertEqual(r.size, im.size)
        for y in range(im.size[1]):
            for x in range(im.size[0]):
                if not (200 <= x < 600 and 300 <= y < 700):
                    self.assertEqual(r.getpixel((x, y)), im.getpixel((x, y)), (x, y))
        self.assertEqual(r.getpixel((400, 500)), (255, 0, 0))

    def test_보호_겹침(self):  # 2b
        p, im = self.원본((400, 400))
        out = self.d / "결과_AI생성.png"
        코드, 말, _ = 실행("고치기", p, out, "--자리", "50,50,300,300", "--보호", "150,150,250,250", "--프롬프트", "x", env=self.env)
        self.assertEqual(코드, 0)
        self.assertIn("[보호]", 말)
        r = Image.open(out).convert("RGB")
        self.assertEqual(r.getpixel((200, 200)), im.getpixel((200, 200)))
        self.assertEqual(r.getpixel((80, 80)), (255, 0, 0))

    def test_비율이_달라도_원본_크기(self):  # 2c
        p, im = self.원본((1080, 1350))
        out = self.d / "결과_AI생성.jpg"
        self.assertEqual(실행("고치기", p, out, "--자리", "100,100,400,400", "--프롬프트", "x", env=self.env)[0], 0)
        self.assertEqual(Image.open(out).size, (1080, 1350))
        p2, _ = self.원본((900, 900))
        out2 = self.d / "b_AI생성.png"
        self.assertEqual(실행("고치기", p2, out2, "--자리", "100,100,400,400", "--프롬프트", "x", env=self.env)[0], 0)
        self.assertEqual(Image.open(out2).size, (900, 900))

    def test_이름에_AI생성_없으면_2(self):  # 2e
        p, _ = self.원본((200, 200))
        코드, 말, 부름 = 실행("고치기", p, self.d / "결과.png", "--자리", "1,1,50,50", "--프롬프트", "x", env=self.env)
        self.assertEqual(코드, 2)
        self.assertIn("[이름]", 말)
        부름.assert_not_called()
        코드, _, 부름 = 실행("만들기", self.d / "결과.png", "--프롬프트", "x", env=self.env)
        self.assertEqual(코드, 2)
        부름.assert_not_called()

    def test_HTTP_오류는_1이고_키_없음(self):  # 2f
        p, _ = self.원본((200, 200))
        본문 = json.dumps({"error": {"message": f"Incorrect API key provided: {KEY}"}})
        코드, 말, _ = 실행("고치기", p, self.d / "결과_AI생성.png", "--자리", "1,1,50,50", "--프롬프트", "x", env=self.env, 응답=(401, 본문))
        self.assertEqual(코드, 1)
        self.assertIn("[GPT 오류] 401", 말)
        self.assertNotIn(KEY, 말)

    def test_기록_줄(self):  # 2g
        p, _ = self.원본((200, 200))
        log = self.d / "log.md"
        for _ in range(2):
            self.assertEqual(실행("고치기", p, self.d / "결과_AI생성.png", "--자리", "1,1,50,50", "--프롬프트", "글 지우기", "--기록", log, env=self.env)[0], 0)
        줄 = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(줄), 2)
        self.assertIn("gpt그림 고치기", 줄[0])
        self.assertIn("글 지우기", 줄[0])
        self.assertNotIn(KEY, log.read_text(encoding="utf-8"))

    def test_원본_덮어쓰기_거부(self):
        p = self.d / "원본_AI생성.png"
        Image.new("RGB", (100, 100)).save(p)
        코드, _, 부름 = 실행("고치기", p, p, "--자리", "1,1,50,50", "--프롬프트", "x", env=self.env)
        self.assertEqual(코드, 2)
        부름.assert_not_called()


class 키_테스트(unittest.TestCase):  # 2d
    def test_env_파일_환경변수_우선_없음(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            out = t / "만든_AI생성.png"
            (t / ".env").write_text("# OPENAI_API_KEY=주석\nOPENAI_API_KEY = \"sk-from-file\"\nOPENAI_IMAGE_MODEL=m-file\n", encoding="utf-8")
            with mock.patch.object(gpt그림, "작업폴더", t), mock.patch.object(gpt그림, "부르기", return_value=가짜응답()) as 부름, \
                    mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gpt그림.main(["만들기", str(out), "--프롬프트", "x"]), 0)
                self.assertEqual(부름.call_args[0][1]["Authorization"], "Bearer sk-from-file")
                self.assertEqual(json.loads(부름.call_args[0][2])["model"], "m-file")
                with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}):
                    gpt그림.main(["만들기", str(out), "--프롬프트", "x"])
                    self.assertEqual(부름.call_args[0][1]["Authorization"], "Bearer sk-env")
            self.assertEqual(Image.open(out).size, (64, 64))
            코드, 말, _ = 실행("만들기", out, "--프롬프트", "x", 폴더=t / "빈곳")
            self.assertEqual(코드, 2)
            self.assertIn("[키 없음]", 말)


if __name__ == "__main__":
    unittest.main()


class 키넣기_테스트(unittest.TestCase):
    def test_맥_아니면_env에_저장하고_값은_안_찍힘(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            (t / ".env").write_text("OPENAI_IMAGE_MODEL=m1\nOPENAI_API_KEY=old\n", encoding="utf-8")
            나옴 = io.StringIO()
            with mock.patch.object(gpt그림, "작업폴더", t), mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.object(sys.stdin, "isatty", return_value=True, create=True), \
                    mock.patch.object(gpt그림.getpass, "getpass", return_value="sk-new123"), \
                    mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(나옴):
                self.assertEqual(gpt그림.main(["키넣기"]), 0)
                self.assertEqual(gpt그림.main(["키확인"]), 0)
                self.assertEqual(gpt그림.설정값("OPENAI_API_KEY"), "sk-new123")
            self.assertEqual((t / ".env").read_text(encoding="utf-8"), "OPENAI_IMAGE_MODEL=m1\nOPENAI_API_KEY=sk-new123\n")
            self.assertNotIn("sk-new123", 나옴.getvalue())

    def test_빈_값은_저장_안_함_키확인_없음은_2(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(gpt그림, "작업폴더", Path(d)), mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.object(sys.stdin, "isatty", return_value=True, create=True), \
                    mock.patch.object(gpt그림.getpass, "getpass", return_value="  "), \
                    mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gpt그림.main(["키넣기"]), 2)
                self.assertEqual(gpt그림.main(["키확인"]), 2)
            self.assertFalse((Path(d) / ".env").exists())
