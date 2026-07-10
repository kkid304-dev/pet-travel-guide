import requests
from config import KEY

url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
params = {
    "serviceKey": KEY,
    "MobileOS": "ETC",
    "MobileApp": "PetTest",
    "_type": "json",
    "numOfRows": 10,
    "pageNo": 1,
    "arrange": "C",
    "lDongRegnCd": "11",   # 서울
}

response = requests.get(url, params=params)
data = response.json()

items = data["response"]["body"]["items"]["item"]

print("=== 서울 반려동물 동반 가능 장소 ===")

detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

for place in items:
    print(place["title"], "|", place["addr1"])

    detail_params = {
        "serviceKey": KEY,
        "MobileOS": "ETC",
        "MobileApp": "PetTest",
        "_type": "json",
        "contentId": place["contentid"],   # ← 이 장소의 ID를 그대로 넣음
    }
    detail_response = requests.get(detail_url, params=detail_params)
    detail_data = detail_response.json()

    detail_item = detail_data["response"]["body"]["items"]["item"][0]
    condition = detail_item["acmpyPsblCpam"]
    if condition == "":
        condition = detail_item["acmpyTypeCd"]   # 동반 구분으로 대체
    if condition == "":
        condition = "동반 정보 미확인 (방문 전 문의 권장)"
    print("  └ 동반 조건:", condition)
    print()