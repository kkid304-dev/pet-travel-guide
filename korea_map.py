"""첫 화면 지역 선택용 인라인 SVG 지도 좌표 생성.

실제 행정구역 경계선을 트레이싱하거나 외부 지도 데이터/이미지를 가져온 것이 아니라,
17개 시도를 상대적 위치에 맞춰 격자 타일로 배치한 자체 제작 개략도(카토그램)다.
외부 소스를 전혀 쓰지 않았기 때문에 라이선스 확인이 필요 없다.
"""

CELL = 48
TILE = 42
RADIUS = 8
MARGIN = 10

# (col, row) — col: 서→동, row: 북→남. 제주는 바다를 나타내기 위해 한 행 띄워 배치.
# pet_service.REGION_CODES의 17개 키와 정확히 일치해야 함.
GRID = {
    "서울": (2, 0), "강원": (3, 0),
    "인천": (1, 1), "경기": (2, 1),
    "충남": (1, 2), "세종": (2, 2), "충북": (3, 2), "경북": (4, 2),
    "전북": (1, 3), "대전": (2, 3), "대구": (3, 3),
    "광주": (1, 4), "경남": (3, 4), "울산": (4, 4),
    "전남": (1, 5), "부산": (4, 5),
    "제주": (1, 7),
}


def _rounded_rect_path(x, y, w, h, r):
    return (
        f"M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} "
        f"V{y + h - r} A{r},{r} 0 0 1 {x + w - r},{y + h} "
        f"H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} "
        f"V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z"
    )


def korea_map_regions():
    """[{name, d, cx, cy}, ...] — 지도에 그릴 17개 시도 타일."""
    regions = []
    for name, (col, row) in GRID.items():
        x = MARGIN + col * CELL
        y = MARGIN + row * CELL
        regions.append({
            "name": name,
            "d": _rounded_rect_path(x, y, TILE, TILE, RADIUS),
            "cx": x + TILE / 2,
            "cy": y + TILE / 2,
        })
    return regions


def map_view_box():
    max_col = max(c for c, _ in GRID.values())
    max_row = max(r for _, r in GRID.values())
    width = MARGIN * 2 + (max_col + 1) * CELL - (CELL - TILE)
    height = MARGIN * 2 + (max_row + 1) * CELL - (CELL - TILE)
    return f"0 0 {width} {height}"
