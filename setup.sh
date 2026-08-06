#!/bin/bash
# setup.sh

# Exit immediately if any command fails
set -e

echo "🚀 Starting Cloud Spanner Video Search Hub Auto-Deployment..."

# 1. Collect Project Variables
read -p "Enter GCP Project ID [YOUR_GCP_PROJECT]: " PROJECT_ID
PROJECT_ID=${PROJECT_ID:-"YOUR_GCP_PROJECT"}

read -p "Enter Spanner Instance ID [YOUR_SPANNER_INSTANCE]: " INSTANCE_ID
INSTANCE_ID=${INSTANCE_ID:-"YOUR_SPANNER_INSTANCE"}

read -p "Enter Spanner Database ID [YOUR_SPANNER_DATABASE]: " DATABASE_ID
DATABASE_ID=${DATABASE_ID:-"YOUR_SPANNER_DATABASE"}

read -p "Enter GCS Bucket Name [YOUR_SPANNER_INSTANCE]: " GCS_BUCKET
GCS_BUCKET=${GCS_BUCKET:-"YOUR_SPANNER_INSTANCE"}

# Set GCP Context
gcloud config set project "$PROJECT_ID"

# 2. Enable Required GCP APIs
echo "🌐 Enabling Spanner and Vertex AI APIs..."
gcloud services enable spanner.googleapis.com aiplatform.googleapis.com storage.googleapis.com --async

# 3. Create Spanner Instance (If missing)
if ! gcloud spanner instances describe "$INSTANCE_ID" &>/dev/null; then
    echo "💾 Creating Spanner Instance: $INSTANCE_ID (Regional: us-central1)..."
    gcloud spanner instances create "$INSTANCE_ID" \
        --config=regional-us-central1 \
        --description="Media Streaming Demo Instance" \
        --processing-units=100
else
    echo "✅ Spanner Instance '$INSTANCE_ID' already exists."
fi

# 4. Create Spanner Database and Apply DDL Schema
if ! gcloud spanner databases describe --instance="$INSTANCE_ID" "$DATABASE_ID" &>/dev/null; then
    echo "📂 Creating Database '$DATABASE_ID' and applying schema.sql..."
    gcloud spanner databases create "$DATABASE_ID" \
        --instance="$INSTANCE_ID" \
        --ddl-file=schema.sql
else
    echo "✅ Spanner Database '$DATABASE_ID' already exists."
fi

# 5. Set up Python Environment & Install Dependencies
echo "🐍 Setting up Python Virtual Environment (venv)..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Fetch the Video File locally
if [ ! -f "moving_google_app.mp4" ]; then
    echo "🎥 Fetching local playback video 'moving_google_app.mp4' from GCS..."
    gcloud storage cp gs://"$GCS_BUCKET"/moving_google_app.mp4 ./moving_google_app.mp4 || {
        echo "⚠️ Could not download moving_google_app.mp4. Please copy it manually to this folder!"
    }
fi

# 7. Execute Ingestion Pipelines
read -p "📥 Do you want to run the ingestion pipelines now? (y/n) [y]: " RUN_INGEST
RUN_INGEST=${RUN_INGEST:-"y"}

if [ "$RUN_INGEST" == "y" ]; then
    echo "🧠 Running Visual Vector Ingestion..."
    python3 ingest_visual.py
    echo "🗣️ Running Dialogue Transcript Ingestion..."
    python3 ingest_transcript.py
    echo "✅ Database tables fully populated!"
fi

# 8. Start Web Server
echo "🚀 Booting up Streamlit Search Hub on Port 8080..."
streamlit run app.py --server.port 8080
