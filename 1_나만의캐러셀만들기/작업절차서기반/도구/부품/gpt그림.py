"""gpt그림 — OpenAI 이미지 API로 그림을 새로 만들거나(만들기), 사진의 지정한 자리만 고친다(고치기). Pillow 필요.

고치기 결과는 지정한 자리(--자리) 밖 픽셀이 원본과 완전히 같다 — GPT가 받은 그림에서 자리만 원본 위에 붙인다.
쓰기:
  python3 도구/부품/gpt그림.py 만들기 <출력_AI생성.png> --프롬프트 "…" [--크기 1024x1536] [--기록 log.md]
  python3 도구/부품/gpt그림.py 고치기 <원본> <출력_AI생성.jpg> --자리 x0,y0,x1,y1 (여러 번) --프롬프트 "…"
          [--보호 x0,y0,x1,y1 (여러 번)] [--번짐 6] [--기록 log.md]
좌표는 원본 픽셀 기준. 출력 이름에 `_AI생성`이 있어야 한다. 원본은 덮어쓰지 않는다.
  python3 도구/부품/gpt그림.py 키넣기      키를 입력받아 저장(맥 = 키체인, 그 밖 = 작업 폴더 .env). 맥은 숨김 입력 창, 그 밖은 터미널 입력
  python3 도구/부품/gpt그림.py 키확인      키가 있는지만 알린다(끝 코드 0 있음 · 2 없음)
키 읽는 순서: 환경변수 OPENAI_API_KEY → 맥 키체인(서비스 이름 OPENAI_API_KEY) → 작업 폴더 .env. 모델은 OPENAI_IMAGE_MODEL(환경변수·.env), 없으면 gpt-image-1.
키 값은 어디에도 찍지 않는다. 오류: 끝 코드 1(GPT 오류) · 2(입력·키·이름). 재시도 없음, 제한 180초.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

작업폴더 = Path(__file__).resolve().parents[2]
주소 = "https://api.openai.com/v1/images/"
크기들 = ["1024x1536", "1536x1024", "1024x1024"]


키이름 = "OPENAI_API_KEY"


def 키체인():
    """맥 키체인에서 키를 읽는다. 맥이 아니거나 없으면 None."""
    if sys.platform != "darwin":
        return None
    r = subprocess.run(["security", "find-generic-password", "-s", 키이름, "-w"], capture_output=True, text=True)
    return r.stdout.strip() or None if r.returncode == 0 else None


def 키_어디():
    """키가 있는 곳 이름(값은 돌려주지 않는다). 없으면 None."""
    if os.environ.get(키이름):
        return "환경변수"
    if 키체인():
        return "키체인"
    return ".env" if 설정값(키이름) else None


def 키넣기():
    """키를 입력받아 저장한다. 맥 = 키체인, 그 밖 = 작업 폴더 .env. 값은 찍지 않는다."""
    if sys.stdin.isatty():
        값 = getpass.getpass("OpenAI API 키(입력해도 보이지 않습니다): ")
    elif sys.platform == "darwin":  # 세션이 대신 띄워도 사람이 숨김 창에 직접 넣는다
        r = subprocess.run(["osascript", "-e", 'text returned of (display dialog "OpenAI API 키를 넣어 주세요(GPT 그림 도구용)" '
                            'default answer "" with hidden answer with title "GPT 키 넣기")'], capture_output=True, text=True)
        값 = r.stdout if r.returncode == 0 else ""
    else:
        return 끝내기(2, "[키넣기] 터미널에서 직접 실행해 주세요: python3 도구/부품/gpt그림.py 키넣기")
    값 = 값.strip()
    if not 값 or any(c.isspace() or c in "\"'\\" for c in 값):
        return 끝내기(2, "[키넣기] 취소했거나 키에 빈칸·따옴표가 있습니다. 저장하지 않았습니다.")
    if sys.platform == "darwin":  # 키를 명령 인자로 넘기지 않으려고 security -i 의 표준입력으로 준다
        r = subprocess.run(["security", "-i"], input=f'add-generic-password -U -a "{getpass.getuser()}" -s {키이름} -w "{값}"\n',
                           capture_output=True, text=True)
        if r.returncode or 키체인() != 값:
            return 끝내기(1, "[키넣기] 키체인에 저장하지 못했습니다.")
        return 끝내기(0, "저장: 맥 키체인(서비스 이름 OPENAI_API_KEY)")
    f = 작업폴더 / ".env"
    줄들 = [줄 for 줄 in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []) if 줄.partition("=")[0].strip() != 키이름]
    f.write_text("\n".join(줄들 + [f"{키이름}={값}"]) + "\n", encoding="utf-8")
    try:
        f.chmod(0o600)
    except OSError:
        pass
    return 끝내기(0, f"저장: {f} — 이 파일은 공유·복사하지 않습니다")


def 설정값(이름, 기본=None):
    if os.environ.get(이름):
        return os.environ[이름]
    if 이름 == 키이름 and 키체인():
        return 키체인()
    try:
        for 줄 in (작업폴더 / ".env").read_text(encoding="utf-8").splitlines():
            줄 = 줄.strip()
            if 줄 and not 줄.startswith("#") and 줄.partition("=")[0].strip() == 이름:
                값 = 줄.partition("=")[2].strip().strip("'\"").strip()
                if 값:
                    return 값
    except OSError:
        pass
    return 기본


def 부르기(url, 머리, 몸):
    """네트워크 호출은 여기 한 곳. (상태코드, 본문 문자열). 연결 실패는 상태 0."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=몸, headers=머리, method="POST"), timeout=180) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # 연결 실패·시간 초과도 한 줄 오류로
        return 0, f"{type(e).__name__}: {e}"


def 끝내기(코드, 말):
    print(말)
    return 코드


def 받기(url, 머리, 몸, 키):
    """응답에서 그림(PIL)을 꺼낸다. 실패하면 (None, 오류 줄) — 키 값은 지워서."""
    상태, 본문 = 부르기(url, 머리, 몸)
    try:
        return Image.open(io.BytesIO(base64.b64decode(json.loads(본문)["data"][0]["b64_json"]))), None
    except Exception:
        return None, f"[GPT 오류] {상태} {본문[:300]}".replace(키, "***")


def 좌표(s):
    try:
        x0, y0, x1, y1 = (int(v) for v in s.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"x0,y0,x1,y1 정수 네 개여야 합니다: {s}")
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def 칸에_넣기(im, 캔버스):
    """비율 유지로 줄여 캔버스 가운데에 넣고 남는 띠는 가장자리 픽셀로 채운다. (그림, 안쪽 상자)."""
    w, h = im.size
    cw, ch = 캔버스
    s = min(cw / w, ch / h)
    nw, nh = round(w * s), round(h * s)
    ox, oy = (cw - nw) // 2, (ch - nh) // 2
    작 = im.resize((nw, nh), Image.LANCZOS)
    판 = Image.new(im.mode, 캔버스)
    판.paste(작, (ox, oy))
    if ox:
        판.paste(작.crop((0, 0, 1, nh)).resize((ox, nh)), (0, oy))
        판.paste(작.crop((nw - 1, 0, nw, nh)).resize((cw - ox - nw, nh)), (ox + nw, oy))
    if oy:
        판.paste(판.crop((0, oy, cw, oy + 1)).resize((cw, oy)), (0, 0))
        판.paste(판.crop((0, oy + nh - 1, cw, oy + nh)).resize((cw, ch - oy - nh)), (0, oy + nh))
    return 판, (ox, oy, ox + nw, oy + nh)


def 칠하기(크기, 자리들, 칠, 바탕=0):
    m = Image.new("L", 크기, 바탕)
    for r in 자리들:
        ImageDraw.Draw(m).rectangle((r[0], r[1], r[2] - 1, r[3] - 1), fill=칠)
    return m


def 겹침(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def 고치기(a, 키, 모델):
    원본 = Image.open(a.원본).convert("RGB")
    W, H = 원본.size
    크기 = min(크기들, key=lambda t: abs(int(t.split("x")[0]) / int(t.split("x")[1]) - W / H))
    캔버스 = tuple(int(v) for v in 크기.split("x"))
    판, 안 = 칸에_넣기(원본, 캔버스)
    자리m = 칠하기((W, H), a.자리, 255)
    알파 = ImageOps.invert(칸에_넣기(자리m, 캔버스)[0])  # 자리 = alpha 0
    마스크 = Image.merge("RGBA", (*Image.new("RGB", 캔버스).split(), 알파))
    경계 = uuid.uuid4().hex
    몸 = b""
    for 이름, 값 in (("model", 모델), ("prompt", a.프롬프트), ("size", 크기)):
        몸 += f'--{경계}\r\nContent-Disposition: form-data; name="{이름}"\r\n\r\n{값}\r\n'.encode()
    for 이름, 그림 in (("image", 판), ("mask", 마스크)):
        b = io.BytesIO()
        그림.save(b, "PNG")
        몸 += f'--{경계}\r\nContent-Disposition: form-data; name="{이름}"; filename="{이름}.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + b.getvalue() + b"\r\n"
    몸 += f"--{경계}--\r\n".encode()
    받음, 오류 = 받기(주소 + "edits", {"Authorization": f"Bearer {키}", "Content-Type": f"multipart/form-data; boundary={경계}"}, 몸, 키)
    if 오류:
        return 끝내기(1, 오류)
    새 = 받음.convert("RGB").resize(캔버스, Image.LANCZOS).crop(안).resize((W, H), Image.LANCZOS)
    if any(겹침(g, p) for g in a.자리 for p in a.보호):
        print("[보호] --자리가 --보호와 겹칩니다. 겹친 곳은 원본 그대로 둡니다.")
    붙일곳 = ImageChops.subtract(자리m, 칠하기((W, H), a.보호, 255))  # 자리 − 보호
    if a.번짐 > 0:  # 번짐은 안쪽으로만: 줄여서 흐린 뒤 원래 영역으로 다시 자른다(밖은 0 그대로)
        흐림 = 붙일곳.filter(ImageFilter.MinFilter(2 * a.번짐 + 1)).filter(ImageFilter.GaussianBlur(a.번짐 / 2))
        붙일곳 = ImageChops.darker(흐림, 붙일곳)
    자리 = ";".join(",".join(map(str, g)) for g in a.자리)
    return 저장(Image.composite(새, 원본, 붙일곳), a, 모델, 자리, a.원본)


def 저장(im, a, 모델, 자리="", 원본=""):
    a.출력.parent.mkdir(parents=True, exist_ok=True)
    if a.출력.suffix.lower() in (".jpg", ".jpeg"):
        im.convert("RGB").save(a.출력, quality=95)
    else:
        im.save(a.출력)
    if a.기록:
        칸 = [f"- {date.today()} gpt그림 {a.명령}", 모델] + ([str(원본)] if 원본 else []) + ([자리] if 자리 else []) + [a.프롬프트.replace("\n", " "), str(a.출력)]
        with open(a.기록, "a", encoding="utf-8") as f:
            f.write(" · ".join(칸) + "\n")
    return 끝내기(0, f"저장: {a.출력}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="gpt그림", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="명령", required=True)
    sub.add_parser("키넣기", help="키를 입력받아 저장(맥 = 키체인, 그 밖 = .env)")
    sub.add_parser("키확인", help="키가 있는지만 알린다")
    for 이름 in ("만들기", "고치기"):
        s = sub.add_parser(이름, help="새 그림 만들기" if 이름 == "만들기" else "사진의 지정한 자리만 고치기")
        if 이름 == "고치기":
            s.add_argument("원본", type=Path)
        s.add_argument("출력", type=Path)
        s.add_argument("--프롬프트", required=True)
        s.add_argument("--기록", type=Path)
        if 이름 == "만들기":
            s.add_argument("--크기", choices=크기들, default="1024x1536")
        else:
            s.add_argument("--자리", type=좌표, action="append", required=True)
            s.add_argument("--보호", type=좌표, action="append", default=[])
            s.add_argument("--번짐", type=int, default=6)
    a = p.parse_args(argv)
    if a.명령 == "키넣기":
        return 키넣기()
    if a.명령 == "키확인":
        곳 = 키_어디()
        return 끝내기(0, f"GPT 키 있음({곳})") if 곳 else 끝내기(2, "GPT 키 없음 — `python3 도구/부품/gpt그림.py 키넣기`로 넣습니다")
    if "_AI생성" not in a.출력.name:
        return 끝내기(2, f"[이름] 출력 파일 이름에 `_AI생성`이 있어야 합니다: {a.출력.name}")
    if a.명령 == "고치기":
        if not a.원본.is_file():
            return 끝내기(2, f"[원본] 파일이 없습니다: {a.원본}")
        if a.출력.resolve() == a.원본.resolve():
            return 끝내기(2, "[출력] 원본을 덮어쓸 수 없습니다.")
    키 = 설정값("OPENAI_API_KEY")
    if not 키:
        return 끝내기(2, "[키 없음] OPENAI_API_KEY 가 없습니다 — `python3 도구/부품/gpt그림.py 키넣기`로 넣습니다.")
    모델 = 설정값("OPENAI_IMAGE_MODEL", "gpt-image-1")
    if a.명령 == "고치기":
        return 고치기(a, 키, 모델)
    받음, 오류 = 받기(주소 + "generations", {"Authorization": f"Bearer {키}", "Content-Type": "application/json"},
                  json.dumps({"model": 모델, "prompt": a.프롬프트, "size": a.크기}).encode(), 키)
    return 끝내기(1, 오류) if 오류 else 저장(받음, a, 모델)


if __name__ == "__main__":
    sys.exit(main())
