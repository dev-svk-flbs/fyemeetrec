#!/usr/bin/env python3
"""
Windows FFmpeg Audio Streaming Client
Uses your proven FFmpeg setup to stream audio to the ultra-fast UDP server.
Run this on Windows to stream audio from your Avaya B109 mic to the Linux server.
"""

import subprocess
import sys
import time
import argparse
from pathlib import Path


class WindowsAudioStreamer:
    def __init__(self, server_ip="172.105.109.189", server_port=9000):
        self.server_ip = server_ip
        self.server_port = server_port
        
        # Your proven audio devices
        self.audio_devices = {
            "avaya": "Echo Cancelling Speakerphone (Avaya B109)",
            "emeet": "Microphone (HD Webcam eMeet C960)",
            "intel": "Microphone Array (Intel® Smart Sound Technology for Digital Microphones)"
        }
        
        # System audio source - VoiceMeeter B1 (requires VoiceMeeter running)
        self.system_audio_device = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        
    def list_audio_devices(self):
        """List available audio devices using FFmpeg"""
        print("🎤 Discovering audio devices...")
        try:
            cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            audio_devices = []
            output_text = result.stderr if result.stderr else result.stdout
            for line in output_text.split('\n'):
                if '"' in line and 'audio' in line.lower():
                    # Extract device name
                    start = line.find('"') + 1
                    end = line.find('"', start)
                    if start > 0 and end > start:
                        device_name = line[start:end]
                        audio_devices.append(device_name)
            
            print("\n📋 Available audio input devices (microphones):")
            for device in audio_devices:
                print(f"   • {device}")
            
            print(f"\n🎯 Predefined microphone shortcuts:")
            for shortcut, device in self.audio_devices.items():
                print(f"   --{shortcut}: {device}")
            
            print(f"\n🔊 For system audio capture, we'll automatically detect your default playback device")
            print(f"💡 Use --mix-system to capture both mic and system audio for meetings")
                
        except FileNotFoundError:
            print("❌ FFmpeg not found! Please install FFmpeg and add it to PATH")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error listing devices: {e}")
    
    def get_system_audio_device(self, interactive=True):
        """Get system audio device for loopback capture with user assistance"""
        try:
            # Get list of all audio devices
            cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Extract all audio devices (FFmpeg device listing goes to stderr)
            audio_devices = []
            output_text = result.stderr if result.stderr else result.stdout
            for line in output_text.split('\n'):
                if '"' in line and 'audio' in line.lower():
                    start = line.find('"') + 1
                    end = line.find('"', start)
                    if start > 0 and end > start:
                        device_name = line[start:end]
                        audio_devices.append(device_name)
            
            if not audio_devices:
                print("❌ No audio devices found!")
                return None
                
            if not interactive:
                # Try automatic detection as fallback - prioritize Stereo Mix
                # First look for exact match to your working device
                if "Stereo Mix (Realtek(R) Audio)" in audio_devices:
                    return "Stereo Mix (Realtek(R) Audio)"
                
                # Then look for any Stereo Mix
                for device_name in audio_devices:
                    if "stereo mix" in device_name.lower():
                        return device_name
                
                # Fallback to other patterns
                for device_name in audio_devices:
                    device_lower = device_name.lower()
                    if any(pattern.lower() in device_lower for pattern in ["speakers", "headphones", "realtek", "stereo mix"]):
                        return device_name
                return None
            
            # Interactive mode - show user all devices and let them choose
            print(f"\n🔍 SYSTEM AUDIO DEVICE SELECTION")
            print(f"{'='*50}")
            print(f"To capture the other person's voice in meetings, we need to")
            print(f"capture your system's audio output (what you hear).")
            print(f"\n📋 Available audio devices on your system:")
            
            # Group devices by likely type for easier selection
            likely_mics = []
            likely_speakers = []
            other_devices = []
            
            for i, device in enumerate(audio_devices, 1):
                device_lower = device.lower()
                if any(word in device_lower for word in ["microphone", "mic", "array", "webcam", "usb"]):
                    likely_mics.append((i, device))
                elif any(word in device_lower for word in ["speakers", "headphones", "output", "realtek", "stereo mix", "loopback"]):
                    likely_speakers.append((i, device))
                else:
                    other_devices.append((i, device))
            
            if likely_speakers:
                print(f"\n🔊 LIKELY SPEAKER/OUTPUT DEVICES (what you want for system audio):")
                for i, device in likely_speakers:
                    print(f"   [{i}] {device}")
            
            if likely_mics:
                print(f"\n🎤 LIKELY MICROPHONE DEVICES (you probably don't want these for system audio):")
                for i, device in likely_mics:
                    print(f"   [{i}] {device}")
            
            if other_devices:
                print(f"\n❓ OTHER AUDIO DEVICES:")
                for i, device in other_devices:
                    print(f"   [{i}] {device}")
            
            print(f"\n💡 HELP: Look for devices with names like:")
            print(f"   • 'Speakers' or 'Headphones'")
            print(f"   • Your audio driver name (e.g., 'Realtek', 'IDT', 'Conexant')")
            print(f"   • 'Stereo Mix' (if available)")
            print(f"   • Anything that sounds like audio OUTPUT (not input/microphone)")
            
            if not likely_speakers:
                print(f"\n⚠️  NO OBVIOUS SPEAKER DEVICES FOUND!")
                print(f"💡 This is common on some systems. Try these options:")
                print(f"   1. Check if 'Stereo Mix' is enabled in Windows Sound settings")
                print(f"   2. Some devices can work for both input and output")
                print(f"   3. The Avaya B109 might work as it's a speakerphone")
                print(f"   4. Skip and use microphone-only mode")
            
            while True:
                try:
                    print(f"\n❓ Which device captures your SYSTEM AUDIO (what you hear)?")
                    print(f"   Enter device number (1-{len(audio_devices)}) or 'skip' to use mic only: ", end="")
                    
                    choice = input().strip().lower()
                    
                    if choice == 'skip':
                        print(f"⏩ Skipping system audio capture - using microphone only")
                        return None
                    
                    device_num = int(choice)
                    if 1 <= device_num <= len(audio_devices):
                        selected_device = audio_devices[device_num - 1]
                        print(f"✅ Selected system audio device: {selected_device}")
                        return selected_device
                    else:
                        print(f"❌ Please enter a number between 1 and {len(audio_devices)}")
                        
                except ValueError:
                    print(f"❌ Please enter a valid number or 'skip'")
                except KeyboardInterrupt:
                    print(f"\n⏹️ Selection cancelled")
                    return None
            
        except Exception as e:
            print(f"⚠️ Warning: Could not get audio devices: {e}")
            return None
    
    def setup_system_audio_interactive(self):
        """Interactive setup to help user identify their system audio device"""
        print(f"🔧 SYSTEM AUDIO SETUP FOR MEETINGS")
        print(f"{'='*50}")
        print(f"This will help you identify the correct audio device to capture")
        print(f"system audio (the other person's voice) during meetings.")
        print(f"\nWhen you use headphones, the other person's voice goes through")
        print(f"your system audio, not your microphone. We need to capture that!")
        
        # First, show all devices
        system_device = self.get_system_audio_device(interactive=True)
        
        if system_device:
            print(f"\n🧪 TESTING YOUR SELECTION")
            print(f"{'='*30}")
            print(f"Let's test the selected device: {system_device}")
            print(f"\n📋 INSTRUCTIONS:")
            print(f"1. Put on your headphones/earbuds")
            print(f"2. Play some audio (music, YouTube, etc.) - you should hear it")
            print(f"3. We'll record a 5-second test to see if we capture that audio")
            
            test_choice = input(f"\n❓ Ready to test? (y/n): ").strip().lower()
            
            if test_choice == 'y':
                self.test_system_audio_device(system_device)
            else:
                print(f"⏩ Test skipped. Remember your selection: {system_device}")
        
        print(f"\n💾 SAVE YOUR DEVICE NAME")
        print(f"{'='*25}")
        if system_device:
            print(f"✅ Your system audio device: {system_device}")
            print(f"\n📝 To use this in the future, you can:")
            print(f"   • Use --mix-system flag (auto-detects)")
            print(f"   • Or create a custom shortcut in the code")
        else:
            print(f"❌ No system audio device selected.")
            print(f"💡 You can still use --mix-system, but it will try auto-detection")
            print(f"\n🔧 TROUBLESHOOTING: No speaker devices found?")
            print(f"{'='*45}")
            print(f"If you don't see any speaker/output devices, try:")
            print(f"1. Enable 'Stereo Mix' in Windows:")
            print(f"   • Right-click speaker icon in taskbar")
            print(f"   • Open 'Sound settings' → 'More sound settings'")
            print(f"   • Go to 'Recording' tab")
            print(f"   • Right-click empty space → 'Show Disabled Devices'")
            print(f"   • Enable 'Stereo Mix' if available")
            print(f"   • Run this setup again")
            print(f"2. Some USB devices (like Avaya B109) can capture system audio")
            print(f"3. Use VoiceMeeter or Virtual Audio Cable software")
            print(f"4. For now, use microphone-only mode")
    
    def test_system_audio_device(self, device_name):
        """Test the selected system audio device with a short recording"""
        import tempfile
        import os
        
        print(f"\n🎬 Recording 5-second test...")
        print(f"🔊 Make sure audio is playing through your headphones NOW!")
        
        # Create temporary file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_file = f"test_system_audio_{timestamp}.wav"
        
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "dshow", "-i", f"audio={device_name}",
                "-t", "5",
                "-ar", "44100",
                "-ac", "2",
                temp_file
            ]
            
            print(f"⏱️ Recording... (5 seconds)")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Test recording saved: {temp_file}")
                print(f"\n🎧 Please listen to this file to check if it captured your system audio")
                print(f"💡 If it captured the audio you were playing, this device works!")
                print(f"❌ If it's silent or wrong audio, try a different device")
                
                # Ask if they want to keep or delete the test file
                keep_file = input(f"\n❓ Keep test file for review? (y/n): ").strip().lower()
                if keep_file != 'y':
                    try:
                        os.remove(temp_file)
                        print(f"🗑️ Test file deleted")
                    except:
                        pass
            else:
                print(f"❌ Test recording failed!")
                print(f"💡 Error: {result.stderr}")
                print(f"💡 This device might not support audio capture")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def stream_audio_only(self, device_name, duration=60, mix_system=False):
        """Stream only audio (no video) using your proven filters"""
        print(f"🎧 Starting AUDIO-ONLY stream...")
        print(f"📡 Target: {self.server_ip}:{self.server_port}")
        print(f"🎤 Microphone: {device_name}")
        
        if mix_system:
            system_device = self.get_system_audio_device()
            if system_device:
                print(f"🔊 System Audio: {system_device}")
                print(f"🎯 Mode: Mixed (mic + system audio for meetings)")
            else:
                print(f"⚠️ Warning: Could not detect system audio device, using microphone only")
                mix_system = False
        else:
            print(f"🎯 Mode: Microphone only")
            
        print(f"⏱️  Duration: {duration}s")
        print(f"🔊 Format: 16kHz mono PCM (optimized for transcription)")
        
        if mix_system and system_device:
            # Mixed audio command with two inputs
            cmd = [
                "ffmpeg",
                "-y",
                "-thread_queue_size", "512",
                "-fflags", "nobuffer",
                "-f", "dshow", "-i", f"audio={device_name}",          # Microphone input
                "-thread_queue_size", "512", 
                "-f", "dshow", "-i", f"audio={system_device}",        # System audio input
                "-t", str(duration),
                "-filter_complex", 
                "[0:a]highpass=f=120,lowpass=f=8000,afftdn=nf=-28[mic];"
                "[1:a]highpass=f=120,lowpass=f=8000,afftdn=nf=-28[sys];"
                "[mic][sys]amix=inputs=2:duration=longest:dropout_transition=2,loudnorm=I=-14:LRA=10:TP=-1.5[out]",
                "-map", "[out]",
                "-ac", "1",          # Mono for transcription
                "-ar", "16000",      # 16kHz for transcription
                "-f", "s16le",       # Raw PCM
                "-acodec", "pcm_s16le",
                f"udp://{self.server_ip}:{self.server_port}?pkt_size=512"
            ]
        else:
            # Single microphone input (original behavior)
            cmd = [
                "ffmpeg",
                "-y",
                "-thread_queue_size", "512",
                "-fflags", "nobuffer",
                "-f", "dshow", "-i", f"audio={device_name}",
                "-t", str(duration),
                "-filter:a", "highpass=f=120,lowpass=f=8000,afftdn=nf=-28,loudnorm=I=-14:LRA=10:TP=-1.5",
                "-ac", "1",          # Mono for transcription
                "-ar", "16000",      # 16kHz for transcription
                "-f", "s16le",       # Raw PCM
                "-acodec", "pcm_s16le",
                f"udp://{self.server_ip}:{self.server_port}?pkt_size=512"
            ]
        
        print(f"\n🚀 Streaming... (Press Ctrl+C to stop early)")
        if len(' '.join(cmd)) > 200:
            print(f"💡 Using mixed audio capture (mic + system)")
        else:
            print(f"💡 Command: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(cmd, check=True)
            print(f"\n✅ Stream completed successfully!")
            
        except KeyboardInterrupt:
            print(f"\n⏹️  Stream stopped by user")
            
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FFmpeg error: {e}")
            if mix_system:
                print(f"💡 Try running without --mix-system if system audio capture fails")
            print(f"💡 Try running with --list-devices to check audio device names")
            
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
    
    def stream_video_and_audio(self, device_name, duration=60, mix_system=False):
        """Stream both video and audio using your exact proven command (saves to file)"""
        print(f"🎬 Starting VIDEO + AUDIO recording...")
        print(f"🎤 Microphone: {device_name}")
        
        if mix_system:
            system_device = self.get_system_audio_device()
            if system_device:
                print(f"🔊 System Audio: {system_device}")
                print(f"🎯 Mode: Mixed (mic + system audio for meetings)")
            else:
                print(f"⚠️ Warning: Could not detect system audio device, using microphone only")
                mix_system = False
        else:
            print(f"🎯 Mode: Microphone only")
            
        print(f"⏱️  Duration: {duration}s")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"recording_{timestamp}.mkv"
        
        if mix_system and system_device:
            # Mixed audio recording with video
            cmd = [
                "ffmpeg",
                "-y",
                "-thread_queue_size", "512",
                "-fflags", "nobuffer",
                "-f", "gdigrab", "-framerate", "5", 
                "-offset_x", "-5760", "-offset_y", "0", 
                "-video_size", "1920x1080", "-i", "desktop",
                "-thread_queue_size", "512",
                "-f", "dshow", "-i", f"audio={device_name}",          # Microphone
                "-thread_queue_size", "512",
                "-f", "dshow", "-i", f"audio={system_device}",        # System audio
                "-t", str(duration),
                "-vf", "scale=1280:-1",
                "-filter_complex", 
                "[1:a]highpass=f=120,lowpass=f=8000,afftdn=nf=-28[mic];"
                "[2:a]highpass=f=120,lowpass=f=8000,afftdn=nf=-28[sys];"
                "[mic][sys]amix=inputs=2:duration=longest:dropout_transition=2,loudnorm=I=-14:LRA=10:TP=-1.5[aout]",
                "-map", "0:v",       # Video from screen capture
                "-map", "[aout]",    # Mixed audio output
                "-c:v", "libx265", "-preset", "fast", "-crf", "32", "-pix_fmt", "yuv420p",
                "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "-ar", "48000",
                "-movflags", "+faststart",
                output_file
            ]
        else:
            # Original single microphone recording
            cmd = [
                "ffmpeg",
                "-y",
                "-thread_queue_size", "512",
                "-fflags", "nobuffer",
                "-f", "gdigrab", "-framerate", "5", 
                "-offset_x", "-5760", "-offset_y", "0", 
                "-video_size", "1920x1080", "-i", "desktop",
                "-thread_queue_size", "512",
                "-f", "dshow", "-i", f"audio={device_name}",
                "-t", str(duration),
                "-vf", "scale=1280:-1",
                "-filter:a", "highpass=f=120,lowpass=f=8000,afftdn=nf=-28,loudnorm=I=-14:LRA=10:TP=-1.5",
                "-c:v", "libx265", "-preset", "fast", "-crf", "32", "-pix_fmt", "yuv420p",
                "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "-ar", "48000",
                "-movflags", "+faststart",
                output_file
            ]
        
        print(f"\n🚀 Recording... (Press Ctrl+C to stop early)")
        print(f"💾 Output: {output_file}")
        
        try:
            process = subprocess.run(cmd, check=True)
            print(f"\n✅ Recording saved: {output_file}")
            
        except KeyboardInterrupt:
            print(f"\n⏹️  Recording stopped by user")
            print(f"💾 Partial file saved: {output_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FFmpeg error: {e}")
            if mix_system:
                print(f"💡 Try running without --mix-system if system audio capture fails")
            
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Windows FFmpeg Audio Streaming Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python streamaudio.py --setup-system-audio             # FIRST: Setup system audio for meetings
  python streamaudio.py --list-devices                   # Show available devices
  python streamaudio.py --stream                          # Stream mic audio from Avaya B109
  python streamaudio.py --stream --mix-system            # Stream mic + system audio (for meetings)
  python streamaudio.py --stream --emeet --mix-system    # Stream from eMeet + system audio  
  python streamaudio.py --record --intel                 # Record video+audio from Intel mic
  python streamaudio.py --record --mix-system            # Record video+mixed audio
  python streamaudio.py --stream --duration 30           # Stream for 30 seconds
  python streamaudio.py --stream --server 192.168.1.100  # Stream to different server
        """
    )
    
    parser.add_argument('--server', default='172.105.109.189', 
                        help='Server IP address (default: your Linux server)')
    parser.add_argument('--port', type=int, default=9000, 
                        help='Server port (default: 9000)')
    parser.add_argument('--duration', type=int, default=60, 
                        help='Duration in seconds (default: 60)')
    
    # Action group
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--stream', action='store_true', 
                             help='Stream audio only to server (for transcription)')
    action_group.add_argument('--record', action='store_true', 
                             help='Record video+audio to local file (your proven setup)')
    action_group.add_argument('--list-devices', action='store_true', 
                             help='List available audio devices')
    action_group.add_argument('--setup-system-audio', action='store_true',
                             help='Interactive setup to identify your system audio device for meetings')
    
    # Audio mixing options
    parser.add_argument('--mix-system', action='store_true',
                       help='Mix microphone with system audio (for capturing both sides of meetings when using headphones)')
    
    # Device shortcuts
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument('--avaya', action='store_true', 
                             help='Use Avaya B109 speakerphone (default)')
    device_group.add_argument('--emeet', action='store_true', 
                             help='Use eMeet C960 webcam mic')
    device_group.add_argument('--intel', action='store_true', 
                             help='Use Intel Smart Sound microphone array')
    device_group.add_argument('--device', 
                             help='Custom device name (use quotes if contains spaces)')
    
    args = parser.parse_args()
    
    # Create streamer instance
    streamer = WindowsAudioStreamer(server_ip=args.server, server_port=args.port)
    
    # Handle list devices
    if args.list_devices:
        streamer.list_audio_devices()
        return
    
    # Handle system audio setup
    if args.setup_system_audio:
        streamer.setup_system_audio_interactive()
        return
    
    # Determine device name
    if args.device:
        device_name = args.device
    elif args.emeet:
        device_name = streamer.audio_devices["emeet"]
    elif args.intel:
        device_name = streamer.audio_devices["intel"]
    else:  # Default to Avaya
        device_name = streamer.audio_devices["avaya"]
    
    # Execute action
    if args.stream:
        streamer.stream_audio_only(device_name, args.duration, args.mix_system)
    elif args.record:
        streamer.stream_video_and_audio(device_name, args.duration, args.mix_system)


if __name__ == "__main__":
    main()