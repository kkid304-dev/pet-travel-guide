import requests
from config import KEY
def judge(condition_text, pet_size):
    # 정보가 없는 경우
    if condition_text == "":
        return "⚠️ 정보 미확인 (방문 전 문의 권장)"

    # 명확히 가능한 경우
    if "전 견종" in condition_text or "전구역" in condition_text:
        return "✅ 동반 가능"

    # 크기 제한이 있는 경우: 입력한 크기가 조건에 언급되면 가능
    if pet_size in condition_text:
        return "✅ 동반 가능 (" + condition_text + ")"

    # 그 외에는 조건부로 안내
    return "⚠️ 조건 확인 필요: " + condition_text


pet_size = input("반려동물 크기를 입력하세요 (소형/중형/대형): ")
print(pet_size, "기준으로 검색합니다\n")

url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
params = {
    "serviceKey": KEY,
    "MobileOS": "ETC",
    "MobileApp": "PetTest",
    "_type": "json",
    "numOfRows": 18,
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

    print("  └", judge(condition, pet_size))
    print()