#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# One-time: Store all secrets in Google Cloud Secret Manager
# Usage: ./deploy/setup-secrets.sh
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - GCP_PROJECT_ID env var set
#   - Fill in values below before running
# ═══════════════════════════════════════════════════════════════

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[OK]${NC} $1"; }

store_secret() {
    local name="$1" value="$2"
    if [ -z "$value" ] || [ "$value" = "FILL_ME" ]; then
        echo -e "${RED}[SKIP]${NC} $name — empty value, set it manually later"
        return
    fi
    echo -n "$value" | gcloud secrets create "$name" \
        --data-file=- --replication-policy=automatic \
        --project="$PROJECT_ID" 2>/dev/null || \
    echo -n "$value" | gcloud secrets versions add "$name" \
        --data-file=- --project="$PROJECT_ID"
    info "$name"
}

echo "Storing backend secrets..."

# ─── Fill in these values ───
store_secret "kodama-database-url"        "FILL_ME"  # auto-set by deploy.sh setup
store_secret "kodama-livekit-url"         "wss://rain-rzuxgl19.livekit.cloud"
store_secret "kodama-livekit-api-key"     "FILL_ME"
store_secret "kodama-livekit-api-secret"  "FILL_ME"
store_secret "kodama-aihubmix-api-key"    "FILL_ME"
store_secret "kodama-dashscope-api-key"   "FILL_ME"

# Firebase service account JSON (paste as string or use file)
# store_secret "kodama-firebase-credentials" "$(cat path/to/firebase-sa.json)"
store_secret "kodama-firebase-credentials" "FILL_ME"

echo ""
echo "Storing frontend build secrets..."

store_secret "kodama-frontend-api-url"                "FILL_ME"  # e.g. https://kodama-backend-xxx.run.app
store_secret "kodama-firebase-api-key"                "FILL_ME"
store_secret "kodama-firebase-auth-domain"            "FILL_ME"  # e.g. your-project.firebaseapp.com
store_secret "kodama-firebase-project-id"             "FILL_ME"
store_secret "kodama-firebase-storage-bucket"         "FILL_ME"
store_secret "kodama-firebase-messaging-sender-id"    "FILL_ME"
store_secret "kodama-firebase-app-id"                 "FILL_ME"

echo ""
echo "Done. Update FILL_ME values with:"
echo "  gcloud secrets versions add SECRET_NAME --data-file=- --project=$PROJECT_ID <<< 'value'"
