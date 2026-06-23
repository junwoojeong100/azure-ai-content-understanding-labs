"""작업지시서 PDF 를 분석해 모든 데이터를 JSON 으로 추출한다.

처리 흐름
1. 설정 로드 및 클라이언트 생성
2. 작업지시서 커스텀 분석기 보장(없으면 자동 생성)
3. PDF 바이트를 ``begin_analyze_binary`` 로 분석
4. 서비스 원본 JSON 전체를 ``<out>.raw.json`` 으로 저장 (모든 데이터 보존)
5. 구조화 필드 + 마크다운 + 표를 정제해 ``<out>.json`` 으로 저장

사용법:
    python -m src.extract_work_order 작업지시서.pdf
    python -m src.extract_work_order 작업지시서.pdf --out output/result.json --with-confidence
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from azure.ai.contentunderstanding import ContentUnderstandingClient

from .config import build_credential, load_settings
from .create_analyzer import ensure_analyzer

# 분석기 raw JSON 의 스칼라 타입 -> value 키 매핑
_VALUE_KEYS = {
    "string": "valueString",
    "number": "valueNumber",
    "integer": "valueInteger",
    "date": "valueDate",
    "time": "valueTime",
    "boolean": "valueBoolean",
}


def _simplify_field(field: dict[str, Any], *, with_confidence: bool) -> Any:
    """단일 필드를 사람이 읽기 쉬운 값(또는 {value, confidence})으로 변환."""

    if not isinstance(field, dict):
        return field

    field_type = field.get("type")

    if field_type == "array":
        return [_simplify_field(item, with_confidence=with_confidence) for item in field.get("valueArray", []) or []]

    if field_type == "object":
        return {
            key: _simplify_field(value, with_confidence=with_confidence)
            for key, value in (field.get("valueObject", {}) or {}).items()
        }

    # 스칼라 값 추출
    value: Any = None
    value_key = _VALUE_KEYS.get(field_type or "")
    if value_key and value_key in field:
        value = field.get(value_key)
    else:  # 알 수 없는 타입은 value* 키를 탐색
        for key, val in field.items():
            if key.startswith("value"):
                value = val
                break

    if with_confidence and field.get("confidence") is not None:
        return {"value": value, "confidence": field.get("confidence")}
    return value


def _simplify_fields(fields: dict[str, Any], *, with_confidence: bool) -> dict[str, Any]:
    return {name: _simplify_field(defn, with_confidence=with_confidence) for name, defn in (fields or {}).items()}


def _unwrap_result(response_json: dict[str, Any]) -> dict[str, Any]:
    """LRO 응답({id,status,result})과 결과 본문 양쪽을 모두 지원."""
    if isinstance(response_json.get("result"), dict):
        return response_json["result"]
    return response_json


def analyze_pdf(pdf_path: Path, *, with_confidence: bool, ensure: bool, recreate_analyzer: bool) -> dict[str, Any]:
    """PDF 를 분석하고 (raw_json, structured_json) 를 반환한다."""

    settings = load_settings()
    client = ContentUnderstandingClient(endpoint=settings.endpoint, credential=build_credential(settings))

    analyzer_id = settings.analyzer_id
    if ensure:
        analyzer_id = ensure_analyzer(client, settings, recreate=recreate_analyzer)

    file_bytes = pdf_path.read_bytes()
    print(f"'{pdf_path.name}' 을(를) 분석기 '{analyzer_id}' 로 분석합니다... (페이지 수에 따라 시간이 걸릴 수 있음)")

    poller = client.begin_analyze_binary(
        analyzer_id=analyzer_id,
        binary_input=file_bytes,
        cls=lambda pipeline_response, deserialized, headers: (deserialized, pipeline_response.http_response),
    )
    _, raw_http_response = poller.result()
    raw_json: dict[str, Any] = raw_http_response.json()

    result_body = _unwrap_result(raw_json)
    contents = result_body.get("contents", []) or []

    # 문서는 보통 단일 content. 여러 개면 모두 담는다.
    documents: list[dict[str, Any]] = []
    for content in contents:
        documents.append(
            {
                "fields": _simplify_fields(content.get("fields", {}) or {}, with_confidence=with_confidence),
                "markdown": content.get("markdown"),
                "tables": content.get("tables", []),
                "startPageNumber": content.get("startPageNumber"),
                "endPageNumber": content.get("endPageNumber"),
            }
        )

    structured: dict[str, Any] = {
        "sourceFile": pdf_path.name,
        "analyzerId": result_body.get("analyzerId", analyzer_id),
        "apiVersion": result_body.get("apiVersion"),
        "warnings": result_body.get("warnings", []),
        # 단일 문서면 평탄화해서 바로 fields 를 노출
        "fields": documents[0]["fields"] if len(documents) == 1 else None,
        "markdown": documents[0]["markdown"] if len(documents) == 1 else None,
        "tables": documents[0]["tables"] if len(documents) == 1 else None,
        "documents": documents if len(documents) != 1 else None,
    }
    # None 값 정리
    structured = {k: v for k, v in structured.items() if v is not None}

    return {"raw": raw_json, "structured": structured}


def _default_out(pdf_path: Path) -> Path:
    return Path("output") / f"{pdf_path.stem}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="작업지시서 PDF -> JSON 추출")
    parser.add_argument("pdf", type=Path, help="작업지시서 PDF 파일 경로")
    parser.add_argument("--out", type=Path, default=None, help="구조화 JSON 출력 경로 (기본: output/<파일명>.json)")
    parser.add_argument("--with-confidence", action="store_true", help="각 값에 confidence 점수 포함")
    parser.add_argument("--no-ensure", action="store_true", help="분석기 자동 생성/확인 건너뛰기")
    parser.add_argument("--recreate-analyzer", action="store_true", help="분석기를 삭제 후 재생성")
    parser.add_argument("--no-raw", action="store_true", help="원본(raw) JSON 파일을 저장하지 않음")
    args = parser.parse_args()

    if not args.pdf.exists():
        sys.exit(f"파일을 찾을 수 없습니다: {args.pdf}")

    out_path: Path = args.out or _default_out(args.pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_pdf(
        args.pdf,
        with_confidence=args.with_confidence,
        ensure=not args.no_ensure,
        recreate_analyzer=args.recreate_analyzer,
    )

    out_path.write_text(json.dumps(result["structured"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"구조화 결과 저장: {out_path}")

    if not args.no_raw:
        raw_path = out_path.with_suffix(".raw.json")
        raw_path.write_text(json.dumps(result["raw"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"원본(raw) 결과 저장: {raw_path}")

    fields = result["structured"].get("fields") or {}
    print(f"추출된 최상위 필드 {len(fields)}개.")
    line_items = fields.get("lineItems")
    if isinstance(line_items, list):
        print(f"품목 내역(lineItems) {len(line_items)}건.")


if __name__ == "__main__":
    main()
