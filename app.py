import os
import json
import streamlit as st
import streamlit.components.v1 as components
import vertexai
from google.cloud import spanner, aiplatform
from vertexai.vision_models import MultiModalEmbeddingModel
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
from vertexai.generative_models import GenerativeModel, GenerationConfig

# ==========================================
# 🔧 Configure Your GCP & Spanner Settings
# ==========================================
PROJECT_ID = "my-project-840969-350821"
INSTANCE_ID = "mediastreamingdemo"
DATABASE_ID = "mediademo"

# Page Configurations
st.set_page_config(layout="wide", page_title="Spanner Video Search Hub")
st.title("🎥 Cloud Spanner: Unified Video Search Hub")

# Sidebar Configuration
st.sidebar.markdown("### 🔧 Connection & Assets")
st.sidebar.info(f"**Instance:** `{INSTANCE_ID}`\n\n**Database:** `{DATABASE_ID}`")

video_source = "moving_google_app.mp4"
active_video_id = "moving_google_app"

if not os.path.exists(video_source):
    st.sidebar.error("❌ moving_google_app.mp4 not found in this folder!")
    st.stop()
else:
    st.sidebar.success("✅ Local moving_google_app.mp4 loaded!")

@st.cache_resource
def get_spanner_db():
    spanner_client = spanner.Client(project=PROJECT_ID)
    return spanner_client.instance(INSTANCE_ID).database(DATABASE_ID)

try:
    database = get_spanner_db()
except Exception as e:
    st.error(f"Spanner connection error: {e}")
    st.stop()

# ==========================================
# 🎫 DYNAMIC TABS DEFINITION
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "👁️ Visual Search", 
    "💬 Transcript Search", 
    "🌀 Unified Search", 
    "🤖 Autonomous Hybrid Search (Gemini)"
])

# -------------------------------------------------------------
# 👁️ TAB 1: VISUAL SEARCH
# -------------------------------------------------------------
with tab1:
    st.header("Search Visual Scenes inside Video")
    visual_query = st.text_input("What scene are you looking for?", placeholder="e.g., 'carrying a green couch'", key="tab1_vis")
    
    if visual_query:
        with st.spinner("🧠 Generating multimodal query..."):
            aiplatform.init(project=PROJECT_ID)
            model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
            text_emb = model.get_embeddings(contextual_text=visual_query)
            query_vector = text_emb.text_embedding
            
        with st.spinner("⚡ Querying Spanner Vector Index..."):
            query = """
            SELECT s.VideoId, v.Title, v.GcsUri, s.StartOffsetSec, s.EndOffsetSec,
                   COSINE_DISTANCE(s.Embedding, @query_vector) as distance
            FROM VisualVideoSegments s
            JOIN VisualVideos v ON s.VideoId = v.VideoId
            WHERE s.VideoId = @video_id
            ORDER BY distance ASC
            LIMIT 3
            """
            with database.snapshot() as session:
                results = list(session.execute_sql(query, params={"query_vector": query_vector, "video_id": active_video_id}, param_types={"query_vector": spanner.param_types.Array(spanner.param_types.FLOAT64), "video_id": spanner.param_types.STRING}))
                
        if results:
            for idx, (vid, title, gcs, start_sec, end_sec, distance) in enumerate(results):
                col_left, col_right = st.columns([1, 2])
                duration = end_sec - start_sec
                with col_left:
                    similarity_percentage = round((1.0 - distance) * 100, 1)
                    st.success(f"**Result #{idx+1}: {title}**")
                    st.write(f"⏱️ **Matched Block:** `{start_sec}s` to `{end_sec}s` ({duration}s duration)")
                    st.write(f"🎯 **Similarity:** `{similarity_percentage}%`")
                with col_right:
                    st.video(video_source, start_time=start_sec)
                    js_code = f"""
                    <script>
                    setTimeout(function() {{
                        const video = window.parent.document.querySelectorAll('video')[{idx}];
                        if (video) {{
                            video.addEventListener('timeupdate', function() {{
                                if (video.currentTime >= {end_sec}) {{
                                    video.pause();
                                }}
                            }});
                        }}
                    }}, 1000);
                    </script>
                    """
                    components.html(js_code, height=0)
                st.markdown("---")

# -------------------------------------------------------------
# 💬 TAB 2: TRANSCRIPT SEARCH
# -------------------------------------------------------------
with tab2:
    st.header("Search Spoken Dialogues")
    search_mode = st.radio("Choose Search Mechanism:", ["Semantic Vector Search", "FTS Keyword Index"], horizontal=True, key="tab2_mode")
    srt_query = st.text_input("What spoken dialogue are you searching for?", placeholder="e.g., 'Goodwill'", key="tab2_srt")

    if srt_query:
        results = []
        if search_mode == "Semantic Vector Search":
            with st.spinner("🧠 Generating text embedding..."):
                model = TextEmbeddingModel.from_pretrained("text-embedding-004")
                query_vector = model.get_embeddings([TextEmbeddingInput(srt_query, "RETRIEVAL_QUERY")])[0].values
            with st.spinner("⚡ Executing Spanner Vector Query..."):
                sql = """
                SELECT s.VideoId, v.Title, v.GcsUri, s.StartOffsetSec, s.EndOffsetSec, s.SubtitleText,
                       COSINE_DISTANCE(s.Embedding, @query_vector) as distance
                FROM VideoTranscripts s
                JOIN TranscriptVideos v ON s.VideoId = v.VideoId
                WHERE s.VideoId = @video_id
                ORDER BY distance ASC
                LIMIT 3
                """
                with database.snapshot() as session:
                    results = list(session.execute_sql(sql, params={"query_vector": query_vector, "video_id": active_video_id}, param_types={"query_vector": spanner.param_types.Array(spanner.param_types.FLOAT64), "video_id": spanner.param_types.STRING}))
        else:
            with st.spinner("⚡ Querying Spanner Full-Text Search..."):
                sql = """
                SELECT s.VideoId, v.Title, v.GcsUri, s.StartOffsetSec, s.EndOffsetSec, s.SubtitleText,
                       SCORE(SubtitleText_Tokens, @query_text) as score
                FROM VideoTranscripts s
                JOIN TranscriptVideos v ON s.VideoId = v.VideoId
                WHERE SEARCH(SubtitleText_Tokens, @query_text) AND s.VideoId = @video_id
                ORDER BY score DESC
                LIMIT 3
                """
                with database.snapshot() as session:
                    results = list(session.execute_sql(sql, params={"query_text": srt_query, "video_id": active_video_id}, param_types={"query_text": spanner.param_types.STRING, "video_id": spanner.param_types.STRING}))

        if results:
            for idx, (vid, title, gcs, start_sec, end_sec, subtitle_text, score_val) in enumerate(results):
                col_left, col_right = st.columns([1, 2])
                duration = end_sec - start_sec
                with col_left:
                    st.info(f"**Dialogue Result #{idx+1}**")
                    st.markdown(f'🗣️ **Spoken:** \n> *"{subtitle_text}"*')
                    st.write(f"⏱️ **Timestamp:** `{start_sec}s` to `{end_sec}s` ({duration}s duration)")
                    if search_mode == "Semantic Vector Search":
                        st.write(f"🎯 **Similarity:** `{round((1.0 - score_val) * 100, 2)}%`")
                    else:
                        st.write(f"🏷️ **FTS Score:** `{round(score_val, 4)}`")
                with col_right:
                    st.video(video_source, start_time=start_sec)
                    js_code = f"""
                    <script>
                    setTimeout(function() {{
                        const video = window.parent.document.querySelectorAll('video')[{idx}];
                        if (video) {{
                            video.addEventListener('timeupdate', function() {{
                                if (video.currentTime >= {end_sec}) {{
                                    video.pause();
                                }}
                            }});
                        }}
                    }}, 1000);
                    </script>
                    """
                    components.html(js_code, height=0)
                st.markdown("---")
# -------------------------------------------------------------
# 🌀 TAB 3: UNIFIED MULTI-MODAL SEARCH
# -------------------------------------------------------------
with tab3:
    st.header("🌀 Unified Spanner Multi-Modal Search")
    st.write("This tab finds the best matching visual scene and pulls corresponding dialogues spoken during that sequence.")
    
    col1, col2 = st.columns(2)
    with col1:
        uni_visual = st.text_input("Describe the visual scene:", value="carrying a green couch", key="tab3_vis")
    with col2:
        uni_keyword = st.text_input("Spoken FTS keywords:", value="legs", key="tab3_key")
        
    if st.button("🚀 Run Unified Spanner SQL Query", key="tab3_btn"):
        with st.spinner("🧠 Preparing visual embedding..."):
            aiplatform.init(project=PROJECT_ID)
            vis_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
            visual_vector = vis_model.get_embeddings(contextual_text=uni_visual).text_embedding
            
        with st.spinner("⚡ Executing Unified Spanner SQL..."):
            unified_sql = """
            SELECT 
              s.VideoId,
              v.Title,
              s.StartOffsetSec,
              s.EndOffsetSec,
              t.SubtitleText,
              COSINE_DISTANCE(s.Embedding, @visual_query_vector) as distance
            FROM VisualVideoSegments s
            JOIN VisualVideos v ON s.VideoId = v.VideoId
            JOIN VideoTranscripts t ON s.VideoId = t.VideoId 
              AND t.StartOffsetSec >= s.StartOffsetSec - 3
              AND t.StartOffsetSec <= s.EndOffsetSec + 3
            WHERE s.VideoId = @video_id AND SEARCH(t.SubtitleText_Tokens, @fts_query_text)
            ORDER BY distance ASC
            LIMIT 3
            """
            try:
                with database.snapshot() as session:
                    results = list(session.execute_sql(
                        unified_sql,
                        params={"visual_query_vector": visual_vector, "video_id": active_video_id, "fts_query_text": uni_keyword},
                        param_types={"visual_query_vector": spanner.param_types.Array(spanner.param_types.FLOAT64), "video_id": spanner.param_types.STRING, "fts_query_text": spanner.param_types.STRING}
                    ))
            except Exception as e:
                st.error(f"Unified Spanner SQL failed: {e}")
                results = []
                
        if results:
            st.success(f"🎉 Spanner found {len(results)} matching visual moments!")
            for idx, (vid, title, start_sec, end_sec, spoken_text, distance) in enumerate(results):
                col_left, col_right = st.columns([1, 2])
                duration = end_sec - start_sec
                display_speech = spoken_text if spoken_text is not None else "[No spoken dialogues during this visual frame]"
                
                with col_left:
                    similarity_percentage = round((1.0 - distance) * 100, 1)
                    st.info(f"**Moment #{idx+1}**")
                    st.markdown(f"**Visual Segment:** `{start_sec}s - {end_sec}s`")
                    st.markdown(f"🗣️ **Dialogue Spoken:**\n> *\"{display_speech}\"*")
                    st.write(f"🎯 **Visual Similarity:** `{similarity_percentage}%`")
                with col_right:
                    st.video(video_source, start_time=start_sec)
                    js_code = f"""
                    <script>
                    setTimeout(function() {{
                        const video = window.parent.document.querySelectorAll('video')[{idx}];
                        if (video) {{
                            video.addEventListener('timeupdate', function() {{
                                if (video.currentTime >= {end_sec}) {{
                                    video.pause();
                                }}
                            }});
                        }}
                    }}, 1000);
                    </script>
                    """
                    components.html(js_code, height=0)
                st.markdown("---")
        else:
            st.warning("No matches found in database.")

# -------------------------------------------------------------
# 🤖 TAB 4: AUTONOMOUS HYBRID SEARCH (GEMINI PARSER + SQL FALLBACK)
# -------------------------------------------------------------
with tab4:
    st.header("🤖 Autonomous Gemini + Spanner Hybrid Search")
    st.write("Type a natural sentence. Gemini will automatically extract what is seen and what is said, and Spanner will perform the unified lookup.")
    
    user_prompt = st.text_input(
        "Enter your combined search query:", 
        value="Show me the driving car carrying a mattress on the road",
        key="tab4_prompt"
    )
    
    if st.button("🚀 Run Intelligent Hybrid Query", key="tab4_btn"):
        with st.spinner("🤖 Gemini is parsing and decomposing your query..."):
            vertexai.init(project=PROJECT_ID, location="us-central1")
            
            # Load stable Gemini 2.5 Flash
            model = GenerativeModel("gemini-2.5-flash")
            
            system_prompt = """
            You are an advanced AI query parsing agent. Your task is to split a user's video search query into two distinct parameters:
            1. 'visual_scene': A clean, descriptive keyword string describing what is visually shown on screen.
            2. 'spoken_keyword': A single, clean word or phrase that is spoken aloud in the video dialogue.
            
            You MUST return your answer in raw, valid JSON format only, with no markdown code blocks.
            
            Examples:
            Input: "Find the scene of the green car when they ask for directions"
            Output: {"visual_scene": "green car driving on street", "spoken_keyword": "directions"}
            
            Input: "Show me where they are carrying the green couch when someone says legs"
            Output: {"visual_scene": "carrying green couch", "spoken_keyword": "legs"}
            """
            
            try:
                response = model.generate_content(
                    f"{system_prompt}\n\nUser Input: {user_prompt}",
                    generation_config=GenerationConfig(response_mime_type="application/json")
                )
                parsed_json = json.loads(response.text.strip())
                visual_scene = parsed_json.get("visual_scene", "")
                spoken_keyword = parsed_json.get("spoken_keyword", "")
                
                # Render parsed values in the UI
                col1, col2 = st.columns(2)
                col1.metric("👁️ Extracted Visual Target", f'"{visual_scene}"')
                col2.metric("🗣️ Extracted Spoken Keyword", f'"{spoken_keyword}"')
                
            except Exception as e:
                st.error(f"Gemini LLM Parser failed: {e}")
                st.stop()
                
        with st.spinner("🧠 Generating vectors for extracted parameters..."):
            # Embed Visual scene (1408-dim)
            vis_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
            visual_vector = vis_model.get_embeddings(contextual_text=visual_scene).text_embedding
            
        with st.spinner("⚡ Executing Unified Spanner SQL Query..."):
            # 1. PYTHON-LEVEL FAST CHECK: Does the spoken keyword exist in Spanner's transcripts?
            check_sql = """
            SELECT COUNT(*) 
            FROM VideoTranscripts 
            WHERE VideoId = @video_id AND SEARCH(SubtitleText_Tokens, @fts_query_text)
            """
            keyword_exists = False
            try:
                with database.snapshot() as session:
                    res = list(session.execute_sql(
                        check_sql,
                        params={"video_id": active_video_id, "fts_query_text": spoken_keyword},
                        param_types={"video_id": spanner.param_types.STRING, "fts_query_text": spanner.param_types.STRING}
                    ))
                    if res and res[0][0] > 0:
                        keyword_exists = True
            except Exception as e:
                keyword_exists = False

            # 2. SELECT THE COMPILER-SAFE SQL STATEMENT Based on Keyword Existence
            if keyword_exists:
                # Precise Temporal Inner-Join Query (No LEFT JOIN, 100% legal for SEARCH!)
                unified_sql = """
                SELECT 
                  s.VideoId,
                  v.Title,
                  s.StartOffsetSec,
                  s.EndOffsetSec,
                  t.SubtitleText,
                  COSINE_DISTANCE(s.Embedding, @visual_query_vector) as distance
                FROM VisualVideoSegments s
                JOIN VisualVideos v ON s.VideoId = v.VideoId
                JOIN VideoTranscripts t ON s.VideoId = t.VideoId 
                  AND t.StartOffsetSec >= s.StartOffsetSec - 3
                  AND t.StartOffsetSec <= s.EndOffsetSec + 3
                WHERE s.VideoId = @video_id AND SEARCH(t.SubtitleText_Tokens, @fts_query_text)
                ORDER BY distance ASC
                LIMIT 3
                """
                params = {"visual_query_vector": visual_vector, "video_id": active_video_id, "fts_query_text": spoken_keyword}
                param_types = {
                    "visual_query_vector": spanner.param_types.Array(spanner.param_types.FLOAT64),
                    "video_id": spanner.param_types.STRING,
                    "fts_query_text": spanner.param_types.STRING
                }
            else:
                # Fallback: High-precision Visual Vector-Only Query (Guarantees zero compilation errors!)
                st.info(f"💡 Dialogue keyword '{spoken_keyword}' not spoken in this video. Running autonomous visual-only search instead!")
                unified_sql = """
                SELECT 
                  s.VideoId,
                  v.Title,
                  s.StartOffsetSec,
                  s.EndOffsetSec,
                  CAST(NULL AS STRING) as SubtitleText,
                  COSINE_DISTANCE(s.Embedding, @visual_query_vector) as distance
                FROM VisualVideoSegments s
                JOIN VisualVideos v ON s.VideoId = v.VideoId
                WHERE s.VideoId = @video_id
                ORDER BY distance ASC
                LIMIT 3
                """
                params = {"visual_query_vector": visual_vector, "video_id": active_video_id}
                param_types = {
                    "visual_query_vector": spanner.param_types.Array(spanner.param_types.FLOAT64),
                    "video_id": spanner.param_types.STRING
                }

            # 3. RUN DATABASE TRANSACTION
            try:
                with database.snapshot() as session:
                    results = list(session.execute_sql(unified_sql, params=params, param_types=param_types))
            except Exception as e:
                st.error(f"Unified Spanner SQL failed: {e}")
                results = []
                
        if results:
            st.success(f"🎉 Spanner successfully completed the multi-modal search!")
            for idx, (vid, title, start_sec, end_sec, spoken_text, distance) in enumerate(results):
                col_left, col_right = st.columns([1, 2])
                duration = end_sec - start_sec
                display_speech = spoken_text if spoken_text is not None else "[No spoken dialogues matching this visual frame]"
                
                with col_left:
                    similarity_percentage = round((1.0 - distance) * 100, 1)
                    st.info(f"**Matched Moment #{idx+1}**")
                    st.markdown(f"**Visual Segment:** `{start_sec}s - {end_sec}s`")
                    st.markdown(f"🗣️ **Dialogue Spoken:**\n> *\"{display_speech}\"*")
                    st.write(f"🎯 **Visual Similarity:** `{similarity_percentage}%`")
                with col_right:
                    st.video(video_source, start_time=start_sec)
                    js_code = f"""
                    <script>
                    setTimeout(function() {{
                        const video = window.parent.document.querySelectorAll('video')[{idx}];
                        if (video) {{
                            video.addEventListener('timeupdate', function() {{
                                if (video.currentTime >= {end_sec}) {{
                                    video.pause();
                                }}
                            }});
                        }}
                    }}, 1000);
                    </script>
                    """
                    components.html(js_code, height=0)
                st.markdown("---")
        else:
            st.warning("No matches found in database.")
