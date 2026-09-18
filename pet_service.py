from concurrent.futures import ThreadPoolExecutor, as_completed

from config import KEY
from judge import judge
from api_helpers import api_get

LIST_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
KEYWORD_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/searchKeyword2"
DETAIL_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"
LDONG_CODE_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/ldongCode2"

REGION_CODES = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "51", "충북": "43", "충남": "44",
    "전북": "52", "전남": "46", "경북": "47", "경남": "48",
    "제주": "50",
}

CATEGORY_CODES = {
    "관광지": "12", "문화시설": "14", "레포츠": "28",
    "숙박": "32", "쇼핑": "38", "음식점": "39",
}

CATEGORY_LABELS = {code: name for name, code in CATEGORY_CODES.items()}
CATEGORY_LABELS.update({"15": "축제공연", "25": "여행코스"})


_SIGUNGU_CACHE = {}  # {지역명: {시군구명: 코드}} — 장소 데이터가 아닌 코드 테이블이라 앱 프로세스 생존 기간 동안 메모리 보관


def _fetch_sigungu_codes(region):
    data, err = api_get(LDONG_CODE_URL, {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "lDongRegnCd": REGION_CODES[region], "numOfRows": 100, "pageNo": 1,
    })
    if data is None:
        return region, {}
    items_box = data["response"]["body"].get("items", "")
    if items_box == "":
        return region, {}
    codes = {item["name"]: item["code"] for item in items_box["item"]}
    return region, codes


def warm_sigungu_cache():
    """앱 기동 시 1회 호출. 17개 지역의 시군구 코드 테이블을 병렬로 받아 메모리에 채워둔다."""
    with ThreadPoolExecutor(max_workers=8) as executor:
        for region, codes in executor.map(_fetch_sigungu_codes, REGION_CODES):
            _SIGUNGU_CACHE[region] = codes


def get_sigungu_codes(region):
    """region의 {시군구명: 코드} 테이블 반환. warm_sigungu_cache 실행 전이면 그 자리에서 1회 채움."""
    if region not in REGION_CODES:
        return {}
    if region not in _SIGUNGU_CACHE:
        _, codes = _fetch_sigungu_codes(region)
        _SIGUNGU_CACHE[region] = codes
    return _SIGUNGU_CACHE[region]


def _fetch_detail_condition(content_id):
    data, err = api_get(DETAIL_URL, {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "contentId": content_id,
    })
    if data is None:
        return "", err
    items_box = data["response"]["body"]["items"]
    if items_box == "":
        return "", None
    item = items_box["item"][0]
    condition = item.get("acmpyPsblCpam", "")
    if not condition:
        condition = item.get("acmpyTypeCd", "")
    return condition, None


def search_places(region, category, pet_weight, is_dangerous_breed, limit=12, page=1, sigungu_code=None, keyword=None):
    """지역·카테고리·시군구·장소명으로 목록을 조회하고, 상세 조건을 병렬로 가져와 judge() 판정까지 붙여 반환.

    상세 조회는 장소당 API 호출 1건이라 numOfRows개를 순차로 돌리면 왕복 지연이 그대로
    누적된다 (12곳이면 12번 왕복). ThreadPoolExecutor로 동시에 쏴서 체감 대기시간을
    가장 느린 1건 수준으로 줄인다.

    page는 "더보기"에서 다음 페이지를 이어 받아오는 데 쓴다 (이미 받은 페이지는 재호출하지 않음).
    sigungu_code는 선택 사항 (드롭다운에서 이미 코드값으로 넘어옴, None/빈 값이면 지역 전체).
    keyword가 있으면 areaBasedList2 대신 searchKeyword2를 쓴다 — 이 오퍼레이션이 반려동반
    데이터셋에만 국한되어 있고(같은 키워드로 KorService2 조회 결과와 비교해 확인됨) 지역·
    시군구·카테고리 필터를 그대로 받아들이는 것을 실측으로 확인했음. 목록을 다 받아온 뒤
    부분일치로 거르는 방식보다 API가 직접 걸러주는 이 방식이 더 정확하고 페이지네이션도
    자연스럽게 맞아떨어진다.

    반환: (결과 리스트, 전체 개수, 에러메시지 또는 None)
    """
    params = {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": limit, "pageNo": page, "arrange": "O",
    }
    if region in REGION_CODES:
        params["lDongRegnCd"] = REGION_CODES[region]
        if sigungu_code:
            params["lDongSignguCd"] = sigungu_code
    if category in CATEGORY_CODES:
        params["contentTypeId"] = CATEGORY_CODES[category]

    if keyword:
        params["keyword"] = keyword
        data, err = api_get(KEYWORD_URL, params)
    else:
        data, err = api_get(LIST_URL, params)
    if data is None:
        return [], 0, err

    body = data["response"]["body"]
    total_count = body.get("totalCount", 0)
    items_box = body["items"]
    if items_box == "":
        return [], total_count, None
    items = items_box["item"]

    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_idx = {
            executor.submit(_fetch_detail_condition, place["contentid"]): i
            for i, place in enumerate(items)
        }
        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            condition, _detail_err = future.result()
            place = items[i]
            results[i] = {
                "title": place["title"],
                "addr": place.get("addr1", ""),
                "category": CATEGORY_LABELS.get(place.get("contenttypeid"), "기타"),
                "condition": condition or "(정보 없음)",
                "verdict": judge(condition, pet_weight, is_dangerous_breed),
            }

    return results, total_count, None
