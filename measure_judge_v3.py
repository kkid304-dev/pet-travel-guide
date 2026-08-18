import re
import sys
from prototype import judge

sys.stdout.reconfigure(encoding="utf-8")

# condition_scan.txt의 "⚠️ 판정 문장 목록" 섹션에서 원문 조건을 뽑아
# v3로 재판정했을 때 ⚠️ 비율이 얼마나 줄었는지 확인 (API 호출 없이 오프라인 측정)

PET_WEIGHT_PLACEHOLDER = 10.0

with open("condition_scan.txt", encoding="utf-8") as f:
    lines = f.readlines()

start = lines.index("--- ⚠️ 판정 문장 목록 (카테고리 | 장소명 | 판정 | 원문 조건) ---\n") + 1
end = lines.index("\n", start)

conditions = []
for line in lines[start:end]:
    line = line.strip()
    if not line:
        continue
    verdict_part = line.split("|", 1)[1].strip()
    if "조건 확인 필요:" in verdict_part:
        conditions.append(verdict_part.split("조건 확인 필요:", 1)[1].strip())
    else:
        conditions.append("")  # 정보 미확인(빈 값) 케이스

still_warning = 0
resolved = []

for text in conditions:
    verdict = judge(text, PET_WEIGHT_PLACEHOLDER)
    if verdict.startswith("⚠️"):
        still_warning += 1
    else:
        resolved.append((text, verdict))

before_pct = 100.0
after_pct = (still_warning / len(conditions) * 100) if conditions else 0

print(f"v2에서 ⚠️였던 문장: {len(conditions)}건 (100%)")
print(f"v3 재판정 후에도 ⚠️: {still_warning}건 ({after_pct:.1f}%)")
print(f"v3로 새로 해소된 문장: {len(resolved)}건 ({100 - after_pct:.1f}%)\n")

print("--- 새로 해소된 문장 ---")
for text, verdict in resolved:
    print(f"[{text or '(빈 값)'}] → {verdict}")

print("\n--- 여전히 ⚠️인 문장 (정책상 의도된 것 포함) ---")
for text in conditions:
    verdict = judge(text, PET_WEIGHT_PLACEHOLDER)
    if verdict.startswith("⚠️"):
        print(f"[{text or '(빈 값)'}] → {verdict}")
