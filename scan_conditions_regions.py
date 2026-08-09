import sys
import time
from config import KEY
from prototype import judge  # v3 judge 재사용 (main()으로 분리되어 있어 import 시 실행 안 됨)
from api_helpers import api_get, is_quota_error

sys.stdout.reconfigure(encoding="utf-8")

list_url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

REGIONS = {"부산": "26", "제주": "50", "강원": "51"}

PLAN = {
    "관광지": ("12", 60),
    "숙박": ("32", 30),
    "음식점": ("39", 30),
    "쇼핑": ("38", 50),
}

# 같은 지점(체인·프랜차이즈)이 동일 문구를 그대로 쓰는 경우가 많아 장소 수만 세면
# 다양성을 과대평가함 → 한 문장이 이 비율 이상을 차지하면 "체인성 반복 의심"으로 표시
CHAIN_SUSPECT_RATIO = 0.3
CHAIN_SUSPECT_MIN_COUNT = 5

PET_WEIGHT_PLACEHOLDER = 10.0


def load_seoul_known_warn_texts():
    """v2 시절 서울 ⚠️ 목록(condition_scan.txt)을 v3로 재판정해,
    v3에서도 여전히 ⚠️로 남는 문장 집합을 '이미 알려진 패턴' 기준선으로 삼는다."""
    with open("condition_scan.txt", encoding="utf-8") as f:
        lines = f.readlines()

    start = lines.index("--- ⚠️ 판정 문장 목록 (카테고리 | 장소명 | 판정 | 원문 조건) ---\n") + 1
    end = lines.index("\n", start)

    known = set()
    for line in lines[start:end]:
        line = line.strip()
        if not line:
            continue
        verdict_part = line.split("|", 1)[1].strip()
        if "조건 확인 필요:" in verdict_part:
            text = verdict_part.split("조건 확인 필요:", 1)[1].strip()
        else:
            text = ""
        if judge(text, PET_WEIGHT_PLACEHOLDER).startswith("⚠️"):
            known.add(text)
    return known


SEOUL_KNOWN_WARN_TEXTS = load_seoul_known_warn_texts()

report_lines = []
total_api_calls = 0
quota_hit = False


def collect_region(region_name, region_code):
    global total_api_calls, quota_hit
    region_places = []  # (category, title, condition, verdict)

    for cat_name, (cat_code, limit) in PLAN.items():
        if quota_hit:
            break
        params = {
            "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
            "_type": "json", "numOfRows": limit, "pageNo": 1,
            "arrange": "O", "lDongRegnCd": region_code,
            "contentTypeId": cat_code,
        }
        data, err = api_get(list_url, params)
        total_api_calls += 1
        if err:
            print(region_name, cat_name, "목록 응답 이상:", err)
            if is_quota_error(err):
                quota_hit = True
                print("!! API 일일 한도로 보임. 중단합니다.")
            continue

        items_box = data["response"]["body"]["items"]
        if items_box == "":
            continue
        items = items_box["item"]
        print(f"{region_name}/{cat_name} 목록 수집 완료: {len(items)}곳")

        for i, place in enumerate(items):
            if quota_hit:
                break
            detail_params = {
                "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
                "_type": "json", "contentId": place["contentid"],
            }
            time.sleep(0.2)
            data, err = api_get(detail_url, detail_params)
            total_api_calls += 1
            if err:
                print(place["contentid"], "상세 응답 이상:", err)
                if is_quota_error(err):
                    quota_hit = True
                    print("!! API 일일 한도로 보임. 중단합니다.")
                continue
            items_box = data["response"]["body"]["items"]

            if items_box == "":
                cpam, acmpy_type = "", ""
            else:
                detail_item = items_box["item"][0]
                cpam = detail_item.get("acmpyPsblCpam", "")
                acmpy_type = detail_item.get("acmpyTypeCd", "")

            condition = cpam if cpam else acmpy_type
            verdict = judge(condition, PET_WEIGHT_PLACEHOLDER)
            region_places.append((cat_name, place["title"], condition, verdict))

            if i % 20 == 0:
                print(i, "/", len(items), "처리 중...")

    return region_places


for region_name, region_code in REGIONS.items():
    if quota_hit:
        print(f"{region_name} 건너뜀 (API 일일 한도)")
        break
    print(f"\n=== {region_name} 수집 시작 ===")
    places = collect_region(region_name, region_code)
    total = len(places)

    verdict_counts = {"✅": 0, "❌": 0, "⚠️": 0, "?": 0}
    text_counts = {}
    for cat_name, title, condition, verdict in places:
        if verdict.startswith("✅"):
            verdict_counts["✅"] += 1
        elif verdict.startswith("❌"):
            verdict_counts["❌"] += 1
        elif verdict.startswith("⚠️"):
            verdict_counts["⚠️"] += 1
        else:
            verdict_counts["?"] += 1
        text_counts[condition] = text_counts.get(condition, 0) + 1

    unique_texts = len(text_counts)
    diversity_ratio = (unique_texts / total * 100) if total else 0

    report_lines.append(f"=== {region_name} ({total}곳, API 호출 누적 {total_api_calls}건) ===")
    report_lines.append(
        f"판정 분포: ✅ {verdict_counts['✅']} / ⚠️ {verdict_counts['⚠️']} / ❌ {verdict_counts['❌']}"
    )
    report_lines.append(f"고유 문장 수: {unique_texts}개 (장소 수 대비 {diversity_ratio:.1f}%)")

    report_lines.append("--- 반복 문장 전체 (체인성 반복 의심 포함) ---")
    for text, count in sorted(text_counts.items(), key=lambda x: -x[1]):
        label = text if text else "(빈 값)"
        ratio = count / total if total else 0
        suspect = " ← 체인성 반복 의심" if (count >= CHAIN_SUSPECT_MIN_COUNT and ratio >= CHAIN_SUSPECT_RATIO) else ""
        report_lines.append(f"{count}곳 | {label}{suspect}")

    report_lines.append("--- v3로도 ⚠️인 문장 중 서울 표본엔 없던 신규 패턴 ---")
    new_patterns = set()
    for cat_name, title, condition, verdict in places:
        if verdict.startswith("⚠️") and condition not in SEOUL_KNOWN_WARN_TEXTS:
            new_patterns.add(condition or "(빈 값)")
    if new_patterns:
        for text in sorted(new_patterns):
            report_lines.append(f"[신규] {text}")
    else:
        report_lines.append("(신규 패턴 없음 — 서울에서 이미 확인된 패턴으로 커버됨)")

    report_lines.append("")

with open("condition_scan_regions.txt", "w", encoding="utf-8") as f:
    f.write(f"=== 지역 확장 스캔 결과 (부산·제주·강원, API 호출 총 {total_api_calls}건) ===\n")
    if quota_hit:
        f.write("** API 일일 한도로 중단됨. 일부 지역/카테고리가 누락됐을 수 있음 **\n")
    f.write("\n")
    f.write("\n".join(report_lines))

print(f"\n완료. condition_scan_regions.txt 저장됨. 총 API 호출 {total_api_calls}건")
