import sys
import time
from config import KEY
from prototype import judge  # v3 judge 재사용
from api_helpers import api_get, is_quota_error

sys.stdout.reconfigure(encoding="utf-8")

list_url = "http://apis.data.go.kr/B551011/KorPetTourService2/areaBasedList2"
detail_url = "http://apis.data.go.kr/B551011/KorPetTourService2/detailPetTour2"

# 쇼핑(38)은 전국 8,647곳으로 사실상 획일적(전구역 동반가능)이라 제외.
# 축제공연(15)·여행코스(25)는 전국 0곳이라 제외.
PLAN = {
    "관광지": "12",
    "문화시설": "14",
    "레포츠": "28",
    "숙박": "32",
    "음식점": "39",
}

PET_WEIGHT_PLACEHOLDER = 10.0
RAW_FILE = "condition_scan_nationwide_raw.txt"

total_api_calls = 0
quota_hit = False


def api_call(url, params):
    """실패 시 None 반환. 한도 초과로 보이는 오류면 quota_hit을 True로 세팅."""
    global total_api_calls, quota_hit
    total_api_calls += 1
    data, err = api_get(url, params)
    if err:
        if is_quota_error(err):
            quota_hit = True
            print(f"!! 일일 한도로 보이는 오류 감지 (누적 {total_api_calls}건): {err}")
        else:
            print(f"경고 - 호출 실패(건너뜀, 누적 {total_api_calls}건): {err}")
        return None
    return data


# 이전 실행에서 이미 처리된 contentId를 읽어와 이어서 진행 (한도 초과로 여러 날에
# 걸쳐 나눠 돌려야 하는 상황을 대비한 재개 로직)
places = []  # (category, content_id, title, condition, verdict)
done_ids = set()
try:
    with open(RAW_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            cat_name, content_id, title, condition, verdict = parts
            places.append((cat_name, content_id, title, condition, verdict))
            done_ids.add(content_id)
except FileNotFoundError:
    pass

if done_ids:
    print(f"이전 실행 결과 {len(done_ids)}곳 발견 — 이어서 진행합니다.")

raw_file = open(RAW_FILE, "a", encoding="utf-8")

for cat_name, cat_code in PLAN.items():
    if quota_hit:
        break

    data = api_call(list_url, {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": 1, "pageNo": 1,
        "arrange": "O", "contentTypeId": cat_code,
    })
    if data is None:
        continue
    cat_total = data["response"]["body"]["totalCount"]

    data = api_call(list_url, {
        "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
        "_type": "json", "numOfRows": cat_total, "pageNo": 1,
        "arrange": "O", "contentTypeId": cat_code,
    })
    if data is None:
        continue
    items_box = data["response"]["body"]["items"]
    if items_box == "":
        print(cat_name, "결과 없음, 건너뜀")
        continue
    items = items_box["item"]
    print(f"=== {cat_name} 목록 수집 완료: {len(items)}곳 (전국) ===")

    for i, place in enumerate(items):
        if quota_hit:
            break
        content_id = place["contentid"]
        if content_id in done_ids:
            continue
        try:
            time.sleep(0.2)
            data = api_call(detail_url, {
                "serviceKey": KEY, "MobileOS": "ETC", "MobileApp": "PetTest",
                "_type": "json", "contentId": content_id,
            })
            if data is None:
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
            places.append((cat_name, content_id, place["title"], condition, verdict))
            done_ids.add(content_id)

            # 조건 텍스트에 개행/탭이 섞여 오는 경우가 있어 그대로 쓰면 한 레코드가
            # 여러 줄로 쪼개져 재개 로직이 깨짐 — 저장 전 한 줄로 정리
            def _flatten(s):
                return " ".join(str(s).split())

            raw_file.write(
                f"{_flatten(cat_name)}\t{content_id}\t{_flatten(place['title'])}\t"
                f"{_flatten(condition)}\t{_flatten(verdict)}\n"
            )
            raw_file.flush()

        except Exception as e:
            print(f"경고 - 레코드 처리 중 오류(건너뜀): {place.get('title', '?')} — {e}")
            continue

        if i % 50 == 0:
            print(i, "/", len(items), "처리 중... (누적 API 호출", total_api_calls, "건)")

raw_file.close()

total = len(places)
verdict_counts = {"✅": 0, "❌": 0, "⚠️": 0, "?": 0}
text_counts = {}
for cat_name, content_id, title, condition, verdict in places:
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

with open("condition_scan_nationwide.txt", "w", encoding="utf-8") as f:
    f.write("=== 전국 스캔 결과 (쇼핑 제외, 누적) ===\n")
    f.write(f"조사 완료: {total}곳 / 목표 1,048곳 (이번 실행 API 호출 {total_api_calls}건)\n")
    if quota_hit:
        f.write("** 일일 API 한도로 보이는 오류로 중단됨. 나머지는 다음날 이어서 진행 필요 (재개 지원됨) **\n")
    f.write(f"\n판정 분포: ✅ {verdict_counts['✅']} / ⚠️ {verdict_counts['⚠️']} / ❌ {verdict_counts['❌']}\n")
    f.write(f"고유 문장 수: {unique_texts}개 (장소 수 대비 {diversity_ratio:.1f}%)\n")

    f.write("\n--- 반복 상위 30개 문장 ---\n")
    for text, count in sorted(text_counts.items(), key=lambda x: -x[1])[:30]:
        label = text if text else "(빈 값)"
        f.write(f"{count}곳 | {label}\n")

    f.write("\n--- v3로도 ⚠️인 문장 전체 ---\n")
    for cat_name, content_id, title, condition, verdict in places:
        if verdict.startswith("⚠️"):
            f.write(f"[{cat_name}] {title} | {verdict}\n")

print(f"\n완료. condition_scan_nationwide.txt / condition_scan_nationwide_raw.txt 저장됨.")
print(f"누적 조사: {total}곳 / 이번 실행 API 호출 {total_api_calls}건 / quota_hit={quota_hit}")
print(f"판정 분포: ✅ {verdict_counts['✅']} / ⚠️ {verdict_counts['⚠️']} / ❌ {verdict_counts['❌']}")
