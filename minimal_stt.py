#!/usr/bin/env python3
import subprocess
import queue
import numpy as np
import threading
import time
from pathlib import Path
from faster_whisper import WhisperModel

def get_ffmpeg_path():
    script_dir = Path(__file__).parent.absolute()
    ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    return str(ffmpeg_path) if ffmpeg_path.exists() else "ffmpeg"

# Initialize
audio_queue = queue.Queue()
transcription_active = True
whisper_model = WhisperModel("base.en", compute_type="int8")

def capture_audio():
    cmd = [get_ffmpeg_path(), "-y", "-loglevel", "quiet", "-f", "dshow", 
           "-i", "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)", 
           "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    chunk_size = 16000 * 3 * 2  # 3 seconds
    
    while transcription_active:
        chunk = process.stdout.read(chunk_size)
        if chunk:
            audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            audio_queue.put(audio_data)
        else:
            break

def transcribe():
    buffer = []
    required_samples = 16000 * 3
    
    while transcription_active:
        try:
            data = audio_queue.get(timeout=0.1)
            buffer.extend(data.flatten())
            
            if len(buffer) >= required_samples:
                audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                buffer = buffer[required_samples:]
                
                segments, _ = whisper_model.transcribe(audio_chunk, beam_size=1, language="en")
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        timestamp = time.strftime('%H:%M:%S')
                        print(f"💬 [{timestamp}] {text}")
        except queue.Empty:
            continue

# Run
threading.Thread(target=capture_audio, daemon=True).start()
transcribe()