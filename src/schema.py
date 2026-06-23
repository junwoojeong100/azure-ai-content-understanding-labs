"""무역회사 작업지시서(Work Order / 작업지시서) 필드 스키마.

Azure AI Content Understanding 커스텀 분석기가 PDF 에서 추출할 구조화 필드를 정의한다.

설계 원칙
- 다양한 양식에 견고하게 대응하기 위해 대부분 ``generate`` 방식을 사용한다.
- 통화/인도조건처럼 값이 고정된 항목은 ``classify`` (enum) 를 사용한다.
- 반복 항목(품목 내역)은 best practice 에 따라 *object 의 array* 로 정의한다.
- 필드 키는 JSON 사용성을 위해 영문 camelCase, 설명(description)은 한국어 별칭을
  풍부하게 담아 모델이 한국어 작업지시서를 정확히 인식하도록 유도한다.
"""

from __future__ import annotations

from azure.ai.contentunderstanding.models import (
    ContentFieldDefinition,
    ContentFieldSchema,
    ContentFieldType,
    GenerationMethod,
)

SCHEMA_NAME = "trade_work_order_schema"
SCHEMA_DESCRIPTION = "무역회사 작업지시서에서 추출하는 전체 데이터 스키마"


def _s(description: str, method: GenerationMethod = GenerationMethod.GENERATE) -> ContentFieldDefinition:
    """문자열 필드 헬퍼."""
    return ContentFieldDefinition(type=ContentFieldType.STRING, method=method, description=description)


def _n(description: str) -> ContentFieldDefinition:
    """숫자 필드 헬퍼."""
    return ContentFieldDefinition(type=ContentFieldType.NUMBER, method=GenerationMethod.GENERATE, description=description)


def _d(description: str) -> ContentFieldDefinition:
    """날짜 필드 헬퍼 (ISO 8601 로 정규화됨)."""
    return ContentFieldDefinition(type=ContentFieldType.DATE, method=GenerationMethod.GENERATE, description=description)


def _enum(description: str, values: list[str]) -> ContentFieldDefinition:
    """분류(enum) 필드 헬퍼."""
    return ContentFieldDefinition(
        type=ContentFieldType.STRING,
        method=GenerationMethod.CLASSIFY,
        description=description,
        enum=values,
    )


def _party(role: str) -> ContentFieldDefinition:
    """거래 당사자(고객/공급처 등) 공통 object 정의."""
    return ContentFieldDefinition(
        type=ContentFieldType.OBJECT,
        method=GenerationMethod.GENERATE,
        description=f"{role} 정보",
        properties={
            "name": _s(f"{role} 상호/회사명. '업체명', '거래처명', '고객사', 'Company' 등으로 표기될 수 있음"),
            "businessNumber": _s(f"{role} 사업자등록번호 또는 사업자번호 (Business Reg. No.)"),
            "address": _s(f"{role} 주소"),
            "contactPerson": _s(f"{role} 담당자명. '담당', '담당자', 'Attn', 'Contact' 등"),
            "phone": _s(f"{role} 전화/연락처 (Tel, Phone, Mobile)"),
            "email": _s(f"{role} 이메일 주소"),
        },
    )


def build_work_order_schema() -> ContentFieldSchema:
    """작업지시서 전체 필드 스키마를 생성한다."""

    # 품목 내역(라인 아이템) 한 행의 구조
    line_item = ContentFieldDefinition(
        type=ContentFieldType.OBJECT,
        method=GenerationMethod.GENERATE,
        description="품목 내역 한 줄(행)",
        properties={
            "lineNo": _n("순번/항번 (No, 번호)"),
            "itemCode": _s("품번/품목코드/모델번호 (Item Code, Part No, Model)"),
            "itemName": _s("품명/제품명 (Item, Description, 품목)"),
            "specification": _s("규격/사양/사이즈 (Spec, Size, 규격)"),
            "hsCode": _s("HS 코드/세번 (HS Code)"),
            "quantity": _n("수량 (Qty, Quantity)"),
            "unit": _s("단위 (EA, SET, PCS, KG, CTN 등)"),
            "unitPrice": _n("단가 (Unit Price)"),
            "amount": _n("금액/공급가액 (Amount, 금액)"),
            "deliveryDate": _d("해당 품목 납기일 (있을 경우)"),
            "remarks": _s("비고/특기사항"),
        },
    )

    fields: dict[str, ContentFieldDefinition] = {
        # ── 문서 기본 정보 ───────────────────────────────────────────────
        "documentTitle": _s("문서 제목/유형. 예) '작업지시서', 'WORK ORDER', '제조지시서'"),
        "workOrderNumber": _s("작업지시서 번호/지시번호 (W/O No, Work Order No, 지시No)"),
        "issueDate": _d("발행일/작성일/지시일 (Issue Date, Date)"),
        "dueDate": _d("납기일/완료예정일/출하예정일 (Due Date, Delivery Date)"),
        "author": _s("작성자/지시자/담당자 이름"),
        "department": _s("작성 부서/담당 부서"),
        "approver": _s("승인자/결재자 이름"),

        # ── 거래 당사자 ─────────────────────────────────────────────────
        "customer": _party("고객사/발주처(주문한 무역회사 고객)"),
        "supplier": _party("공급처/제조처/생산처(작업을 수행하는 업체)"),

        # ── 주문/계약 식별자 ────────────────────────────────────────────
        "poNumber": _s("발주번호/구매주문번호 (PO No, Purchase Order)"),
        "orderNumber": _s("수주번호/오더번호 (Order No, Sales Order)"),
        "contractNumber": _s("계약번호 (Contract No)"),
        "projectName": _s("프로젝트명/건명"),

        # ── 무역 조건 ──────────────────────────────────────────────────
        "incoterms": _enum(
            "인도조건/가격조건 (Incoterms). 예) FOB Busan -> FOB",
            ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP", "기타"],
        ),
        "paymentTerms": _s("결제조건 (Payment Terms). 예) T/T 30 days, L/C at sight, 현금"),
        "currency": _enum(
            "통화 코드 (Currency). 문서의 금액 통화",
            ["KRW", "USD", "EUR", "JPY", "CNY", "GBP", "기타"],
        ),
        "countryOfOrigin": _s("원산지 (Country of Origin, 원산지)"),
        "destinationCountry": _s("도착국/수출 대상국 (Destination)"),

        # ── 선적/운송 정보 ──────────────────────────────────────────────
        "shipment": ContentFieldDefinition(
            type=ContentFieldType.OBJECT,
            method=GenerationMethod.GENERATE,
            description="선적/운송 정보",
            properties={
                "portOfLoading": _s("선적항/출발지 (Port of Loading, POL)"),
                "portOfDischarge": _s("도착항/양륙항 (Port of Discharge, POD)"),
                "shipmentDate": _d("선적예정일/출하일 (Shipment Date, ETD)"),
                "transportMode": _s("운송수단 (해상/항공/육상, Sea/Air, By Vessel)"),
                "vesselOrFlight": _s("선명/항공편명 (Vessel, Flight No)"),
            },
        ),

        # ── 포장 정보 ──────────────────────────────────────────────────
        "packing": ContentFieldDefinition(
            type=ContentFieldType.OBJECT,
            method=GenerationMethod.GENERATE,
            description="포장 정보",
            properties={
                "packingMethod": _s("포장방법/포장형태 (Packing, 포장)"),
                "totalPackages": _n("총 포장 수량/박스 수 (Total CTN, 박스수)"),
                "netWeight": _n("순중량 (Net Weight, N.W.)"),
                "grossWeight": _n("총중량 (Gross Weight, G.W.)"),
                "weightUnit": _s("중량 단위 (KG, TON 등)"),
                "volumeCbm": _n("부피 (Volume, CBM, 용적)"),
            },
        ),

        # ── 품목 내역 (표) ─────────────────────────────────────────────
        "lineItems": ContentFieldDefinition(
            type=ContentFieldType.ARRAY,
            method=GenerationMethod.GENERATE,
            description="품목 내역 표의 모든 행. 각 행은 품번/품명/규격/수량/단가/금액 등을 포함",
            item_definition=line_item,
        ),

        # ── 합계 ───────────────────────────────────────────────────────
        "totals": ContentFieldDefinition(
            type=ContentFieldType.OBJECT,
            method=GenerationMethod.GENERATE,
            description="합계 정보",
            properties={
                "totalQuantity": _n("총수량 (Total Qty)"),
                "subtotal": _n("소계/공급가액 합계 (Subtotal)"),
                "taxAmount": _n("세액/부가세 (VAT, Tax)"),
                "totalAmount": _n("총금액/합계금액 (Total Amount, 합계)"),
            },
        ),

        # ── 기타 자유 텍스트 ────────────────────────────────────────────
        "specialInstructions": _s("작업/주의 지시사항, 특이사항 (Special Instructions, 지시사항)"),
        "qualityRequirements": _s("품질/검사 요구사항 (Quality, Inspection)"),
        "remarks": _s("비고/기타 메모 (Remarks, Note, 비고)"),
    }

    return ContentFieldSchema(name=SCHEMA_NAME, description=SCHEMA_DESCRIPTION, fields=fields)
