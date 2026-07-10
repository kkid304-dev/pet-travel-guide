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
for place in items:
    print(place["title"], "|", place["addr1"])

print("서울 전체:", data["response"]["body"]["totalCount"], "곳")