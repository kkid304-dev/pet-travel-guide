import sys
from prototype import judge

sys.stdout.reconfigure(encoding="utf-8")

# 지역/전국 스캔에서 실제로 발견된 문제들 + 리뷰에서 잡힌 순서 버그에 대한 회귀 테스트.
# API 호출 없이 오프라인으로 judge()만 검증한다.

WINTER_SEASON_TEXT = (
    "- 대형견은 여름에만 동반 가능합니다.(야외테이블 이용 가능 계절, "
    "보호자의 각별한 주의를 요청드립니다.)\n"
    "- 고양이나 다른 반려동물도 입장 가능하나, 동물에 따라 필요한 경우 "
    "케이지를 이용해야 합니다."
)

# (설명, 조건문, 반려동물 무게kg, is_dangerous_breed, 기대하는 판정 접두어)
cases = [
    (
        "대형견 예외+계절 조건 - 소형견은 무관하게 허용돼야 함",
        WINTER_SEASON_TEXT, 10.0, None, "✅",
    ),
    (
        "같은 문장, 대형견은 계절 조건이라 확답 대신 유보",
        WINTER_SEASON_TEXT, 30.0, None, "⚠️",
    ),
    (
        "맹견=입마개 조건은 배제가 아니라 준비물, 견종 무관 확신 있게 ✅",
        "전 견종 출입 가능(맹견의 경우, 입마개 착용 필수)", 10.0, None, "✅",
    ),
    (
        "맹견 '제외' + 견종 미입력 → 여전히 유보",
        "맹견 제외 전 견종 동반 가능", 10.0, None, "⚠️",
    ),
    (
        "맹견 '제외' + 맹견 아님(False) → 확정 ✅",
        "맹견 제외 전 견종 동반 가능", 10.0, False, "✅",
    ),
    (
        "맹견 '제외' + 맹견 맞음(True) → 확정 ❌",
        "맹견 제외 전 견종 동반 가능", 10.0, True, "❌",
    ),
    (
        "순서 버그 회귀: 맹견 제외+무게 동시 등장, 맹견이 무게보다 우선해야 함",
        "맹견 제외 15kg 이하 동반 가능", 8.0, True, "❌",
    ),
    (
        "'전견종'(공백 없음) 정규화",
        "전견종 동반 가능", 10.0, None, "✅",
    ),
    (
        "'전 경종'(오타) 정규화",
        "전 경종 동반 가능", 10.0, None, "✅",
    ),
    (
        "'제한없음'도 긍정 신호로 인식",
        "제한없음", 10.0, None, "✅",
    ),
    (
        "안내견은 이제 유보가 아니라 확정 ❌ (일반 반려견 기준)",
        "맹인 안내견", 10.0, None, "❌",
    ),
    (
        "저정보 문장('반려견'만)은 친절한 메시지로 유보",
        "반려견", 10.0, None, "⚠️",
    ),
    (
        "접종 언급 시 준비물 안내가 덧붙는지 확인",
        "맹견 제외 예방접종 완료한 전 견종 동반 가능", 10.0, False, "✅",
    ),
    (
        "순수 크기 단어 배타 조건(소형견만)은 기존처럼 무게로 우선 판정",
        "7kg이내 소형견만 동반 가능", 10.0, None, "❌",
    ),
    (
        "kg 없는 순수 크기 단어 배타 조건은 여전히 그대로 배타 판정",
        "소형견만 가능", 30.0, None, "❌",
    ),
]

failed = 0
for desc, text, weight, breed, expected_prefix in cases:
    verdict = judge(text, weight, breed)
    ok = verdict.startswith(expected_prefix)
    status = "PASS" if ok else "FAIL"
    if not ok:
        failed += 1
    print(f"[{status}] {desc}\n  → {verdict}\n")

# 준비물 문구가 실제로 붙었는지 별도 확인 (판정 접두어만으론 못 잡음)
prep_verdict = judge("맹견 제외 예방접종 완료한 전 견종 동반 가능", 10.0, False)
if "준비물" not in prep_verdict:
    print("[FAIL] 준비물 안내 누락\n  →", prep_verdict, "\n")
    failed += 1
else:
    print("[PASS] 준비물 안내 포함 확인\n  →", prep_verdict, "\n")

total = len(cases) + 1
print(f"{total - failed}/{total} 통과")
if failed:
    sys.exit(1)
