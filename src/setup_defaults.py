"""Foundry 리소스의 기본 모델 매핑 설정 (1회성).

Content Understanding 의 prebuilt/custom 분석기는 gpt-4.1, gpt-4.1-mini,
text-embedding-3-large 배포가 필요하다. 이 스크립트는 실제 배포 이름을
분석기가 요구하는 표준 모델명에 매핑한다. Foundry 리소스당 1회만 실행하면 된다.

사용법:
    python -m src.setup_defaults
"""

from __future__ import annotations

import os

from azure.ai.contentunderstanding import ContentUnderstandingClient

from .config import build_credential, load_settings


def configure_defaults() -> None:
    settings = load_settings()
    client = ContentUnderstandingClient(endpoint=settings.endpoint, credential=build_credential(settings))

    model_deployments = {
        "gpt-4.1": os.getenv("GPT_4_1_DEPLOYMENT", "gpt-4.1"),
        "gpt-4.1-mini": os.getenv("GPT_4_1_MINI_DEPLOYMENT", "gpt-4.1-mini"),
        "text-embedding-3-large": os.getenv("TEXT_EMBEDDING_3_LARGE_DEPLOYMENT", "text-embedding-3-large"),
    }

    print("기본 모델 매핑을 설정합니다...")
    updated = client.update_defaults(model_deployments=model_deployments)

    print("설정 완료. 현재 매핑:")
    for model_name, deployment in (updated.model_deployments or {}).items():
        print(f"  {model_name} -> {deployment}")


if __name__ == "__main__":
    configure_defaults()
