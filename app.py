import streamlit as st
import assemblyai as aai
import os
import re
import time
from datetime import timedelta
from typing import Optional, Dict, Any, List, Tuple

# ==========================================
# CONFIGURATION
# ==========================================
ASSEMBLYAI_API_KEY = "265abe2425ad4b33b711487abc7da9fc"
aai.settings.api_key = ASSEMBLYAI_API_KEY

st.set_page_config(
    page_title="AI Podcast Transcriber & Character Diarization",
    page_icon="🎙️",
    layout="wide"
)

def format_timestamp(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def is_youtube_url(url: str) -> bool:
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return bool(re.search(youtube_regex, url))

def is_valid_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def get_audio_source(url: str) -> Tuple[str, Optional[str]]:
    clean_url = url.strip().strip('"').strip("'")

    if is_youtube_url(clean_url):
        import yt_dlp
        output_dir = "temp_downloads"
        os.makedirs(output_dir, exist_ok=True)
        out_template = os.path.join(output_dir, "%(id)s.%(ext)s")

        # Fast direct audio stream download without heavy ffmpeg re-encode
        dl_opts = {
            'format': 'ba[ext=m4a]/ba[ext=mp3]/ba',
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            video_id = info.get('id', 'audio')
            
            downloaded_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id):
                    downloaded_file = os.path.join(output_dir, f)
                    break

            if not downloaded_file or not os.path.exists(downloaded_file):
                raise RuntimeError("Audio file download complete nahi ho payi.")

            return downloaded_file, downloaded_file

    elif is_valid_url(clean_url):
        return clean_url, None
    else:
        if not os.path.exists(clean_url):
            raise FileNotFoundError(f"Local file nahi mili: '{clean_url}'")
        return clean_url, None

# --- HEADER ---
st.title("🎙️ AI Podcast Transcriber & Character Diarization")
st.caption("⚡ Powered by AssemblyAI Universal GPU Engine | Accurate Speaker Separation & Timestamps")

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    st.subheader("👥 Speakers / Characters Ke Naam")
    custom_names_input = st.text_input(
        "Speakers ke Naam (Comma-separated):",
        placeholder="e.g. Raj Shamani, Sachin Puri",
        help="Aap pehle se naam de sakte hain. First name Speaker A ko milega, second Speaker B ko."
    )
    
    predefined_names = [n.strip() for n in custom_names_input.split(",") if n.strip()] if custom_names_input else []

    if predefined_names:
        st.success(f"Configured: {', '.join(predefined_names)}")
    else:
        speakers_known = st.checkbox("Mujhe sirf speaker count pata hai", value=False)
        expected_spk = None
        if speakers_known:
            expected_spk = st.number_input("Expected Speakers Count", min_value=1, max_value=20, value=2)

    st.subheader("🌐 Language")
    lang_mode = st.radio("Language Setting:", ["Auto-Detect (Recommended)", "English", "Hindi"], index=0)
    lang_code = None
    if lang_mode == "English":
        lang_code = "en"
    elif lang_mode == "Hindi":
        lang_code = "hi"

    st.markdown("---")
    st.info("💡 **Diarization Active:** Har character ka audio alag analyze hota hai. Temporary files automatically delete ho jati hain.")

# --- MAIN INPUT SECTION ---
tab1, tab2 = st.tabs(["🔗 Audio / YouTube Link", "📁 Local Audio File Upload"])

source_target = None
source_label = ""

with tab1:
    url_input = st.text_input(
        "Podcast / YouTube / Web Audio Link:",
        placeholder="https://www.youtube.com/watch?v=... ya https://example.com/audio.mp3"
    )
    if url_input and url_input.strip():
        source_target = url_input.strip()
        source_label = url_input.strip()

with tab2:
    uploaded_file = st.file_uploader(
        "Apne system se Audio ya Video file choose karein:",
        type=["mp3", "wav", "m4a", "mp4", "aac", "ogg", "flac"]
    )
    if uploaded_file is not None:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        local_path = os.path.join(temp_dir, uploaded_file.name)
        with open(local_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        source_target = local_path
        source_label = uploaded_file.name

# Session state initialization
if "transcript_data" not in st.session_state:
    st.session_state.transcript_data = None
if "speaker_names" not in st.session_state:
    st.session_state.speaker_names = {}

# --- RUN BUTTON ---
if st.button("🚀 Transcribe & Diarize Podcast", type="primary", use_container_width=True):
    if not source_target:
        st.warning("⚠️ Kripya pehle koi link dalein ya audio file upload karein!")
    else:
        temp_cleanup = None
        prog_bar = st.progress(0, text="Audio check ho raha hai...")

        try:
            if is_youtube_url(source_target):
                prog_bar.progress(15, text="📥 YouTube audio stream cache ho raha hai (Fast Mode)...")
            
            audio_source_path, temp_cleanup = get_audio_source(source_target)

            prog_bar.progress(35, text="🚀 Cloud GPU par transcription job submit ho raha hai...")

            config_args = {
                "speaker_labels": True,
                "punctuate": True,
                "format_text": True,
            }
            
            if predefined_names:
                config_args["speakers_expected"] = len(predefined_names)
            elif 'expected_spk' in locals() and expected_spk:
                config_args["speakers_expected"] = int(expected_spk)

            if lang_code:
                config_args["language_code"] = lang_code
            else:
                config_args["language_detection"] = True

            config = aai.TranscriptionConfig(**config_args)
            transcriber = aai.Transcriber()

            job = transcriber.submit(audio_source_path, config=config)
            job_id = job.id
            prog_bar.progress(45, text=f"⚡ Processing Audio & Separating Speakers (Job: {job_id[:8]}...)...")

            # Polling loop
            start_time = time.time()
            sim_progress = 45
            while True:
                time.sleep(1.5)
                res = aai.Transcript.get_by_id(job_id)
                status = res.status

                if status == aai.TranscriptStatus.completed:
                    prog_bar.progress(100, text="🎉 Transcription & Diarization Complete!")
                    break
                elif status == aai.TranscriptStatus.error:
                    raise RuntimeError(f"AssemblyAI Error: {res.error}")
                else:
                    if sim_progress < 90:
                        sim_progress += 4
                    prog_bar.progress(sim_progress, text=f"⏳ Diarizing speakers in progress... ({int(time.time() - start_time)}s elapsed)")

            # Store in session state
            utterances_data = []
            distinct_speakers = set()
            for u in res.utterances:
                distinct_speakers.add(u.speaker)
                utterances_data.append({
                    "speaker": u.speaker,
                    "start": u.start,
                    "end": u.end,
                    "text": u.text
                })

            sorted_spks = sorted(list(distinct_speakers))
            st.session_state.transcript_data = {
                "source": source_label,
                "utterances": utterances_data,
                "speakers": sorted_spks,
                "duration_seconds": int(time.time() - start_time)
            }

            # Predefined names map karna
            new_speaker_map = {}
            for i, spk in enumerate(sorted_spks):
                if i < len(predefined_names):
                    new_speaker_map[spk] = predefined_names[i]
                else:
                    new_speaker_map[spk] = f"Speaker {spk}"
            st.session_state.speaker_names = new_speaker_map
            st.rerun()

        except Exception as e:
            prog_bar.empty()
            st.error(f"❌ Error aaya: {str(e)}")
        finally:
            if temp_cleanup and os.path.exists(temp_cleanup):
                try:
                    os.remove(temp_cleanup)
                except Exception:
                    pass

# --- DISPLAY RESULTS & CUSTOMIZATION ---
if st.session_state.transcript_data:
    data = st.session_state.transcript_data
    speakers = data["speakers"]

    st.markdown("---")
    st.success(f"🎯 **Success!** Total `{len(speakers)}` speakers detect huye ({data['duration_seconds']}s me process hua).")

    # --- CHARACTER NAME MAPPER & SWAP BUTTON ---
    with st.expander("🏷️ Speakers ke Real Names Edit / Swap Karein", expanded=True):
        st.write("Aap yahan se kisi bhi speaker ka naam change kar sakte hain ya do speakers ko aapas me **Swap** kar sakte hain:")
        col_list = st.columns(min(len(speakers), 4))
        for i, spk in enumerate(speakers):
            col = col_list[i % len(col_list)]
            current_name = st.session_state.speaker_names.get(spk, f"Speaker {spk}")
            new_name = col.text_input(f"Speaker {spk} (Audio Turn {i+1}):", value=current_name, key=f"name_{spk}")
            if new_name.strip():
                st.session_state.speaker_names[spk] = new_name.strip()

        # Swap button agar kam se kam 2 speakers hon
        if len(speakers) >= 2:
            st.markdown("---")
            swap_cols = st.columns([2, 2, 2])
            with swap_cols[0]:
                spk1 = st.selectbox("Speaker 1:", [f"Speaker {s} ({st.session_state.speaker_names.get(s)})" for s in speakers], index=0)
            with swap_cols[1]:
                spk2 = st.selectbox("Speaker 2:", [f"Speaker {s} ({st.session_state.speaker_names.get(s)})" for s in speakers], index=1)
            with swap_cols[2]:
                st.write("")
                st.write("")
                if st.button("🔄 Swap Names"):
                    k1 = spk1.split()[1]
                    k2 = spk2.split()[1]
                    st.session_state.speaker_names[k1], st.session_state.speaker_names[k2] = (
                        st.session_state.speaker_names[k2],
                        st.session_state.speaker_names[k1]
                    )
                    st.rerun()

    # --- SPEAKER STATS METRICS ---
    st.subheader("📊 Speaker Analytics")
    stats_cols = st.columns(len(speakers))
    for i, spk in enumerate(speakers):
        display_name = st.session_state.speaker_names.get(spk, f"Speaker {spk}")
        spk_turns = [u for u in data["utterances"] if u["speaker"] == spk]
        total_time_ms = sum((u["end"] - u["start"]) for u in spk_turns)
        total_words = sum(len(u["text"].split()) for u in spk_turns)
        time_str = str(timedelta(seconds=int(total_time_ms / 1000)))
        
        with stats_cols[i]:
            st.metric(label=display_name, value=f"{len(spk_turns)} turns", delta=f"{time_str} speaking | {total_words} words")

    # --- FILTER BY SPEAKER ---
    st.markdown("---")
    filter_option = st.selectbox(
        "🔍 Filter Transcript by Speaker:",
        ["Sabhi Characters (All Speakers)"] + [st.session_state.speaker_names[s] for s in speakers]
    )

    # --- CHAT-BUBBLE TRANSCRIPT VIEW ---
    st.subheader("💬 Character-by-Character Transcript")
    
    avatar_list = ["🧑‍🦱", "🧔", "👩", "👨‍🦳", "👱", "👧", "👨"]
    md_output_lines = [
        f"# 🎙️ Podcast Transcript\n- **Source:** {data['source']}\n- **Total Speakers:** {len(speakers)}\n\n---\n"
    ]

    for u in data["utterances"]:
        spk_id = u["speaker"]
        spk_name = st.session_state.speaker_names.get(spk_id, f"Speaker {spk_id}")

        if filter_option != "Sabhi Characters (All Speakers)" and spk_name != filter_option:
            continue

        spk_index = speakers.index(spk_id) if spk_id in speakers else 0
        avatar = avatar_list[spk_index % len(avatar_list)]
        time_str = f"{format_timestamp(u['start'])} - {format_timestamp(u['end'])}"

        with st.chat_message(spk_name, avatar=avatar):
            st.markdown(f"**{spk_name}** `[{time_str}]`")
            st.write(u["text"])

        md_output_lines.append(f"**{spk_name}** `[{time_str}]`:\n> {u['text']}\n\n")

    # --- DOWNLOAD BUTTON ---
    st.markdown("---")
    full_markdown = "\n".join(md_output_lines)
    st.download_button(
        label="📥 Download Full Diarized Transcript (.md)",
        data=full_markdown,
        file_name="diarized_podcast_transcript.md",
        mime="text/markdown",
        use_container_width=True
    )
