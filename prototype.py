import requests
import re
from config import KEY

# 소형/중형/대형 kg 경계: 반려동물 등록제·펫보험에서 흔히 쓰는 구간을 따름
# (10kg 이하 소형, 10~25kg 중형, 25kg 초과 대형)
def pet_size_label(pet_weight):
    if pet_weight <= 10:
        return "소형"
    if pet_weight <= 25:
        return "중형"
    return "대형"


def judge(condition_text, pet_weight):
    text = re.sub(r"\s+", " ", condition_text).strip()
    text = text.replace("전 견동", "전 견종")  # 실데이터에서 발견한 오타 정규화
    # "대/중/소형" 같은 축약 표기를 크기 단어 매칭이 되도록 펼침
    text = re.sub(r"대\s*[/·,]?\s*중\s*[/·,]?\s*소형", "대형/중형/소형", text)

    if text == "":
        return "⚠️ 정보 미확인 (방문 전 문의 권장)"

    if "안내견" in text or "보조견" in text:
        return "⚠️ 안내견만 가능 (일반 반려동물은 별도 확인 필요)"

    if "털날림" in text:
        return "⚠️ 품종 특성 확인 필요: " + text

    if "불가" in text and "가능" not in text:
        return "❌ 동반 불가"

    pet_size = pet_size_label(pet_weight)

    if "대형견 제외" in text or "대형 제외" in text:
        if pet_size == "대형":
            return "❌ 동반 불가 (대형견 제외)"

    if "맹견" in text:
        return "⚠️ 맹견 해당 여부 확인 필요 (맹견 제외 조건, 견종 미입력): " + text

    # 무게 제한: "10kg 이하" / "10kg미만" 같은 패턴 (이하=포함, 미만=미포함)
    match = re.search(r"(\d+)\s*kg\s*(이하|미만)?", text, re.IGNORECASE)
    if match:
        limit = float(match.group(1))
        strict = match.group(2) == "미만"
        ok = pet_weight < limit if strict else pet_weight <= limit
        if ok:
            return "✅ 동반 가능 (제한: " + text + ")"
        else:
            return "❌ 동반 불가 (제한: " + text + ")"

    mentioned_sizes = [size for size in ("소형", "중형", "대형") if size in text]
    if mentioned_sizes:
        if pet_size in mentioned_sizes:
            return "✅ 동반 가능 (" + pet_size + "견 조건 충족)"
        else:
            return "❌ 동반 불가 (" + "/".join(mentioned_sizes) + "만 허용)"

    if "이동장" in text or "켄넬" in text:
        return "✅ 동반 가능 (준비물: 이동장/켄넬 필요 — " + text + ")"

    if "접종" in text or "증빙서류" in text or "서류" in text:
        return "✅ 동반 가능 (준비물: 접종 증빙서류 필요 — " + text + ")"

    if "일부구역" in text or "일부 구역" in text:
        return "✅ 동반 가능 (구역 제한 있음 — " + text + ")"

    if text.startswith("가능") or "가능(" in text:
        return "✅ 동반 가능 (" + text + ")"

    if "전 견종" in text or "전구역" in text:
        return "✅ 동반 가능"

    return "⚠️ 조건 확인 필요: " + text

def main():
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


if __name__ == "__main__":
    main()