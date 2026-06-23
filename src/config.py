"""환경 변수 기반 설정 로더.

`.env` 파일(있으면)과 OS 환경 변수에서 Content Understanding 접속 정보를 읽어온다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Content Understanding 실행에 필요한 설정값."""

    endpoint: str
    key: str | None
    analyzer_id: str
    completion_model: str
    embedding_model: str

    @property
    def use_api_key(self) -> bool:
        return bool(self.key)


def load_settings() -> Settings:
    """환경 변수에서 설정을 로드한다. 엔드포인트가 없으면 친절한 오류를 던진다."""

    endpoint = os.getenv("CONTENTUNDERSTANDING_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit(
            "CONTENTUNDERSTANDING_ENDPOINT 가 설정되지 않았습니다.\n"
            "  1) infra/setup_azure.sh 를 실행해 리소스를 만들고 .env 를 생성하거나\n"
            "  2) .env.example 를 복사해 .env 를 직접 채워주세요."
        )

    return Settings(
        endpoint=endpoint,
        key=os.getenv("CONTENTUNDERSTANDING_KEY", "").strip() or None,
        analyzer_id=os.getenv("WORK_ORDER_ANALYZER_ID", "trade_work_order").strip(),
        completion_model=os.getenv("COMPLETION_MODEL", "gpt-4.1").strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large").strip(),
    )


def build_credential(settings: Settings):
    """API 키가 있으면 AzureKeyCredential, 없으면 DefaultAzureCredential 을 반환."""

    if settings.use_api_key:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(settings.key)  # type: ignore[arg-type]

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()
