import requests

# 실제로 확인된 한도 초과 오류에서 나온 단어들 ("LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
# "일일 서비스 요청제한 횟수 초과 에러") 기준
QUOTA_KEYWORDS = ("LIMIT", "EXCEED", "QUOTA", "한도", "초과")


def parse_response(r):
    """공공데이터포털 응답을 안전하게 해석. (data, None) 또는 (None, 오류설명)을 반환."""
    try:
        data = r.json()
    except ValueError:
        return None, f"JSON 파싱 실패: {r.text[:200]}"

    # 포털 공통 오류 포맷 (실제 관측: {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {...}}})
    if "OpenAPI_ServiceResponse" in data:
        h = data["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        return None, f"포털 오류: {h.get('returnAuthMsg') or h.get('errMsg')}"
    if "cmmMsgHeader" in data:  # 최상위로 오는 변형 대비
        h = data["cmmMsgHeader"]
        return None, f"포털 오류: {h.get('returnAuthMsg') or h.get('errMsg')}"

    if "response" not in data:
        return None, f"예상 밖 응답 형식: {str(data)[:200]}"

    result_code = data["response"].get("header", {}).get("resultCode")
    if result_code not in ("0000", "00", "0"):
        result_msg = data["response"].get("header", {}).get("resultMsg")
        return None, f"resultCode={result_code} {result_msg}"

    return data, None


def is_quota_error(err_message):
    return any(k.lower() in err_message.lower() for k in QUOTA_KEYWORDS)


def api_get(url, params, timeout=15):
    """requests.get + parse_response를 합친 안전 호출. (data, err) 반환. data가 None이면 err에 사유가 담김."""
    try:
        r = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as e:
        return None, f"네트워크 오류: {e}"
    return parse_response(r)
