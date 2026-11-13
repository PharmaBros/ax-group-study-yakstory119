"""사진준비 — 기존 게시물 장에서 얹힌 글만 지워 깔개 사진(<이름>_보정.jpg)을 만든다. OpenCV 필요.

얼굴·사람 위는 건드리지 않는다(머리는 보호 상자로 준다). AI로 그리지 않는다 — 상자 색 메움, 사진보정.py, 옆 면 붙이기뿐.
쓰기: .venv-cv/bin/python 도구/부품/사진준비.py <일.json> [--출력 <폴더>]
일.json (좌표는 폭을 맞춘 뒤 그림 기준, x y w h):
  {"<이름>": {"원본": "<경로>", "폭": 1080,
              "상자글": [[x,y,w,h,"흰"|"검"|"중앙"], …],   상자 안 글 → 상자 색으로 메움
              "사진위글": [[x,y,w,h], …], "방식": "질감"|"메움", "보호": [[x,y,w,h], …],   사진 위 글 → 사진보정.py
              "옮김": [[x,y,w,h, sx,sy], …]}}              지운 자국 위에 (sx,sy)의 옆 면을 cv2.seamlessClone 으로 붙임
순서: 폭 줄임 → 상자글 → 사진위글 → 옮김. 출처: 임시 편 스크립트(한 편의 사진준비.py)를 일반화.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import 공통  # noqa: E402

try:
    import cv2
    import numpy as np
    import 사진보정
except ImportError:  # 시스템 python3: --help 만 가능
    cv2 = None

방식들 = ("질감", "메움")


def 상자_메우기(im, 상자들, 이름="") -> None:
    """상자 안 글 획을 상자 색으로 메운다(제자리 수정). 메운 상자의 위치·색을 출력한다."""
    for x, y, bw, bh, 색 in 상자들:
        roi = im[y:y + bh, x:x + bw]
        중 = np.median(roi.reshape(-1, 3), axis=0)
        같음 = (roi.min(2) > 225) if 색 == "흰" else (roi.max(2) < 40) if 색 == "검" else (np.abs(roi.astype(int) - 중).max(2) < 28)
        m = cv2.morphologyEx(같음.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 45), np.uint8))  # 글 획만 메움(상자 사이 틈은 그대로)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))                     # 사진 속 작은 밝은 점은 뺌
        if m.any():
            면 = np.median(roi[같음], axis=0)
            roi[m.astype(bool)] = 면
            ys, xs = np.nonzero(m)
            print("   %s %s 상자 x%d y%d w%d h%d 색 #%02X%02X%02X" % (
                이름, 색, x + xs.min(), y + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, *[int(v) for v in 면[::-1]]))


def 옮겨_붙이기(im, 옮김):
    """지운 자국 자리에 바로 옆 깨끗한 면을 옮겨 붙인다(cv2.seamlessClone)."""
    for x, y, w, h, sx, sy in 옮김:
        조각 = im[sy:sy + h, sx:sx + w].copy()
        im = cv2.seamlessClone(조각, im, np.full((h, w), 255, np.uint8), (x + w // 2, y + h // 2), cv2.NORMAL_CLONE)
    return im


def 준비(이름: str, 항목: dict):
    src = 공통.작업폴더_경로(항목["원본"])
    im = cv2.imread(str(src))
    if im is None:
        공통.실패(f"{이름}: 그림을 읽을 수 없습니다: {src}")
    h, w = im.shape[:2]
    폭 = int(항목.get("폭", 1080))
    im = cv2.resize(im, (폭, round(h * 폭 / w)), interpolation=cv2.INTER_AREA)
    상자_메우기(im, 항목.get("상자글", []), 이름)
    글들 = 항목.get("사진위글", [])
    if 글들:
        방식 = 항목.get("방식")
        if 방식 not in 방식들:
            공통.실패(f"{이름}: 사진위글이 있으면 방식은 {'|'.join(방식들)} 중 하나여야 합니다(받은 값: {방식})")
        H, W = im.shape[:2]
        박스 = lambda g: 사진보정.상자_읽기("%d,%d,%d,%d" % (g[0], g[1], g[0] + g[2], g[1] + g[3]), W, H)
        im, n = 사진보정.보정(im, [박스(g) for g in 글들], [박스(g) for g in 항목.get("보호", [])], 방식)
        print(f"   {이름} 사진 위 글 잉크 {n}픽셀 지움({방식})")
    return 옮겨_붙이기(im, 항목.get("옮김", []))


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="원본 장에서 얹힌 글만 지워 <이름>_보정.jpg 를 만든다. 얼굴·사람 위는 건드리지 않는다(머리는 보호 상자로 준다). AI 아님.")
    ap.add_argument("일", help="일.json (사진마다 원본·상자글·사진위글·방식·보호·옮김)")
    ap.add_argument("--출력", help="결과 폴더(기본: 일.json 이 있는 폴더)")
    a = ap.parse_args(argv)
    if cv2 is None:
        공통.실패("OpenCV가 없습니다: .venv-cv/bin/python 으로 실행하세요")
    일경로 = 공통.작업폴더_경로(a.일)
    if not 일경로.is_file():
        공통.실패(f"일.json 을 찾을 수 없습니다: {일경로}")
    try:
        일 = json.loads(일경로.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        공통.실패(f"일.json 을 읽지 못했습니다(JSON 오류): {e}")
    출력 = 공통.작업폴더_경로(a.출력) if a.출력 else 일경로.parent
    출력.mkdir(parents=True, exist_ok=True)
    for 이름, 항목 in 일.items():
        끝 = 출력 / f"{이름}_보정.jpg"
        cv2.imwrite(str(끝), 준비(이름, 항목), [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"[완료] {끝}")


if __name__ == "__main__":
    main()
