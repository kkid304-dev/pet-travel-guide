import requests
import re
from config import KEY
def judge(condition_text, pet_weight):
    if condition_text == "":
        return "⚠️ 정보 미확인 (방문 전 문의 권장)"

    # 무게 제한 찾기: "10kg 이하" 같은 패턴
    match = re.search(r"(\d+)\s*kg", condition_text)
    if match:
        limit = float(match.group(1))
        if pet_weight <= limit:
            return "✅ 동반 가능 (제한: " + condition_text + ")"
        else:
            return "❌ 동반 불가 (제한: " + condition_text + ")"

    if "전 견종" in condition_text or "전구역" in condition_text:
        return "✅ 동반 가능"

    return "⚠️ 조건 확인 필요: " + condition_text


pet_weight = float(input("반려동물 무게를 입력하세요 (kg, 숫자만): "))
print(pet_weight, "kg 기준으로 검색합니다\n")

url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
params = {
    "serviceKey": KEY,
    "MobileOS": "ETC",
    "MobileApp": "PetTest",
    "_type": "json",
    "numOfRows": 10,
    "pageNo": 1,
    "arrange": "O",
    "lDongRegnCd": "11",   # 서울
    "contentTypeId": "39",  
}

response = requests.get(url, params=params)
data = response.json()


items = data["response"]["body"]["items"]["item"]

print("=== 서울 반려동물 동반 가능 장소 ===")

detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

category = {
    "12": "관광지", "14": "문화시설", "15": "축제공연",
    "25": "여행코스", "28": "레포츠", "32": "숙박",
    "38": "쇼핑", "39": "음식점",
}

for place in items:
    print("[" + category.get(place["contenttypeid"], "기타") + "]", place["title"], "|", place["addr1"])

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
    
    print("  └", judge(condition, pet_weight))
    print()
print("전체:", data["response"]["body"]["totalCount"], "곳")