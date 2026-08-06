# ingest_visual.py
from google.cloud import aiplatform, spanner
from vertexai.vision_models import MultiModalEmbeddingModel, Video, VideoSegmentConfig

# ==========================================
# 🔧 Configure Your GCP & Spanner Settings
# ==========================================
PROJECT_ID = "YOUR_GCP_PROJECT"
INSTANCE_ID = "YOUR_SPANNER_INSTANCE"
DATABASE_ID = "YOUR_SPANNER_DATABASE"

VIDEO_ID = "moving_google_app"
TITLE = "Moving - Meet the Google App"
GCS_URI = "gs://YOUR_SPANNER_INSTANCE/moving_google_app.mp4"
INTERVAL_SEC = 4  # Legal minimum for the API

def ingest_visual_video():
    print("🚀 Initializing Vertex AI Multimodal Embedding Model...")
    aiplatform.init(project=PROJECT_ID)
    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
    
    video = Video.load_from_file(GCS_URI) 
    
    print(f"🎞️ Generating high-precision visual embeddings (4-second intervals)...")
    try:
        embeddings = model.get_embeddings(
            video=video,
            video_segment_config=VideoSegmentConfig(
                start_offset_sec=0, 
                interval_sec=INTERVAL_SEC
            )
        )
    except Exception as e:
        print(f"❌ Failed to retrieve embeddings from Vertex AI: {e}")
        return

    num_segments = len(embeddings.video_embeddings)
    print(f"🎯 Vertex AI successfully returned {num_segments} visual segments!")
    
    print("💾 Connecting to Cloud Spanner...")
    spanner_client = spanner.Client(project=PROJECT_ID)
    database = spanner_client.instance(INSTANCE_ID).database(DATABASE_ID)
    
    def write_tx(transaction):
        print(f"📥 Loading/Updating video metadata for '{TITLE}'...")
        transaction.insert_or_update(
            "VisualVideos",
            columns=["VideoId", "Title", "GcsUri"],
            values=[(VIDEO_ID, TITLE, GCS_URI)]
        )
        
        segment_rows = []
        for i, emb in enumerate(embeddings.video_embeddings):
            segment_rows.append((
                VIDEO_ID, 
                i, 
                int(emb.start_offset_sec), 
                int(emb.end_offset_sec), 
                emb.embedding
            ))
            
        print(f"📥 Inserting {len(segment_rows)} visual segments into Spanner...")
        transaction.insert_or_update(
            "VisualVideoSegments",
            columns=["VideoId", "SegmentId", "StartOffsetSec", "EndOffsetSec", "Embedding"],
            values=segment_rows
        )
        
    try:
        database.run_in_transaction(write_tx)
        print("✅ Visual Ingestion Complete!")
    except Exception as e:
        print(f"❌ Transaction failed on Spanner: {e}")

if __name__ == "__main__":
    ingest_visual_video()

