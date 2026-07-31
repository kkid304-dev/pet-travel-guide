import sys
import requests
import time
import re
from config import KEY

sys.stdout.reconfigure(encoding="utf-8")

list_url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

category = {
    "12": "관광지", "14": "문화시설", "15": "축제공연",
    "25": "여행코스", "28": "레포츠", "32": "숙박",
    "38": "쇼핑", "39": "음식점",
}

plan = {
    "관광지": ("12", 60),
    "숙박": ("32", 30),
    "음식점": ("39", 30),
    "쇼핑": ("38", 50),
}

BREED_KEYWORDS = [
    "말티즈", "푸들", "치와와", "리트리버", "진돗개", "시츄", "포메라니안",
    "웰시코기", "불독", "비숑", "요크셔테리어", "닥스훈트", "골든리트리버",
    "래브라도", "시바견", "슈나우저", "코카스파니엘", "사모예드", "허스키", "보더콜리",
]

# judge()의 ⚠️ 분기(정보 미확인/조건 확인 필요)는 무게와 무관하므로 스캔용 임의값 사용
PET_WEIGHT_PLACEHOLDER = 10.0


def judge(condition_text, pet_weight):
    if condition_text == "":
        return "⚠️ 정보 미확인 (방문 전 문의 권장)"

    if "불가" in condition_text and "가능" not in condition_text:
        return "❌ 동반 불가"

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


unmatched = []                                   # judge() ⚠️ 케이스: [카테고리, 이름, 판정, 원문조건]
breed_hits = {b: 0 for b in BREED_KEYWORDS}
field_filled = {"acmpyPsblCpam": 0, "acmpyNeedMtr": 0, "etcAcmpyInfo": 0}
total_places = 0
api_call_count = 0

for name, (code, limit) in plan.items():
    print(f"=== {name} 수집 시작 ===")
    params = {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": limit, "pageNo": 1,
        "arrange": "O", "lDongRegnCd": "11",
        "contentTypeId": code,
    }
    response = requests.get(list_url, params=params)
    api_call_count += 1

    try:
        items_box = response.json()["response"]["body"]["items"]
    except ValueError:
        print(name, "목록 응답 이상:", response.text[:200])
        continue

    if items_box == "":
        print(name, "결과 없음, 건너뜀")
        continue

    items = items_box["item"]
    print(name, "목록 수집 완료:", len(items), "곳")

    for i, place in enumerate(items):
        cid = place["contentid"]
        title = place["title"]

        detail_params = {
            "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
            "_type": "json", "contentId": cid,
        }
        time.sleep(0.2)
        r = requests.get(detail_url, params=detail_params)
        api_call_count += 1

        try:
            items_box = r.json()["response"]["body"]["items"]
        except ValueError:
            print(cid, "상세 응답 이상:", r.text[:200])
            continue

        total_places += 1

        if items_box == "":
            cpam, need, etc, acmpy_type = "", "", "", ""
        else:
            detail_item = items_box["item"][0]
            cpam = detail_item.get("acmpyPsblCpam", "")
            need = detail_item.get("acmpyNeedMtr", "")
            etc = detail_item.get("etcAcmpyInfo", "")
            acmpy_type = detail_item.get("acmpyTypeCd", "")

        if cpam:
            field_filled["acmpyPsblCpam"] += 1
        if need:
            field_filled["acmpyNeedMtr"] += 1
        if etc:
            field_filled["etcAcmpyInfo"] += 1

        condition = cpam if cpam else acmpy_type
        verdict = judge(condition, PET_WEIGHT_PLACEHOLDER)

        if verdict.startswith("⚠️"):
            unmatched.append((name, title, verdict, condition))

        combined_text = " ".join([cpam, need, etc])
        for breed in BREED_KEYWORDS:
            if breed in combined_text:
                breed_hits[breed] += 1

        if i % 20 == 0:
            print(i, "/", len(items), "처리 중...")

print("\n=== 스캔 완료: 결과 파일 저장 중 ===")

with open("condition_scan.txt", "w", encoding="utf-8") as f:
    f.write("=== 조건 텍스트 대량 스캔 결과 ===\n")
    f.write(f"총 조사 장소: {total_places}곳 (API 호출 {api_call_count}건)\n\n")

    f.write("--- 필드별 값 존재 비율 ---\n")
    for field, count in field_filled.items():
        pct = (count / total_places * 100) if total_places else 0
        f.write(f"{field}: {count}/{total_places} ({pct:.1f}%)\n")

    f.write(f"\n--- judge() ⚠️ 판정 비율 ---\n")
    unmatched_pct = (len(unmatched) / total_places * 100) if total_places else 0
    f.write(f"⚠️ 판정: {len(unmatched)}/{total_places} ({unmatched_pct:.1f}%)\n")

    f.write("\n--- 견종 키워드 등장 횟수 ---\n")
    for breed, count in sorted(breed_hits.items(), key=lambda x: -x[1]):
        if count > 0:
            f.write(f"{breed}: {count}건\n")
    total_breed_mentions = sum(breed_hits.values())
    f.write(f"(견종명이 언급된 장소 총 {total_breed_mentions}건 — 중복 카운트 가능)\n")

    f.write("\n--- ⚠️ 판정 문장 목록 (카테고리 | 장소명 | 판정 | 원문 조건) ---\n")
    for cat, title, verdict, condition in unmatched:
        f.write(f"[{cat}] {title} | {verdict}\n")

    f.write("\n--- ⚠️ 조건 문장 반복 빈도 (상위) ---\n")
    condition_counts = {}
    for cat, title, verdict, condition in unmatched:
        key = condition if condition else "(빈 값)"
        condition_counts[key] = condition_counts.get(key, 0) + 1
    for text, count in sorted(condition_counts.items(), key=lambda x: -x[1])[:20]:
        f.write(f"{count}건 | {text}\n")

print("condition_scan.txt 저장 완료")
print(f"총 {total_places}곳 조사, API 호출 {api_call_count}건, ⚠️ 판정 {len(unmatched)}건 ({unmatched_pct:.1f}%)")
