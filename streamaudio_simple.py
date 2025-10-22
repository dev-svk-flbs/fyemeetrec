#!/usr/bin/env python3
"""
🏆 GOLD STANDARD - Ultra-Simple Audio Streaming Client
=====================================================

Records from VoiceMeeter B1 (which already mixes mic + Teams audio).
Optimized for transcription: 16kHz mono with noise filtering.

FINAL WORKING SOLUTION:
- No complex device detection
- No manual audio mixing  
- VoiceMeeter handles all mixing
- Just capture the final B1 output
- Proven audio settings for transcription

Setup (one-time):
1. VoiceMeeter running
2. Teams speaker → "VoiceMeeter Input"  
3. VoiceMeeter: Your mic → Hardware Input, Virtual Input → B output enabled

Usage:
  python streamaudio_simple.py 30        # Stream 30 seconds
  python streamaudio_simple.py --check   # Verify setup
"""

import subprocess
import argparse


class UltraSimpleStreamer:
    def __init__(self, server_ip="172.105.109.189", server_port=9000):
        self.server_ip = server_ip
        self.server_port = server_port
        self.audio_source = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        
    def check_setup(self):
        """Check if VoiceMeeter B1 is ready"""
        try:
            cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_text = result.stderr if result.stderr else result.stdout
            
            if self.audio_source in output_text:
                print("✅ VoiceMeeter B1 ready")
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
    
    def stream(self, duration=60):
        """Stream VoiceMeeter B1 (already mixed audio)"""
        if not self.check_setup():
            return
            
        print(f"� Streaming VoiceMeeter B1 → {self.server_ip}:{self.server_port}")
        print(f"⏱️  Duration: {duration}s (Ctrl+C to stop)")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-t", str(duration),
            "-filter:a", "highpass=f=120,lowpass=f=8000,afftdn=nf=-28,loudnorm=I=-14:LRA=10:TP=-1.5",
            "-ac", "1", "-ar", "16000", "-f", "s16le",
            f"udp://{self.server_ip}:{self.server_port}?pkt_size=512"
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print("✅ Stream completed!")
        except KeyboardInterrupt:
            print("⏹️ Stream stopped")
        except Exception as e:
            print(f"❌ Error: {e}")

    def record(self, duration=60):
        """Record VoiceMeeter B1 to file"""
        if not self.check_setup():
            return
            
        import time
        output_file = f"recording_{time.strftime('%Y%m%d_%H%M%S')}.wav"
        print(f"📁 Recording VoiceMeeter B1 → {output_file}")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-t", str(duration),
            "-filter:a", "highpass=f=120,lowpass=f=8000,afftdn=nf=-28,loudnorm=I=-14:LRA=10:TP=-1.5",
            "-ac", "1", "-ar", "16000",
            output_file
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Saved: {output_file}")
        except KeyboardInterrupt:
            print(f"⏹️ Stopped - partial file saved")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Ultra-Simple Audio Streaming - Just VoiceMeeter B1",
        epilog="""
Examples:
  python streamaudio_simple.py 30               # Stream for 30 seconds
  python streamaudio_simple.py 120              # Stream for 2 minutes  
  python streamaudio_simple.py --record 30      # Record 30 seconds to file
  python streamaudio_simple.py --check          # Check setup
        """
    )
    
    parser.add_argument('duration', type=int, nargs='?', default=60, help='Duration in seconds (default: 60)')
    parser.add_argument('--server', default='172.105.109.189', help='Server IP')
    parser.add_argument('--port', type=int, default=9000, help='Server port')  
    parser.add_argument('--record', action='store_true', help='Record to file instead of streaming')
    parser.add_argument('--check', action='store_true', help='Check setup')
    
    args = parser.parse_args()
    
    streamer = UltraSimpleStreamer(server_ip=args.server, server_port=args.port)
    
    if args.check:
        streamer.check_setup()
    elif args.record:
        streamer.record(args.duration)
    else:
        # Default action is stream
        streamer.stream(args.duration)


if __name__ == "__main__":
    main()