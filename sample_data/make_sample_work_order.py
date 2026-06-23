"""테스트용 한국어 무역회사 작업지시서 샘플 PDF 생성기.

실제 작업지시서가 없을 때 추출 파이프라인을 검증하기 위한 합성 샘플을 만든다.

    python sample_data/make_sample_work_order.py
"""

from __future__ import annotations

from pathlib import Path

from weasyprint import HTML

HTML_DOC = """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8">
<style>
  @page { size: A4; margin: 16mm; }
  * { font-family: 'Apple SD Gothic Neo', sans-serif; }
  body { color: #111; font-size: 11px; }
  h1 { text-align: center; letter-spacing: 8px; font-size: 24px; margin: 0 0 2px; }
  .sub { text-align: center; color: #555; font-size: 11px; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
  td, th { border: 1px solid #888; padding: 4px 6px; }
  .meta td { font-size: 11px; }
  .label { background: #f0f0f0; font-weight: bold; white-space: nowrap; }
  .items th { background: #e8eef7; font-size: 10.5px; }
  .items td { font-size: 10.5px; text-align: center; }
  .right { text-align: right; }
  .sec { font-weight: bold; margin: 10px 0 4px; border-left: 4px solid #2a5; padding-left: 6px; }
  .note { font-size: 10.5px; line-height: 1.5; }
</style></head>
<body>
  <h1>작 업 지 시 서</h1>
  <div class="sub">WORK ORDER &nbsp;|&nbsp; 한빛글로벌무역(주) &nbsp;|&nbsp; HANBIT GLOBAL TRADING CO., LTD.</div>

  <table class="meta">
    <tr>
      <td class="label">작업지시서 번호</td><td>WO-2026-0612</td>
      <td class="label">발행일</td><td>2026-06-12</td>
      <td class="label">납기일</td><td>2026-07-20</td>
    </tr>
    <tr>
      <td class="label">발주번호(PO)</td><td>PO-ABC-25-0987</td>
      <td class="label">수주번호</td><td>SO-2026-0331</td>
      <td class="label">계약번호</td><td>CT-2026-118</td>
    </tr>
    <tr>
      <td class="label">작성자</td><td>이정우</td>
      <td class="label">부서</td><td>해외영업1팀</td>
      <td class="label">승인자</td><td>박상호 이사</td>
    </tr>
  </table>

  <div class="sec">거래처 정보</div>
  <table class="meta">
    <tr>
      <td class="label">고객사</td><td>ABC Imports LLC</td>
      <td class="label">담당자</td><td>John Carter</td>
    </tr>
    <tr>
      <td class="label">주소</td><td>1200 Harbor Blvd, Long Beach, CA, USA</td>
      <td class="label">연락처</td><td>+1-562-555-0142</td>
    </tr>
    <tr>
      <td class="label">공급처(제조)</td><td>대성정밀공업(주)</td>
      <td class="label">담당자</td><td>김영호 / 031-555-7788</td>
    </tr>
  </table>

  <div class="sec">무역 / 선적 조건</div>
  <table class="meta">
    <tr>
      <td class="label">인도조건</td><td>FOB Busan</td>
      <td class="label">결제조건</td><td>T/T 30 days</td>
      <td class="label">통화</td><td>USD</td>
    </tr>
    <tr>
      <td class="label">원산지</td><td>Republic of Korea</td>
      <td class="label">선적항</td><td>Busan, Korea</td>
      <td class="label">도착항</td><td>Long Beach, USA</td>
    </tr>
    <tr>
      <td class="label">운송수단</td><td>해상 (By Vessel)</td>
      <td class="label">선적예정일</td><td>2026-07-10</td>
      <td class="label">선명</td><td>HMM GARNET 014W</td>
    </tr>
  </table>

  <div class="sec">품목 내역</div>
  <table class="items">
    <tr>
      <th>No</th><th>품번</th><th>품명</th><th>규격</th><th>HS코드</th>
      <th>수량</th><th>단위</th><th>단가(USD)</th><th>금액(USD)</th><th>비고</th>
    </tr>
    <tr><td>1</td><td>DS-BR-6204</td><td>볼 베어링</td><td>6204-2RS</td><td>8482.10</td>
        <td>2,000</td><td>EA</td><td>1.85</td><td>3,700.00</td><td>-</td></tr>
    <tr><td>2</td><td>DS-SH-1015</td><td>구동 샤프트</td><td>Ø15 x 120mm</td><td>8483.10</td>
        <td>1,500</td><td>EA</td><td>4.20</td><td>6,300.00</td><td>도금</td></tr>
    <tr><td>3</td><td>DS-GR-0808</td><td>평기어</td><td>M2 24T</td><td>8483.40</td>
        <td>800</td><td>EA</td><td>3.10</td><td>2,480.00</td><td>-</td></tr>
    <tr><td>4</td><td>DS-HS-2002</td><td>하우징 케이스</td><td>AL6061</td><td>8487.90</td>
        <td>500</td><td>SET</td><td>7.50</td><td>3,750.00</td><td>아노다이징</td></tr>
  </table>

  <table class="meta">
    <tr>
      <td class="label">총수량</td><td class="right">4,800</td>
      <td class="label">소계</td><td class="right">USD 16,230.00</td>
    </tr>
    <tr>
      <td class="label">부가세(0%)</td><td class="right">USD 0.00</td>
      <td class="label">합계금액</td><td class="right"><b>USD 16,230.00</b></td>
    </tr>
  </table>

  <div class="sec">포장 정보</div>
  <table class="meta">
    <tr>
      <td class="label">포장방법</td><td>수출용 카톤박스 (Export Carton)</td>
      <td class="label">총 박스수</td><td>48 CTN</td>
    </tr>
    <tr>
      <td class="label">순중량(N.W.)</td><td>1,150 KG</td>
      <td class="label">총중량(G.W.)</td><td>1,320 KG</td>
    </tr>
    <tr>
      <td class="label">부피(CBM)</td><td>3.85 CBM</td>
      <td class="label">화인(Shipping Mark)</td><td>ABC / LB / C-NO / MADE IN KOREA</td>
    </tr>
  </table>

  <div class="sec">작업 지시 / 특이사항</div>
  <div class="note">
    1. 전 품목 RoHS 준수 자재 사용, 출하 전 전수 외관검사 실시.<br>
    2. 베어링은 방청유 도포 후 개별 비닐 포장.<br>
    3. 하우징 케이스 아노다이징 색상: 블랙(무광).<br>
    4. 납기 엄수 — 7/20 이전 부산항 CY 반입 완료할 것.<br>
    5. 품질 요구사항: 치수공차 ±0.05mm, 출하검사성적서(COA) 동봉.
  </div>

  <div class="sec">비고</div>
  <div class="note">선적서류(B/L, P/L, C/I)는 선적 후 3일 이내 이메일 송부. 클레임은 도착 후 14일 이내.</div>
</body></html>
"""


def main() -> None:
    out = Path(__file__).parent / "sample_work_order.pdf"
    HTML(string=HTML_DOC).write_pdf(str(out))
    print(f"생성 완료: {out}")


if __name__ == "__main__":
    main()
