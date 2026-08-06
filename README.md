# Cloud Spanner In-Video Search Hub 🎥

A production-ready multi-modal, semantic, and full-text hybrid in-video search application powered by **Cloud Spanner** and **Vertex AI**.

This application splits the video-searching process into two parallel tracks:
1. **Visual Search**: Generates 1408-dimensional embeddings of video frames using Vertex AI's `multimodalembedding@001` and queries them natively in Spanner using `COSINE_DISTANCE`.
2. **Dialogue Search**: Generates 768-dimensional embeddings of video transcripts using `text-embedding-004` and queries them alongside tokenized full-text keywords.

---

## 🎯 Key Application Features (4-Tab Interface)

*   **👁️ Tab 1: Visual Search** - Search across video scenes using pure visual descriptions. Translates inputs into 1408-dimensional vectors to find matching frame boundaries.
*   **💬 Tab 2: Transcript Search** - Choose between semantic vector searches (finding conceptual dialogue matches) or Full-Text Keyword Indexes (tokenized FTS keyword lookups).
*   **🌀 Tab 3: Unified Search** - Combines visual and spoken criteria. Executes a co-located relational `JOIN` that finds visual moments where specific keywords are spoken within a localized temporal window.
*   **🤖 Tab 4: Autonomous Hybrid Search** - The showstopper feature. Leverages **Gemini 2.5 Flash** as an intelligent query decomposer to automatically extract the visual intent and spoken keywords from a single, natural-language sentence. It then executes a compiler-safe, programmatic fallback routine to deliver error-free hybrid results.

---

## 🚀 One-Click Future Deployment

To deploy this entire architecture onto any Google Cloud Project from scratch:

1. Clone this repository:
   ```bash
   git clone https://github.com/saurabh8774/spanner-in-video-search.git
   cd spanner-in-video-search

Make the setup script executable and run it:

chmod +x setup.sh
./setup.sh

Open your browser and navigate to the printed Streamlit IP on port 8080.
📁 Repository Map
app.py: 4-Tab Streamlit frontend containing the Gemini query decomposer and JavaScript-synchronized video cards.

schema.sql: Spanner schema with interleaved child layouts and native FTS and Vector indexes.

ingest_visual.py: Visual frame vector encoder (Vertex AI multimodalembedding@001).

ingest_transcript.py: Dialogue text vector encoder (Vertex AI text-embedding-004).

requirements.txt: Python package dependencies.

setup.sh: Automated environment orchestrator and database deployer.
