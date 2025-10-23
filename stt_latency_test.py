#!/usr/bin/env python3
"""
Barebones STT Latency Testing Script
Tests real-time speech-to-text latency using same FFmpeg pipeline and Faster Whisper setup
"""

import subprocess
import time
import threading
import queue
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel

def get_ffmpeg_path():
    """Get the path to the local FFmpeg executable"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    
    if ffmpeg_path.exists():
        return str(ffmpeg_path)
    else:
        # Fallback to system FFmpeg if local not found
        return "ffmpeg"


class STTLatencyTester:
    def __init__(self):
        # Audio configuration (copied exactly from dual_stream.py)
        self.audio_source = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
        self.sample_rate = 16000
        self.channels = 1
        self.audio_queue = queue.Queue()
        self.transcription_active = False
        self.audio_process = None
        
        # Timing statistics
        self.chunk_times = []
        self.transcription_times = []
        
        print("🔄 Loading Faster-Whisper model...")
        # Initialize with EXACT same parameters as dual_stream.py
        self.whisper_model = WhisperModel("base.en", compute_type="int8")
        print("✅ Faster-Whisper model loaded")
        
    def check_setup(self):
        """Verify VoiceMeeter B1 is available (copied from dual_stream.py)"""
        try:
            cmd = [get_ffmpeg_path(), "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_text = result.stderr if result.stderr else result.stdout
            
            if self.audio_source in output_text:
                print("✅ VoiceMeeter B1 ready")
                return True
            else:
                print("❌ VoiceMeeter B1 not found!")
                print("Available devices:")
                for line in output_text.split('\n'):
                    if 'DirectShow audio' in line:
                        print(f"  {line}")
                return False
                
        except FileNotFoundError:
            print("❌ FFmpeg not found!")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def capture_audio(self):
        """FFmpeg audio capture - EXACT same command as dual_stream.py"""
        cmd = [
            get_ffmpeg_path(), "-y", "-loglevel", "quiet",
            "-f", "dshow", "-i", f"audio={self.audio_source}",
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
        ]
        
        try:
            self.transcription_active = True
            self.audio_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # EXACT same chunk processing as dual_stream.py
            chunk_size = 16000 * 3 * 2  # 3 seconds at 16kHz, 16-bit = 96000 bytes
            process = self.audio_process
            
            while self.transcription_active and process and process.poll() is None:
                chunk_start = time.time()
                chunk = process.stdout.read(chunk_size)
                
                if chunk:
                    # EXACT same conversion as dual_stream.py
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    chunk_end = time.time()
                    
                    # Record chunk timing
                    chunk_time = chunk_end - chunk_start
                    self.chunk_times.append(chunk_time)
                    
                    # Add timestamp for latency tracking
                    self.audio_queue.put((audio_data, chunk_end))
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
    
    def transcribe_and_measure(self):
        """Process audio with Faster-Whisper - EXACT same parameters as dual_stream.py"""
        buffer = []
        block_duration = 3  # seconds - SAME as dual_stream.py
        required_samples = 16000 * block_duration
        
        while self.transcription_active:
            try:
                # Get audio data from queue (timeout to allow periodic checks)
                data_tuple = self.audio_queue.get(timeout=0.1)
                audio_data, chunk_timestamp = data_tuple
                buffer.extend(audio_data.flatten())

                # When we have enough samples, transcribe - SAME logic as dual_stream.py
                if len(buffer) >= required_samples:
                    # Get the chunk and remove from buffer
                    audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                    buffer = buffer[required_samples:]

                    # Measure transcription latency
                    transcribe_start = time.time()
                    
                    # EXACT same Whisper call as dual_stream.py
                    segments, _ = self.whisper_model.transcribe(
                        audio_chunk,
                        beam_size=1,
                        language="en"
                    )

                    transcribe_end = time.time()
                    transcription_time = transcribe_end - transcribe_start
                    total_latency = transcribe_end - chunk_timestamp
                    
                    # Record timing statistics
                    self.transcription_times.append(transcription_time)
                    
                    # Process segments and show results
                    for segment in segments:
                        text = segment.text.strip()
                        if text:
                            print(f"💬 [{transcription_time:.3f}s trans, {total_latency:.3f}s total] {text}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Transcription error: {e}")
                continue
        
        print("✅ Transcription testing completed")
    
    def run_test(self, duration=60):
        """Run latency test for specified duration"""
        if not self.check_setup():
            return False
            
        print(f"🧪 STT LATENCY TEST")
        print(f"🎤 Audio Source: {self.audio_source}")
        print(f"⏱️  Test Duration: {duration} seconds")
        print(f"🧠 Model: Faster-Whisper base.en (int8)")
        print(f"📊 Measuring: chunk capture + transcription latency")
        print("-" * 60)
        
        # Reset statistics
        self.chunk_times = []
        self.transcription_times = []
        
        # Start audio capture in background thread
        audio_thread = threading.Thread(target=self.capture_audio, daemon=True)
        audio_thread.start()
        
        # Start transcription processing in background thread
        transcription_thread = threading.Thread(target=self.transcribe_and_measure, daemon=True)
        transcription_thread.start()
        
        # Run test for specified duration
        try:
            print("🎙️ Speak now to test latency...")
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n⏹️ Test stopped by user")
        finally:
            # Stop transcription
            self.transcription_active = False
        
        # Wait for threads to complete
        audio_thread.join(timeout=5)
        transcription_thread.join(timeout=5)
        
        # Print statistics
        self.print_statistics()
        return True
    
    def print_statistics(self):
        """Print latency statistics"""
        print("\n" + "=" * 60)
        print("📊 LATENCY STATISTICS")
        print("=" * 60)
        
        if self.chunk_times:
            avg_chunk = sum(self.chunk_times) / len(self.chunk_times)
            print(f"🎵 Audio Chunks: {len(self.chunk_times)} captured")
            print(f"📏 Average chunk time: {avg_chunk:.3f}s (target: 3.0s)")
        
        if self.transcription_times:
            avg_transcription = sum(self.transcription_times) / len(self.transcription_times)
            min_transcription = min(self.transcription_times)
            max_transcription = max(self.transcription_times)
            
            print(f"🧠 Transcriptions: {len(self.transcription_times)} processed")
            print(f"⚡ Average transcription: {avg_transcription:.3f}s")
            print(f"🏃 Fastest transcription: {min_transcription:.3f}s")
            print(f"🐌 Slowest transcription: {max_transcription:.3f}s")
            
            # Real-time performance indicator
            if avg_transcription < 1.0:
                print("✅ EXCELLENT: Sub-second transcription latency")
            elif avg_transcription < 2.0:
                print("✅ GOOD: Under 2 second transcription latency")
            elif avg_transcription < 3.0:
                print("⚠️ FAIR: Near real-time performance")
            else:
                print("❌ SLOW: Above real-time - may cause delays")
        else:
            print("❌ No transcriptions captured - check audio input")


def main():
    """Main function with simple command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description="STT Latency Tester")
    parser.add_argument('--duration', type=int, default=60, 
                       help='Test duration in seconds (default: 60)')
    parser.add_argument('--check', action='store_true', 
                       help='Just check setup without running test')
    
    args = parser.parse_args()
    
    tester = STTLatencyTester()
    
    if args.check:
        tester.check_setup()
    else:
        tester.run_test(args.duration)


if __name__ == "__main__":
    main()