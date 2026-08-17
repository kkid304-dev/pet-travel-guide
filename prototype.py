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

# "{크기}견 ... (제외|불가|안됨|금지)"처럼 크기 단어 바로 뒤(쉼표/마침표/괄호 전까지) 15자
# 이내에 배제 단어가 나오면 그 크기를 배제 대상으로 본다. 절 경계(,.())에서 창을 끊어서
# "소형견 전용 ... 대형견 불가"처럼 한 문장에 서로 다른 크기가 반대 의미로 섞여 있어도
# 엉뚱한 크기까지 배제로 오인하지 않게 한다.
SIZE_EXCLUDE_RE = re.compile(
    r"(소형|중형|대형)견?\s*(?:은|는)?\s*[^,.()]{0,15}?(?:제외|불가능|불가|안됨|금지)"
)
# "{크기}은 ~만 가능" + 뒤에 "다른 반려동물/그 외/이외" 같은 잔여 허용 어구가 있으면
# 그 크기만 예외 조건(계절 등)이 걸린 것이지 전체를 그 크기 전용으로 읽으면 안 됨.
SIZE_EXCEPTION_RE = re.compile(r"(소형|중형|대형)견?은\s*[^.]*만\s*(동반\s*)?가능")


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


def _weight_verdict(text, pet_weight):
    """"10kg 이하"/"10kg미만"/"㎏" 같은 무게 제한 패턴을 찾아 판정 문자열을 반환.
    문장에 무게 조건이 없으면 None."""
    match = re.search(r"(\d+)\s*(?:kg|㎏)\s*(이하|미만)?", text, re.IGNORECASE)
    if not match:
        return None
    limit = float(match.group(1))
    strict = match.group(2) == "미만"
    ok = pet_weight < limit if strict else pet_weight <= limit
    if ok:
        return "✅ 동반 가능 (제한: " + text + ")"
    return "❌ 동반 불가 (제한: " + text + ")"


def _size_verdict(text, pet_weight, pet_size):
    """크기 단어(소형/중형/대형)가 얽힌 조건을 "배제 대상"과 "허용 대상"으로 나눠 판단한다.
    문장에 크기 단어가 전혀 없으면(무게 숫자도 없으면) None.

    예전에는 "대형견 제외"라는 정확한 문구만 찾는 좁은 규칙(3번)과, 크기 단어가 있으면
    무조건 "그 크기만 허용"으로 읽는 넓은 규칙(옛 8번)이 따로 있었는데, 후자가 "대형견
    제외 전 견종 가능"처럼 배제 의미로 쓰인 크기 단어까지 허용 목록으로 오독했다
    (지역 확장 스캔의 계절예외 버그와 동일한 실패 패턴, 실 사례: 답다니수국밭).
    또 "소형견 전용...대형견 불가" 같은 문장은 배제 대상이 좁은데(대형만) 5번의 넓은
    "불가 있고 가능 없음" 규칙에 먼저 걸려 전체가 배제로 오판됐다(실 사례: 반디빌리지,
    행복한하루 — 정작 그 펜션이 받는 소형견에게 ❌가 나감). 그래서 배제/허용을 먼저
    분리해서 보고, 배제 대상이 아니면 남은 무게 조건까지 확인한 뒤에야 확정한다."""
    # 같은 크기 단어가 문장 안에서 여러 번 나오는데 그중 일부만 배제 문맥이면
    # (예: "1~9번 중·소형견 사이트 - 10~16번 대형견 전용(중·소형견 불가)"처럼 구역별로
    # 신호가 엇갈리는 경우) 확신 있게 배제로 단정하지 않는다 — 모든 언급이 배제
    # 문맥일 때만 배제 대상으로 인정한다 (실 사례: 미산분교 캠핑장 회귀 방지).
    exclude_candidates = SIZE_EXCLUDE_RE.findall(text)
    candidate_counts = {size: exclude_candidates.count(size) for size in set(exclude_candidates)}
    exclude_sizes = {size for size, c in candidate_counts.items() if c >= text.count(size)}
    # 신호가 엇갈려서(일부 언급만 배제 문맥) 배제 대상 인정을 보류한 크기 — 이건
    # "배제 신호가 아예 없음"과 다르다. 아래로 흘려보내면 mentioned_sizes 배타 목록이
    # "대형견 불가"라고 쓰인 문장의 대형견한테까지 확신에 찬 ✅를 내버릴 수 있다
    # (신호 엇갈림 가드를 우회하는 4번째 재발 형태). 내 반려견이 바로 그 애매한
    # 크기라면 확답 대신 유보한다.
    ambiguous_sizes = {size for size, c in candidate_counts.items() if c < text.count(size)}

    if pet_size in exclude_sizes:
        return "❌ 동반 불가 (" + "/".join(sorted(exclude_sizes)) + " 제외 조건)"
    if pet_size in ambiguous_sizes:
        return "⚠️ 조건 확인 필요 (구역/조건별로 다르게 보임): " + text
    if exclude_sizes:
        weight_verdict = _weight_verdict(text, pet_weight)
        if weight_verdict is not None:
            return weight_verdict
        return "✅ 동반 가능 (" + "/".join(sorted(exclude_sizes)) + " 외 별도 제한 없음): " + text

    exception_match = SIZE_EXCEPTION_RE.search(text)
    if exception_match and ("다른 반려동물" in text or "그 외" in text or "이외" in text):
        restricted_size = exception_match.group(1)
        if pet_size == restricted_size:
            return "⚠️ 조건부 허용 (예외 조건 확인 필요): " + text
        return "✅ 동반 가능 (" + restricted_size + "견 외 별도 제한 언급 없음): " + text

    # 배제 표현 없이 숫자 무게만 있는 문장은 무게가 크기 단어보다 우선 (숫자가 더 정확한 정보)
    weight_verdict = _weight_verdict(text, pet_weight)
    if weight_verdict is not None:
        return weight_verdict

    # 배제 없이 특정 크기만 언급 — 배타적 허용 목록으로 본다 ("소형견만 가능" 류)
    mentioned_sizes = [size for size in ("소형", "중형", "대형") if size in text]
    if mentioned_sizes:
        if pet_size in mentioned_sizes:
            return "✅ 동반 가능 (" + pet_size + "견 조건 충족)"
        return "❌ 동반 불가 (" + "/".join(mentioned_sizes) + "만 허용)"

    return None


def _judge_core(text, pet_weight, is_dangerous_breed):
    # 0. 저정보 문장 / 빈 값 — 판정할 정보 자체가 없음
    if text == "" or text in LOW_INFO_TEXTS:
        label = text if text else "정보 없음"
        return "⚠️ 정보 부족 (방문 전 문의 권장): " + label

    # 1. 안내견/보조견만 언급 — 이 앱 사용자는 거의 항상 일반 반려견 보호자이므로
    # "확인 필요"로 유보하지 않고 확정 판정한다.
    # 알려진 한계: "대형견 제외 15kg 미만 입장 가능... 안내견도 입장 가능"처럼 안내견이
    # 배타 조건이 아니라 추가 허용 조항으로만 붙는 복합 문장에서는 과잉확신 오판 위험이
    # 있음(실 사례: 메이즈랜드). 안내견 언급 자체가 드물어 v3.1로 보류.
    if "안내견" in text or "보조견" in text:
        return "❌ 일반 반려견 불가 (안내견/보조견만 가능)"

    # 2~4. 특수 카테고리(품종 특성 / 크기 / 맹견)는 반드시 5번(불가&가능없음)
    # 같은 일반 규칙보다 먼저 봐야 한다. "맹견 동반 불가"처럼 특정 대상에만 한정된
    # "불가"가 있는데 일반 규칙이 먼저 걸리면, 실제로는 맹견만 배제하는 관대한
    # 정책을 전체 배제로 오판하게 된다 (전국 스캔에서 실제로 발견: 태화강 국가정원
    # "맹견 동반 불가"가 일반견까지 ❌로 처리되던 문제, 통인 1939 "털날림 많은 종은
    # 불가"가 전용 메시지 대신 일반 ❌로 처리되던 문제, 반디빌리지·행복한하루의
    # "대형견 불가"가 정작 그 업체가 받는 소형견까지 ❌로 처리되던 문제).
    if "털날림" in text:
        return "⚠️ 품종 특성 확인 필요: " + text

    pet_size = pet_size_label(pet_weight)

    size_verdict = _size_verdict(text, pet_weight, pet_size)
    if size_verdict is not None:
        # 크기 조건으로 이미 배제 확정(❌)이면 맹견 여부와 무관하게 그대로 반환.
        # 그런데 크기 조건을 통과했어도(✅) 문장에 "맹견"이 같이 있으면 아직 끝난 게
        # 아니다 — "맹견 및 대형견 제외 동반 가능"처럼 크기·맹견이 각자 독립적으로
        # 배제 조건일 수 있어서, 대형이 아니라고 끝내버리면 맹견 여부 확인을 건너뛰게
        # 된다. 이 경우엔 아래 맹견 분기가 마저 판단하도록 넘긴다.
        if size_verdict.startswith("❌") or "맹견" not in text:
            return size_verdict

    if "맹견" in text:
        is_exclude = any(w in text for w in DANGEROUS_BREED_EXCLUDE_WORDS)
        is_equipment = any(w in text for w in DANGEROUS_BREED_EQUIPMENT_WORDS)

        if is_equipment and not is_exclude:
            # "맹견은 입마개 착용 필수" 같은 조건은 배제가 아니라 준비물 추가일 뿐이라
            # 견종과 무관하게 입장 자체는 항상 가능하다.
            return "✅ 동반 가능 (맹견은 준비물 추가 필요): " + text

        # 그 외(명시적 배제, 또는 배제/장비 여부가 불명확한 모호한 언급)는
        # 실제로 맹견인지에 따라 결과가 갈리므로 입력값으로 확정한다.
        #
        # 주의: "맹견 제외"는 맹견만 배제할 뿐, 같은 문장에 무게 제한이 같이 있으면
        # (예: "맹견 제외 15kg 이하") 맹견이 아니어도 무게를 넘으면 여전히 배제된다.
        # 맹견 여부만 보고 바로 확정해버리면 이 무게 조건을 건너뛰게 되므로, 먼저
        # 무게 조건을 확인하고 그 결과와 맹견 여부를 같이 반영한다 (전국 스캔에서
        # 확인된 회귀: 11건 전부 "맹견 아님"으로 답한 초과 체중 반려동물에게 확신에
        # 찬 ✅가 나가던 문제).
        weight_verdict = _weight_verdict(text, pet_weight)
        if weight_verdict is not None:
            if weight_verdict.startswith("❌"):
                return weight_verdict  # 무게만으로 이미 배제 확정 — 맹견 여부와 무관
            if is_dangerous_breed is False:
                return weight_verdict  # 맹견 아님 + 무게 충족 → 확정 가능
            if is_dangerous_breed is True:
                return "❌ 동반 불가 (맹견 제외 조건 해당): " + text
            # 무게는 충족하지만 맹견 여부가 아직 불확실
            return "⚠️ 맹견 해당 여부 확인 필요: " + text

        if is_dangerous_breed is True:
            return "❌ 동반 불가 (맹견 제외 조건 해당): " + text
        if is_dangerous_breed is False:
            return "✅ 동반 가능 (맹견 제외 조건, 일반 견종은 무관): " + text
        return "⚠️ 맹견 해당 여부 확인 필요: " + text

    # 5. "불가"만 있고 "가능"이 없으면 그냥 전면 불가 — 위에서 특수 카테고리를
    # 전부 걸러낸 뒤에 도는 일반 규칙이라 더 이상 특정 대상 한정 "불가"를 삼키지 않는다.
    # 주의: "불가능"이라는 단어 자체에 "가능"이 부분문자열로 들어있어서, 다른 곳에
    # 진짜 "가능"이 없어도 "불가능"만으로 이 조건을 피해가 폴백 ⚠️로 새 버린다.
    # "불가능"을 지운 나머지에 "가능"이 남아있는지로 판단해야 진짜 불가만 잡는다.
    if "불가" in text and "가능" not in text.replace("불가능", ""):
        return "❌ 동반 불가"

    # 6. 무게·크기 조건은 위 `_size_verdict` 호출(2~4번 자리)에서 이미 처리됨 —
    # 여기 도달했다는 건 무게 숫자도, 크기 단어도 없는 문장이라는 뜻.

    if "이동장" in text or "켄넬" in text:
        return "✅ 동반 가능 (준비물: 이동장/켄넬 필요 — " + text + ")"

    if "일부구역" in text or "일부 구역" in text:
        return "✅ 동반 가능 (구역 제한 있음 — " + text + ")"

    if text.startswith("가능") or "가능(" in text:
        return "✅ 동반 가능 (" + text + ")"

    # 7. 긍정 신호 — 조건 없이 다 받아준다는 문장
    if any(sig in text for sig in POSITIVE_SIGNALS):
        return "✅ 동반 가능"

    # 8. 그 외엔 원문을 보여주고 유보
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