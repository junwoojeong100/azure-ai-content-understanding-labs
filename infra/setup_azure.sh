#!/usr/bin/env bash
#
# Azure AI Content Understanding 용 리소스를 현재 연결된 구독에 생성한다.
#
#   1) 리소스 그룹
#   2) Microsoft Foundry(=AIServices) 리소스 (custom subdomain 포함)
#   3) 모델 배포: gpt-4.1, gpt-4.1-mini, text-embedding-3-large
#   4) 본인 계정에 'Cognitive Services User' 역할 부여 (DefaultAzureCredential 용)
#   5) 프로젝트 루트에 .env 생성 (엔드포인트/배포 이름)
#
# 사용법:
#   ./infra/setup_azure.sh
#   LOCATION=swedencentral ACCOUNT_NAME=my-foundry ./infra/setup_azure.sh
#
# 사전 요구사항: az CLI 로그인(az login), 구독에 리소스 생성 권한(Contributor 이상).
set -euo pipefail

# ── 설정값 (환경 변수로 재정의 가능) ─────────────────────────────────────
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-trade-content-understanding}"
LOCATION="${LOCATION:-eastus2}"

# ── 사전 점검: az CLI 설치 및 로그인 확인 ───────────────────────────────
if ! command -v az >/dev/null 2>&1; then
  echo "[오류] Azure CLI(az) 가 설치되어 있지 않습니다. https://aka.ms/azcli 참고." >&2
  exit 1
fi
# python3 우선, 없으면 python 으로 폴백 (Windows Git Bash 대응)
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "[오류] python3(또는 python) 가 필요합니다(모델 버전 조회에 사용)." >&2
  exit 1
fi
if ! az account show >/dev/null 2>&1; then
  echo "[오류] Azure 에 로그인되어 있지 않습니다. 먼저 'az login' 을 실행하세요." >&2
  echo "       구독이 여러 개면: az account set --subscription <구독ID 또는 이름>" >&2
  exit 1
fi

# 전역적으로 고유한 이름이 필요하므로 구독 ID 일부를 접미사로 사용
SUB_ID="$(az account show --query id -o tsv)"
SUFFIX="$(printf '%s' "$SUB_ID" | tr -dc 'a-f0-9' | cut -c1-8)"
ACCOUNT_NAME="${ACCOUNT_NAME:-tradecu${SUFFIX}}"

# Content Understanding GA 지원 리전
SUPPORTED_REGIONS="eastus eastus2 westus westus3 southcentralus northeurope westeurope swedencentral uksouth japaneast australiaeast"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

echo "=========================================================="
echo " Azure AI Content Understanding 리소스 생성"
echo "=========================================================="
echo "  구독        : $(az account show --query name -o tsv) ($SUB_ID)"
echo "  리소스그룹  : $RESOURCE_GROUP"
echo "  리전        : $LOCATION"
echo "  리소스 이름 : $ACCOUNT_NAME"
echo "----------------------------------------------------------"

if ! grep -qw "$LOCATION" <<< "$SUPPORTED_REGIONS"; then
  echo "[경고] '$LOCATION' 은(는) Content Understanding GA 지원 리전이 아닐 수 있습니다."
  echo "       지원 리전: $SUPPORTED_REGIONS"
fi

# ── 0) 리소스 공급자 등록 ───────────────────────────────────────────────
echo "[0/5] 리소스 공급자(Microsoft.CognitiveServices) 등록 확인..."
az provider register --namespace Microsoft.CognitiveServices --wait >/dev/null 2>&1 || true

# ── 1) 리소스 그룹 ─────────────────────────────────────────────────────
echo "[1/5] 리소스 그룹 생성/확인..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --only-show-errors -o none

# ── 2) Foundry(AIServices) 리소스 ──────────────────────────────────────
echo "[2/5] Foundry(AIServices) 리소스 생성/확인..."
if az cognitiveservices account show -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "      이미 존재함: $ACCOUNT_NAME"
else
  az cognitiveservices account create \
    --name "$ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --kind AIServices \
    --sku S0 \
    --location "$LOCATION" \
    --custom-domain "$ACCOUNT_NAME" \
    --allow-project-management true \
    --yes \
    --only-show-errors -o none
  echo "      생성 완료: $ACCOUNT_NAME (Foundry 리소스, 프로젝트 관리 활성화)"
fi

# Foundry 프로젝트 생성(있으면 건너뜀) — Foundry 포털(ai.azure.com) 노출용
PROJECT_NAME="${PROJECT_NAME:-${ACCOUNT_NAME}-project}"
if az cognitiveservices account project show -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" --project-name "$PROJECT_NAME" >/dev/null 2>&1; then
  echo "      프로젝트 이미 존재: $PROJECT_NAME"
else
  az cognitiveservices account project create \
    -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" \
    --project-name "$PROJECT_NAME" --location "$LOCATION" \
    --only-show-errors -o none \
    && echo "      Foundry 프로젝트 생성: $PROJECT_NAME" \
    || echo "      [참고] 프로젝트 생성 생략/실패(권한 또는 미지원). Content Understanding 사용에는 영향 없음."
fi


# ── 3) 모델 배포 ───────────────────────────────────────────────────────
deploy_model() {
  local model="$1" capacity_cap="$2"

  if az cognitiveservices account deployment show \
        -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" --deployment-name "$model" >/dev/null 2>&1; then
    echo "      배포 이미 존재: $model"
    return 0
  fi

  # 모델의 최신 버전과 시도할 SKU 후보 목록(선호 순서)을 가져온다.
  # 출력 1행: version, 이후 각 행: "sku<TAB>capacity"
  local plan
  plan=$(az cognitiveservices account list-models -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" -o json \
        | MODEL="$model" CAP="$capacity_cap" "$PYTHON_BIN" -c '
import json, os, sys
models = json.load(sys.stdin)
name, cap = os.environ["MODEL"], int(os.environ["CAP"])
cand = [m for m in models if m.get("name") == name and m.get("format") == "OpenAI"]
if not cand:
    print("NONE"); sys.exit(0)
cand.sort(key=lambda m: m.get("version", ""))
m = cand[-1]
avail = {s.get("name"): (s.get("capacity") or {}) for s in m.get("skus", [])}
pref = ["GlobalStandard", "Standard", "DataZoneStandard"]
ordered = [s for s in pref if s in avail] + [s for s in avail if s not in pref]
sys.stdout.write((m.get("version") or "") + "\n")
for sku in ordered:
    c = avail[sku]
    default_cap = c.get("default") or c.get("maximum") or 1
    cap_final = min(int(default_cap), cap) if default_cap else cap
    sys.stdout.write(sku + "\t" + str(cap_final) + "\n")
')

  if [ "$plan" = "NONE" ] || [ -z "$plan" ]; then
    echo "      [경고] 리전 '$LOCATION' 에서 모델 '$model' 을(를) 찾을 수 없습니다. 다른 리전을 시도하세요."
    return 1
  fi

  local version
  version="$(printf '%s\n' "$plan" | head -n1)"

  # SKU 후보를 순서대로 시도하고, 할당량(quota) 부족 시 다음 SKU 로 폴백
  local line sku capacity
  while IFS=$'\t' read -r sku capacity; do
    [ -z "$sku" ] && continue
    echo "      배포 시도: $model (version=$version, sku=$sku, capacity=$capacity)"
    if az cognitiveservices account deployment create \
        -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" \
        --deployment-name "$model" \
        --model-name "$model" --model-version "$version" --model-format OpenAI \
        --sku-name "$sku" --sku-capacity "$capacity" \
        --only-show-errors -o none 2>/dev/null; then
      echo "      배포 성공: $model ($sku)"
      return 0
    fi
    echo "      -> $sku 실패(할당량 부족 등). 다음 SKU 시도..."
  done < <(printf '%s\n' "$plan" | tail -n +2)

  echo "      [경고] '$model' 배포 실패. 'az cognitiveservices usage list -l $LOCATION' 로 할당량을 확인하거나 다른 리전을 시도하세요."
  return 1
}

echo "[3/5] 모델 배포 (gpt-4.1, gpt-4.1-mini, text-embedding-3-large)..."
deploy_model "gpt-4.1" 30 || true
deploy_model "gpt-4.1-mini" 30 || true
deploy_model "text-embedding-3-large" 50 || true

# 배포 결과 검증 — 누락 모델을 수집(성공으로 오인하지 않도록)
echo "      배포 상태 확인..."
MISSING_MODELS=""
for req in gpt-4.1 gpt-4.1-mini text-embedding-3-large; do
  state="$(az cognitiveservices account deployment show -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" --deployment-name "$req" --query "properties.provisioningState" -o tsv 2>/dev/null || true)"
  if [ "$state" = "Succeeded" ]; then
    echo "        [OK]   $req"
  else
    echo "        [누락] $req (상태: ${state:-없음})"
    MISSING_MODELS="$MISSING_MODELS $req"
  fi
done

# ── 4) 역할 부여 ───────────────────────────────────────────────────────
# 이 리소스는 보안 기본값으로 키(로컬) 인증이 비활성화되어 있어 Entra ID 인증을 사용합니다.
# 따라서 호출 주체에게 'Cognitive Services User' 역할이 필요합니다.
echo "[4/5] 'Cognitive Services User' 역할 부여..."
ACCOUNT_ID="$(az cognitiveservices account show -n "$ACCOUNT_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)"
USER_OID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)"
ROLE_OK=0
if [ -n "$USER_OID" ]; then
  if az role assignment create \
       --assignee-object-id "$USER_OID" --assignee-principal-type User \
       --role "Cognitive Services User" --scope "$ACCOUNT_ID" \
       --only-show-errors -o none 2>/dev/null; then
    echo "      부여 완료 (전파에 1~2분 소요될 수 있음)"
    ROLE_OK=1
  elif az role assignment list --assignee "$USER_OID" --scope "$ACCOUNT_ID" \
         --query "[?roleDefinitionName=='Cognitive Services User']" -o tsv 2>/dev/null | grep -q .; then
    echo "      이미 부여되어 있습니다."
    ROLE_OK=1
  else
    echo "      [경고] 역할을 자동 부여하지 못했습니다."
    echo "             역할 부여에는 이 스코프의 Owner 또는 User Access Administrator 권한이 필요합니다."
    echo "             관리자에게 다음 역할 부여를 요청하세요: 리소스 '$ACCOUNT_NAME' 에 대해 'Cognitive Services User'."
  fi
else
  echo "      [경고] 로그인 사용자 ID 조회 실패 — 수동으로 'Cognitive Services User' 역할을 부여하세요."
fi

# ── 5) .env 작성 ───────────────────────────────────────────────────────
echo "[5/5] .env 파일 작성..."
ENDPOINT="https://${ACCOUNT_NAME}.services.ai.azure.com/"

cat > "$ENV_FILE" <<EOF
# infra/setup_azure.sh 가 자동 생성한 파일입니다.
CONTENTUNDERSTANDING_ENDPOINT=${ENDPOINT}

# 인증: DefaultAzureCredential(az login) 사용. 'Cognitive Services User' 역할이 필요합니다.
# (이 리소스는 보안 기본값으로 키 인증이 비활성화되어 있습니다.)
CONTENTUNDERSTANDING_KEY=

WORK_ORDER_ANALYZER_ID=trade_work_order

GPT_4_1_DEPLOYMENT=gpt-4.1
GPT_4_1_MINI_DEPLOYMENT=gpt-4.1-mini
TEXT_EMBEDDING_3_LARGE_DEPLOYMENT=text-embedding-3-large

COMPLETION_MODEL=gpt-4.1
EMBEDDING_MODEL=text-embedding-3-large
EOF

echo "=========================================================="
if [ -n "$MISSING_MODELS" ]; then
  echo " ⚠ 경고: 일부 필수 모델이 배포되지 않았습니다 →${MISSING_MODELS}"
  echo "   원인은 대개 리전 할당량 부족입니다. 아래 중 하나로 해결하세요:"
  echo "     - 'az cognitiveservices usage list -l $LOCATION -o table' 로 할당량 확인"
  echo "     - 다른 리전으로 재실행: LOCATION=<region> bash infra/setup_azure.sh"
  echo "     - 포털에서 해당 모델 할당량 증설 요청"
  echo "   ※ 누락 모델을 배포하기 전에는 setup_defaults / 추출이 실패할 수 있습니다."
  echo "----------------------------------------------------------"
fi
if [ "$ROLE_OK" != "1" ]; then
  echo " ⚠ 경고: 'Cognitive Services User' 역할이 부여되지 않았습니다."
  echo "   역할이 없으면 setup_defaults / 추출이 401/403 으로 실패합니다."
  echo "   Owner/User Access Administrator 권한이 있으면 본 스크립트를 다시 실행하거나,"
  echo "   관리자에게 리소스 '$ACCOUNT_NAME' 의 'Cognitive Services User' 역할 부여를 요청하세요."
  echo "----------------------------------------------------------"
fi
echo " 완료!  엔드포인트: $ENDPOINT"
echo "=========================================================="
echo "다음 단계:"
echo "  1) python3 -m venv .venv && source .venv/bin/activate   # Windows(Git Bash): source .venv/Scripts/activate"
echo "  2) pip install -r requirements.txt"
echo "  3) python -m src.setup_defaults          # 모델 매핑(1회)"
echo "  4) python -m src.extract_work_order 작업지시서.pdf"
echo ""
echo "참고: 역할 전파 지연으로 3) 단계가 처음에 401/403 으로 실패하면 1~2분 후 다시 실행하세요."
