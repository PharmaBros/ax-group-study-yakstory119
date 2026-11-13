"""누끼 — 흰(또는 단색) 바탕 장에서 사람·그림만 알파 png로 떼어 낸다.

출처: R/2026-11-10_디자인시스템/도구/_tools_A/cutout.py (2026-11-10 판)
쓰기: .venv-cv/bin/python 도구/부품/누끼.py 원본.jpg 출력.png --상자 x0,y0,x1,y1 [--바탕 #FFFFFF] [--문턱 N]
상자 가장자리에 닿은 바탕 덩어리를 지우고 가장 큰 덩어리만 남긴다. 가장자리 확인용 확대 그림 <출력>_확인.png 도 저장(교훈 8).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import 공통  # noqa: E402

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None


def cutout(im, box, thr=250, keep=1, erode=1, blur=1.0, bgcol=None):
    """im BGR uint8 → (RGBA 조각, 원본 좌표 상자). bgcol 이 없으면 흰색(세 채널 모두 thr 이상)이 바탕."""
    x0, y0, x1, y1 = box
    c = im[y0:y1, x0:x1].astype(np.int32)
    if bgcol is None:
        cand = c.min(axis=2) >= thr
    else:
        cand = np.abs(c - np.array(bgcol)).max(axis=2) <= (255 - thr)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=4)
    h, w = cand.shape
    bg = np.zeros_like(cand)
    for i in range(1, n):
        x, y, ww, hh, _a = st[i]
        if x == 0 or y == 0 or x + ww == w or y + hh == h:  # 가장자리에 닿은 덩어리 = 바탕
            bg |= lab == i
    fg = (~bg).astype(np.uint8)
    n2, l2, s2, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if n2 < 2:
        공통.실패("떼어 낼 그림이 없습니다 — --상자·--문턱을 확인하세요")
    fg = np.isin(l2, np.argsort(-s2[1:, cv2.CC_STAT_AREA])[:keep] + 1).astype(np.uint8)
    if erode:
        fg = cv2.erode(fg, np.ones((3, 3), np.uint8), iterations=erode)
    a = np.clip(cv2.GaussianBlur(fg.astype(np.float32), (0, 0), blur), 0, 1)
    ys, xs = np.where(a > 0.02)
    if len(ys) == 0:
        공통.실패("떼어 낼 그림이 없습니다 — --상자·--문턱을 확인하세요")
    bx = [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]
    rgba = np.dstack([c.astype(np.uint8), (a * 255).astype(np.uint8)])[bx[1]:bx[3], bx[0]:bx[2]]
    return rgba, [int(x0 + bx[0]), int(y0 + bx[1]), int(x0 + bx[2]), int(y0 + bx[3])]


def 확인그림(rgba, 최대=2000):
    """알파 조각을 분홍 바탕에 얹어 정수 배로 키움(가장자리 깨짐·흰 테두리 확인용)."""
    k = max(1, min(4, 최대 // max(rgba.shape[:2])))
    a = rgba[..., 3:4].astype(np.float32) / 255
    분홍 = np.array([255, 0, 255], np.float32)  # BGR
    합 = (rgba[..., :3] * a + 분홍 * (1 - a)).astype(np.uint8)
    return cv2.resize(합, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="바탕이 단색(기본 흰색)인 장에서 그림만 알파 png로 떼어 낸다.")
    ap.add_argument("원본", help="원본 jpg")
    ap.add_argument("출력", help="출력 png (알파)")
    ap.add_argument("--상자", required=True, metavar="x0,y0,x1,y1", help="떼어 낼 그림이 든 상자(원본 픽셀)")
    ap.add_argument("--바탕", metavar="#RRGGBB", help="바탕색(기본: 흰색). 흰색이 아니면 --문턱을 낮춰 허용 오차를 키운다")
    ap.add_argument("--문턱", type=int, default=250, help="바탕 판정 문턱 0~255(기본 250). 바탕색 허용 오차 = 255 - 문턱")
    a = ap.parse_args(argv)
    if cv2 is None:
        공통.실패("OpenCV가 없습니다: .venv-cv/bin/python 으로 실행하세요")
    src, dst = 공통.작업폴더_경로(a.원본), 공통.작업폴더_경로(a.출력)
    im = cv2.imread(str(src))
    if im is None:
        공통.실패(f"그림을 읽을 수 없습니다: {src}")
    try:
        x0, y0, x1, y1 = [int(float(v)) for v in a.상자.split(",")]
    except ValueError:
        공통.실패(f"상자는 x0,y0,x1,y1 숫자 4개여야 합니다: {a.상자}")
    h, w = im.shape[:2]
    상자 = (max(0, x0), max(0, y0), min(w, x1), min(h, y1))
    if 상자[2] <= 상자[0] or 상자[3] <= 상자[1]:
        공통.실패(f"상자가 그림 밖이거나 비었습니다: {a.상자} (그림 {w}x{h})")
    bgcol = None
    if a.바탕:
        s = a.바탕.lstrip("#")
        if len(s) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in s):
            공통.실패(f"--바탕은 #RRGGBB 꼴이어야 합니다: {a.바탕}")
        bgcol = (int(s[4:], 16), int(s[2:4], 16), int(s[:2], 16))  # BGR
    rgba, 박스 = cutout(im, 상자, thr=a.문턱, bgcol=bgcol)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), rgba)
    확 = dst.with_name(dst.stem + "_확인.png")
    cv2.imwrite(str(확), 확인그림(rgba))
    print(f"[완료] {dst} (원본 좌표 상자 {박스}) · 확인 그림 {확}")


if __name__ == "__main__":
    main()
