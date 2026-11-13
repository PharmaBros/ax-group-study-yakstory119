"""부품마다 견본.json을 디자인시스템 json의 `json_자리` 경로에 넣는다(json_자리 칸은 뺀 객체를 넣음).

출처: R/새방식_공용도구/방법_새방식_디자인시스템.md 6절 코드 · R/2026-11-10_캐러셀2/json_put.py, 2026-11-10 판.
같은 자리(또는 한쪽이 다른 쪽의 윗 자리)에 두 부품이 겹치면 아무것도 쓰지 않고 실패한다.

사용
  python3 -I 도구/부품/견본넣기.py <부품 폴더들의 상위 폴더> <디자인시스템.json>          # 바뀔 자리 목록만
  python3 -I 도구/부품/견본넣기.py <부품 폴더들의 상위 폴더> <디자인시스템.json> --write  # 저장(indent 2, 한글 그대로)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import 공통  # noqa: E402


def 견본_읽기(상위: Path) -> list[tuple[list[str], dict, str]]:
    """[(자리 경로 조각, 견본 객체(json_자리 뺌), 부품 이름)]. 자리가 겹치면 실패."""
    결과 = []
    for f in sorted(상위.glob("*/견본.json")):
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            공통.실패(f"{f.parent.name}/견본.json을 읽지 못했습니다(JSON 오류): {e}")
        자리 = v.pop("json_자리", None)
        if not 자리 or not isinstance(자리, str):
            공통.실패(f"{f.parent.name}/견본.json에 `json_자리`가 없습니다.")
        결과.append((자리.split("."), v, f.parent.name))
    for i, (a, _, 이름a) in enumerate(결과):
        for b, _, 이름b in 결과[i + 1:]:
            if a[:len(b)] == b or b[:len(a)] == a:
                공통.실패(f"같은 자리에 겹칩니다: {이름a}({'.'.join(a)}) ↔ {이름b}({'.'.join(b)})")
    return 결과


def 넣기(d: dict, 견본들) -> list[str]:
    """d에 견본을 넣고 줄별 결과(새로/바뀜/같음)를 돌려준다."""
    보고 = []
    for 키들, v, 이름 in 견본들:
        cur = d
        for k in 키들[:-1]:
            cur = cur.setdefault(k, {})
            if not isinstance(cur, dict):
                공통.실패(f"{이름}: 자리 중간 '{k}'가 객체가 아닙니다: {'.'.join(키들)}")
        끝 = 키들[-1]
        상태 = "새로" if 끝 not in cur else ("같음" if cur[끝] == v else "바뀜")
        cur[끝] = v
        보고.append(f"{상태:<2} {'.'.join(키들)}  ← {이름}")
    return 보고


def main(argv=None) -> int:
    ap = 공통.한글ArgumentParser(description="부품 견본.json을 디자인시스템 json의 json_자리에 넣는다. 기본은 바뀔 자리 목록만 보여 준다.")
    ap.add_argument("상위폴더", help="부품 폴더들이 들어 있는 폴더 (작업 폴더 기준)")
    ap.add_argument("디자인시스템", help="견본을 넣을 디자인시스템 json")
    ap.add_argument("--write", action="store_true", help="json 파일에 저장")
    a = ap.parse_args(argv)
    상위, 대상 = 공통.작업폴더_경로(a.상위폴더), 공통.작업폴더_경로(a.디자인시스템)
    for p, 뜻 in ((상위, "부품 상위 폴더"), (대상, "디자인시스템 json")):
        if not p.exists():
            공통.실패(f"{뜻}를 찾을 수 없습니다: {p}")
    견본들 = 견본_읽기(상위)
    if not 견본들:
        공통.실패(f"견본.json이 있는 부품 폴더가 없습니다: {상위}")
    raw = 대상.read_text(encoding="utf-8")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        공통.실패(f"디자인시스템 json을 읽지 못했습니다(JSON 오류): {e}")
    print("\n".join(넣기(d, 견본들)))
    if a.write:
        대상.write_text(json.dumps(d, ensure_ascii=False, indent=2) + ("\n" if raw.endswith("\n") else ""), encoding="utf-8")
        print(f"저장: {대상} (부품 {len(견본들)}개)")
    else:
        print(f"(화면만 — 부품 {len(견본들)}개. 저장하려면 --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
