# Kodama Google Cloud Deployment Guide

Goal: Deploy to Google Cloud, internet-accessible, GitHub/Google login, tenant isolation.

## Architecture

```
Internet
   │
   ├── kodama-frontend (Cloud Run)  ← Next.js SSR
   │       │
   │       ▼
   ├── kodama-backend (Cloud Run)   ← FastAPI API server
   │       │
   │       ├── Cloud SQL (PostgreSQL 15)
   │       └── Secret Manager (all credentials)
   │
   └── kodama-worker (Cloud Run)    ← LiveKit Agent Worker
           │
           ├── LiveKit Cloud (wss://...)  ← WebRTC signaling
           ├── AIHubMix (LLM/TTS gateway)
           └── DashScope (ASR/TTS)

Auth: Firebase Auth (Google + GitHub OAuth)
CI/CD: GitHub Actions → Artifact Registry → Cloud Run
```

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- GitHub repo with Actions enabled
- Firebase project created

---

## Step 1: Create GCP Project

```bash
export GCP_PROJECT_ID=kodama-492602
export GCP_REGION=asia-east1

gcloud projects create $GCP_PROJECT_ID --name="Kodama"
gcloud config set project $GCP_PROJECT_ID

# Enable billing (required for Cloud SQL)
# Go to: https://console.cloud.google.com/billing
```

## Step 2: Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com
```

## Step 3: Create Artifact Registry

```bash
gcloud artifacts repositories create kodama \
  --repository-format=docker \
  --location=$GCP_REGION
```

## Step 4: Create Cloud SQL (PostgreSQL)

```bash
# Create instance (~5 min)
gcloud sql instances create kodama-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$GCP_REGION \
  --storage-size=10GB \
  --storage-auto-increase

# Create database
gcloud sql databases create kodama --instance=kodama-db

# Create user
DB_PASSWORD=$(openssl rand -base64 24)
gcloud sql users create kodama --instance=kodama-db --password="$DB_PASSWORD"

echo "Save this password: $DB_PASSWORD"

# Run schema
# Option A: Cloud SQL Auth Proxy
gcloud sql connect kodama-db --user=kodama --database=kodama < deploy/schema.sql

# Option B: via Cloud Shell
# Upload deploy/schema.sql, then run above command
```

## Step 5: Setup Firebase Auth

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create project (or link to existing GCP project `$GCP_PROJECT_ID`)
3. Enable Authentication:
   - Sign-in methods → Enable **Google**
   - Sign-in methods → Enable **GitHub**
     - GitHub OAuth App: `https://github.com/settings/developers`
     - Set callback URL from Firebase console
4. Get Web App config:
   - Project Settings → General → Your apps → Add Web App
   - Copy the config object (apiKey, authDomain, projectId, etc.)
5. Generate service account key:
   - Project Settings → Service accounts → Generate new private key
   - Save as `firebase-sa.json`

## Step 6: Store Secrets

```bash
CONNECTION_NAME=$(gcloud sql instances describe kodama-db \
  --format='value(connectionName)')

# Backend secrets
echo -n "postgresql+asyncpg://kodama:${DB_PASSWORD}@/${kodama}?host=/cloudsql/${CONNECTION_NAME}" | \
  gcloud secrets create kodama-database-url --data-file=-

# LiveKit (from your LiveKit Cloud dashboard)
echo -n "wss://your-project.livekit.cloud" | \
  gcloud secrets create kodama-livekit-url --data-file=-
echo -n "YOUR_LIVEKIT_API_KEY" | \
  gcloud secrets create kodama-livekit-api-key --data-file=-
echo -n "YOUR_LIVEKIT_API_SECRET" | \
  gcloud secrets create kodama-livekit-api-secret --data-file=-

# AI Providers
echo -n "sk-YOUR_AIHUBMIX_KEY" | \
  gcloud secrets create kodama-aihubmix-api-key --data-file=-
echo -n "sk-YOUR_DASHSCOPE_KEY" | \
  gcloud secrets create kodama-dashscope-api-key --data-file=-

# Firebase service account
cat firebase-sa.json | \
  gcloud secrets create kodama-firebase-credentials --data-file=-
```

## Step 7: Create Service Account for GitHub Actions

```bash
# Create SA
gcloud iam service-accounts create kodama-deployer \
  --display-name="Kodama CI/CD Deployer"

SA_EMAIL=kodama-deployer@${GCP_PROJECT_ID}.iam.gserviceaccount.com

# Grant roles
for ROLE in \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor \
  roles/cloudsql.client \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}"
done

# Also grant Cloud Run service agent access to secrets
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Generate key
gcloud iam service-accounts keys create sa-key.json \
  --iam-account=$SA_EMAIL

echo "Upload sa-key.json content as GitHub Secret: GCP_SA_KEY"
```

## Step 8: Configure GitHub Secrets

Go to GitHub repo → Settings → Secrets and variables → Actions.

Add these secrets:

| Secret | Value |
|--------|-------|
| `GCP_PROJECT_ID` | your GCP project ID |
| `GCP_SA_KEY` | Content of `sa-key.json` |
| `GCP_REGION` | `asia-east1` |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | From Firebase console |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `your-project.firebaseapp.com` |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Firebase project ID |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | `your-project.firebasestorage.app` |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | From Firebase config |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | From Firebase config |

## Step 9: First Deploy

```bash
git add -A
git commit -m "feat: Google Cloud deployment with Firebase Auth + tenant isolation"
git push origin main
```

GitHub Actions will:
1. Run backend tests (pytest, SQLite)
2. Build & push backend + worker images
3. Deploy backend + worker to Cloud Run
4. Build frontend (injecting backend URL)
5. Deploy frontend to Cloud Run
6. Update backend CORS with frontend URL

## Step 10: Seed Production Database

After first deploy, seed the database:

```bash
# Connect via Cloud SQL Auth Proxy
cloud-sql-proxy $CONNECTION_NAME &

# Or run directly on Cloud Run
gcloud run jobs create kodama-seed \
  --image=$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/kodama/backend:latest \
  --region=$GCP_REGION \
  --add-cloudsql-instances=$CONNECTION_NAME \
  --set-secrets="DATABASE_URL=kodama-database-url:latest" \
  --set-env-vars="APP_ENV=production" \
  --command="python,-m,backend.db.seed" \
  --execute-now
```

## Step 11: Verify

1. Open frontend URL from GitHub Actions summary
2. Click "Continue with Google" → should redirect to Google OAuth
3. Click "Continue with GitHub" → should redirect to GitHub OAuth
4. After login, you should see 0 agents (new tenant, isolated)
5. Create an agent → only visible to your organization

## Custom Domain (Optional)

```bash
# Map custom domain to frontend
gcloud run domain-mappings create \
  --service=kodama-frontend \
  --domain=kodama.yourdomain.com \
  --region=$GCP_REGION

# Map API domain
gcloud run domain-mappings create \
  --service=kodama-backend \
  --domain=api.kodama.yourdomain.com \
  --region=$GCP_REGION

# Then update:
# 1. DNS CNAME records as shown by gcloud
# 2. CORS_ORIGINS on backend
# 3. Firebase authorized domains
# 4. GitHub OAuth callback URL
```

## Cost Estimate (Low Traffic)

| Service | Config | Monthly |
|---------|--------|---------|
| Cloud SQL | db-f1-micro | ~$10 |
| Cloud Run (backend) | min=0, max=3 | ~$0-5 |
| Cloud Run (worker) | min=1 (always on) | ~$15-25 |
| Cloud Run (frontend) | min=0, max=3 | ~$0-3 |
| Artifact Registry | Storage | ~$1 |
| **Total** | | **~$25-45/mo** |

## Troubleshooting

```bash
# View logs
gcloud run services logs read kodama-backend --region=$GCP_REGION --limit=50
gcloud run services logs read kodama-worker --region=$GCP_REGION --limit=50

# Check service status
gcloud run services describe kodama-backend --region=$GCP_REGION
gcloud run services describe kodama-frontend --region=$GCP_REGION

# Force redeploy
# Go to GitHub → Actions → Run workflow (manual dispatch)

# Test backend health
curl https://kodama-backend-xxx.run.app/health
```
