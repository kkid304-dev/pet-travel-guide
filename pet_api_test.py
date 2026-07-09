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
print(response.status_code)
print(response.json())