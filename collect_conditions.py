import time
from config import KEY
from api_helpers import api_get, is_quota_error

list_url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

plan = {
    "관광지": ("12", 60),
    "숙박": ("32", 30),
    "음식점": ("39", 30),
    "쇼핑": ("38", 50),
}
open("conditions.txt", "w", encoding="utf-8").close()

quota_hit = False

for name, (code, limit) in plan.items():
    if quota_hit:
        break
    print(f"=== {name} 수집 시작 ===")
    content_ids = []
    params = {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": limit, "pageNo": 1,
        "arrange": "O", "lDongRegnCd": "11",
        "contentTypeId": code,
    }

    data, err = api_get(list_url, params)
    if err:
        print(name, "목록 조회 실패:", err)
        if is_quota_error(err):
            quota_hit = True
            print("!! API 일일 한도로 보임. 중단합니다.")
        continue
    items_box = data["response"]["body"]["items"]
    if items_box == "":
        print(name, "결과 없음, 건너뜀")
        continue
    items = items_box["item"]
    for place in items:
        content_ids.append(place["contentid"])
    print(name, "목록 수집 완료:", len(content_ids), "곳")

    counts = {}

    for i, cid in enumerate(content_ids):
        if quota_hit:
            break
        detail_params = {
            "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
            "_type": "json", "contentId": cid,
        }

        time.sleep(0.2)
        data, err = api_get(detail_url, detail_params)
        if err:
            print(cid, "응답 이상:", err)
            if is_quota_error(err):
                quota_hit = True
                print("!! API 일일 한도로 보임. 중단합니다.")
            continue
        items_box = data["response"]["body"]["items"]

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