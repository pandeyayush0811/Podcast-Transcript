import os
import sys
import re
import time
import subprocess
from datetime import timedelta
from typing import Optional, Dict, Any, List, Tuple
import assemblyai as aai

# ==========================================
# SECURE CONFIGURATION (NO HARDCODED SECRETS)
# ==========================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_api_key() -> str:
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
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return bool(re.search(youtube_regex, url))

def is_valid_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def select_true_original_format_id(formats: List[Dict[str, Any]]) -> str:
    """
    STRICT FILTER: YouTube ke audio tracks me se sirf CREATOR KA TRUE ORIGINAL track
    select karta hai. Kisi bhi language ki 'dubbed' ya 'dubbed-auto' audio ko reject karta hai.
    """
    audio_formats = [f for f in formats if f.get('vcodec') == 'none']
    
    # Priority 1: Formats explicitly marked 'original' or language_preference == 10
    original_candidates = []
    for f in audio_formats:
        note = str(f.get('format_note', '')).lower()
        fid = str(f.get('format_id', '')).lower()
        pref = f.get('language_preference')
        
        # Dubbed tracks ko reject karo
        if 'dubbed' in note or 'dubbed' in fid:
            continue
            
        if 'original' in note or 'original' in fid or pref == 10:
            original_candidates.append(f)

    if original_candidates:
        # Lowest bitrate original candidate uthao (fast download ke liye)
        original_candidates.sort(key=lambda x: x.get('tbr') or x.get('abr') or 999)
        return original_candidates[0]['format_id']

    # Priority 2: Filter out all dubbed tracks
    non_dubbed = [f for f in audio_formats if 'dubbed' not in str(f.get('format_note', '')).lower()]
    if non_dubbed:
        non_dubbed.sort(key=lambda x: x.get('tbr') or x.get('abr') or 999)
        return non_dubbed[0]['format_id']

    return 'bestaudio'

def convert_to_mono_speech(input_file: str, output_dir: str = "temp_downloads") -> Tuple[str, bool]:
    """
    Original audio ko pure 1-Channel MONO (16kHz 24kbps) me convert karta hai.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    mono_output = os.path.join(output_dir, f"{base_name}_original_mono.mp3")

    orig_size_mb = round(os.path.getsize(input_file) / (1024 * 1024), 2)
    print(f"\n[🎙️] Converting Original Audio to Mono 1-Channel (16kHz)...")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-vn",                  # Video stream discard
        "-ac", "1",             # Pure MONO (1 channel)
        "-ar", "16000",         # 16kHz Speech Standard
        "-b:a", "24k",          # 24 kbps speech bitrate
        mono_output
    ]

    try:
        t0 = time.time()
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(mono_output) and os.path.getsize(mono_output) > 0:
            new_size_mb = round(os.path.getsize(mono_output) / (1024 * 1024), 2)
            dur = round(time.time() - t0, 1)
            print(f"[✅] Mono Conversion Complete in {dur}s! Size: {new_size_mb} MB (from {orig_size_mb} MB)")
            return mono_output, True
    except Exception as e:
        print(f"[⚠️] FFmpeg note: {e}. Original file use ki jayegi.")

    return input_file, False

def get_audio_source(url: str) -> Tuple[str, List[str]]:
    clean_url = url.strip().strip('"').strip("'")
    temp_files = []

    if is_youtube_url(clean_url):
        import yt_dlp
        output_dir = "temp_downloads"
        os.makedirs(output_dir, exist_ok=True)

        # Step A: Probe audio formats to find TRUE ORIGINAL track
        print(f"\n[🔍] YouTube metadata analyze ho raha hai (Searching True Original Track)...")
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl_probe:
            meta = ydl_probe.extract_info(clean_url, download=False)
            chosen_fid = select_true_original_format_id(meta.get('formats', []))
            title = meta.get('title', 'YouTube Podcast')
            
            # Find chosen format info
            chosen_fmt = next((f for f in meta.get('formats', []) if f.get('format_id') == chosen_fid), {})
            lang_label = chosen_fmt.get('language') or chosen_fmt.get('format_note') or 'Original'
            print(f"[🎯] Selected TRUE Original Track: Format {chosen_fid} ({lang_label}) [Dubbed tracks ignored]")

        # Step B: Download ONLY the chosen original audio format
        out_template = os.path.join(output_dir, f"{meta.get('id', 'audio')}_orig.%(ext)s")
        dl_opts = {
            'format': chosen_fid,
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(dl_opts) as ydl_down:
            ydl_down.download([clean_url])

            downloaded_raw = None
            for f in os.listdir(output_dir):
                if f.startswith(f"{meta.get('id', 'audio')}_orig"):
                    downloaded_raw = os.path.join(output_dir, f)
                    break

            if not downloaded_raw or not os.path.exists(downloaded_raw):
                raise RuntimeError("Original audio download fail ho gaya.")

            temp_files.append(downloaded_raw)
            print(f"[✅] Original Audio Downloaded: '{title}'")

            # Step C: Convert that Original Audio to Mono
            mono_file, is_new = convert_to_mono_speech(downloaded_raw, output_dir)
            if is_new:
                temp_files.append(mono_file)
            return mono_file, temp_files

    elif is_valid_url(clean_url):
        print(f"\n[🌐] Direct Web Audio URL: '{clean_url}'")
        return clean_url, []

    else:
        if not os.path.exists(clean_url):
            raise FileNotFoundError(f"Local file nahi mili: '{clean_url}'")
        
        file_size_mb = os.path.getsize(clean_url) / (1024 * 1024)
        print(f"\n[📁] Local file detect hui: {os.path.basename(clean_url)} ({round(file_size_mb, 1)} MB)")

        mono_file, is_new = convert_to_mono_speech(clean_url)
        if is_new:
            temp_files.append(mono_file)
        return mono_file, temp_files

def transcribe_with_diarization(
    source: str, 
    speaker_names: Optional[List[str]] = None,
    num_speakers: Optional[int] = None, 
    language_code: Optional[str] = None,
    cleanup_temp: bool = True
) -> Optional[Dict[str, Any]]:
    source_clean = source.strip().strip('"').strip("'")
    if not source_clean:
        print("[❌] Error: Input source empty hai.")
        return None

    try:
        audio_target, temp_cleanups = get_audio_source(source_clean)
    except Exception as e:
        print(f"[❌] Source Resolution Error: {e}")
        return None

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

    print("\n" + "="*65)
    print("🚀 [Cloud GPU Engine] Uploading & Submitting Job (Original Mono)...")
    if speaker_names:
        print(f"👥 Configured Character Names: {', '.join(speaker_names)}")
    print("="*65)

    try:
        t_upload_start = time.time()
        transcript_job = transcriber.submit(audio_target, config=config)
        upload_dur = round(time.time() - t_upload_start, 1)
        job_id = transcript_job.id
        print(f"[+] Upload & Submission completed in only {upload_dur}s! (Job ID: {job_id})")
    except Exception as e:
        print(f"[❌] API Submission Failed: {e}")
        return None

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
        
        print(f"\033[1;36m[{time_range}] {display_name}:\033[0m")
        print(f"   {u.text}\n")

        lines.append(f"**{display_name}** `[{time_range}]`:\n> {u.text}\n")

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

    output_filename = f"transcript_{int(time.time())}.md"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[💾] Complete Transcript successfully saved to: {os.path.abspath(output_filename)}")

    if cleanup_temp and temp_cleanups:
        for tf in temp_cleanups:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception:
                    pass
        print("[🧹] Temporary downloaded & compressed files cleaned up automatically.")

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
