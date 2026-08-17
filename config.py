import os
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ.get("KTO_API_KEY")
if not KEY:
    raise RuntimeError(
        "KTO_API_KEY 환경변수가 없습니다. 로컬에서는 .env 파일에 KTO_API_KEY=... 를 "
        "추가하세요 (.env.example 참고). 배포 환경에서는 플랫폼의 환경변수 설정에 추가하세요."
    )
