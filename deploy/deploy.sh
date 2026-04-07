#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# Kodama — Google Cloud Deployment Script
# Usage: ./deploy/deploy.sh [setup|build|deploy|all]
# ═══════════════════════════════════════════════════════════════

# ─── Configuration (edit these) ───
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-asia-east1}"
DB_INSTANCE="kodama-db"
DB_NAME="kodama"
DB_USER="kodama"
REPO="kodama"

BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend"
WORKER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/worker"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend"

# ─── Colors ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ═══════════════════════════════════════════════════════════════
# Phase 1: One-time Setup
# ═══════════════════════════════════════════════════════════════
setup() {
    info "Phase 1: Setting up Google Cloud infrastructure..."

    # Enable APIs
    info "Enabling APIs..."
    gcloud services enable \
        run.googleapis.com \
        sqladmin.googleapis.com \
        secretmanager.googleapis.com \
        artifactregistry.googleapis.com \
        --project="${PROJECT_ID}"

    # Create Artifact Registry repo
    info "Creating Artifact Registry repository..."
    gcloud artifacts repositories create "${REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --project="${PROJECT_ID}" 2>/dev/null || true

    # Create Cloud SQL instance
    info "Creating Cloud SQL PostgreSQL instance..."
    gcloud sql instances describe "${DB_INSTANCE}" --project="${PROJECT_ID}" 2>/dev/null || \
    gcloud sql instances create "${DB_INSTANCE}" \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region="${REGION}" \
        --storage-size=10GB \
        --storage-auto-increase \
        --project="${PROJECT_ID}"

    # Create database and user
    info "Creating database and user..."
    gcloud sql databases create "${DB_NAME}" \
        --instance="${DB_INSTANCE}" \
        --project="${PROJECT_ID}" 2>/dev/null || true

    DB_PASSWORD=$(openssl rand -base64 24)
    gcloud sql users create "${DB_USER}" \
        --instance="${DB_INSTANCE}" \
        --password="${DB_PASSWORD}" \
        --project="${PROJECT_ID}" 2>/dev/null || true

    # Store secrets
    info "Storing secrets in Secret Manager..."
    CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" --format='value(connectionName)' --project="${PROJECT_ID}")
    DB_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

    _store_secret "kodama-database-url" "${DB_URL}"

    # Initialize database schema
    info "Running schema migration..."
    info "  Connect to Cloud SQL and run: psql -f deploy/schema.sql"
    info "  Then run: python -m backend.db.seed (to seed agent data)"

    echo ""
    info "=== Setup complete ==="
    info "Remaining manual steps:"
    info "  1. Store secrets: kodama-livekit-url, kodama-livekit-api-key, kodama-livekit-api-secret"
    info "  2. Store secrets: kodama-aihubmix-api-key, kodama-dashscope-api-key"
    info "  3. Store secret:  kodama-firebase-credentials (JSON string)"
    info "  4. Run schema.sql on Cloud SQL"
    info "  5. Run: ./deploy/deploy.sh build"
    info "  6. Run: ./deploy/deploy.sh deploy"
    echo ""
    warn "DB password generated: ${DB_PASSWORD}"
    warn "Save this password securely — it won't be shown again."
}

_store_secret() {
    local name="$1" value="$2"
    echo -n "${value}" | gcloud secrets create "${name}" \
        --data-file=- \
        --replication-policy="automatic" \
        --project="${PROJECT_ID}" 2>/dev/null || \
    echo -n "${value}" | gcloud secrets versions add "${name}" \
        --data-file=- \
        --project="${PROJECT_ID}"
}

# ═══════════════════════════════════════════════════════════════
# Phase 2: Build & Push Images
# ═══════════════════════════════════════════════════════════════
build() {
    info "Phase 2: Building Docker images..."

    # Configure Docker auth
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

    # Build backend
    info "Building backend..."
    docker build -t "${BACKEND_IMAGE}:latest" -f Dockerfile.backend .

    # Build worker
    info "Building worker..."
    docker build -t "${WORKER_IMAGE}:latest" -f Dockerfile.worker .

    # Build frontend (needs build args)
    info "Building frontend..."
    if [ -f deploy/.env.frontend.production ]; then
        BUILD_ARGS=""
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            BUILD_ARGS="${BUILD_ARGS} --build-arg ${key}=${value}"
        done < deploy/.env.frontend.production
        eval docker build ${BUILD_ARGS} -t "${FRONTEND_IMAGE}:latest" -f Dockerfile.frontend .
    else
        warn "deploy/.env.frontend.production not found, building without env vars"
        docker build -t "${FRONTEND_IMAGE}:latest" -f Dockerfile.frontend .
    fi

    # Push
    info "Pushing images..."
    docker push "${BACKEND_IMAGE}:latest"
    docker push "${WORKER_IMAGE}:latest"
    docker push "${FRONTEND_IMAGE}:latest"

    info "Build & push complete."
}

# ═══════════════════════════════════════════════════════════════
# Phase 3: Deploy to Cloud Run
# ═══════════════════════════════════════════════════════════════
deploy() {
    info "Phase 3: Deploying to Cloud Run..."

    CONNECTION_NAME=$(gcloud sql instances describe "${DB_INSTANCE}" --format='value(connectionName)' --project="${PROJECT_ID}")
    FRONTEND_URL=$(gcloud run services describe kodama-frontend --region="${REGION}" --format='value(status.url)' --project="${PROJECT_ID}" 2>/dev/null || echo "https://kodama-frontend-xxx.run.app")

    # Deploy backend
    info "Deploying backend..."
    gcloud run deploy kodama-backend \
        --image="${BACKEND_IMAGE}:latest" \
        --region="${REGION}" \
        --platform=managed \
        --allow-unauthenticated \
        --port=8000 \
        --cpu=1 --memory=512Mi \
        --min-instances=0 --max-instances=3 \
        --add-cloudsql-instances="${CONNECTION_NAME}" \
        --set-secrets="DATABASE_URL=kodama-database-url:latest,LIVEKIT_URL=kodama-livekit-url:latest,LIVEKIT_API_KEY=kodama-livekit-api-key:latest,LIVEKIT_API_SECRET=kodama-livekit-api-secret:latest,AIHUBMIX_API_KEY=kodama-aihubmix-api-key:latest,DASHSCOPE_API_KEY=kodama-dashscope-api-key:latest,FIREBASE_CREDENTIALS_JSON=kodama-firebase-credentials:latest" \
        --set-env-vars="APP_ENV=production,APP_DEBUG=false,AUTH_PROVIDER=firebase,AIHUBMIX_BASE_URL=https://aihubmix.com/v1,CORS_ORIGINS=${FRONTEND_URL}" \
        --project="${PROJECT_ID}"

    BACKEND_URL=$(gcloud run services describe kodama-backend --region="${REGION}" --format='value(status.url)' --project="${PROJECT_ID}")
    info "Backend deployed: ${BACKEND_URL}"

    # Deploy worker
    info "Deploying worker..."
    gcloud run deploy kodama-worker \
        --image="${WORKER_IMAGE}:latest" \
        --region="${REGION}" \
        --platform=managed \
        --no-allow-unauthenticated \
        --cpu=2 --memory=1Gi \
        --min-instances=1 --max-instances=2 \
        --no-cpu-throttling \
        --add-cloudsql-instances="${CONNECTION_NAME}" \
        --set-secrets="DATABASE_URL=kodama-database-url:latest,LIVEKIT_URL=kodama-livekit-url:latest,LIVEKIT_API_KEY=kodama-livekit-api-key:latest,LIVEKIT_API_SECRET=kodama-livekit-api-secret:latest,AIHUBMIX_API_KEY=kodama-aihubmix-api-key:latest,DASHSCOPE_API_KEY=kodama-dashscope-api-key:latest,FIREBASE_CREDENTIALS_JSON=kodama-firebase-credentials:latest" \
        --set-env-vars="APP_ENV=production,APP_DEBUG=false,AIHUBMIX_BASE_URL=https://aihubmix.com/v1" \
        --project="${PROJECT_ID}"

    info "Worker deployed."

    # Deploy frontend
    info "Deploying frontend..."
    gcloud run deploy kodama-frontend \
        --image="${FRONTEND_IMAGE}:latest" \
        --region="${REGION}" \
        --platform=managed \
        --allow-unauthenticated \
        --port=3000 \
        --cpu=1 --memory=256Mi \
        --min-instances=0 --max-instances=3 \
        --project="${PROJECT_ID}"

    FRONTEND_URL=$(gcloud run services describe kodama-frontend --region="${REGION}" --format='value(status.url)' --project="${PROJECT_ID}")
    info "Frontend deployed: ${FRONTEND_URL}"

    # Update backend CORS with actual frontend URL
    info "Updating backend CORS with frontend URL..."
    gcloud run services update kodama-backend \
        --region="${REGION}" \
        --update-env-vars="CORS_ORIGINS=${FRONTEND_URL}" \
        --project="${PROJECT_ID}"

    echo ""
    info "=== Deployment complete ==="
    info "Frontend: ${FRONTEND_URL}"
    info "Backend:  ${BACKEND_URL}"
}

# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
case "${1:-all}" in
    setup)  setup ;;
    build)  build ;;
    deploy) deploy ;;
    all)    setup && build && deploy ;;
    *)      echo "Usage: $0 [setup|build|deploy|all]"; exit 1 ;;
esac
