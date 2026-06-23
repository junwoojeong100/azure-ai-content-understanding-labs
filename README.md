# 무역회사 작업지시서 PDF → JSON 추출 (Azure AI Content Understanding)

무역회사 고객의 **작업지시서(Work Order)** PDF 를 Azure AI Content Understanding 으로
읽어 **모든 데이터를 JSON 으로 추출**하는 Python 프로젝트입니다.
관련 Azure 리소스를 생성하는 스크립트도 포함되어 있습니다.

## 동작 방식

```
작업지시서.pdf
      │
      ▼
 [커스텀 분석기]  ← ① src/schema.py 필드 스키마 (서비스가 fields 생성)
      │            Azure AI Content Understanding (Microsoft Foundry)
      ▼
 서비스 RAW 응답 ─────────────────────────▶ output/작업지시서.raw.json (원본 전체 보존)
      │
      ▼ ② _simplify_field() 평탄화 후처리 (extract_work_order.py)
 output/작업지시서.json  ← 정제된 구조화 필드 + 마크다운 + 표
```

- **커스텀 분석기**로 작업지시서에 특화된 필드(문서정보·거래처·무역조건·선적·포장·품목 내역·합계 등)를 구조화 추출합니다.
- 동시에 **원본 JSON 전체**(마크다운·레이아웃·표 포함)를 저장하므로 스키마에 없는 데이터도 보존됩니다.

## 정제된 구조화 데이터는 어떻게 만들어지나

`output/<name>.json` 의 `fields` 는 서비스가 그대로 준 것이 아니라 **두 단계의 추가 작업**으로 만들어집니다.

### ① 필드 스키마 정의 — `src/schema.py` (무엇을 뽑을지)

`prebuilt-documentSearch` 만 쓰면 마크다운·표(텍스트)만 나오고 **업무 필드는 나오지 않습니다.**
커스텀 분석기에 작업지시서 필드 스키마(`build_work_order_schema()`)를 넣어 분석기를 만들면,
서비스 측 LLM(gpt-4.1)이 RAW 응답 안에 `fields`(`workOrderNumber`, `customer.name`,
`lineItems[]` …)를 생성합니다.
- 배열(품목 내역)은 `item_definition`, 객체(거래처 등)는 `properties`, 고정값(통화·인도조건)은 enum(`classify`)
- 필드 `description` 의 한국어 별칭이 추출 정확도를 높입니다.

### ② 평탄화 후처리 — `src/extract_work_order.py` 의 `_simplify_field()` (보기 좋게 다듬기)

RAW 의 각 필드는 `type / value* / spans / confidence / source` 가 붙은 장황한 객체입니다.
이를 재귀적으로 **값만** 남깁니다.

```jsonc
// RAW (output/<name>.raw.json)
"workOrderNumber": {
  "type": "string", "valueString": "WO-2026-0612",
  "spans": [{ "offset": 107, "length": 12 }],
  "confidence": 0.72, "source": "D(1,2.07,1.33,...)"
}
```
```jsonc
// 정제본 (output/<name>.json)
"workOrderNumber": "WO-2026-0612"
```

- 스칼라: `type` 에 맞는 `value*` 키(`valueString`/`valueNumber`/`valueDate`…)만 추출
- object → `valueObject`, array(품목) → `valueArray` 안으로 재귀
- `--with-confidence` 옵션을 주면 `{ "value": ..., "confidence": ... }` 형태로 신뢰도 보존

> **두 출력 파일의 관계**: `*.json` = RAW 안 `fields` 의 정제본 · `*.raw.json` = 서비스 원본 전체(spans·confidence·source·layout 포함, **정보 손실 없음**).
> 즉 ①은 "무엇을 뽑을지"를 서비스에 지시(추출 품질 결정), ②는 "뽑힌 결과를 보기 좋게 다듬는" 로컬 변환입니다.

## 사전 요구사항

- **Azure 구독** 과 권한:
  - 리소스/모델 생성: **Contributor** 이상
  - 역할 자동 부여(`Cognitive Services User`): **Owner** 또는 **User Access Administrator**.
    이 권한이 없으면 스크립트가 역할 부여만 건너뛰며, 관리자에게 해당 역할을 요청하면 됩니다.
- **Azure CLI(`az`)** 설치 — https://aka.ms/azcli
- **Python 3.9+**
- **셸**: macOS/Linux 는 기본 터미널(bash). **Windows 는 WSL 또는 Git Bash** 에서 실행하세요(`infra/*.sh` 는 bash 스크립트).
- Content Understanding GA 리전(아래 중 하나, 기본값 `eastus2`): `eastus`, `eastus2`, `westus`, `westus3`,
  `southcentralus`, `northeurope`, `westeurope`, `swedencentral`, `uksouth`, `japaneast`, `australiaeast`

## 빠른 시작

> 아래 0→4 단계를 순서대로 실행하면 됩니다. 처음부터 끝까지 복붙용 한 묶음은 맨 아래
> [전체 순서 요약](#전체-순서-요약-복붙용) 을 참고하세요.

### 0) 사전 준비 — 로그인 & 코드 받기

```bash
# 코드 가져오기(이미 받았다면 생략)
git clone <이 저장소 URL> content-understanding
cd content-understanding

# Azure 로그인
az login
# 구독이 여러 개면 사용할 구독을 선택
az account set --subscription "<구독 ID 또는 이름>"
az account show --query name -o tsv      # 현재 구독 확인
```

### 1) Azure 리소스 생성

현재 로그인된 구독에 Foundry 리소스 + 모델 배포 + 역할 부여 + `.env` 생성을 한 번에 수행합니다.

```bash
bash infra/setup_azure.sh
# 리전/이름 변경: LOCATION=swedencentral ACCOUNT_NAME=my-foundry bash infra/setup_azure.sh
```

생성 항목:
| 리소스 | 설명 |
| --- | --- |
| 리소스 그룹 | `rg-trade-content-understanding` (기본값) |
| Foundry(AIServices) 계정 | `kind=AIServices` + `allowProjectManagement=true` 인 **Azure AI Foundry 리소스**. custom subdomain 포함, 엔드포인트 `https://<name>.services.ai.azure.com/` |
| Foundry 프로젝트 | `<name>-project` (Foundry 포털 ai.azure.com 노출용) |
| 모델 배포 | `gpt-4.1`, `gpt-4.1-mini`, `text-embedding-3-large` |
| 역할 | 본인에게 `Cognitive Services User` (DefaultAzureCredential 용) |

성공하면 마지막에 `완료!  엔드포인트: https://....services.ai.azure.com/` 가 출력되고 프로젝트 루트에 `.env` 가 생성됩니다.

> **이미 Foundry 리소스가 있는 경우**(이 단계를 건너뛰려면): `.env.example` 을 `.env` 로 복사한 뒤
> `CONTENTUNDERSTANDING_ENDPOINT` 만 본인 리소스 엔드포인트로 채우고, 모델 3종(`gpt-4.1`,
> `gpt-4.1-mini`, `text-embedding-3-large`)이 배포되어 있는지, 본인에게 `Cognitive Services User`
> 역할이 있는지 확인하세요.

### 2) 파이썬 환경

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows(Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
```

### 3) 모델 매핑(1회)

```bash
python -m src.setup_defaults
```
> 역할 전파 지연으로 처음 401/403 으로 실패하면 1~2분 후 다시 실행하세요.

### 4) 작업지시서 분석

```bash
python -m src.extract_work_order 작업지시서.pdf
```
> **첫 실행 시** 커스텀 분석기(`trade_work_order`)가 자동으로 생성됩니다(수십 초~1분 소요).
> 이후 실행은 기존 분석기를 재사용합니다. 결과는 `output/작업지시서.json`(정제본)과
> `output/작업지시서.raw.json`(원본)에 저장됩니다.

> **샘플로 바로 테스트**해 보려면(실제 작업지시서가 없을 때):
> ```bash
> pip install -r requirements-dev.txt          # weasyprint (샘플 생성용)
> python sample_data/make_sample_work_order.py # sample_data/sample_work_order.pdf 생성
> python -m src.extract_work_order sample_data/sample_work_order.pdf
> ```

옵션:
```bash
# 출력 경로 지정 + 값에 신뢰도 포함 + 분석기 재생성
python -m src.extract_work_order 작업지시서.pdf --out output/result.json --with-confidence --recreate-analyzer
```
| 옵션 | 설명 |
| --- | --- |
| `--out <경로>` | 정제 JSON 출력 경로(기본 `output/<파일명>.json`) |
| `--with-confidence` | 각 값에 신뢰도(confidence) 점수 포함 |
| `--recreate-analyzer` | 분석기를 삭제 후 재생성(스키마 변경 시) |
| `--no-raw` | 원본(raw) JSON 파일을 저장하지 않음 |

분석기만 따로 만들거나 갱신하려면:
```bash
python -m src.create_analyzer            # 없으면 생성
python -m src.create_analyzer --recreate # 스키마 변경 후 재생성
```

## 전체 순서 요약 (복붙용)

처음부터 끝까지 한 번에 따라 할 수 있는 명령 모음입니다(macOS/Linux 기준, Windows 는 Git Bash).

```bash
# 0) 로그인 & 코드
az login
az account set --subscription "<구독 ID 또는 이름>"
git clone <이 저장소 URL> content-understanding && cd content-understanding

# 1) Azure 리소스 생성 (.env 자동 생성)
bash infra/setup_azure.sh

# 2) 파이썬 환경
python3 -m venv .venv
source .venv/bin/activate                 # Windows(Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt

# 3) 모델 매핑(1회) — 401/403 이면 1~2분 후 재실행
python -m src.setup_defaults

# 4-a) (선택) 샘플 PDF 로 동작 확인
pip install -r requirements-dev.txt
python sample_data/make_sample_work_order.py
python -m src.extract_work_order sample_data/sample_work_order.pdf

# 4-b) 실제 작업지시서 분석
python -m src.extract_work_order /경로/작업지시서.pdf
# 결과: output/작업지시서.json (정제본) + output/작업지시서.raw.json (원본)
```

## 출력 예시 (`output/작업지시서.json`)

```json
{
  "sourceFile": "작업지시서.pdf",
  "analyzerId": "trade_work_order",
  "fields": {
    "documentTitle": "작업지시서",
    "workOrderNumber": "WO-2026-0123",
    "issueDate": "2026-06-23",
    "customer": { "name": "ABC무역", "contactPerson": "김철수", "phone": "02-1234-5678" },
    "supplier": { "name": "대한정밀" },
    "incoterms": "FOB",
    "currency": "USD",
    "lineItems": [
      { "lineNo": 1, "itemCode": "A-100", "itemName": "베어링", "quantity": 500, "unit": "EA", "unitPrice": 2.5, "amount": 1250 }
    ],
    "totals": { "totalQuantity": 500, "totalAmount": 1250 }
  },
  "markdown": "## 작업지시서 ...",
  "tables": [ ... ]
}
```

## 프로젝트 구조

```
.
├── infra/
│   ├── setup_azure.sh       # Azure 리소스 생성 + .env 작성
│   └── teardown_azure.sh    # 리소스 정리(과금 중단)
├── src/
│   ├── config.py            # .env 설정 로드/인증
│   ├── schema.py            # ① 작업지시서 필드 스키마(무엇을 뽑을지)
│   ├── setup_defaults.py    # 모델 매핑(1회)
│   ├── create_analyzer.py   # 커스텀 분석기 생성/갱신
│   └── extract_work_order.py# PDF → JSON 추출(메인) · ② _simplify_field 평탄화
├── sample_data/
│   └── make_sample_work_order.py  # 테스트용 샘플 작업지시서 PDF 생성기
├── requirements.txt         # 런타임 의존성
├── requirements-dev.txt     # 샘플 생성용(weasyprint)
├── .env.example
└── README.md
```

## 스키마 커스터마이징

작업지시서 양식에 맞춰 `src/schema.py` 의 `build_work_order_schema()` 에서 필드를 추가/수정한 뒤
`python -m src.create_analyzer --recreate` 로 분석기를 다시 만들면 됩니다.
필드 `description` 에 한국어 별칭(예: "납기일/완료예정일/Due Date")을 풍부하게 적을수록 추출 정확도가 올라갑니다.

## 비용/정리

리소스는 사용량 기반 과금됩니다. 사용 후 정리:
```bash
bash infra/teardown_azure.sh    # 리소스 그룹 전체 삭제(확인 프롬프트 있음)
```

## 문제 해결 (Troubleshooting)

| 증상 | 원인 / 해결 |
| --- | --- |
| `az login` 미로그인 / 구독 여러 개 | `setup_azure.sh` 가 감지해 안내합니다. `az login` 후 `az account set --subscription "<구독 ID 또는 이름>"` 로 대상 구독을 선택하세요. |
| 파이썬 실행 시 인증 오류(`DefaultAzureCredential`/401) | ① `az login` 세션이 살아있는지, ② 본인에게 리소스의 `Cognitive Services User` 역할이 있는지 확인하세요. 이 리소스는 보안 기본값으로 **키 인증이 비활성화**되어 있어 Entra ID(역할) 인증이 필요합니다. |
| 역할 자동 부여 실패(Contributor만 보유) | 역할 부여에는 **Owner/User Access Administrator** 가 필요합니다. 관리자에게 리소스에 대한 `Cognitive Services User` 역할 부여를 요청한 뒤 3) 단계를 진행하세요. |
| Windows 에서 `infra/*.sh` 실행 안 됨 | bash 스크립트입니다. **WSL** 또는 **Git Bash** 에서 `bash infra/setup_azure.sh` 로 실행하세요. |
| `InsufficientQuota ... GlobalStandard` | 해당 리전의 모델 할당량 부족. `setup_azure.sh` 는 자동으로 `Standard` → `DataZoneStandard` SKU 로 폴백합니다. 모두 0이면 `LOCATION=<다른리전>` 으로 재실행하거나 포털에서 할당량 증설을 요청하세요. (`az cognitiveservices usage list -l <region>` 로 확인) |
| `setup_defaults` 가 401/403 | `Cognitive Services User` 역할 미부여 또는 전파 지연. 역할이 부여돼 있으면 1~2분 후 재실행, 없으면 위 '역할 자동 부여 실패' 행을 참고하세요. |
| `InvalidAnalyzerId ... cannot contain '-'` | 분석기 ID 에는 하이픈을 쓸 수 없습니다. `WORK_ORDER_ANALYZER_ID` 는 영숫자/언더스코어만 사용(`trade_work_order`). |
| 추출 정확도가 낮음 | `src/schema.py` 의 필드 `description` 에 양식에 맞는 한국어 별칭을 추가하고 `python -m src.create_analyzer --recreate` 로 재생성하세요. |

## 참고
- SDK: [`azure-ai-contentunderstanding`](https://pypi.org/project/azure-ai-contentunderstanding/) (API `2025-11-01`)
- 문서: https://learn.microsoft.com/azure/ai-services/content-understanding/
