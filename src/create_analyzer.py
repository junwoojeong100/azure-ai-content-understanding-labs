"""작업지시서용 커스텀 분석기를 생성/갱신한다.

작업지시서 필드 스키마(``src.schema``)를 사용해 ``prebuilt-document`` 기반의
커스텀 분석기를 만든다. 분석기는 한 번 만들면 재사용되며, 여러 PDF 를
같은 분석기로 분석할 수 있다.

사용법:
    python -m src.create_analyzer            # 없으면 생성, 있으면 그대로 둠
    python -m src.create_analyzer --recreate # 기존 분석기를 삭제 후 재생성
"""

from __future__ import annotations

import argparse

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import (
    ContentAnalyzer,
    ContentAnalyzerConfig,
)
from azure.core.exceptions import ResourceNotFoundError

from .config import Settings, build_credential, load_settings
from .schema import build_work_order_schema


def _analyzer_exists(client: ContentUnderstandingClient, analyzer_id: str) -> bool:
    try:
        client.get_analyzer(analyzer_id=analyzer_id)
        return True
    except ResourceNotFoundError:
        return False


def ensure_analyzer(
    client: ContentUnderstandingClient,
    settings: Settings,
    *,
    recreate: bool = False,
) -> str:
    """분석기가 존재하도록 보장하고 analyzer_id 를 반환한다."""

    analyzer_id = settings.analyzer_id

    if _analyzer_exists(client, analyzer_id):
        if not recreate:
            print(f"분석기 '{analyzer_id}' 가 이미 존재합니다. (재사용)")
            return analyzer_id
        print(f"기존 분석기 '{analyzer_id}' 를 삭제합니다...")
        client.delete_analyzer(analyzer_id=analyzer_id)

    print(f"커스텀 분석기 '{analyzer_id}' 를 생성합니다...")

    analyzer = ContentAnalyzer(
        base_analyzer_id="prebuilt-document",
        description="무역회사 작업지시서 데이터 추출 분석기",
        config=ContentAnalyzerConfig(
            enable_ocr=True,
            enable_layout=True,
            enable_formula=False,
            estimate_field_source_and_confidence=True,
            return_details=True,
        ),
        field_schema=build_work_order_schema(),
        models={
            "completion": settings.completion_model,
            "embedding": settings.embedding_model,
        },
    )

    poller = client.begin_create_analyzer(
        analyzer_id=analyzer_id,
        resource=analyzer,
        allow_replace=True,
    )
    poller.result()

    created = client.get_analyzer(analyzer_id=analyzer_id)
    field_count = len(created.field_schema.fields) if created.field_schema and created.field_schema.fields else 0
    print(f"분석기 '{analyzer_id}' 생성 완료. 최상위 필드 {field_count}개.")
    return analyzer_id


def main() -> None:
    parser = argparse.ArgumentParser(description="작업지시서 커스텀 분석기 생성")
    parser.add_argument("--recreate", action="store_true", help="기존 분석기를 삭제하고 다시 생성")
    args = parser.parse_args()

    settings = load_settings()
    client = ContentUnderstandingClient(endpoint=settings.endpoint, credential=build_credential(settings))
    ensure_analyzer(client, settings, recreate=args.recreate)


if __name__ == "__main__":
    main()
