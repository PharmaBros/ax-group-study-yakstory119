"""도구/ 스크립트 핵심 함수 테스트. 실행: python3 -m unittest discover 도구/tests
실제 iCloud 자료는 쓰지 않고 임시 폴더에 작은 가짜 약사님 폴더를 만들어 검사한다.
"""
from __future__ import annotations

import json
import re
import os
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import 공통  # noqa: E402
import 수집검증  # noqa: E402
import 캡션통계  # noqa: E402
import 슬라이드실측  # noqa: E402
import 한눈에보기  # noqa: E402
import 비슷한장검사  # noqa: E402

from PIL import Image  # noqa: E402


def 가짜폴더(루트: Path) -> Path:
    """임시 약사님 폴더 `시험약사_test_yaksa` 를 만든다(폴더명 일부는 NFD로 저장해 NFC 처리도 검사)."""
    이름 = unicodedata.normalize("NFD", "시험약사") + "_test_yaksa"
    A = 루트 / 이름
    (A / "01_수집").mkdir(parents=True)
    (A / "02_대표슬라이드" / "슬라이드").mkdir(parents=True)
    (A / "03_분석").mkdir()
    (A / "동의기록.md").write_text("")
    (A / "읽어주세요.md").write_text("안내", encoding="utf-8")
    목록 = [
        {"순서": 1, "id": "AAA", "게시일": "2026-01-01", "유형": "캐러셀/사진", "분류": "정보형",
         "캡션": "🎈 비타민D 정리했어요 :)\n⠀\n✔️ 아침에 드세요\n✔️ 저는 매일 먹어요!\n저장해두세요. 댓글 남겨주세요\n#비타민 #약사"},
        {"순서": 2, "id": "BBB", "게시일": "2026-01-02", "유형": "캐러셀/사진", "분류": "공구",
         "캡션": "공구오픈 오메가3\n1️⃣ 가격 안내\n제가 직접 먹어봤습니다\nDM 주세요 @partner_shop"},
        {"순서": 3, "id": "CCC", "게시일": "2026-01-03", "유형": "릴스", "분류": "개인·일상", "캡션": "오늘 산책했다"},
    ]
    (A / "01_수집" / "게시물목록.json").write_text(json.dumps(목록, ensure_ascii=False), encoding="utf-8")
    (A / "02_대표슬라이드" / "분류.md").write_text(
        "# 분류\n\n| 게시일_아이디 | 캡션 첫 줄 | 장 수 | 종류(설계서) | 이전 분류 |\n|---|---|---|---|---|\n"
        "| 2026-01-01_AAA | 비타민D | 3 | **건강 정보** | ① 정보형 |\n"
        "| 2026-01-02_BBB | 오메가3 | 2 | **공구 안내** | ② 공구 |\n", encoding="utf-8")
    # 편 1: 1080×1350 세 장, 2장과 3장은 같은 그림(중복), 출처.json 있음
    편1 = A / "02_대표슬라이드" / "슬라이드" / "2026-01-01_AAA"
    편1.mkdir()
    Image.new("RGB", (1080, 1350), (255, 255, 255)).save(편1 / "1.jpg")
    같은 = Image.new("RGB", (1080, 1350), (230, 120, 60))
    같은.save(편1 / "2.jpg", quality=90)
    (편1 / "3.jpg").write_bytes((편1 / "2.jpg").read_bytes())
    (편1 / "출처.json").write_text("{}", encoding="utf-8")
    # 편 2: 720×720 두 장, 출처.json 없음
    편2 = A / "02_대표슬라이드" / "슬라이드" / "2026-01-02_BBB"
    편2.mkdir()
    Image.new("RGB", (720, 720), (40, 90, 200)).save(편2 / "1.jpg")
    Image.new("RGB", (720, 720), (250, 250, 250)).save(편2 / "2.jpg")
    return A


class 공통테스트(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.A = 가짜폴더(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_약사님폴더_NFC(self):
        정보 = 공통.약사님폴더_검사(str(self.A))
        self.assertEqual(정보["계정"], "test_yaksa")
        self.assertEqual(정보["표시이름"], "시험약사")
        self.assertIsNotNone(정보["01"])
        self.assertIsNotNone(정보["02"])
        self.assertIsNone(정보["04"])

    def test_분류_읽기(self):
        정보 = 공통.약사님폴더_검사(str(self.A))
        분류 = 공통.분류_읽기(정보)
        self.assertEqual(분류["편"]["2026-01-01_AAA"], "건강 정보")
        self.assertEqual(분류["아이디"]["BBB"], "공구 안내")
        self.assertEqual(공통.종류_정리("① 정보형"), "정보형")
        self.assertTrue(공통.개인일상인가("개인·일상"))
        self.assertTrue(공통.개인일상인가("**개인 일상**"))
        self.assertFalse(공통.개인일상인가("건강 정보"))

    def test_편_목록(self):
        정보 = 공통.약사님폴더_검사(str(self.A))
        편들 = 공통.편_목록(정보)
        self.assertEqual([e["이름"] for e in 편들], ["2026-01-01_AAA", "2026-01-02_BBB"])
        self.assertEqual([n for n, _ in 편들[0]["이미지"]], [1, 2, 3])

    def test_이모지(self):
        self.assertTrue(공통.이모지인가("🎈"))
        self.assertTrue(공통.이모지인가("✔"))
        self.assertFalse(공통.이모지인가("⠀"))  # 점자 공백
        self.assertFalse(공통.이모지인가("가"))
        es = 공통.이모지_추출("🎈 비타민 ✔️ 1️⃣ 👍🏻 ⠀")
        self.assertEqual(len(es), 4)
        self.assertEqual(공통.이모지_정규화("✔️"), "✔")
        self.assertEqual(공통.이모지_정규화("1️⃣"), "1️⃣")

    def test_마크다운표(self):
        t = 공통.마크다운표(["a", "b"], [["x|y", 1]])
        self.assertIn("| x｜y | 1 |", t)
        self.assertIn("(없음)", 공통.마크다운표(["a"], []))


class 수집검증테스트(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.A = 가짜폴더(Path(self.tmp.name))
        self.정보 = 공통.약사님폴더_검사(str(self.A))

    def tearDown(self):
        self.tmp.cleanup()

    def test_캡션_검사(self):
        c = 수집검증.캡션_검사([{"캡션": "a" * 301}, {"캡션": "b�"}])
        self.assertTrue(c["300초과"])
        self.assertEqual(c["깨진글자"], 1)
        self.assertFalse(수집검증.캡션_검사([{"캡션": "짧다"}])["300초과"])

    def test_중복_저해상도_출처(self):
        편들 = 공통.편_목록(self.정보)
        self.assertEqual(수집검증.편내_중복(편들[0]["이미지"]), [["2.jpg", "3.jpg"]])
        self.assertEqual(수집검증.편내_중복(편들[1]["이미지"]), [])
        self.assertEqual(수집검증.표지_크기(편들[1]["이미지"]), (720, 720))
        self.assertIsNone(편들[1]["출처"])
        본문, 확인 = 수집검증.검증(self.정보)
        self.assertIn("2026-01-02_BBB", 본문)
        self.assertIn("확인 필요", 본문)
        self.assertGreater(확인, 0)


class 캡션통계테스트(unittest.TestCase):
    def test_주당_편수(self):
        목록 = [{"순서": 1, "게시일": "2026-10-20"}, {"순서": 2, "게시일": "2025-01-29"},
              {"순서": 3, "게시시각_utc": "2026-10-29T03:00:00.000Z"}, {"순서": 4, "게시일": ""},
              {"순서": 5, "게시일_og": "2026-10-22", "고정": False}, {"순서": 6, "게시일": None},
              {"순서": 7, "게시일": "2026-10-15"}, {"순서": 8, "게시일": "2026-10-01", "고정": True}]
        r = 캡션통계.주당_편수(목록)
        # 순서 1·2는 고정 의심(뒤보다 날짜가 이름), 8은 고정 표시 → 3~7의 5편, 14일
        self.assertEqual((r["편수"], r["일수"], r["주당"], r["날짜없음"], r["고정"], r["고정의심"]), (5, 14, 2.0, 2, 1, 2))
        # 하루 차이(시차)는 고정 의심이 아니다
        r2 = 캡션통계.주당_편수([{"순서": 1, "게시일": "2026-10-28"}, {"순서": 2, "게시일": "2026-10-29"}, {"순서": 3, "게시일": "2026-10-21"}])
        self.assertEqual(r2["고정의심"], 0)
        self.assertEqual(캡션통계.게시_날짜({"게시시각_utc": "2026-10-28T20:00:00.000Z"}).isoformat(), "2026-10-29")
        self.assertIsNone(캡션통계.주당_편수([{"순서": 1, "게시일": "2026-10-29"}]))

    def test_끝맺음_어미(self):
        self.assertEqual(캡션통계.끝맺음_어미("오늘도 정리했어요"), "~했어요")
        self.assertEqual(캡션통계.끝맺음_어미("꼭 저장해두세요!"), "~세요")
        self.assertEqual(캡션통계.끝맺음_어미("이게 좋거든요~"), "~거든요")
        self.assertEqual(캡션통계.끝맺음_어미("비타민 정리해요 :)"), "~해요 :)")
        self.assertEqual(캡션통계.끝맺음_어미("드립니다"), "~ㅂ니다")
        self.assertIsNone(캡션통계.끝맺음_어미("#비타민 #약사"))
        self.assertIsNone(캡션통계.끝맺음_어미("500mg"))
        self.assertIsNone(캡션통계.끝맺음_어미("임신 준비할 때"))  # 줄 중간 끊김

    def test_문장_나누기(self):
        s = 캡션통계.문장_나누기("정리했어요 :) 오늘은요. 다음!\n줄바꿈")
        self.assertEqual(s, ["정리했어요 :) 오늘은요", "다음", "줄바꿈"])

    def test_존댓말(self):
        self.assertEqual(캡션통계.존댓말_판정("먹어요"), "존댓말")
        self.assertEqual(캡션통계.존댓말_판정("먹었다"), "반말")
        self.assertIsNone(캡션통계.존댓말_판정("500mg"))
        self.assertEqual(캡션통계.존댓말_판정("그렇게 하세용"), "존댓말")
        self.assertEqual(캡션통계.존댓말_판정("먹었니당"), "존댓말")
        self.assertEqual(캡션통계.판정불가_종류("드시면"), "연결어미 끝")

    def test_일인칭(self):
        c = 캡션통계.일인칭_세기("저는 약사예요. 제가 먹어봤어요. 저희 부부는 제품을 좋아해요. 약사인 저도요")
        self.assertEqual(c["저는"], 1)
        self.assertEqual(c["제가"], 1)
        self.assertEqual(c["저희~"], 1)
        self.assertEqual(c["약사인 저"], 1)
        self.assertNotIn("제품을", c)

    def test_해시태그_광고_불릿(self):
        self.assertEqual(캡션통계.해시태그_위치("본문\n더\n#a #b"), "끝 줄 몰림")
        self.assertEqual(캡션통계.해시태그_위치("#a 본문\n더"), "본문 안")
        self.assertIsNone(캡션통계.해시태그_위치("태그 없음"))
        self.assertEqual(캡션통계.광고_위치("공구오픈\n둘\n셋\n넷\n다섯\n여섯\n일곱"), "첫 3줄")
        self.assertEqual(캡션통계.불릿_기호("✔️ 항목"), "✔")
        self.assertEqual(캡션통계.불릿_기호("⠀1️⃣ 항목"), "1️⃣")
        self.assertEqual(캡션통계.불릿_기호("- 항목"), "-")
        self.assertIsNone(캡션통계.불릿_기호("-5도"))
        self.assertIsNone(캡션통계.불릿_기호("그냥 글"))

    def test_엔그램_첫줄(self):
        c = ["임신 준비 영양제 정리\n#태그", "임신 준비 영양제 추천", "임신 준비 영양제 비교"]
        g = dict(캡션통계.엔그램_세기(c, 최소=3))
        self.assertIn("임신 준비 영양제", g)
        self.assertEqual(g["임신 준비 영양제"], 3)
        self.assertNotIn("임신 준비", g)  # 더 긴 것에 포함되고 횟수 같으면 뺀다
        self.assertTrue(캡션통계.제목형인가("🎈 비타민D 정리"))
        self.assertFalse(캡션통계.제목형인가("오늘은 비타민D를 정리해 봤어요."))

    def test_집계_개인일상_제외(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            정보 = 공통.약사님폴더_검사(str(A))
            목록 = 공통.게시물목록_읽기(정보)
            R = 캡션통계.집계(목록, 공통.분류_읽기(정보), ["개인·일상"], False)
            self.assertEqual(R["캡션수"], 2)
            self.assertEqual(R["제외"]["개인·일상"], 1)
            self.assertEqual(R["CTA"]["저장"], 1)
            self.assertEqual(R["CTA"]["DM"], 1)
            self.assertEqual(dict(R["멘션"]), {"@partner_shop": 1})
            self.assertEqual(R["점자줄"], 1)
            self.assertEqual(R["광고수"], 1)
            self.assertIn("건강 정보", R["종류별"])
            본문 = 캡션통계.보고서(정보, R, None, "종류(설계서)")
            self.assertIn("끝맺음", 본문)
            self.assertNotIn("비타민D 정리했어요", 본문)  # 캡션 원문은 싣지 않는다
        finally:
            tmp.cleanup()


class 슬라이드실측테스트(unittest.TestCase):
    def test_비율_판정(self):
        self.assertEqual(슬라이드실측.비율_판정(1080, 1350), "4:5")
        self.assertEqual(슬라이드실측.비율_판정(1440, 1801), "4:5")  # 오차 2% 안
        self.assertEqual(슬라이드실측.비율_판정(1080, 1080), "1:1")
        self.assertEqual(슬라이드실측.비율_판정(1440, 1920), "3:4")
        self.assertEqual(슬라이드실측.비율_판정(1080, 1920), "9:16")
        self.assertEqual(슬라이드실측.비율_판정(1000, 1300), "기타")

    def test_색(self):
        im = Image.new("RGB", (100, 100), (255, 255, 255))
        for x in range(50):
            for y in range(100):
                im.putpixel((x, y), (230, 120, 60))
        d = 슬라이드실측.색_세기(im)
        c = 슬라이드실측.주요색(d)
        self.assertAlmostEqual(c["무채색비율"], 50.0, delta=1)
        self.assertEqual(c["유채색"][0][0], "#E6783C")
        self.assertTrue(슬라이드실측.무채색인가(240, 240, 240))
        self.assertFalse(슬라이드실측.무채색인가(230, 120, 60))
        f = 슬라이드실측.표지_특징(im)
        self.assertEqual(f["배경추정"], "단색·그래픽(추정)")

    def test_실측_전체(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            정보 = 공통.약사님폴더_검사(str(A))
            R = 슬라이드실측.실측(정보, None, None)
            self.assertEqual(len(R["편"]), 2)
            self.assertEqual(R["편"][0]["비율"], "4:5")
            self.assertTrue(R["편"][1]["저해상도"])
            본문 = 슬라이드실측.보고서(R)
            self.assertIn("4:5", 본문)
            self.assertIn("2026-01-02_BBB", 본문)
            R2 = 슬라이드실측.실측(정보, None, "공구 안내")
            self.assertEqual([e["편"] for e in R2["편"]], ["2026-01-02_BBB"])
        finally:
            tmp.cleanup()


class 한눈에보기테스트(unittest.TestCase):
    def test_배치(self):
        b = 한눈에보기.배치_계산([(1080, 1350)] * 7)
        self.assertEqual(b["줄수"], 2)
        self.assertEqual(b["위치"][0][2:], (360, 450))
        self.assertEqual(b["캔버스"][0], 8 + 5 * 368)

    def test_만들기와_보존(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            정보 = 공통.약사님폴더_검사(str(A))
            편 = 공통.편_목록(정보)[0]
            out = Path(tmp.name) / "out" / "x.jpg"
            크기 = 한눈에보기.한눈에보기_만들기([p for _, p in 편["이미지"]], out)
            self.assertTrue(out.exists())
            self.assertEqual(크기[0], 8 + 3 * 368)
            이전 = 한눈에보기.이전이름(out)
            self.assertEqual(이전.name, "x_이전.jpg")
        finally:
            tmp.cleanup()


class 반말_꼬리_테스트(unittest.TestCase):
    def test_반말_오탐_회귀(self):
        for 문장 in ["미토콘드리아", "교통사고 방지", "먹는데", "아젤리아", "고객에게", "영양제를 먹는데"]:
            self.assertNotEqual(캡션통계.존댓말_판정(문장), "반말", 문장)
        for 문장 in ["이건 먹는다", "나는 있어", "내가 할게", "내일 갈게", "오늘 한다"]:
            self.assertEqual(캡션통계.존댓말_판정(문장), "반말", 문장)
        self.assertEqual(캡션통계.끝맺음_어미("이건 먹는다"), "~는다")
        self.assertEqual(캡션통계.끝맺음_어미("오늘 한다"), "~ㄴ다")
        self.assertEqual(캡션통계.끝맺음_어미("내일 갈게"), "~ㄹ게")
        self.assertEqual(캡션통계.존댓말_판정("드셔보세요"), "존댓말")

    def test_꼬리_어미_인식(self):
        self.assertEqual(캡션통계.끝맺음_어미("저장해두세요><"), "~세요")
        self.assertEqual(캡션통계.끝맺음_어미("정리했어요ㅠㅠ"), "~했어요")
        self.assertEqual(캡션통계.끝맺음_어미("좋아요ㅎㅎ"), "~아요")
        self.assertIsNone(캡션통계.끝맺음_어미("(아!"))  # 한글 1글자 어절

    def test_종류_키_통합(self):
        self.assertEqual(공통.종류_키("월간 일정"), 공통.종류_키("월간일정"))
        self.assertEqual(공통.종류_키("**개인·일상**"), 공통.종류_키("개인 일상"))
        self.assertTrue(공통.개인일상인가("개인 일상"))
        목록 = [{"id": "X1", "분류": "월간 일정", "캡션": "공지드려요"}, {"id": "X2", "분류": "월간일정", "캡션": "또 공지드려요"}]
        R = 캡션통계.집계(목록, {"편": {}, "아이디": {}, "열이름": None}, [], False)
        self.assertEqual(R["종류별_옛분류"].get("월간 일정", (0,))[0], 2)
        self.assertEqual(len(R["종류별_옛분류"]), 1)
        self.assertEqual(len(R["종류별"]), 0)

    def test_이모지_불릿_제외와_끝구조(self):
        목록 = [{"id": "A", "분류": "정보형", "캡션": "✔️ 하나\n✔️ 둘 😊\n저장해두세요\n#태그"},
              {"id": "B", "분류": "정보형", "캡션": "내용이에요\n⠀\n문의는 DM 주세요 @shop"}]
        R = 캡션통계.집계(목록, {"편": {}, "아이디": {}, "열이름": None}, [], False)
        self.assertEqual(R["불릿이모지수"], 2)
        self.assertEqual(dict(R["이모지"]), {"😊": 1})
        self.assertEqual(R["이모지평균"], 0.5)
        self.assertEqual(R["이모지평균_불릿포함"], 1.5)
        self.assertEqual(R["끝구조"]["해시태그"], 1)
        self.assertEqual(R["끝구조"]["CTA 문구"], 1)
        self.assertEqual(캡션통계.마지막줄_모양("본문\n😊😊"), "이모지만")
        self.assertEqual(캡션통계.마지막줄_모양("본문\n오늘도 건강하세요"), "인사말")
        self.assertEqual(캡션통계.마지막줄_모양("본문\n@shop"), "멘션")
        self.assertEqual(캡션통계.마지막줄_모양("본문\n그냥 끝\n⠀"), "기타")
        # CTA 패턴
        self.assertFalse(캡션통계.CTA패턴["공유"].search("공유드릴게요"))
        # "[저장] or [공유]" 대괄호 표기(한 계정 36개 캡션)도 센다 — 2026-11-03
        self.assertTrue(캡션통계.CTA패턴["저장"].search("📍[저장] or [공유]하셔서"))
        self.assertTrue(캡션통계.CTA패턴["공유"].search("📌 [저장] Or [ 공유 ] 해두셨다가"))
        self.assertFalse(캡션통계.CTA패턴["저장"].search("[자료 저장소]"))
        self.assertTrue(캡션통계.CTA패턴["공유"].search("친구에게 공유해주세요"))
        self.assertFalse(캡션통계.CTA패턴["프로필"].search("링크 드릴게요"))
        self.assertTrue(캡션통계.CTA패턴["프로필"].search("링크 눌러주세요"))
        self.assertFalse(공통.이모지인가("©"))
        self.assertFalse(공통.이모지인가("®"))


class 표없는형_분류_테스트(unittest.TestCase):
    def test_표없는형_분류md_읽기(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            (A / "02_대표슬라이드" / "분류.md").write_text(
                "# samples 분류\n\n| 폴더(`슬라이드/`) | 게시물 | 분류 | 장 | 메모 |\n|---|---|---|---|---|\n"
                "| 2026-01-01_AAA | 비타민D | ① 정보형 | 3 | 크림 |\n"
                "| 2026-01-02_BBB | 오메가3 | ③ 공구 오픈 | 2 | 사진 |\n", encoding="utf-8")
            정보 = 공통.약사님폴더_검사(str(A))
            분류 = 공통.분류_읽기(정보)
            self.assertEqual(분류["편"]["2026-01-01_AAA"], "정보형")
            self.assertEqual(분류["아이디"]["BBB"], "공구 오픈")
            self.assertEqual(분류["열이름"], "분류")
            # 설계서 5종이 아닌 값 → "게시물목록(옛 분류)" 쪽 표로 간다
            R = 캡션통계.집계(공통.게시물목록_읽기(정보), 분류, ["개인·일상"], False)
            self.assertEqual(len(R["종류별"]), 0)
            self.assertEqual(len(R["종류별_옛분류"]), 2)
            본문 = 캡션통계.보고서(정보, R, None, 분류["열이름"])
            self.assertIn("분류.md 기준(설계서 5종)", 본문)
            self.assertIn("게시물목록 기준(옛 분류·참고)", 본문)
            self.assertIn("판정 불가", 본문)
        finally:
            tmp.cleanup()


class 분류표_우선순위_테스트(unittest.TestCase):
    def test_전체_판정표가_대표편_기록표보다_우선(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            (A / "02_대표슬라이드" / "분류.md").write_text(
                "# 분류\n\n## (기록) 결정 전 대표 편\n\n| 종류 | 게시일_아이디 | 좋아요 |\n|---|---|---|\n"
                "| 영양제 트렌드 | 2026-01-01_AAA | 9 |\n\n## 게시물별 판정\n\n"
                "| 순서 | 게시일_아이디 | 종류 |\n|---|---|---|\n"
                "| 1 | 2026-01-01_AAA | 건강 정보 |\n| 2 | 2026-01-02_BBB | 공구 안내 |\n", encoding="utf-8")
            분류 = 공통.분류_읽기(공통.약사님폴더_검사(str(A)))
            self.assertEqual(분류["편"]["2026-01-01_AAA"], "건강 정보")
            self.assertEqual(분류["아이디"]["AAA"], "건강 정보")
        finally:
            tmp.cleanup()


class 수집검증_추가_테스트(unittest.TestCase):
    def test_캡션상태와_해상도_낮음(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            목록경로 = A / "01_수집" / "게시물목록.json"
            목록 = json.loads(목록경로.read_text(encoding="utf-8"))
            목록[0]["캡션"] = "가" * 400 + "�"
            목록[0]["캡션상태"] = "인스타 제공 한계까지(잘림)"
            목록[1]["캡션상태"] = "전문"
            목록경로.write_text(json.dumps(목록, ensure_ascii=False), encoding="utf-8")
            편2 = A / "02_대표슬라이드" / "슬라이드" / "2026-01-02_BBB"
            (편2 / "출처.json").write_text(json.dumps({"해상도": "낮음(720px)"}, ensure_ascii=False), encoding="utf-8")
            정보 = 공통.약사님폴더_검사(str(A))
            본문, 확인 = 수집검증.검증(정보)
            self.assertIn("캡션상태별 개수", 본문)
            self.assertIn("참고(인스타 한계, 건수에 안 셈)", 본문)
            self.assertIn("기록됨(통과)", 본문)
            self.assertIn("## 참고(건수에 안 셈)", 본문)
            # 중복 1건(편1 2.jpg=3.jpg)만 남는다: �는 참고로, 720px는 기록됨으로, 출처.json 있음
            self.assertEqual(확인, 1)
        finally:
            tmp.cleanup()

    def test_목록없음이어도_멈추지_않음(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            (A / "01_수집" / "게시물목록.json").unlink()
            정보 = 공통.약사님폴더_검사(str(A))
            본문, 확인 = 수집검증.검증(정보)
            self.assertIn("게시물목록.json 없음 — 확인 필요 1건", 본문)
            self.assertGreaterEqual(확인, 1)
        finally:
            tmp.cleanup()


class 슬라이드실측_추가_테스트(unittest.TestCase):
    def test_720px_편도_색_집계와_강조색(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            정보 = 공통.약사님폴더_검사(str(A))
            R = 슬라이드실측.실측(정보, None, None)
            편2 = [e for e in R["편"] if e["편"] == "2026-01-02_BBB"][0]
            self.assertTrue(편2["저해상도"])
            self.assertIn("색", 편2)
            self.assertTrue(편2["색"]["강조색후보"])
            본문 = 슬라이드실측.보고서(R)
            self.assertIn("표지 가로 1080 미만", 본문)
            self.assertNotIn("720px 편 제외", 본문)
            self.assertIn("강조색 후보", 본문)
            색행 = [l for l in 본문.splitlines() if l.startswith("| 2026-01-02_BBB") and "#" in l]
            self.assertTrue(색행)
        finally:
            tmp.cleanup()

    def test_개인일상_제외와_못잰_편(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            슬라이드 = A / "02_대표슬라이드" / "슬라이드"
            (슬라이드 / "2026-01-03_CCC").mkdir()
            Image.new("RGB", (1080, 1350), (10, 10, 10)).save(슬라이드 / "2026-01-03_CCC" / "1.jpg")
            (슬라이드 / "2026-01-04_DDD").mkdir()  # 그림 0장
            (A / "02_대표슬라이드" / "분류.md").write_text(
                "| 게시일_아이디 | 종류 |\n|---|---|\n| 2026-01-01_AAA | 건강 정보 |\n| 2026-01-02_BBB | 공구 안내 |\n"
                "| 2026-01-03_CCC | 개인 일상 |\n| 2026-01-04_DDD | 건강 정보 |\n", encoding="utf-8")
            정보 = 공통.약사님폴더_검사(str(A))
            R = 슬라이드실측.실측(정보, None, None)
            self.assertNotIn("2026-01-03_CCC", [e["편"] for e in R["편"]])
            self.assertEqual(R["개인일상제외"], ["2026-01-03_CCC"])
            R2 = 슬라이드실측.실측(정보, None, None, True)
            self.assertIn("2026-01-03_CCC", [e["편"] for e in R2["편"]])
            본문 = 슬라이드실측.보고서(R)
            self.assertIn("못 잰 편", 본문)
            못 = [e for e in R["편"] if e["편"] == "2026-01-04_DDD"][0]
            self.assertTrue(못["못잼"])
            self.assertNotIn("2026-01-04_DDD", [l.split("|")[1].strip() for l in 본문.split("## 슬라이드 비율")[0].splitlines() if l.startswith("| 2026")])
        finally:
            tmp.cleanup()


class 수정2회차_테스트(unittest.TestCase):
    def test_어미_요_단독_삭제(self):
        self.assertIsNone(캡션통계.끝맺음_어미("이건 중요"))
        self.assertIsNone(캡션통계.끝맺음_어미("꼭 필요"))
        self.assertEqual(캡션통계.끝맺음_어미("이게 돼요"), "~돼요")
        self.assertEqual(캡션통계.끝맺음_어미("제가 먹을 거예요"), "~거예요")
        self.assertEqual(캡션통계.존댓말_판정("제가 먹을 거예요"), "존댓말")
        self.assertNotIn("요", 캡션통계.어미사전)

    def test_DM_문의_전문의약품(self):
        dm = 캡션통계.CTA패턴["DM"]
        self.assertIsNone(dm.search("전문의약품 안내"))
        self.assertIsNotNone(dm.search("문의 주세요"))

    def test_판정불가_세분(self):
        self.assertEqual(캡션통계.판정불가_종류("✔️ 아침 식후"), "불릿 항목")
        self.assertEqual(캡션통계.판정불가_종류("임신 준비할 때"), "명사·구 끝")
        self.assertEqual(캡션통계.판정불가_종류("하루 500mg"), "숫자·영어")
        self.assertEqual(캡션통계.판정불가_종류("먹는데"), "연결어미 끝")
        목록 = [{"id": "Z1", "분류": "정보", "캡션": "정리했어요\n✔️ 아침 식후\n임신 준비할 때\n하루 500mg\n먹는데"}]
        R = 캡션통계.집계(목록, {"편": {}, "아이디": {}, "열이름": None}, [], False)
        self.assertEqual(R["판정불가"], 4)
        self.assertEqual(sum(R["판정불가_세부"].values()), 4)
        정보 = {"이름": "시험"}
        본문 = 캡션통계.보고서(정보, R, None, None)
        self.assertIn("종결어미가 있는 문장 1개 기준", 본문)
        self.assertIn("불릿 항목 1 / 명사·구 끝 1 / 숫자·영어 1 / 연결어미 끝 1", 본문)

    def test_제외_표시_합침(self):
        목록 = [{"id": "A", "분류": "개인·일상", "캡션": "가"}, {"id": "B", "분류": "개인 일상", "캡션": "나"}]
        R = 캡션통계.집계(목록, {"편": {}, "아이디": {}, "열이름": None}, [], False)
        self.assertEqual(sum(R["제외"].values()), 2)
        self.assertEqual(len(R["제외"]), 1)

    def test_종류_정리_공백(self):
        self.assertEqual(공통.종류_정리("개인   일상\u00a0 글"), "개인 일상 글")

    def test_한글_파서_오류(self):
        import io
        import contextlib
        ap = 공통.한글ArgumentParser(add_help=False)
        ap.add_argument("약사님폴더")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                ap.parse_args([])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("[실패] 필요한 값이 빠졌습니다: 약사님폴더 — 사용법은 --help", err.getvalue())

    def test_강조색_피부_나무_띠_제외(self):
        self.assertFalse(슬라이드실측.강조색_후보인가(230, 140, 80))   # 주황/살구(H≈27°, S<0.75)
        self.assertTrue(슬라이드실측.강조색_후보인가(228, 35, 0))      # 빨강
        self.assertTrue(슬라이드실측.강조색_후보인가(18, 132, 204))    # 파랑
        self.assertTrue(슬라이드실측.강조색_후보인가(255, 120, 0))     # 선명한 주황은 S≥0.75라 남김

    def test_강조색_그래픽장_집계(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            A = 가짜폴더(Path(tmp.name))
            정보 = 공통.약사님폴더_검사(str(A))
            R = 슬라이드실측.실측(정보, None, None)
            편2 = [e for e in R["편"] if e["편"] == "2026-01-02_BBB"][0]
            self.assertEqual(편2["그래픽장수"], 2)
            h = 편2["색"]["강조색후보"][0][0]  # JPG 손실로 ±몇 단계 차이
            for a, b in zip((int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)), (40, 90, 200)):
                self.assertLessEqual(abs(a - b), 6)
        finally:
            tmp.cleanup()


import 디자인시스템변환기  # noqa: E402


class 변환기시험(unittest.TestCase):
    최종 = {
        "_계정": "시험_test",
        "색": {"바탕": ["#FFFFFF"], "본문": "#000000", "제목": "#000000", "본문_사진위": "#FFFFFF",
              "강조": {"역할": "빨강", "선택지": "#F70302"}, "형광펜": {"선택지": ["#FFEB5A", "#F8F335"]},
              "보조": {"초록_선택지": "#D1FF09"}},
        "글씨": {"제목": {"글꼴": "선택지", "선택지": "프리텐다드 Black", "크기": [62, 89], "크기_권고": 76,
                       "보조": [{"글꼴": "굵은 고딕", "대체": "지마켓 산스 Bold"}]},
                "소제목": {"크기": [32, 53]}, "본문": {"대체": "프리텐다드", "크기": [23, 75]},
                "손글씨": {"대체": "강원교육모두", "크기": None}},
        "여백": {"좌우": [40, 51], "좌우_권고": 40, "위": [40, 103]},
        "사진위글자": {"방식": "흰 글자 + 검정 외곽선 직접 또는 검정 바", "모서리px": 0},
        "출력_크기_기본": [1080, 1350],
    }

    def test_토큰(self):
        t = 디자인시스템변환기.토큰_만들기(self.최종, ["색.형광펜.선택지"])
        이름 = [x["name"] for x in t["color"]["tokens"]]
        self.assertIn("accent", 이름)
        self.assertIn("highlight-choice-1", 이름)          # 고르기 전 후보는 따로
        self.assertIn("green", 이름)
        self.assertEqual(len(이름), len(set(이름)))           # 이름 겹침 없음
        self.assertIn('"Pretendard"', t["type"]["families"]["title"])
        self.assertEqual(t["type"]["families"]["hand"], "sans-serif")   # 못 부르는 글꼴은 기본 고딕
        self.assertIn({"name": "margin-x", "value": "40px", "usage": "장 왼쪽·오른쪽 여백 권고값(여백.좌우_권고)"},
                      t["spacing"]["tokens"])

    def test_장_그리기(self):
        최종 = json.loads(json.dumps(self.최종))
        최종["사진위글자"]["꼴"] = [{"이름": "바", "바색": "#000000", "바_글자색": ["#FFFFFF", "#FEEFC4"], "굵기": "Bold",
                                "글자높이px": {"자막바": 78}, "안쪽여백px": {"위": 26, "아래": 18, "좌우": 26},
                                "위치px": {"자막바_위": 931}}]
        장 = {"부품": "SlideBody", "이름": "본문", "장": 2, "편": "2026-11-01_AAA", "설명": "시험", "사진": "c.jpg",
             "글": [{"글": "공동구매 사전 알림", "꼴": "바", "글꼴": "제목", "굵기": "꼴.굵기", "크기": "꼴.글자높이px.자막바",
                    "글자색": "꼴.바_글자색[1]", "배경": "꼴.바색", "안쪽여백": "꼴.안쪽여백px", "위": "꼴.위치px.자막바_위",
                    "정렬": "가운데", "강조": {"공동구매": "색.보조.초록_선택지"}}]}
        안, 없음, _, _ = 디자인시스템변환기.장_안쪽(최종, 장, {"c.jpg": "/_blob/abc"})
        self.assertIn('/_blob/abc', 안)
        self.assertIn("color:#D1FF09", 안)
        self.assertIn("font-size:78px", 안)
        self.assertIn("font-weight:700", 안)                # 굵기 낱말 → 고정 표
        self.assertIn("padding:26px 26px 18px", 안)
        self.assertIn("top:931px", 안)
        # 장 안의 px 숫자는 모두 최종 json에 있다(지어낸 값 없음 — 작업 설계서 2.2판 7-2)
        숫자들 = 디자인시스템변환기.json_숫자들(최종)
        for 값 in re.findall(r"(\d+(?:\.\d+)?)px", 안):
            self.assertIn(float(값), {float(x) for x in 숫자들}, f"{값}px가 json에 없음")
        self.assertIn("줄 간격(글꼴 기본으로 그림)", 없음)
        장["글"][0]["꼴"] = "없는 꼴"                          # json에 없는 꼴은 그리지 않고 표시
        안, 없음, _, _ = 디자인시스템변환기.장_안쪽(최종, 장, {})
        self.assertNotIn("padding:", 안)
        self.assertTrue(any("없는 꼴" in x for x in 없음))
        self.assertEqual(디자인시스템변환기.굵기숫자("Regular·Medium, 강조 Bold"), 400)

    def test_2회차_고침(self):
        V = 디자인시스템변환기
        self.assertEqual(V.이름굵기("프리텐다드 Black"), 900)
        self.assertIsNone(V.이름굵기("검은고딕(Black Han Sans)"))   # 글꼴 이름 속 Black은 굵기가 아님
        self.assertEqual(V.영문("머리말바"), "head-bar")
        self.assertEqual(V.영문("머리_윗줄"), "meori-witjul")          # 표에 없는 자리는 로마자
        self.assertTrue(re.fullmatch(r"[a-z0-9-]+", V.영문("이벤트_본문_둘째줄")))
        self.assertEqual(V.로마자("머리"), "meori")
        최종 = json.loads(json.dumps(self.최종))
        최종["사진위글자"]["꼴"] = [{"이름": "바", "글자높이px": {"자막바": 78}, "위치px": {"끝바_위": 203},
                                "엇갈림_오른쪽여백px": 33, "굵기": "Bold"}]
        t = V.토큰_만들기(최종, [])
        이름 = [x["name"] for x in t["type"]["groups"][0]["styles"]] + [x["name"] for x in t["spacing"]["tokens"]]
        self.assertIn("style1-sub-bar", 이름)
        self.assertIn("style1-top-end-bar-top", 이름)
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", n) for n in 이름))
        장 = {"부품": "SlideEnd", "이름": "끝", "장": 8, "편": "x", "설명": "", "사진": None, "글": [
            {"글": "첫 줄", "꼴": "바", "글꼴": "제목", "위": "꼴.위치px.끝바_위", "정렬": "왼쪽", "붙음": "왼쪽"},
            {"글": "둘째 줄", "꼴": "바", "글꼴": "제목", "위": "이어서", "정렬": "오른쪽", "오른쪽여백": "꼴.엇갈림_오른쪽여백px"}]}
        안, _, _, _ = V.장_안쪽(최종, 장, {})
        self.assertIn("left:0px;right:0px", 안)                 # 오른쪽여백 33은 장 가장자리에서 잰 값
        self.assertIn("padding-right:33px", 안)

    def test_보조색_이름_밖도_토큰(self):
        최종 = json.loads(json.dumps(self.최종))
        최종["색"]["보조"].update({"분홍_형광": "#F8D8E0", "분홍_근거": "설명 글"})
        이름값 = {x["name"]: x["value"] for x in 디자인시스템변환기.토큰_만들기(최종, [])["color"]["tokens"]}
        self.assertEqual(이름값.get("sub-bunhong-hyeonggwang"), "#f8d8e0")
        self.assertFalse(any("geungeo" in n for n in 이름값))      # hex가 아닌 칸은 토큰이 안 됨

    def test_고르기전_확인전(self):
        V = 디자인시스템변환기
        j = {"여백": {"아래": "선택지", "아래_선택지": [[17, 33], [47, 53]]}, "모서리px": "선택지 — 0 또는 24"}
        self.assertEqual(V.남은_선택지(j), ["여백.아래", "여백.아래_선택지", "모서리px"])
        self.assertEqual(V.남은_선택지({"여백": {"아래": [17, 30], "아래_선택지": [[17, 33], [47, 53]]}}), [])  # 아래를 골랐으면 끝
        self.assertEqual(V.남은_선택지({"제목": {"글꼴": "선택지", "선택지": ["A", "B"]}}), ["제목.글꼴", "제목.선택지"])
        self.assertEqual(V.남은_선택지({"제목": {"글꼴": "선택지", "선택지": "A"}}), [])        # 선택지를 골랐으면 표시도 끝
        self.assertEqual(V.남은_선택지({"제목": {"대체": "도현", "선택지": ["A", "B"]}}), [])   # 대체를 정했으면 끝
        self.assertEqual(V.남은_선택지(self.최종), ["색.형광펜.선택지"])
        j = {"_확인전": {"가족_사진": "약사님 확인", "워터마크": "확인"}, "글씨": {"_본문_세리프_확인전": "확인"}}
        self.assertEqual(sorted(V.확인전_칸(j)), ["_확인전.가족_사진", "_확인전.워터마크", "글씨._본문_세리프_확인전"])

    def test_빈틀로도_돌아감(self):
        V = 디자인시스템변환기
        빈틀 = json.loads((TOOLS / "디자인시스템_빈틀.json").read_text(encoding="utf-8"))
        self.assertEqual(V.남은_선택지(빈틀), [])
        self.assertEqual(V.확인전_칸(빈틀), [])
        t = V.토큰_만들기(빈틀, [])
        self.assertEqual(t["color"]["tokens"], [])                       # 값이 없으면 토큰도 없음(지어내지 않음)
        재료 = {"표시이름": "시험", "핸들": "test", "대표편": "x", "장": []}
        self.assertIn("고르기·확인 전 목록", V.README_만들기(빈틀, 재료, {}, [], [], []))

    def test_글_확인과_연락_가리기(self):
        글md = "## 1장\n- 제목: 공동구매 사전 알림\n  선착순 이벤트 있어요!!"
        self.assertEqual(디자인시스템변환기.글_확인(["공동구매 사전 알림\n선착순 이벤트 있어요!!"], 글md), [])
        self.assertEqual(디자인시스템변환기.글_확인(["새로 지은 글"], 글md), ["새로 지은 글"])
        가림 = 디자인시스템변환기.연락_가리기("상담은 https://band.us/x 또는 010-1234-5678")
        self.assertNotIn("band.us", 가림)
        self.assertNotIn("5678", 가림)


class 비슷한장검사_테스트(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        폴더 = Path(self.tmp.name)
        for 부품, 줄 in [("CoverPhotoList", "㉠ 표지 — 같은 계열: …"), ("CoverYellowBand", "㉠ 표지 — 같은 계열: …"),
                        ("GridTable", "㉡ 격자 표 — 같은 계열: …"), ("CoverTableCombo", "㉡ 격자 표 — 같은 계열: …"),
                        ("RoundCardStack", "㉢ 둥근 카드 쌓기 — 같은 계열: …")]:
            (폴더 / 부품).mkdir()
            (폴더 / 부품 / "README.md").write_text(f"# {부품}\n\n설명.\n\n## 모양 계열\n{줄}\n", encoding="utf-8")
        self.계열 = 비슷한장검사.계열_읽기(폴더)

    def tearDown(self):
        self.tmp.cleanup()

    def test_계열_읽기(self):
        self.assertEqual(self.계열["GridTable"], "격자 표")
        self.assertEqual(self.계열["RoundCardStack"], "둥근 카드 쌓기")

    def test_같은_계열_두_장은_걸림(self):
        문제 = 비슷한장검사.검사({"부품": ["CoverPhotoList", "CoverTableCombo", "GridTable"]}, [], self.계열)
        self.assertTrue(any("같은 계열" in m for m in 문제))

    def test_통과(self):
        self.assertEqual(비슷한장검사.검사({"부품": ["CoverPhotoList", "GridTable", "RoundCardStack"]}, [], self.계열), [])

    def test_최근_편과_표지_같으면_걸림(self):
        지난 = [{"편": "A", "날짜": "2026-11-01", "부품": ["CoverPhotoList", "RoundCardStack"]}]
        문제 = 비슷한장검사.검사({"부품": ["CoverPhotoList", "GridTable"]}, 지난, self.계열)
        self.assertTrue(any("표지" in m for m in 문제))

    def test_계열_순서_같으면_걸림(self):
        지난 = [{"편": "A", "날짜": "2026-11-01", "부품": ["CoverYellowBand", "CoverTableCombo"]}]
        문제 = 비슷한장검사.검사({"부품": ["CoverPhotoList", "GridTable"]}, 지난, self.계열)
        self.assertTrue(any("순서" in m for m in 문제))

    def test_최근_3편만_봄(self):
        지난 = [{"편": str(i), "날짜": f"2026-10-0{i}", "부품": ["CoverPhotoList"]} for i in range(1, 5)]
        지난[0]["부품"] = ["CoverYellowBand"]  # 가장 오래된 편(4편째)은 안 봄
        문제 = 비슷한장검사.검사({"부품": ["CoverYellowBand", "GridTable"]}, 지난, self.계열)
        self.assertFalse(any("표지" in m for m in 문제))

    def test_최근_편과_같은_사진이면_걸림(self):
        지난 = [{"편": "A", "날짜": "2026-11-01", "부품": ["CoverYellowBand"], "사진": ["BBBBBBBBBBB 7장"]}]
        문제 = 비슷한장검사.검사({"부품": ["CoverPhotoList"], "사진": ["BBBBBBBBBBB 7장", "X 1장"]}, 지난, self.계열)
        self.assertTrue(any("같은 사진" in m for m in 문제))

    def test_모르는_부품(self):
        문제 = 비슷한장검사.검사({"부품": ["Unknown"]}, [], self.계열)
        self.assertTrue(any("모르는 부품" in m for m in 문제))


if __name__ == "__main__":
    unittest.main()
