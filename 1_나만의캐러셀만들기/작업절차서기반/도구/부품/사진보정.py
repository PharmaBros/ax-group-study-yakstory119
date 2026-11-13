"""사진보정 — 원본 장에서 얹힌 글 잉크(+그림자)만 지워 깔개 사진을 만든다.

출처: R/2026-11-10_디자인시스템/도구/_tools_A/retouch.py (push-pull 메움, 2026-11-10 판)
      R/새방식_공용도구/사진보정/fix2.py (질감 위 흰 글 inpaint) · fix4.py (판 곡면 맞춤)
      R/2026-11-10_디자인시스템/도구/_tools_A/fix_cover3.py (판 전체 3차 곡면)
쓰기: .venv-cv/bin/python 도구/부품/사진보정.py 원본.jpg 출력_보정.jpg --글 x0,y0,x1,y1 --방식 판|질감|메움
머리카락(글 상자 밖으로 이어진 가장 큰 어두운 덩어리)과 --보호 상자는 손대지 않는다(공통 교훈 5·6).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import 공통  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

try:
    import cv2
    import numpy as np
except ImportError:  # 시스템 python3: --help 만 가능
    cv2 = None

문턱 = 14  # 판 곡면과 이만큼 다르면 잉크(fix_cover3 값)


# ─────────── push-pull 메움 (retouch.py) ───────────
def _down(a):
    h, w = a.shape[:2]
    if h % 2:
        a = np.concatenate([a, a[-1:]], 0)
    if w % 2:
        a = np.concatenate([a, a[:, -1:]], 1)
    return a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]


def _up(est, h, w):
    ch = []
    for c in range(est.shape[2]):
        im = Image.fromarray(est[..., c].astype(np.float32)).resize(
            (est.shape[1] * 2, est.shape[0] * 2), Image.BILINEAR)
        ch.append(np.asarray(im)[:h, :w])
    return np.stack(ch, -1)


def pushpull(img, valid):
    """img HxWxC float, valid HxW (1=믿는 픽셀). 모르는 곳을 둘레 평균으로 메운다."""
    H, W = valid.shape
    lv = [(img * valid[..., None], valid.astype(np.float64))]
    while min(lv[-1][1].shape) > 2:
        s, w = lv[-1]
        lv.append((_down(s), _down(w)))
    est = None
    for s, w in reversed(lv):
        cur = np.where(w[..., None] > 1e-6, s / np.maximum(w[..., None], 1e-6), 0)
        if est is not None:
            up = _up(est, cur.shape[0], cur.shape[1])
            cur = np.where(w[..., None] > 0.5, cur, up)
        est = cur
    return est[:H, :W]


def erase(arr, mask, seed=1, blur_edge=3):
    """arr uint8 HxWx3, mask bool. 마스크 안을 둘레에서 메운 색 + 둘레 결 잡음으로 채움."""
    a = arr.astype(np.float64)
    fill = pushpull(a, (~mask).astype(np.float64))
    ring = 확장(mask, 12) & ~mask
    blur = np.asarray(Image.fromarray(arr).filter(ImageFilter.GaussianBlur(2))).astype(np.float64)
    sd = (a - blur)[ring].std() if ring.sum() > 50 else 1.5
    fill = fill + np.random.default_rng(seed).normal(0, sd, fill.shape[:2])[..., None]
    al = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), blur_edge)[..., None]
    return np.clip(a * (1 - al) + fill * al, 0, 255).astype(np.uint8)


# ─────────── 공용 ───────────
def 확장(m, r):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.dilate(m.astype(np.uint8), k) > 0


def 상자_읽기(문자, w, h):
    try:
        x0, y0, x1, y1 = [int(float(v)) for v in 문자.split(",")]
    except ValueError:
        공통.실패(f"상자는 x0,y0,x1,y1 숫자 4개여야 합니다: {문자}")
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        공통.실패(f"상자가 그림 밖이거나 비었습니다: {문자} (그림 {w}x{h})")
    return x0, y0, x1, y1


def 상자_마스크(상자들, h, w):
    m = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in 상자들:
        m[y0:y1, x0:x1] = True
    return m


def 보호_마스크(im, 글, 보호상자):
    """--보호 상자 + 머리카락(글 상자 밖으로 이어진 가장 큰 어두운 덩어리, 판이 밝을 때만)."""
    L = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)[:, :, 0]
    띠 = 확장(글, 40) & ~글
    기준 = np.median(L[띠]) if 띠.any() else 0
    한계 = min(110, 기준 - 50)
    p = 보호상자.copy()
    if 한계 > 0:
        n, lab, _, _ = cv2.connectedComponentsWithStats((L < 한계).astype(np.uint8), connectivity=8)
        밖 = lab[~글]
        ids, cnt = np.unique(밖[밖 > 0], return_counts=True)
        if len(ids):
            p |= 확장(lab == ids[np.argmax(cnt)], 15)
    return p


def 곡면(im, 표본, 영역, d=3):
    """표본 픽셀로 채널별 d차 곡면을 맞춰 영역 안 값을 돌려준다(영역 밖은 원본)."""
    h, w = 표본.shape
    poly = lambda x, y: np.stack([x ** i * y ** j for i in range(d + 1) for j in range(d + 1 - i)], 1)
    ys, xs = np.nonzero(표본)
    if len(ys) < 20:
        공통.실패("판 색을 맞출 둘레 픽셀이 모자랍니다 — --글 상자를 판 안쪽으로 잡으세요")
    sel = np.random.default_rng(0).choice(len(ys), min(60000, len(ys)), replace=False)
    X = poly(xs[sel] / w, ys[sel] / h)
    my, mx = np.nonzero(영역)
    XM = poly(mx / w, my / h)
    out = im.astype(np.float32).copy()
    for c in range(3):
        k, *_ = np.linalg.lstsq(X, im[ys[sel], xs[sel], c].astype(np.float64), rcond=None)
        out[my, mx, c] = XM @ k
    return out


def 잉크_찾기(im, 글, 보호):
    """글 상자 둘레 판으로 곡면을 맞추고(1차), 글 상자 안 잉크가 아닌 픽셀까지 넣어 다시 맞춰(2차) 곡면과 다른 픽셀=잉크."""
    영역 = 확장(글, 60)
    표본 = 영역 & ~글 & ~보호
    for _ in range(2):
        S = 곡면(im, 표본, 영역)
        잉크 = 글 & ~보호 & (np.abs(im.astype(np.float32) - S).max(axis=2) > 문턱)
        표본 = 영역 & ~확장(잉크, 3) & ~보호
    return 확장(잉크, 4) & 글 & ~보호, S


def 보정(im, 글상자, 보호상자, 방식):
    """im BGR uint8 → (보정 그림, 지운 픽셀 수)"""
    h, w = im.shape[:2]
    글 = 상자_마스크(글상자, h, w)
    보호 = 보호_마스크(im, 글, 상자_마스크(보호상자, h, w))
    if 방식 == "질감":  # 흰 글 픽셀+그림자까지 넓혀 inpaint (fix2)
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        마스크 = 확장(글 & (hsv[:, :, 2] > 215) & (hsv[:, :, 1] < 60), 9) & 글 & ~보호
        결과 = cv2.inpaint(im, 마스크.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
    else:
        마스크, S = 잉크_찾기(im, 글, 보호)
        if 방식 == "판":  # 곡면 색으로 바꿈 (fix4·fix_cover3)
            al = cv2.GaussianBlur(마스크.astype(np.float32), (0, 0), 1.5)[..., None]
            결과 = np.clip(im * (1 - al) + S * al, 0, 255).astype(np.uint8)
        else:  # 메움: 둘레 색 + 결 잡음 (retouch)
            결과 = erase(im, 마스크)
    return np.where(보호[..., None], im, 결과), int(마스크.sum())


def 확인그림(out, 글상자):
    """판 색(글 상자 안 중앙값) 기준 명암 8배 — 평균 기준이면 밝은 판이 포화돼 자국이 숨는다(교훈 6)."""
    글 = 상자_마스크(글상자, *out.shape[:2])
    판 = np.median(out[글], axis=0)
    return np.clip(128 + (out.astype(np.float32) - 판) * 8, 0, 255).astype(np.uint8)


def main(argv=None):
    ap = 공통.한글ArgumentParser(description="원본 장에서 글 상자 안 글 잉크(+그림자)만 지워 깔개 사진을 만든다. 머리카락·--보호 상자는 손대지 않는다.")
    ap.add_argument("원본", help="원본 jpg")
    ap.add_argument("출력", help="출력 jpg (이름은 _보정.jpg 로 끝내기)")
    ap.add_argument("--글", action="append", required=True, metavar="x0,y0,x1,y1", help="글이 있는 상자(원본 픽셀, 여러 번 가능)")
    ap.add_argument("--방식", required=True, choices=["판", "질감", "메움"],
                    help="판=매끈한 판·벽(3차 곡면) / 질감=질감 위 흰 글(inpaint) / 메움=둘레 색+결 잡음(push-pull)")
    ap.add_argument("--보호", action="append", default=[], metavar="x0,y0,x1,y1", help="손대지 않을 상자(얼굴·제품 등, 여러 번 가능)")
    ap.add_argument("--확인", action="store_true", help="판 색 기준 명암 8배 그림 <출력>_확인.jpg 도 저장")
    a = ap.parse_args(argv)
    if cv2 is None:
        공통.실패("OpenCV가 없습니다: .venv-cv/bin/python 으로 실행하세요")
    src, dst = 공통.작업폴더_경로(a.원본), 공통.작업폴더_경로(a.출력)
    im = cv2.imread(str(src))
    if im is None:
        공통.실패(f"그림을 읽을 수 없습니다: {src}")
    h, w = im.shape[:2]
    글상자 = [상자_읽기(s, w, h) for s in a.글]
    보호상자 = [상자_읽기(s, w, h) for s in a.보호]
    if not dst.stem.endswith("_보정"):
        print(f"[경고] 출력 이름이 _보정으로 끝나지 않습니다: {dst.name} (원본과 헷갈리지 않게)", file=sys.stderr)
    결과, n = 보정(im, 글상자, 보호상자, a.방식)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), 결과, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"[완료] 글 잉크 {n}픽셀 지움 → {dst}")
    if a.확인:
        확 = dst.with_name(dst.stem + "_확인.jpg")
        cv2.imwrite(str(확), 확인그림(결과, 글상자), [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"[확인] {확}")


if __name__ == "__main__":
    main()
