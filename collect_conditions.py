import requests
import time
from config import KEY

list_url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

plan = {
    "관광지": ("12", 60),
    "숙박": ("32", 30),
    "음식점": ("39", 30),
    "쇼핑": ("38", 50),
}
open("conditions.txt", "w", encoding="utf-8").close()


for name, (code, limit) in plan.items():
    print(f"=== {name} 수집 시작 ===")
    content_ids = []
    params = {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": limit, "pageNo": 1,
        "arrange": "O", "lDongRegnCd": "11",
        "contentTypeId": code,
    }
    
    
    response = requests.get(list_url, params=params)
    items_box = response.json()["response"]["body"]["items"]       # ← 상자까지만 받고
    if items_box == "":                                            # ← 먼저 검사
        print(name, "결과 없음, 건너뜀")
        continue
    items = items_box["item"]                                      # ← 안전 확인 후 열기
    for place in items:
        content_ids.append(place["contentid"])
    print(name, "목록 수집 완료:", len(content_ids), "곳")

    counts = {}

    for i, cid in enumerate(content_ids):
        detail_params = {
            "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
            "_type": "json", "contentId": cid,
        }

        time.sleep(0.2)
        r = requests.get(detail_url, params=detail_params)

        try:
            items_box = r.json()["response"]["body"]["items"]
        except ValueError:
            print(cid, "응답 이상:", r.text[:200])
            continue

        if items_box == "":
            text = "(정보 없음)"
        else:
            text = items_box["item"][0]["acmpyPsblCpam"]
            if text == "":
                text = items_box["item"][0]["acmpyTypeCd"]
            if text == "":
                text = "(빈 값)"

        counts[text] = counts.get(text, 0) + 1

        if i % 50 == 0:
            print(i, "/", len(content_ids), "처리 중...")
       

    print("\n=== 조건 문장 순위 ===")

   
    with open("conditions.txt", "a", encoding="utf-8") as f:
        f.write(f"\n=== {name} ===\n")
        for text, count in sorted(counts.items(), key=lambda x: -x[1]):
            line = str(count) + "곳 | " + text
            print(line)
            f.write(line + "\n")