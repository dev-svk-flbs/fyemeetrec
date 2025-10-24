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
import os
from pathlib import Path
from faster_whisper import WhisperModel
from logging_config import dual_stream_logger as logger, ffmpeg_logger

def get_ffmpeg_path():
    """Get the path to the local FFmpeg executable"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    
    if ffmpeg_path.exists():
        logger.debug(f"🔧 Using local FFmpeg: {ffmpeg_path}")
        return str(ffmpeg_path)
    else:
        # Fallback to system FFmpeg if local not found
        logger.warning("⚠️ Local FFmpeg not found, using system FFmpeg")
        return "ffmpeg"


class DualModeStreamer:
    def __init__(self, server_ip="172.105.109.189", server_port=8000, monitor_config=None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.audio_source = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        self.recording_active = False
        self.transcription_active = False
        self.audio_queue = queue.Queue()
        self.upload_status = {'active': False, 'progress': 0, 'file': None}
        
        # Monitor configuration
        self.monitor_config = monitor_config or {
            'x': -5760, 'y': 0, 'width': 1920, 'height': 1080, 'name': 'Default Monitor'
        }
        
        # Log initialization
        logger.info("🚀 DualModeStreamer initialized")
        logger.info(f"🌐 Server: {server_ip}:{server_port}")
        logger.info(f"🎤 Audio source: {self.audio_source}")
        logger.info(f"📺 Monitor config: {self.monitor_config}")
        
        # Initialize Faster-Whisper model
        logger.info("🔄 Loading Faster-Whisper model...")
        print("🔄 Loading Faster-Whisper model...")
        self.whisper_model = WhisperModel("base.en", compute_type="int8")
        logger.info("✅ Faster-Whisper model loaded successfully")
        print("✅ Faster-Whisper model loaded")
        
    def check_setup(self):
        """Verify VoiceMeeter B1 is available"""
        logger.info("🔍 Checking VoiceMeeter B1 setup...")
        try:
            cmd = [get_ffmpeg_path(), "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            logger.debug(f"🔧 Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_text = result.stderr if result.stderr else result.stdout
            
            if self.audio_source in output_text:
                logger.info("✅ VoiceMeeter B1 ready")
                print("✅ VoiceMeeter B1 ready")
                return True
            else:
                logger.error(f"❌ VoiceMeeter B1 not found! Audio source '{self.audio_source}' not available")
                print("❌ VoiceMeeter B1 not found!")
                return False
                
        except FileNotFoundError:
            logger.error("❌ FFmpeg not found!")
            print("❌ FFmpeg not found!")
            return False
        except Exception as e:
            logger.error(f"❌ Setup check error: {e}")
            print(f"❌ Error: {e}")
            return False
    
    def capture_audio_for_transcription(self):
        """FFmpeg audio capture for transcription - NO DURATION LIMIT"""
        logger.info("🎤 Starting audio capture for transcription...")
        cmd = [
            get_ffmpeg_path(), "-y", "-loglevel", "quiet",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
        ]
        
        logger.debug(f"🔧 Audio capture command: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            logger.info(f"✅ Audio capture process started with PID: {process.pid}")
            chunk_size = 16000 * 3 * 2  # 3 seconds
            
            chunk_count = 0
            while self.transcription_active:
                chunk = process.stdout.read(chunk_size)
                if chunk:
                    chunk_count += 1
                    if chunk_count % 10 == 0:  # Log every 30 seconds
                        logger.debug(f"🔊 Audio chunks captured: {chunk_count}")
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    self.audio_queue.put(audio_data)
                else:
                    logger.warning("⚠️ Audio capture: No data received")
                    break
                    
            logger.info(f"🔄 Audio capture completed - {chunk_count} chunks processed")
            
        except Exception as e:
            logger.error(f"❌ Audio capture error: {e}")
        finally:
            try:
                process.terminate()
                logger.debug("✅ Audio capture process terminated")
            except:
                pass
    
    def transcribe_and_send(self):
        logger.info("🧠 Starting transcription processing...")
        buffer = []
        required_samples = 16000 * 3
        transcription_count = 0
        
        while self.transcription_active:
            try:
                data = self.audio_queue.get(timeout=0.1)
                buffer.extend(data.flatten())
                
                if len(buffer) >= required_samples:
                    audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                    buffer = buffer[required_samples:]
                    
                    logger.debug(f"🔊 Processing audio chunk {transcription_count + 1} ({len(audio_chunk)} samples)")
                    
                    segments, _ = self.whisper_model.transcribe(audio_chunk, beam_size=1, language="en")
                    for segment in segments:
                        text = segment.text.strip()
                        if text:
                            transcription_count += 1
                            timestamp = time.strftime('%H:%M:%S')
                            logger.info(f"💬 [{timestamp}] Transcription #{transcription_count}: {text}")
                            print(f"💬 [{timestamp}] {text}")
                            self.send_text_to_server(text)
                        else:
                            logger.debug("🔇 Empty transcription segment")
                            
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Transcription error: {e}")
                
        logger.info(f"🔄 Transcription processing completed - {transcription_count} transcriptions processed")
    
    def send_text_to_server(self, text):
        payload = {"text": text, "timestamp": time.time(), "source": "faster_whisper_local"}
        try:
            logger.debug(f"📤 Sending to server: {text[:50]}...")
            response = requests.post(f"http://{self.server_ip}:{self.server_port}/transcription", json=payload, timeout=5)
            if response.status_code == 200:
                logger.debug("✅ Successfully sent to server")
            else:
                logger.warning(f"⚠️ Server responded with status {response.status_code}")
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout sending to server: {self.server_ip}:{self.server_port}")
        except Exception as e:
            logger.error(f"❌ Error sending to server: {e}")
        # Always continue even if server is unreachable
    
    def record_video_local(self, output_file):
        """Record screen + audio to local file (main thread) - NO DURATION LIMIT"""
        logger.info("🎥 Starting local video recording...")
        logger.info(f"📁 Output file: {output_file}")
        logger.info(f"📺 Monitor configuration received: {self.monitor_config}")
        
        # Log detailed monitor configuration
        logger.info(f"📍 Monitor position: X={self.monitor_config['x']}, Y={self.monitor_config['y']}")
        logger.info(f"📐 Monitor dimensions: {self.monitor_config['width']}x{self.monitor_config['height']}")
        logger.info(f"🏷️ Monitor name: {self.monitor_config['name']}")
        
        # Build ffmpeg command with dynamic monitor config
        cmd = [
            get_ffmpeg_path(), "-y", "-loglevel", "error",
            "-thread_queue_size", "512", "-fflags", "nobuffer",
            "-f", "gdigrab", "-framerate", "5",
            "-offset_x", str(self.monitor_config['x']), 
            "-offset_y", str(self.monitor_config['y']),
            "-video_size", f"{self.monitor_config['width']}x{self.monitor_config['height']}",
            "-i", "desktop",
            "-thread_queue_size", "512",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-vf", "scale=1280:-1",
            "-filter:a", "volume=1.9",
            "-c:v", "libx265", "-preset", "fast", "-crf", "32", "-pix_fmt", "yuv420p",
            "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "-ar", "48000",
            "-movflags", "+faststart",
            "-async", "1", "-vsync", "1", "-avoid_negative_ts", "make_zero",
            output_file
        ]
        
        # Log the complete FFmpeg command for debugging
        ffmpeg_logger.info("🔧 FFmpeg command parameters:")
        ffmpeg_logger.info(f"   📺 Video input: gdigrab desktop")
        ffmpeg_logger.info(f"   📍 Offset: X={self.monitor_config['x']}, Y={self.monitor_config['y']}")
        ffmpeg_logger.info(f"   📐 Video size: {self.monitor_config['width']}x{self.monitor_config['height']}")
        ffmpeg_logger.info(f"   🎤 Audio input: {self.audio_source}")
        ffmpeg_logger.info(f"   📁 Output: {output_file}")
        ffmpeg_logger.debug(f"   🔧 Full command: {' '.join(cmd)}")
        
        # Print key info to console for immediate visibility
        print(f"📺 Recording Monitor: {self.monitor_config['name']}")
        print(f"📍 Position: ({self.monitor_config['x']}, {self.monitor_config['y']})")
        print(f"📐 Resolution: {self.monitor_config['width']}x{self.monitor_config['height']}")

        self.recording_active = True
        try:
            logger.info("🚀 Starting FFmpeg process...")
            self.video_process = subprocess.Popen(cmd)
            ffmpeg_logger.info(f"✅ FFmpeg process started with PID: {self.video_process.pid}")

            # Poll until process exits or recording_active cleared - NO TIME LIMIT
            while True:
                if not self.recording_active:
                    logger.info("⏹️ Recording stop requested")
                    break
                if self.video_process.poll() is not None:
                    logger.info("⏹️ FFmpeg process ended")
                    break
                time.sleep(0.5)

            if self.video_process and self.video_process.poll() is None:
                logger.info("🛑 Terminating FFmpeg process...")
                try:
                    self.video_process.terminate()
                    ffmpeg_logger.info("✅ FFmpeg process terminated successfully")
                except Exception as e:
                    logger.error(f"❌ Error terminating FFmpeg: {e}")
                self.video_process.wait(timeout=5)

            # Treat exit as success if file exists
            if Path(output_file).exists():
                file_size = Path(output_file).stat().st_size
                logger.info(f"✅ Local recording saved: {output_file}")
                logger.info(f"📊 File size: {file_size / (1024*1024):.1f} MB")
                print(f"✅ Local recording saved: {output_file}")
                # Start background upload
                self.start_background_upload(output_file)
                return True
            else:
                logger.error(f"❌ Recording failed - output file not created: {output_file}")
                return False
        except KeyboardInterrupt:
            logger.info("⏹️ Recording interrupted by user")
            if self.video_process:
                try:
                    self.video_process.terminate()
                    ffmpeg_logger.info("✅ FFmpeg process terminated after interrupt")
                except Exception as e:
                    logger.error(f"❌ Error terminating FFmpeg after interrupt: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during recording: {e}")
            return False
        finally:
            self.recording_active = False
            self.video_process = None
            logger.info("🔄 Recording cleanup completed")
    
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
                        timeout=600  # 10 minute timeout
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Video upload completed: {file_path}")
                        self.upload_status = {'active': False, 'progress': 100, 'file': file_path, 'success': True}
                        
                        # Upload transcript file if it exists
                        self.upload_transcript_file(file_path)
                        
                        # Call upload callback if provided
                        if hasattr(self, 'upload_callback') and self.upload_callback:
                            try:
                                self.upload_callback(file_path, True, response.text)
                            except Exception as callback_error:
                                print(f"⚠️ Upload callback error: {callback_error}")
                    else:
                        print(f"❌ Upload failed: {response.status_code}")
                        self.upload_status = {'active': False, 'progress': 0, 'file': file_path, 'success': False}
                        # Call upload callback if provided
                        if hasattr(self, 'upload_callback') and self.upload_callback:
                            try:
                                self.upload_callback(file_path, False, f"HTTP {response.status_code}")
                            except Exception as callback_error:
                                print(f"⚠️ Upload callback error: {callback_error}")
                        
            except Exception as e:
                print(f"❌ Upload error: {e}")
                self.upload_status = {'active': False, 'progress': 0, 'file': file_path, 'success': False}
                # Call upload callback if provided
                if hasattr(self, 'upload_callback') and self.upload_callback:
                    try:
                        self.upload_callback(file_path, False, str(e))
                    except Exception as callback_error:
                        print(f"⚠️ Upload callback error: {callback_error}")
        
        # Start upload in daemon thread (non-blocking)
        upload_thread = threading.Thread(target=upload_worker, daemon=True)
        upload_thread.start()
    
    def upload_transcript_file(self, video_path):
        """Upload transcript file if it exists"""
        try:
            # Look for transcript file based on video filename
            video_base = os.path.splitext(video_path)[0]
            transcript_path = f"{video_base}_transcript.txt"
            
            # Also check for title-based transcript files in recordings directory
            recordings_dir = Path("recordings")
            if recordings_dir.exists():
                for transcript_file in recordings_dir.glob("*_transcript.txt"):
                    # Use the most recent transcript file if multiple exist
                    transcript_path = str(transcript_file)
                    break
            
            if not os.path.exists(transcript_path):
                print("ℹ️ No transcript file found to upload")
                return
            
            def upload_transcript_worker():
                try:
                    print(f"📤 Starting transcript upload: {transcript_path}")
                    
                    with open(transcript_path, 'rb') as f:
                        files = {'transcript': f}
                        data = {
                            'recording_title': os.path.basename(video_path),
                            'recording_id': str(int(time.time()))  # Use timestamp as ID
                        }
                        
                        response = requests.post(
                            f"http://{self.server_ip}:8000/upload-transcript",
                            files=files,
                            data=data,
                            timeout=60
                        )
                        
                        if response.status_code == 200:
                            print(f"✅ Transcript upload completed: {transcript_path}")
                        else:
                            print(f"⚠️ Transcript upload failed: HTTP {response.status_code}")
                            
                except Exception as e:
                    print(f"⚠️ Transcript upload error: {e}")
            
            # Upload transcript in background thread
            transcript_thread = threading.Thread(target=upload_transcript_worker, daemon=True)
            transcript_thread.start()
            
        except Exception as e:
            print(f"⚠️ Transcript upload setup error: {e}")
    
    def dual_mode_record(self):
        """Main function: Start both local transcription AND video recording - NO TIME LIMIT"""
        logger.info("🚀 Starting dual-mode recording session")
        
        if not self.check_setup():
            logger.error("❌ Setup check failed - aborting")
            return False
            
        # Create recordings directory if it doesn't exist
        recordings_dir = "recordings"
        Path(recordings_dir).mkdir(exist_ok=True)
        logger.debug(f"📁 Recordings directory: {Path(recordings_dir).absolute()}")
        
        # Generate output filename in recordings subfolder
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"{recordings_dir}/meeting_{timestamp}.mkv"
        self.last_output_file = output_file  # Store for database update
        
        logger.info(f"🚀 STARTING RECORDING SESSION")
        logger.info(f"🧠 Transcription → {self.server_ip}:{self.server_port}")
        logger.info(f"📺 Monitor → {self.monitor_config['name']} ({self.monitor_config['width']}x{self.monitor_config['height']} at {self.monitor_config['x']},{self.monitor_config['y']})")
        logger.info(f"🎥 Video → {output_file}")
        
        print(f"🚀 STARTING RECORDING SESSION")
        print(f"🧠 Transcription → {self.server_ip}:{self.server_port}")
        print(f"📺 Monitor → {self.monitor_config['name']} ({self.monitor_config['width']}x{self.monitor_config['height']} at {self.monitor_config['x']},{self.monitor_config['y']})")
        print(f"🎥 Video → {output_file}")
        print("=" * 50)
        
        # Start FFmpeg audio capture in background thread
        logger.info("🎤 Starting audio capture thread...")
        audio_thread = threading.Thread(
            target=self.capture_audio_for_transcription,
            daemon=True
        )
        audio_thread.start()
        
        # Start transcription processing in background thread
        self.transcription_active = True
        logger.info("🧠 Starting transcription thread...")
        transcription_thread = threading.Thread(
            target=self.transcribe_and_send,
            daemon=True
        )
        transcription_thread.start()
        
        # Start video recording in main thread (so Ctrl+C works properly)
        logger.info("🎥 Starting video recording...")
        success = self.record_video_local(output_file)
        
        # Signal transcription to stop
        logger.info("⏹️ Stopping transcription...")
        self.transcription_active = False
        
        # Wait for threads to complete
        logger.info("⏳ Waiting for threads to complete...")
        audio_thread.join(timeout=5)
        transcription_thread.join(timeout=5)
        
        if success:
            logger.info("✅ SESSION COMPLETED SUCCESSFULLY")
            print("\n" + "=" * 50)
            print("✅ SESSION COMPLETED")
            print(f"📁 Video saved locally: {output_file}")
            print(f"📤 Video upload started to: {self.server_ip}:8000")
            print(f"🧠 Live transcriptions sent to server: {self.server_ip}:{self.server_port}")
            print(f"💾 Local transcript file will be uploaded after video upload")
            print("🔄 Background uploads in progress...")
        else:
            logger.error("❌ SESSION FAILED")
        
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
            
        # Create recordings directory if it doesn't exist
        recordings_dir = "recordings"
        Path(recordings_dir).mkdir(exist_ok=True)
        
        # Generate output filename in recordings subfolder
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"{recordings_dir}/local_meeting_{timestamp}.mkv"
        
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