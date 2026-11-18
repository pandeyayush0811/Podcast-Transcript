import os
import sys
import re
import time
from datetime import timedelta
from typing import Optional, Dict, Any, List, Tuple
import assemblyai as aai

# ==========================================
# SECURE CONFIGURATION (NO HARDCODED KEYS)
# ==========================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_api_key() -> str:
    """API key ko environment, .env ya .streamlit/secrets.toml se securely fetch karta hai."""
    key = os.getenv("ASSEMBLYAI_API_KEY")
    if not key and os.path.exists(".streamlit/secrets.toml"):
        try:
            with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
                for line in f:
                    if "ASSEMBLYAI_API_KEY" in line and "=" in line:
                        key = line.split("=")[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

    if not key:
        print("\n[⚠️] ASSEMBLYAI_API_KEY environment ya .env file me nahi mili.")
        key = input("👉 Apni AssemblyAI API Key enter karein: ").strip()

    return key

API_KEY = get_api_key()
if not API_KEY:
    print("[❌] Error: Valid API Key ke bina tool run nahi ho sakta.")
    sys.exit(1)

aai.settings.api_key = API_KEY

def format_timestamp(milliseconds: int) -> str:
    """Milliseconds ko [HH:MM:SS] format me convert karta hai."""
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
    """Check karta hai ki input YouTube ka link hai ya nahi."""
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return bool(re.search(youtube_regex, url))

def is_valid_url(url: str) -> bool:
    """Check karta hai ki input web URL hai ya local file path."""
    return url.startswith("http://") or url.startswith("https://")

def get_audio_source(url: str) -> Tuple[str, Optional[str]]:
    """
    Intelligent Audio Routing:
    - YouTube: Fast direct audio stream download without heavy ffmpeg re-encode.
    - Public Web URLs: Zero-Download Direct Cloud Transfer.
    - Local Files: Direct local file upload.
    Returns: (audio_target, temp_cleanup_path_if_any)
    """
    clean_url = url.strip().strip('"').strip("'")

    if is_youtube_url(clean_url):
        import yt_dlp
        output_dir = "temp_downloads"
        os.makedirs(output_dir, exist_ok=True)
        out_template = os.path.join(output_dir, "%(id)s.%(ext)s")

        dl_opts = {
            'format': 'ba[ext=m4a]/ba[ext=mp3]/ba',
            'outtmpl': out_template,
            'quiet': False,
            'no_warnings': True,
        }
        print(f"\n[📥] YouTube audio stream download ho raha hai (Fast Mode)...")
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            video_id = info.get('id', 'audio')
            title = info.get('title', 'YouTube Podcast')
            
            downloaded_file = None
            for f in os.listdir(output_dir):
                if f.startswith(video_id):
                    downloaded_file = os.path.join(output_dir, f)
                    break

            if not downloaded_file or not os.path.exists(downloaded_file):
                raise RuntimeError("Audio file download complete nahi ho payi.")

            file_size_mb = round(os.path.getsize(downloaded_file) / (1024 * 1024), 2)
            print(f"[✅] Download complete: '{title}' ({file_size_mb} MB)")
            return downloaded_file, downloaded_file

    elif is_valid_url(clean_url):
        print(f"\n[🌐] Direct Public Web URL detect hua: '{clean_url}'")
        print("[⚡] Zero-Download Mode: Direct Cloud-to-Cloud transfer active!")
        return clean_url, None

    else:
        if not os.path.exists(clean_url):
            raise FileNotFoundError(f"Local file nahi mili: '{clean_url}'")
        print(f"\n[📁] Local file detect hui: {os.path.basename(clean_url)}")
        return clean_url, None

def transcribe_with_diarization(
    source: str, 
    speaker_names: Optional[List[str]] = None,
    num_speakers: Optional[int] = None, 
    language_code: Optional[str] = None,
    cleanup_temp: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Robust Diarization Engine with AssemblyAI.
    """
    source_clean = source.strip().strip('"').strip("'")
    if not source_clean:
        print("[❌] Error: Input source empty hai.")
        return None

    # Step 1: Resolve Audio Target
    try:
        audio_target, temp_cleanup = get_audio_source(source_clean)
    except Exception as e:
        print(f"[❌] Source Resolution Error: {e}")
        return None

    # Step 2: Speaker Configuration
    if speaker_names and len(speaker_names) > 0 and not num_speakers:
        num_speakers = len(speaker_names)

    config_args = {
        "speaker_labels": True,
        "punctuate": True,
        "format_text": True,
    }

    if num_speakers and num_speakers > 0:
        config_args["speakers_expected"] = num_speakers
        print(f"[*] Expected Speakers count: {num_speakers}")

    if language_code:
        config_args["language_code"] = language_code
        print(f"[*] Language Code set to: {language_code}")
    else:
        config_args["language_detection"] = True
        print(f"[*] Auto Language Detection: ACTIVE")

    config = aai.TranscriptionConfig(**config_args)
    transcriber = aai.Transcriber()

    # Step 3: Cloud GPU Submission
    print("\n" + "="*65)
    print("🚀 [Cloud GPU Engine] Job Submit ho raha hai...")
    if speaker_names:
        print(f"👥 Configured Character Names: {', '.join(speaker_names)}")
    print("="*65)

    try:
        transcript_job = transcriber.submit(audio_target, config=config)
        job_id = transcript_job.id
        print(f"[+] Job ID: {job_id}")
    except Exception as e:
        print(f"[❌] API Submission Failed: {e}")
        return None

    # Step 4: Non-blocking Polling
    start_time = time.time()
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0

    while True:
        try:
            transcript = aai.Transcript.get_by_id(job_id)
        except Exception as net_err:
            print(f"\n[⚠️] Network retry... ({net_err})")
            time.sleep(2)
            continue

        elapsed = int(time.time() - start_time)
        status = transcript.status

        if status == aai.TranscriptStatus.completed:
            print(f"\r[✅] Processing Complete! (Total Cloud Time: {elapsed} seconds)        \n")
            break
        elif status == aai.TranscriptStatus.error:
            print(f"\r[❌] Transcription Failed: {transcript.error}                  \n")
            return None
        else:
            spin = spinner[idx % len(spinner)]
            print(f"\r[{spin}] Status: {str(status).replace('TranscriptStatus.', '')} | Elapsed: {elapsed}s... ", end="", flush=True)
            idx += 1
            time.sleep(1.5)

    utterances = transcript.utterances or []
    if not utterances:
        print("[⚠️] Warning: Koi speech detect nahi hui.")
        return None

    # Step 5: Map Custom Names
    distinct_speakers = sorted(list(set(u.speaker for u in utterances)))
    speaker_map = {}
    for i, spk_label in enumerate(distinct_speakers):
        if speaker_names and i < len(speaker_names) and speaker_names[i].strip():
            speaker_map[spk_label] = speaker_names[i].strip()
        else:
            speaker_map[spk_label] = f"Speaker {spk_label}"

    speaker_stats: Dict[str, Dict[str, Any]] = {}
    lines = []
    lines.append(f"# 🎙️ Podcast Transcript (Speaker by Speaker)\n")
    lines.append(f"- **Source:** `{source_clean}`")
    lines.append(f"- **Processing Time:** `{int(time.time() - start_time)} seconds`")
    lines.append(f"- **Detected Language:** `{transcript.json_response.get('language_code', 'auto')}`\n")

    print("="*65)
    print("                   PODCAST TRANSCRIPT OUTPUT                  ")
    print("="*65 + "\n")

    for u in utterances:
        display_name = speaker_map.get(u.speaker, f"Speaker {u.speaker}")
        duration_sec = (u.end - u.start) / 1000.0
        words_count = len(u.text.split())

        if display_name not in speaker_stats:
            speaker_stats[display_name] = {"duration_sec": 0.0, "words": 0, "turns": 0}
        speaker_stats[display_name]["duration_sec"] += duration_sec
        speaker_stats[display_name]["words"] += words_count
        speaker_stats[display_name]["turns"] += 1

        time_range = f"{format_timestamp(u.start)} - {format_timestamp(u.end)}"
        
        # Terminal display
        print(f"\033[1;36m[{time_range}] {display_name}:\033[0m")
        print(f"   {u.text}\n")

        # Markdown file output
        lines.append(f"**{display_name}** `[{time_range}]`:\n> {u.text}\n")

    # Speaker Analytics Summary
    lines.append("\n---\n### 📊 Speaker Statistics\n")
    print("-"*65)
    print("📊 SPEAKER BREAKDOWN SUMMARY:")
    print("-"*65)
    for spk_name, data in sorted(speaker_stats.items()):
        dur_str = str(timedelta(seconds=int(data['duration_sec'])))
        stat_line = f"- **{spk_name}:** {data['turns']} turns | {dur_str} speaking time | {data['words']} words"
        lines.append(stat_line)
        print(f" • {spk_name:18}: {dur_str} bolne ka samay | {data['words']:4} words | {data['turns']:2} turns")
    print("="*65)

    # Save to Markdown File
    output_filename = f"transcript_{int(time.time())}.md"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[💾] Complete Transcript successfully saved to: {os.path.abspath(output_filename)}")

    # Auto disk cleanup
    if cleanup_temp and temp_cleanup and os.path.exists(temp_cleanup):
        try:
            os.remove(temp_cleanup)
            print("[🧹] Temporary downloaded audio file cleaned up automatically.")
        except Exception:
            pass

    return {
        "status": "success",
        "output_file": os.path.abspath(output_filename),
        "speakers": list(speaker_stats.keys()),
        "total_time": int(time.time() - start_time)
    }

if __name__ == "__main__":
    print("\n" + "="*65)
    print("   🎙️  ADVANCED PODCAST TRANSCRIBER & DIARIZATION ENGINE  🎙️  ")
    print("="*65)
    
    if len(sys.argv) > 1:
        source_input = sys.argv[1]
    else:
        source_input = input("\n👉 Podcast ka Link (YouTube/Web) ya Local File path enter karein: ").strip()

    if not source_input:
        print("[❌] Koi input provide nahi kiya gaya. Program exit ho raha hai.")
        sys.exit(1)

    names_in = input("👉 Speakers/Characters ke naam enter karein (comma-separated, jaise: Ranveer, Dr. Andrew) ya Enter dabayein: ").strip()
    custom_names = [n.strip() for n in names_in.split(",") if n.strip()] if names_in else None

    num_spk = None
    if not custom_names:
        spk_in = input("👉 Kitne speakers/characters hain? (Agar confirm nahi hai toh Enter dabayein): ").strip()
        num_spk = int(spk_in) if spk_in.isdigit() and int(spk_in) > 0 else None

    transcribe_with_diarization(source_input, speaker_names=custom_names, num_speakers=num_spk)
