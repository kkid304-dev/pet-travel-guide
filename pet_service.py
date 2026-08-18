from concurrent.futures import ThreadPoolExecutor, as_completed

from config import KEY
from judge import judge
from api_helpers import api_get

LIST_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
DETAIL_URL = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

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


def search_places(region, category, pet_weight, is_dangerous_breed, limit=12):
    """지역·카테고리로 목록을 조회하고, 상세 조건을 병렬로 가져와 judge() 판정까지 붙여 반환.

    상세 조회는 장소당 API 호출 1건이라 numOfRows개를 순차로 돌리면 왕복 지연이 그대로
    누적된다 (12곳이면 12번 왕복). ThreadPoolExecutor로 동시에 쏴서 체감 대기시간을
    가장 느린 1건 수준으로 줄인다.

    반환: (결과 리스트, 전체 개수, 에러메시지 또는 None)
    """
    params = {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": limit, "pageNo": 1, "arrange": "O",
    }
    if region in REGION_CODES:
        params["lDongRegnCd"] = REGION_CODES[region]
    if category in CATEGORY_CODES:
        params["contentTypeId"] = CATEGORY_CODES[category]

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
