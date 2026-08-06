# ingest_transcript.py
from google.cloud import spanner, aiplatform
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

PROJECT_ID = "YOUR_GCP_PROJECT"
INSTANCE_ID = "YOUR_SPANNER_INSTANCE"
DATABASE_ID = "YOUR_SPANNER_DATABASE"

VIDEO_ID = "moving_google_app"
TITLE = "Moving - Meet the Google App"
GCS_VIDEO_URI = "gs://YOUR_SPANNER_INSTANCE/moving_google_app.mp4"

TRANSCRIPT_DATA = [
    {"id": 1, "start": 0, "end": 2, "text": "lift with your legs."},
    {"id": 2, "start": 2, "end": 5, "text": "It's not going to fit up the stairs."},
    {"id": 3, "start": 5, "end": 6, "text": "What time does Goodwill close?"},
    {"id": 4, "start": 6, "end": 9, "text": "Goodwill is open until 9:00 p.m."},
    {"id": 5, "start": 9, "end": 10, "text": "Show me a moving company nearby."},
    {"id": 6, "start": 10, "end": 12, "text": "Moving company within 6 miles."},
    {"id": 7, "start": 12, "end": 16, "text": "How do I get to 3221 Carter A 226 High Street?"},
    {"id": 8, "start": 16, "end": 17, "text": "Here are your directions."},
    {"id": 9, "start": 17, "end": 19, "text": "When does my package arrive?"},
    {"id": 10, "start": 19, "end": 21, "text": "Your most recent order has shipped."},
    {"id": 11, "start": 21, "end": 22, "text": "Thank you."},
    {"id": 12, "start": 22, "end": 24, "text": "Setting new home address."},
    {"id": 13, "start": 24, "end": 28, "text": "Text mom. I really like it here."}
]

def ingest_transcript():
    print(f"📝 Loading actual transcript blocks. Embedding with 'text-embedding-004'...")
    aiplatform.init(project=PROJECT_ID)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    
    inputs = [TextEmbeddingInput(b["text"], "RETRIEVAL_DOCUMENT") for b in TRANSCRIPT_DATA]
    embeddings = model.get_embeddings(inputs)
    
    print("💾 Connecting to Spanner...")
    spanner_client = spanner.Client(project=PROJECT_ID)
    database = spanner_client.instance(INSTANCE_ID).database(DATABASE_ID)
    
    def write_tx(transaction):
        transaction.insert_or_update(
            "TranscriptVideos",
            columns=["VideoId", "Title", "GcsUri"],
            values=[(VIDEO_ID, TITLE, GCS_VIDEO_URI)]
        )
        
        transcript_rows = []
        for i, block in enumerate(TRANSCRIPT_DATA):
            transcript_rows.append((
                VIDEO_ID, block["id"], block["start"], block["end"], block["text"], embeddings[i].values
            ))
            
        print("📥 Storing transcript and vectors in Spanner...")
        transaction.insert_or_update(
            "VideoTranscripts",
            columns=["VideoId", "TranscriptId", "StartOffsetSec", "EndOffsetSec", "SubtitleText", "Embedding"],
            values=transcript_rows
        )
        
    database.run_in_transaction(write_tx)
    print("✅ Transcript Ingestion Complete!")

if __name__ == "__main__":
    ingest_transcript()

