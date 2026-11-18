# 🎙️ Advanced AI Podcast Speaker Diarization & Transcription Tool

Yeh tool kisi bhi Podcast audio ya link (YouTube, Web URL, ya Local File) ko lekar har speaker/character ka alag-alag transcript (Speaker A, Speaker B, etc.) timestamps ke sath generate karta hai.

---

## ⚡ Supercharged Features (Latest Update):
1. **🚀 Non-Blocking Async GPU Processing:** Cloud GPU par non-blocking job submission aur live polling spinner/progress bar.
2. **🛡️ Robust Error Handling:** Invalid URLs, YouTube restrictions, network retries, aur API quota errors gracefully handle hote hain.
3. **🌐 Auto Language Detection:** Multi-lingual support (Hindi, English, Hinglish, Spanish, etc.) automatically detect karta hai.
4. **🏷️ Character Real-Name Mapper (Web UI):** Speaker A aur B ko unke asli naam (e.g. *Host*, *Guest*, ya unke actual names) de sakte hain, aur transcript turant update ho jata hai.
5. **📊 Speaker Analytics:** Har speaker ka speaking time duration, total words, aur conversation turns ka complete breakdown.
6. **🧹 Auto Disk Cleanup:** YouTube se download kiye gaye temporary audio files kaam khatam hote hi automatically delete ho jate hain.

---

## 🚀 Kaise Run Karein?

### Option 1: Terminal / Command Line Se Run Karein
```powershell
cd "D:\Python\Tool"

# Interactive prompt me link ya file path enter karein:
python transcriber.py

# Ya direct argument dekar run karein:
python transcriber.py "https://example.com/podcast.mp3"
```

---

### Option 2: Beautiful Web Interface (Streamlit) Se Run Karein
```powershell
cd "D:\Python\Tool"
streamlit run app.py
```
Isse browser me ek clean UI open ho jayega jahan aap:
- YouTube link paste kar sakte hain.
- Direct audio link daal sakte hain.
- Apne computer se koi bhi audio/video file drag & drop karke upload kar sakte hain.
- Character name customize kar sakte hain.
- Speaker-wise transcript filter aur read kar sakte hain.
- Ek click me full customized Markdown transcript download kar sakte hain.
