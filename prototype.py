import requests
import re
from config import KEY
def judge(condition_text, pet_weight):
    if condition_text == "":
        return "⚠️ 정보 미확인 (방문 전 문의 권장)"
    
    if "불가" in condition_text and "가능" not in condition_text:
        return "❌ 동반 불가"

    # 무게 제한 찾기: "10kg 이하" 같은 패턴
    match = re.search(r"(\d+)\s*kg", condition_text, re.IGNORECASE)
    if match:
        limit = float(match.group(1))
        if pet_weight <= limit:
            return "✅ 동반 가능 (제한: " + condition_text + ")"
        else:
            return "❌ 동반 불가 (제한: " + condition_text + ")"

    if "전 견종" in condition_text or "전구역" in condition_text:
        return "✅ 동반 가능"

    return "⚠️ 조건 확인 필요: " + condition_text

region = input("지역을 입력하세요 (서울/부산/인천/제주/...): ")

region_code = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "29", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "51", "충북": "43", "충남": "44",
    "전북": "52", "전남": "46", "경북": "47", "경남": "48",
    "제주": "50",
}

want = input("찾는 종류를 입력하세요 (관광지/음식점/숙박/쇼핑/전체): ")
type_code = {
    "관광지": "12", "문화시설": "14", "레포츠": "28",
    "숙박": "32", "쇼핑": "38", "음식점": "39",
}

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
     
}

if region in region_code:
    params["lDongRegnCd"] = region_code[region]

if want in type_code:
    params["contentTypeId"] = type_code[want]

response = requests.get(url, params=params)
data = response.json()


items = data["response"]["body"]["items"]["item"]

print("===", region, want, "반려동물 동반 가능 장소 ===")

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

    items_box = detail_data["response"]["body"]["items"]
    if items_box == "":
        condition = ""   # 상세 정보 자체가 없는 장소
    else:
        detail_item = items_box["item"][0]
        condition = detail_item["acmpyPsblCpam"]
        if condition == "":
            condition = detail_item["acmpyTypeCd"]
    print("  └", judge(condition, pet_weight))
    print()
print("전체:", data["response"]["body"]["totalCount"], "곳")