#!/usr/bin/env bash
#
# setup_azure.sh 로 만든 리소스를 정리한다. (과금 중단)
# 기본적으로 리소스 그룹 전체를 삭제한다.
#
# 사용법:
#   ./infra/teardown_azure.sh
#   RESOURCE_GROUP=rg-trade-content-understanding ./infra/teardown_azure.sh
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-trade-content-understanding}"

echo "리소스 그룹 '$RESOURCE_GROUP' 을(를) 삭제합니다. 포함된 모든 리소스가 제거됩니다."
read -r -p "계속하려면 'yes' 입력: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "취소되었습니다."
  exit 0
fi

az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "삭제 요청 완료(백그라운드 진행). 상태: az group show -n $RESOURCE_GROUP"
