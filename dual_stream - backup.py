#!/usr/bin/env python3
"""
🏆 DUAL-MODE STREAMING CLIENT - Real-time Audio + Local Video Recording
=====================================================================

ARCHITECTURE:
1. REAL-TIME: Audio stream (VoiceMeeter B1) → Server for live TTS
2. LOCAL: Video + Audio recording → File for persistence/upload

WORKFLOW:
- Start: Both audio streaming AND video recording begin simultaneously  
- During call: Server gets live audio for real-time transcription
- End: Video file saved locally, can be uploaded to server later

Requirements:
- VoiceMeeter running with B1 output enabled
- Teams speaker → "VoiceMeeter Input"
"""

import subprocess
import sys
import time
import threading
import argparse
from pathlib import Path


class DualModeStreamer:
    def __init__(self, server_ip="172.105.109.189", server_port=9000):
        self.server_ip = server_ip
        self.server_port = server_port
        self.audio_source = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        self.recording_active = False
        
    def check_setup(self):
        """Verify VoiceMeeter B1 is available"""
        try:
            cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_text = result.stderr if result.stderr else result.stdout
            
            if self.audio_source in output_text:
                print("✅ VoiceMeeter B1 ready for dual-mode streaming")
                return True
            else:
                print("❌ VoiceMeeter B1 not found!")
                print("Setup: Teams speaker → 'VoiceMeeter Input', Virtual Input → B enabled")
                return False
                
        except FileNotFoundError:
            print("❌ FFmpeg not found! Install FFmpeg first.")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def stream_audio_realtime(self, duration):
        """Stream audio to server for real-time TTS (runs in background thread)"""
        print(f"🔴 LIVE STREAM: Audio → {self.server_ip}:{self.server_port}")
        
        cmd = [
            "ffmpeg", "-y", "-loglevel", "warning",  # Less verbose logging
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-t", str(duration),
            "-filter:a", "highpass=f=120,lowpass=f=12000,afftdn=nf=-28,loudnorm=I=-14:LRA=10:TP=-1.5",
            "-ac", "1", "-ar", "16000", "-f", "s16le",
            f"udp://{self.server_ip}:{self.server_port}?pkt_size=512"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Live audio stream completed")
            else:
                print(f"⚠️ Live stream issues (but continuing): {result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Live stream failed (server may be down): {e}")
        except Exception as e:
            print(f"⚠️ Stream error (continuing anyway): {e}")
    
    def record_video_local(self, duration, output_file):
        """Record screen + audio to local file (main thread)"""
        print(f"🎬 LOCAL RECORDING: Screen + Audio → {output_file}")
        
        # Fixed: Add audio sync options to prevent "backward in time" errors
        cmd = [
            "ffmpeg", "-y",
            "-thread_queue_size", "512", "-fflags", "nobuffer",
            "-f", "gdigrab", "-framerate", "5", 
            "-offset_x", "-1920", "-offset_y", "0", 
            "-video_size", "1920x1080", "-i", "desktop",
            "-thread_queue_size", "512",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-t", str(duration),
            "-vf", "scale=1280:-1",
            "-filter:a", "highpass=f=120,lowpass=f=12000,afftdn=nf=-22,treble=g=3:f=4000,loudnorm=I=-14:LRA=10:TP=-1.5",
            "-c:v", "libx265", "-preset", "fast", "-crf", "32", "-pix_fmt", "yuv420p",
            "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "-ar", "48000",
            "-movflags", "+faststart",
            "-async", "1",           # Fix audio sync issues
            "-vsync", "1",           # Fix video sync issues  
            "-avoid_negative_ts", "make_zero",  # Fix timestamp issues
            output_file
        ]
        
        try:
            self.recording_active = True
            subprocess.run(cmd, check=True)
            print(f"✅ Local recording saved: {output_file}")
            return True
        except KeyboardInterrupt:
            print("⏹️ Recording stopped by user")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Recording error: {e}")
            return False
        except Exception as e:
            print(f"❌ Recording error: {e}")
            return False
        finally:
            self.recording_active = False
    
    def dual_mode_record(self, duration):
        """Main function: Start both audio streaming AND video recording"""
        if not self.check_setup():
            return False
            
        # Generate output filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"meeting_{timestamp}.mkv"
        
        print(f"🚀 DUAL-MODE RECORDING START")
        print(f"📡 Real-time audio stream → Server (for live TTS)")
        print(f"🎥 Video + audio recording → {output_file}")  
        print(f"⏱️  Duration: {duration} seconds")
        print(f"💡 Press Ctrl+C to stop both streams")
        print("-" * 60)
        
        # Start real-time audio streaming in background thread
        audio_thread = threading.Thread(
            target=self.stream_audio_realtime,
            args=(duration,),
            daemon=True
        )
        audio_thread.start()
        
        # Start video recording in main thread (so Ctrl+C works properly)
        success = self.record_video_local(duration, output_file)
        
        # Wait for audio thread to complete
        audio_thread.join(timeout=5)  # Give it 5 seconds to clean up
        
        if success:
            print("\n" + "=" * 60)
            print("✅ DUAL-MODE RECORDING COMPLETED")
            print(f"📁 Local file: {output_file}")
            print(f"📡 Live transcription: Streamed to {self.server_ip}:{self.server_port}")
            print("💡 Upload the local file to server when ready")
        
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
        
        # Just do local recording, no network stream
        success = self.record_video_local(duration, output_file)
        
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
  python dual_stream.py 300                    # 5-min meeting: stream audio + record video
  python dual_stream.py 1800                   # 30-min meeting  
  python dual_stream.py --audio-only 60        # Audio streaming only (no video)
  python dual_stream.py --local-only 300       # Local recording only (no streaming)
  python dual_stream.py --check                # Check setup
        """
    )
    
    parser.add_argument('duration', type=int, nargs='?', default=1800, 
                       help='Duration in seconds (default: 1800 = 30 minutes)')
    parser.add_argument('--server', default='172.105.109.189', help='Server IP')
    parser.add_argument('--port', type=int, default=9000, help='Server port')  
    parser.add_argument('--audio-only', action='store_true', help='Stream audio only (no video recording)')
    parser.add_argument('--local-only', action='store_true', help='Local recording only (no streaming)')
    parser.add_argument('--check', action='store_true', help='Check VoiceMeeter setup')
    
    args = parser.parse_args()
    
    streamer = DualModeStreamer(server_ip=args.server, server_port=args.port)
    
    if args.check:
        streamer.check_setup()
    elif args.audio_only:
        streamer.audio_only_stream(args.duration)
    elif args.local_only:
        streamer.local_only_record(args.duration)
    else:
        # Default: Dual-mode recording
        streamer.dual_mode_record(args.duration)


if __name__ == "__main__":
    main()