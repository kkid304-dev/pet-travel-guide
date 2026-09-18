"""첫 화면 지역 선택용 인라인 SVG 지도.

korea_sido_map.json에 미리 계산해둔 17개 시도 경계 path를 읽어서 그대로 반환한다.
좌표 계산(위경도 -> SVG 좌표 투영, 단순화, 작은 부속섬 제거, 라벨 위치)은
빌드 시점에 shapely로 한 번만 수행했고, 런타임에는 이 정적 JSON만 읽으므로
Flask 앱에는 지리 정보 라이브러리 의존성이 없다.

데이터 출처 (라이선스 체인)
- 원본: 통계청 SGIS(Statistics Korea) 행정동 경계 — 공공누리 제1유형(출처표시)
- 1차 가공: vuski/admdongkor (https://github.com/vuski/admdongkor) — CC BY 4.0,
  SGIS 원본을 시계열로 보정 · 확장
- 2차 가공: DevMinGeonPark/mapcn-kr (https://github.com/DevMinGeonPark/mapcn-kr) — MIT,
  admdongkor 데이터를 시도/시군구 단위로 dissolve
- 3차 가공(본 프로젝트): mapcn-kr의 광주·전남 통합 폴리곤을, 시군구 데이터에서
  광주 5개 자치구(동구·서구·남구·북구·광산구)와 전남 22개 시군을 이름으로 구분해
  다시 둘로 분리(union) — REGION_CODES의 17개 시도 체계와 맞추기 위함.
  이후 좌표 단순화(shapely simplify) 및 이 지도 크기에서 보이지 않는
  작은 부속 섬(가장 큰 폴리곤 대비 0.8% 미만 면적)을 제거.

원본 SGIS 데이터가 공공누리 1유형이므로 출처표시 의무만 있고(가공 여부 무관 승계),
동일조건변경허락 등 추가 제약은 없음. 출처는 README에도 표기.
"""

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "korea_sido_map.json"
_data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def korea_map_regions():
    """[{name, d, cx, cy, show_label}, ...] — 지도에 그릴 17개 시도 polygon."""
    return _data["regions"]


def map_view_box():
    return _data["view_box"]
