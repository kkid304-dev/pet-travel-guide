import requests
from config import KEY

url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"
params = {
    "serviceKey": KEY,
    "MobileOS": "ETC",
    "MobileApp": "PetTest",
    "contentId": "1059479",
    "_type": "json",
    "numOfRows": 10,
    "pageNo": 1,
}

response = requests.get(url, params=params)
import requests
from config import KEY

url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"
params = {
    "serviceKey": KEY,
    "MobileOS": "ETC",
    "MobileApp": "PetTest",
    "contentId": "1059479",
    "_type": "json",
    "numOfRows": 10,
    "pageNo": 1,
}

response = requests.get(url, params=params)
data = response.json()

# 상자 열기: response → body → items → item 리스트의 첫 번째
item = data["response"]["body"]["items"]["item"][0]

print("=== 반려동물 동반 정보 ===")
print("동반 구분:", item["acmpyTypeCd"])
print("동반 가능 동물:", item["acmpyPsblCpam"])
print("필요 사항:", item["acmpyNeedMtr"])
print("기타 정보:", item["etcAcmpyInfo"])