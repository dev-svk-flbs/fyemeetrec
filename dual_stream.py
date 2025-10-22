#!/usr/bin/env python3
"""
Dual-Mode Client: Real-time Transcription + Local Video Recording
Audio (VoiceMeeter B1) → Faster-Whisper → Server + Local Video
"""

import subprocess
import sys
import time
import threading
import argparse
import json
import requests
import queue
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel


class DualModeStreamer:
    def __init__(self, server_ip="172.105.109.189", server_port=8000, monitor_config=None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.audio_source = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        self.recording_active = False
        self.transcription_active = False
        self.audio_queue = queue.Queue()
        self.sample_rate = 16000
        self.channels = 1
        self.video_process = None
        self.audio_process = None
        self.upload_status = {'active': False, 'progress': 0, 'file': None}
        
        # Monitor configuration
        self.monitor_config = monitor_config or {
            'x': -5760, 'y': 0, 'width': 1920, 'height': 1080, 'name': 'Default Monitor'
        }
        
        # Initialize Faster-Whisper model
        print("🔄 Loading Faster-Whisper model...")
        self.whisper_model = WhisperModel("base.en", compute_type="int8")
        print("✅ Faster-Whisper model loaded")
        
    def check_setup(self):
        """Verify VoiceMeeter B1 is available"""
        try:
            cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_text = result.stderr if result.stderr else result.stdout
            
            if self.audio_source in output_text:
                print("✅ VoiceMeeter B1 ready")
                return True
            else:
                print("❌ VoiceMeeter B1 not found!")
                return False
                
        except FileNotFoundError:
            print("❌ FFmpeg not found!")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def capture_audio_for_transcription(self):
        """FFmpeg audio capture for transcription - NO DURATION LIMIT"""
        cmd = [
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
        ]
        
        try:
            self.transcription_active = True
            self.audio_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Read audio data in 3-second chunks like gold standard
            chunk_size = 16000 * 3 * 2  # 3 seconds at 16kHz, 16-bit = 96000 bytes
            process = self.audio_process
            while self.transcription_active and process and process.poll() is None:
                # read may block until chunk_size is available; terminating process will break loop
                chunk = process.stdout.read(chunk_size)
                if chunk:
                    # Convert bytes to numpy array like gold standard
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    self.audio_queue.put(audio_data)
                else:
                    break
            
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
            
        except Exception as e:
            print(f"⚠️ Audio capture error: {e}")
        finally:
            self.transcription_active = False
            self.audio_process = None
    
    def transcribe_and_send(self):
        """Process audio chunks with Faster-Whisper and send text to server"""
        buffer = []
        block_duration = 3  # seconds
        required_samples = 16000 * block_duration
        
        while self.transcription_active:
            try:
                # Get audio data from queue (timeout to allow periodic checks)
                data = self.audio_queue.get(timeout=0.1)
                buffer.extend(data.flatten())

                # When we have enough samples, transcribe
                if len(buffer) >= required_samples:
                    # Get the chunk and remove from buffer
                    audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                    buffer = buffer[required_samples:]

                    # Transcribe
                    segments, _ = self.whisper_model.transcribe(
                        audio_chunk,
                        beam_size=1,
                        language="en"
                    )

                    # Process segments
                    for segment in segments:
                        text = segment.text.strip()
                        if text:
                            print(f"💬 {text}")
                            self.send_text_to_server(text)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Transcription error: {e}")
                continue
        
        print("✅ Transcription completed")
    
    def send_text_to_server(self, text):
        """Send transcribed text to backend server"""
        try:
            payload = {
                "text": text,
                "timestamp": time.time(),
                "source": "faster_whisper_local"
            }
            
            # Send POST request to server
            response = requests.post(
                f"http://{self.server_ip}:{self.server_port}/transcription",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                pass  # Silent success - no spam
            else:
                print(f"⚠️ Server error: {response.status_code}")
                
        except requests.exceptions.RequestException:
            pass  # Silent fail
        except Exception:
            pass  # Silent fail
    
    def record_video_local(self, output_file):
        """Record screen + audio to local file (main thread) - NO DURATION LIMIT"""
        # Build ffmpeg command with dynamic monitor config
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-thread_queue_size", "512", "-fflags", "nobuffer",
            "-f", "gdigrab", "-framerate", "5",
            "-offset_x", str(self.monitor_config['x']), 
            "-offset_y", str(self.monitor_config['y']),
            "-video_size", f"{self.monitor_config['width']}x{self.monitor_config['height']}",
            "-i", "desktop",
            "-thread_queue_size", "512",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-vf", "scale=1280:-1",
            "-filter:a", "highpass=f=120,lowpass=f=12000,afftdn=nf=-22,treble=g=3:f=4000,loudnorm=I=-14:LRA=10:TP=-1.5",
            "-c:v", "libx265", "-preset", "fast", "-crf", "32", "-pix_fmt", "yuv420p",
            "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "-ar", "48000",
            "-movflags", "+faststart",
            "-async", "1", "-vsync", "1", "-avoid_negative_ts", "make_zero",
            output_file
        ]

        self.recording_active = True
        try:
            self.video_process = subprocess.Popen(cmd)

            # Poll until process exits or recording_active cleared - NO TIME LIMIT
            while True:
                if not self.recording_active:
                    break
                if self.video_process.poll() is not None:
                    break
                time.sleep(0.5)

            if self.video_process and self.video_process.poll() is None:
                try:
                    self.video_process.terminate()
                except Exception:
                    pass
                self.video_process.wait(timeout=5)

            # Treat exit as success if file exists
            if Path(output_file).exists():
                print(f"✅ Local recording saved: {output_file}")
                # Start background upload
                self.start_background_upload(output_file)
                return True
            else:
                return False
        except KeyboardInterrupt:
            if self.video_process:
                try:
                    self.video_process.terminate()
                except Exception:
                    pass
            return False
        finally:
            self.recording_active = False
            self.video_process = None
    
    def start_background_upload(self, file_path):
        """Start background upload without blocking"""
        def upload_worker():
            try:
                self.upload_status = {'active': True, 'progress': 0, 'file': file_path}
                print(f"🔄 Starting upload: {file_path}")
                
                with open(file_path, 'rb') as f:
                    files = {'file': (Path(file_path).name, f, 'video/x-matroska')}
                    
                    response = requests.post(
                        f"http://{self.server_ip}:8000/upload",
                        files=files,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Upload completed: {file_path}")
                        self.upload_status = {'active': False, 'progress': 100, 'file': file_path}
                    else:
                        print(f"❌ Upload failed: {response.status_code}")
                        self.upload_status = {'active': False, 'progress': 0, 'file': file_path}
                        
            except Exception as e:
                print(f"❌ Upload error: {e}")
                self.upload_status = {'active': False, 'progress': 0, 'file': file_path}
        
        # Start upload in daemon thread (non-blocking)
        upload_thread = threading.Thread(target=upload_worker, daemon=True)
        upload_thread.start()
    
    def dual_mode_record(self):
        """Main function: Start both local transcription AND video recording - NO TIME LIMIT"""
        if not self.check_setup():
            return False
            
        # Generate output filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"meeting_{timestamp}.mkv"
        
        print(f"🚀 STARTING RECORDING SESSION")
        print(f"🧠 Transcription → {self.server_ip}:{self.server_port}")
        print(f"📺 Monitor → {self.monitor_config['name']} ({self.monitor_config['width']}x{self.monitor_config['height']} at {self.monitor_config['x']},{self.monitor_config['y']})")
        print(f"🎥 Video → {output_file}")
        print("=" * 50)
        
        # Start FFmpeg audio capture in background thread
        audio_thread = threading.Thread(
            target=self.capture_audio_for_transcription,
            daemon=True
        )
        audio_thread.start()
        
        # Start transcription processing in background thread
        self.transcription_active = True
        transcription_thread = threading.Thread(
            target=self.transcribe_and_send,
            daemon=True
        )
        transcription_thread.start()
        
        # Start video recording in main thread (so Ctrl+C works properly)
        success = self.record_video_local(output_file)
        
        # Signal transcription to stop
        self.transcription_active = False
        
        # Wait for threads to complete
        audio_thread.join(timeout=5)
        transcription_thread.join(timeout=5)
        
        if success:
            print("\n" + "=" * 50)
            print("✅ SESSION COMPLETED")
            print(f"📁 Video: {output_file}")
            print(f"🧠 Transcriptions sent to server")
        
        return success
    
    def transcribe_only_mode(self, duration):
        """Transcription only - no video recording"""
        if not self.check_setup():
            return False
            
        print(f"🧠 TRANSCRIPTION-ONLY MODE")
        print(f"🎤 Audio → Faster-Whisper → {self.server_ip}:{self.server_port}")
        print(f"⏱️  Duration: {duration} seconds")
        print(f"💡 No video recording - transcription only")
        print("-" * 50)
        
        # Start audio capture for transcription in background thread
        audio_thread = threading.Thread(
            target=self.capture_audio_for_transcription,
            daemon=True
        )
        audio_thread.start()
        
        # Set a timer to stop after duration
        def stop_after_duration():
            time.sleep(duration)
            self.transcription_active = False
        
        timer_thread = threading.Thread(target=stop_after_duration, daemon=True)
        timer_thread.start()
        
        # Start transcription processing in main thread
        try:
            self.transcribe_and_send()
            success = True
        except KeyboardInterrupt:
            print("⏹️ Transcription stopped by user")
            success = False
        finally:
            self.transcription_active = False
        
        # Wait for audio thread to complete
        audio_thread.join(timeout=5)
        
        if success:
            print("\n" + "=" * 50)
            print("✅ TRANSCRIPTION COMPLETED")
            print(f"🧠 Text sent to: {self.server_ip}:{self.server_port}")
        
        return success
    
    def local_only_record(self, duration):
        """Local recording only - no network streaming (most reliable)"""
        if not self.check_setup():
            return False
            
        # Generate output filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"local_meeting_{timestamp}.mkv"
        
        print(f"🎥 LOCAL-ONLY RECORDING")
        print(f"📁 Screen + audio → {output_file}")  
        print(f"⏱️  Duration: {duration} seconds")
        print(f"💡 No network streaming - pure local recording")
        print("-" * 50)
        
        # Set up duration timer for local recording
        def stop_recording_after_duration():
            time.sleep(duration)
            self.recording_active = False
        
        timer_thread = threading.Thread(target=stop_recording_after_duration, daemon=True)
        timer_thread.start()
        
        # Just do local recording, no network stream
        success = self.record_video_local(output_file)
        
        if success:
            print("\n" + "=" * 50)
            print("✅ LOCAL RECORDING COMPLETED")
            print(f"📁 Saved: {output_file}")
            print("💡 Upload manually to server when ready")
        
        return success


def main():
    parser = argparse.ArgumentParser(
        description="Dual-Mode Streaming: Real-time Audio + Local Video Recording",
        epilog="""
Examples:
  python dual_stream.py 300                    # 5-min meeting: transcribe + record video
  python dual_stream.py 1800                   # 30-min meeting  
  python dual_stream.py --transcribe-only 60   # Transcription only (no video)
  python dual_stream.py --local-only 300       # Local recording only (no transcription)
  python dual_stream.py --check                # Check setup
        """
    )
    
    parser.add_argument('duration', type=int, nargs='?', default=1800, 
                       help='Duration in seconds (default: 1800 = 30 minutes)')
    parser.add_argument('--server', default='172.105.109.189', help='Server IP')
    parser.add_argument('--port', type=int, default=8000, help='Server port')  
    parser.add_argument('--transcribe-only', action='store_true', help='Transcription only (no video recording)')
    parser.add_argument('--local-only', action='store_true', help='Local recording only (no transcription)')
    parser.add_argument('--check', action='store_true', help='Check VoiceMeeter setup')
    
    args = parser.parse_args()
    
    streamer = DualModeStreamer(server_ip=args.server, server_port=args.port)
    
    if args.check:
        streamer.check_setup()
    elif args.transcribe_only:
        streamer.transcribe_only_mode(args.duration)
    elif args.local_only:
        streamer.local_only_record(args.duration)
    else:
        # Default: Dual-mode recording
        streamer.dual_mode_record(args.duration)


if __name__ == "__main__":
    main()