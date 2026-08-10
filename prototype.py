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


# 정보량이 거의 없어 판정 자체가 무의미한 문장들 — 하나씩 계속 늘어날 걸 알기 때문에
# 여기 없어도 결국 6번(폴백)에서 동일하게 ⚠️로 떨어짐. 이 목록은 메시지를 더 친절하게
# 만들어주는 지름길일 뿐, 정확성에는 영향 없음.
LOW_INFO_TEXTS = {
    "반려견", "반려동물", "반려묘", "반려견 및 반려묘", "개, 고양이",
    "전화문의", "문의요망", "사전 협의 필요", "사전 문의 필수",
}

DANGEROUS_BREED_EXCLUDE_WORDS = ("제외", "불가", "안됨", "금지", "X")
DANGEROUS_BREED_EQUIPMENT_WORDS = ("입마개", "목줄", "안전장치")
POSITIVE_SIGNALS = ("전 견종", "전구역", "제한없음", "모든 견종")


def _normalize(condition_text):
    text = re.sub(r"\s+", " ", condition_text).strip()
    text = text.replace("전 견동", "전 견종")  # 실데이터에서 발견한 오타 정규화
    text = text.replace("전견종", "전 견종")  # 공백 없는 표기 정규화
    text = text.replace("전 경종", "전 견종")  # "견종"을 "경종"으로 잘못 쓴 표기 정규화
    # "대/중/소형" 같은 축약 표기를 크기 단어 매칭이 되도록 펼침
    text = re.sub(r"대\s*[/·,]?\s*중\s*[/·,]?\s*소형", "대형/중형/소형", text)
    return text


def judge(condition_text, pet_weight, is_dangerous_breed=None):
    """
    is_dangerous_breed: 맹견 해당 여부. None=미입력(모름), True=맹견, False=맹견 아님.
    맹견 관련 문장은 이 값이 있어야만 확정 판정(✅/❌)이 나오고, 없으면 ⚠️로 유보한다.
    """
    text = _normalize(condition_text)
    verdict = _judge_core(text, pet_weight, is_dangerous_breed)

    # 판정과 별개로: 접종/등록 증빙이 필요하다는 언급이 있으면 준비물 안내를 덧붙인다.
    # 어차피 못 들어가는 곳(❌)에는 준비물 안내가 의미 없으므로 붙이지 않는다.
    if not verdict.startswith("❌") and any(k in text for k in ("접종", "등록", "증빙")):
        if "준비물" not in verdict:
            verdict += " (준비물: 예방접종 증명·동물등록 확인)"
    return verdict


def _judge_core(text, pet_weight, is_dangerous_breed):
    # 0. 저정보 문장 / 빈 값 — 판정할 정보 자체가 없음
    if text == "" or text in LOW_INFO_TEXTS:
        label = text if text else "정보 없음"
        return "⚠️ 정보 부족 (방문 전 문의 권장): " + label

    # 1. 안내견/보조견만 언급 — 이 앱 사용자는 거의 항상 일반 반려견 보호자이므로
    # "확인 필요"로 유보하지 않고 확정 판정한다.
    if "안내견" in text or "보조견" in text:
        return "❌ 일반 반려견 불가 (안내견/보조견만 가능)"

    # 2. "불가"만 있고 "가능"이 없으면 그냥 전면 불가
    if "불가" in text and "가능" not in text:
        return "❌ 동반 불가"

    if "털날림" in text:
        return "⚠️ 품종 특성 확인 필요: " + text

    pet_size = pet_size_label(pet_weight)

    if "대형견 제외" in text or "대형 제외" in text:
        if pet_size == "대형":
            return "❌ 동반 불가 (대형견 제외)"

    # 3. 맹견 — 무게 조건보다 먼저 봐야 한다. "맹견 제외 15kg 이하 동반 가능"처럼
    # 맹견 조건과 무게 조건이 같이 오는 문장에서 무게만 보고 먼저 확정해버리면
    # "맹견 제외"라는 핵심 조건을 건너뛰게 된다.
    if "맹견" in text:
        is_exclude = any(w in text for w in DANGEROUS_BREED_EXCLUDE_WORDS)
        is_equipment = any(w in text for w in DANGEROUS_BREED_EQUIPMENT_WORDS)

        if is_equipment and not is_exclude:
            # "맹견은 입마개 착용 필수" 같은 조건은 배제가 아니라 준비물 추가일 뿐이라
            # 견종과 무관하게 입장 자체는 항상 가능하다.
            return "✅ 동반 가능 (맹견은 준비물 추가 필요): " + text

        # 그 외(명시적 배제, 또는 배제/장비 여부가 불명확한 모호한 언급)는
        # 실제로 맹견인지에 따라 결과가 갈리므로 입력값으로 확정한다.
        if is_dangerous_breed is True:
            return "❌ 동반 불가 (맹견 제외 조건 해당): " + text
        if is_dangerous_breed is False:
            return "✅ 동반 가능 (맹견 제외 조건, 일반 견종은 무관): " + text
        return "⚠️ 맹견 해당 여부 확인 필요: " + text

    # 4. 무게 제한: "10kg 이하" / "10kg미만" 같은 패턴 (이하=포함, 미만=미포함)
    match = re.search(r"(\d+)\s*kg\s*(이하|미만)?", text, re.IGNORECASE)
    if match:
        limit = float(match.group(1))
        strict = match.group(2) == "미만"
        ok = pet_weight < limit if strict else pet_weight <= limit
        if ok:
            return "✅ 동반 가능 (제한: " + text + ")"
        else:
            return "❌ 동반 불가 (제한: " + text + ")"

    # "{크기}견은 ~만 가능"처럼 특정 크기에만 걸린 예외 조건이면서, 동시에 다른 반려동물도
    # 별도로 허용한다는 문구가 있는 경우 — 전체를 그 크기 전용으로 오독하면 안 됨 (지역 확장
    # 스캔에서 발견된 버그: 강원 "대형견은 여름에만 가능... 다른 반려동물도 입장 가능" 사례가
    # 소형견 기준으로 "❌ 대형만 허용"으로 확신에 차 오판됨)
    exception_match = re.search(r"(소형|중형|대형)견?은\s*[^.]*만\s*(동반\s*)?가능", text)
    if exception_match and ("다른 반려동물" in text or "그 외" in text or "이외" in text):
        restricted_size = exception_match.group(1)
        if pet_size == restricted_size:
            return "⚠️ 조건부 허용 (예외 조건 확인 필요): " + text
        return "✅ 동반 가능 (" + restricted_size + "견 외 별도 제한 언급 없음): " + text

    mentioned_sizes = [size for size in ("소형", "중형", "대형") if size in text]
    if mentioned_sizes:
        if pet_size in mentioned_sizes:
            return "✅ 동반 가능 (" + pet_size + "견 조건 충족)"
        else:
            return "❌ 동반 불가 (" + "/".join(mentioned_sizes) + "만 허용)"

    if "이동장" in text or "켄넬" in text:
        return "✅ 동반 가능 (준비물: 이동장/켄넬 필요 — " + text + ")"

    if "일부구역" in text or "일부 구역" in text:
        return "✅ 동반 가능 (구역 제한 있음 — " + text + ")"

    if text.startswith("가능") or "가능(" in text:
        return "✅ 동반 가능 (" + text + ")"

    # 5. 긍정 신호 — 조건 없이 다 받아준다는 문장
    if any(sig in text for sig in POSITIVE_SIGNALS):
        return "✅ 동반 가능"

    # 6. 그 외엔 원문을 보여주고 유보
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
    breed_answer = input("맹견에 해당하나요? (도사견/핏불 등, 예/아니오): ").strip()
    is_dangerous_breed = True if breed_answer == "예" else False if breed_answer == "아니오" else None
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
        print("  └", judge(condition, pet_weight, is_dangerous_breed))
        print()
    print("전체:", data["response"]["body"]["totalCount"], "곳")


if __name__ == "__main__":
    main()