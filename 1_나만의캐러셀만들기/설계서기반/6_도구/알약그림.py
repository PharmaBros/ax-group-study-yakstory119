"""상표 없는 일반 알약 그림을 GPT로 그린다 — 선택 기능(작업 설계서 2.11판, 2026-11-13 결정).

언제 쓰나
- 그 약사님 게시물 실사 → 공식 사이트 실사 → (둘 다 없을 때만) 이 도구. 상표·라벨 글자·성분표·사람은 그리지 않는다.
- 커스텀 설계서에 "AI 그림 안 씀"이 있는 약사님은 키가 있어도 쓰지 않는다.
- 그리기 전에 약사님께 "몇 장, 대략 얼마"를 묻고 허락을 받은 뒤 `--허락` 을 붙여 실행한다. 한 번 실행 = 그림 1장 사용료.

키 등록(약사님이 직접, 한 번만 — 클로드는 키를 보지도 적지도 않는다)
  터미널에서 아래 한 줄을 실행하면 비밀번호 칸이 뜬다. 거기에 OpenAI 키를 붙여 넣고 엔터:
    security add-generic-password -a "$USER" -s openai_api_key -w
  키 확인(값은 보이지 않음): python3 -I 알약그림.py --키확인

사용
  # ① 배경 사진 위에 알약을 놓은 장면으로 그리기(추천 — 빛·그림자가 배경과 맞음)
  python3 -I 알약그림.py --허락 --바탕 <배경 사진> --알약 "흰 원형 정제 2알, 노란 연질캡슐 1알" --출력 <폴더>/알약_셀레늄_AI생성.png
  # ② 투명 배경 낱알(여러 알을 한 장에 — 잘라 쓰면 비용이 준다)
  python3 -I 알약그림.py --허락 --알약 "흰 원형 정제, 주황 연질캡슐, 갈색 경질캡슐" --출력 <폴더>/알약묶음_AI생성.png
  # 결 맞추기(선택): 같은 계정 실사 사진의 색·밝기·잔결에 맞춘다
  python3 -I 알약그림.py --결맞춤 <만든 그림> --기준 <원본 실사 사진> --출력 <폴더>/..._AI생성.png

지키는 것
- 출력 파일 이름에 `_AI생성`이 없으면 멈춘다.
- 받은 그대로의 파일을 같은 폴더 `_AI원본/`에 남기고, 가공한 파일에도 원본의 AI 표시(C2PA, PNG `caBX` 조각)를 옮겨 붙인다.
  AI 표시는 지우지 않는다. 옆에 `<파일>.출처.json`(모델·시각·알약 설명·바탕 파일)을 남긴다.
- 키 값은 화면·파일·기록 어디에도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import io
import json
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

모델 = "gpt-image-1.5"
금지문 = ("no text, no letters, no numbers, no logo, no brand, no label, no packaging, no bottle, "
       "no people, no hands, no faces")


def 키읽기() -> str:
    r = subprocess.run(["security", "find-generic-password", "-s", "openai_api_key", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def png_조각(데이터: bytes) -> list[tuple[bytes, bytes]]:
    """PNG → [(종류, 내용)]."""
    if 데이터[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG가 아님")
    i, 결과 = 8, []
    while i < len(데이터):
        길이 = struct.unpack(">I", 데이터[i:i + 4])[0]
        종류 = 데이터[i + 4:i + 8]
        결과.append((종류, 데이터[i + 8:i + 8 + 길이]))
        i += 12 + 길이
    return 결과


def png_합치기(조각들: list[tuple[bytes, bytes]]) -> bytes:
    import zlib
    out = [b"\x89PNG\r\n\x1a\n"]
    for 종류, 내용 in 조각들:
        out.append(struct.pack(">I", len(내용)) + 종류 + 내용 + struct.pack(">I", zlib.crc32(종류 + 내용) & 0xFFFFFFFF))
    return b"".join(out)


def ai표시_옮기기(원본: bytes, 가공: bytes) -> bytes:
    """원본 PNG의 C2PA(caBX) 조각을 가공 PNG의 IEND 앞에 붙인다. 원본에 없으면 가공을 그대로 돌려준다."""
    표시 = [c for c in png_조각(원본) if c[0] == b"caBX"]
    if not 표시:
        return 가공
    조각 = [c for c in png_조각(가공) if c[0] != b"caBX"]
    끝 = next(i for i, c in enumerate(조각) if c[0] == b"IEND")
    return png_합치기(조각[:끝] + 표시 + 조각[끝:])


def _요청(주소: str, 키: str, 본문: bytes, 형식: str) -> dict:
    req = urllib.request.Request(주소, data=본문, headers={"Authorization": "Bearer " + 키, "Content-Type": 형식})
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenAI 오류 {e.code}: {e.read().decode(errors='replace')[:300]}")


def 그리기(키: str, 알약: str, 바탕: Path | None) -> bytes:
    if 바탕 is None:
        글 = (f"Studio photo of loose generic dietary supplement pills: {알약}. Each pill separate with space around it, "
             f"realistic glossy and matte surfaces, soft natural shadow, photographed from slightly above. {금지문}.")
        본문 = json.dumps({"model": 모델, "prompt": 글, "size": "1536x1024", "background": "transparent",
                         "output_format": "png", "quality": "high", "n": 1}).encode()
        r = _요청("https://api.openai.com/v1/images/generations", 키, 본문, "application/json")
    else:
        글 = (f"Place these loose generic dietary supplement pills on this exact surface: {알약}. Keep the original surface, "
             f"texture, color and lighting unchanged; pills cast soft shadows matching the existing light; casual "
             f"smartphone photo look, slightly uneven arrangement. {금지문}.")
        경계 = uuid.uuid4().hex
        몸 = io.BytesIO()
        def 칸(이름, 값):
            몸.write(f"--{경계}\r\nContent-Disposition: form-data; name=\"{이름}\"\r\n\r\n{값}\r\n".encode())
        칸("model", 모델); 칸("prompt", 글); 칸("size", "1024x1536"); 칸("quality", "high"); 칸("n", "1")
        몸.write(f"--{경계}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"base.png\"\r\n"
                 f"Content-Type: image/png\r\n\r\n".encode())
        from PIL import Image
        b = io.BytesIO()
        Image.open(바탕).convert("RGB").save(b, "PNG")
        몸.write(b.getvalue() + b"\r\n" + f"--{경계}--\r\n".encode())
        r = _요청("https://api.openai.com/v1/images/edits", 키, 몸.getvalue(), f"multipart/form-data; boundary={경계}")
    return base64.b64decode(r["data"][0]["b64_json"])


def 장크기로(데이터: bytes) -> bytes:
    """세로 그림을 1080×1350(4:5)으로 가운데 맞춰 자른다."""
    from PIL import Image
    im = Image.open(io.BytesIO(데이터)).convert("RGB")
    s = max(1080 / im.width, 1350 / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - 1080) // 2, (im.height - 1350) // 2
    out = io.BytesIO()
    im.crop((x, y, x + 1080, y + 1350)).save(out, "PNG")
    return out.getvalue()


def 결맞춤(데이터: bytes, 기준: Path) -> bytes:
    """기준 실사의 평균 색·밝기 폭에 맞추고, 아주 약한 잔결(노이즈)을 더한다."""
    from PIL import Image, ImageStat
    import random
    im = Image.open(io.BytesIO(데이터))
    알파 = im.getchannel("A") if im.mode == "RGBA" else None
    rgb = im.convert("RGB")
    ref = Image.open(기준).convert("RGB")
    a, b = ImageStat.Stat(rgb), ImageStat.Stat(ref)
    띠 = []
    for c in range(3):
        k = (b.stddev[c] / a.stddev[c]) if a.stddev[c] else 1.0
        k = max(0.85, min(1.15, k))
        띠.append(rgb.getchannel(c).point(lambda v, k=k, ma=a.mean[c], mb=b.mean[c]: max(0, min(255, round((v - ma) * k + mb * 0.3 + ma * 0.7)))))
    rgb = Image.merge("RGB", 띠)
    rnd = random.Random(7)
    잡 = Image.effect_noise(rgb.size, 6).convert("L")
    rgb = Image.blend(rgb, Image.merge("RGB", [잡, 잡, 잡]), 0.03 + rnd.random() * 0.01)
    if 알파 is not None:
        rgb.putalpha(알파)
    out = io.BytesIO()
    rgb.save(out, "PNG")
    return out.getvalue()


def 저장(출력: Path, 원본: bytes, 가공: bytes, 기록: dict) -> None:
    if "_AI생성" not in 출력.name:
        raise SystemExit("출력 파일 이름에 _AI생성 이 있어야 합니다.")
    출력.parent.mkdir(parents=True, exist_ok=True)
    보관 = 출력.parent / "_AI원본"
    보관.mkdir(exist_ok=True)
    (보관 / 출력.name).write_bytes(원본)
    출력.write_bytes(ai표시_옮기기(원본, 가공))
    기록 = {**기록, "파일": 출력.name, "받은그대로": f"_AI원본/{출력.name}",
          "AI표시": "C2PA(caBX) 옮겨 붙임" if any(c[0] == b"caBX" for c in png_조각(원본)) else "원본에 C2PA 없음 — 이름 _AI생성으로만 표시"}
    출력.with_suffix(".출처.json").write_text(json.dumps(기록, ensure_ascii=False, indent=1), encoding="utf-8")


def main(인자: list[str]) -> int:
    p = argparse.ArgumentParser(description="상표 없는 일반 알약 그림(선택 기능)")
    p.add_argument("--키확인", action="store_true")
    p.add_argument("--허락", action="store_true", help="약사님께 장 수·사용료를 묻고 허락받았을 때만")
    p.add_argument("--알약", help="예: '흰 원형 정제 2알, 노란 연질캡슐 1알'")
    p.add_argument("--바탕", type=Path)
    p.add_argument("--결맞춤", type=Path)
    p.add_argument("--기준", type=Path)
    p.add_argument("--출력", type=Path)
    a = p.parse_args(인자)
    if a.키확인:
        print("키 있음(값은 보이지 않음)" if 키읽기() else "키 없음 — 약사님이 키를 등록해야 합니다(파일 머리 안내)")
        return 0
    if a.결맞춤:
        if not (a.기준 and a.출력):
            raise SystemExit("--결맞춤에는 --기준과 --출력이 필요합니다.")
        원 = a.결맞춤.read_bytes()
        저장(a.출력, 원, 결맞춤(원, a.기준), {"작업": "결맞춤", "기준": a.기준.name, "시각": _dt.datetime.now().isoformat(timespec="seconds")})
        print("결맞춤 저장:", a.출력)
        return 0
    if not (a.알약 and a.출력):
        p.print_help()
        return 2
    if not a.허락:
        raise SystemExit("그리기 전에 약사님께 '몇 장, 대략 얼마'를 묻고 허락받은 뒤 --허락 을 붙여 다시 실행하세요.")
    키 = 키읽기()
    if not 키:
        raise SystemExit("키 없음 — 약사님이 키를 등록해야 합니다(파일 머리 안내). AI 그림 없이 진행하세요.")
    원 = 그리기(키, a.알약, a.바탕)
    가공 = 장크기로(원) if a.바탕 else 원
    저장(a.출력, 원, 가공, {"작업": "그리기", "모델": 모델, "알약": a.알약, "바탕": a.바탕.name if a.바탕 else None,
                       "시각": _dt.datetime.now().isoformat(timespec="seconds")})
    print("저장:", a.출력, "(1장 사용료가 나갔습니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
