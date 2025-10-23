#!/usr/bin/env python3
"""
Coordinated YouTube Clip Test
Tests single-threaded vs multi-threaded STT with the same audio clip
"""

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

class CoordinatedTest:
    def __init__(self):
        self.results = {}
        
    def wait_for_user_ready(self, test_name):
        """Wait for user to confirm they're ready"""
        print(f"\n{'='*60}")
        print(f"🎬 READY FOR {test_name.upper()} TEST")
        print(f"{'='*60}")
        print("📺 Please prepare your YouTube clip:")
        print("   1. Go to the beginning of the clip you want to test")
        print("   2. Make sure audio is playing through Voicemeeter")
        print("   3. Press ENTER when ready to start the test")
        input("👆 Press ENTER when ready... ")
        
    def test_single_threaded(self, duration=60):
        """Test original single-threaded version"""
        self.wait_for_user_ready("SINGLE-THREADED")
        
        print("🔍 TESTING SINGLE-THREADED VERSION")
        print("🎯 Using base.en model with 1 worker")
        print("-" * 50)
        
        # Initialize single-threaded setup
        audio_queue = queue.Queue()
        transcription_active = True
        whisper_model = WhisperModel("base.en", compute_type="int8")
        
        start_time = time.time()
        transcript_count = 0
        processing_times = []
        all_transcripts = []
        
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
            nonlocal transcript_count, processing_times, all_transcripts
            buffer = []
            required_samples = 16000 * 3
            
            while transcription_active:
                try:
                    data = audio_queue.get(timeout=0.1)
                    buffer.extend(data.flatten())
                    
                    if len(buffer) >= required_samples:
                        audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                        buffer = buffer[required_samples:]
                        
                        process_start = time.time()
                        segments, _ = whisper_model.transcribe(audio_chunk, beam_size=1, language="en")
                        process_end = time.time()
                        
                        processing_time = process_end - process_start
                        processing_times.append(processing_time)
                        
                        for segment in segments:
                            text = segment.text.strip()
                            if text:
                                timestamp = time.strftime('%H:%M:%S')
                                transcript_count += 1
                                transcript_entry = f"[SINGLE|{timestamp}|{processing_time:.3f}s] {text}"
                                all_transcripts.append(transcript_entry)
                                print(f"💬 {transcript_entry}")
                        
                except queue.Empty:
                    continue
        
        # Start test
        print("🚀 Starting single-threaded test in 3 seconds...")
        print("🎬 START YOUR YOUTUBE CLIP NOW!")
        time.sleep(3)
        
        audio_thread = threading.Thread(target=capture_audio, daemon=True)
        transcribe_thread = threading.Thread(target=transcribe, daemon=True)
        
        audio_thread.start()
        transcribe_thread.start()
        
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n⏹️ Single-threaded test stopped")
        
        transcription_active = False
        total_time = time.time() - start_time
        
        # Store results
        self.results['single'] = {
            'model': 'base.en',
            'workers': 1,
            'cpu_threads': 1,
            'total_time': total_time,
            'transcript_count': transcript_count,
            'processing_times': processing_times,
            'avg_processing': np.mean(processing_times) if processing_times else 0,
            'transcripts': all_transcripts
        }
        
        print(f"\n✅ Single-threaded test completed: {transcript_count} transcriptions in {total_time:.1f}s")
        print("📝 Results saved for comparison")
        
    def test_multi_threaded(self, duration=60):
        """Test optimized multi-threaded version"""
        self.wait_for_user_ready("MULTI-THREADED")
        
        print("🚀 TESTING MULTI-THREADED VERSION")
        print("🎯 Using base.en model with 4 workers")
        print("-" * 50)
        
        # Initialize multi-threaded setup
        audio_queue = queue.Queue(maxsize=6)
        transcription_active = True
        whisper_model = WhisperModel("base.en", compute_type="int8", cpu_threads=4)
        
        start_time = time.time()
        transcript_count = 0
        processing_times = []
        all_transcripts = []
        transcript_lock = threading.Lock()
        num_workers = 4
        
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
                    
                    try:
                        audio_queue.put(audio_data, timeout=0.1)
                    except queue.Full:
                        try:
                            audio_queue.get_nowait()  # Drop old chunk
                            audio_queue.put(audio_data, timeout=0.1)
                        except (queue.Empty, queue.Full):
                            pass
                else:
                    break

        def transcription_worker(worker_id):
            nonlocal transcript_count, processing_times, all_transcripts
            buffer = []
            required_samples = 16000 * 3
            
            while transcription_active:
                try:
                    data = audio_queue.get(timeout=0.1)
                    buffer.extend(data.flatten())
                    
                    if len(buffer) >= required_samples:
                        audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                        buffer = buffer[required_samples:]
                        
                        process_start = time.time()
                        segments, _ = whisper_model.transcribe(audio_chunk, beam_size=1, language="en")
                        process_end = time.time()
                        
                        processing_time = process_end - process_start
                        
                        with transcript_lock:
                            processing_times.append(processing_time)
                        
                        for segment in segments:
                            text = segment.text.strip()
                            if text:
                                timestamp = time.strftime('%H:%M:%S')
                                with transcript_lock:
                                    transcript_count += 1
                                    transcript_entry = f"[MULTI-W{worker_id}|{timestamp}|{processing_time:.3f}s] {text}"
                                    all_transcripts.append(transcript_entry)
                                    print(f"💬 {transcript_entry}")
                
                except queue.Empty:
                    continue
        
        # Start test
        print("🚀 Starting multi-threaded test in 3 seconds...")
        print("🎬 START YOUR YOUTUBE CLIP NOW!")
        time.sleep(3)
        
        audio_thread = threading.Thread(target=capture_audio, daemon=True)
        audio_thread.start()
        
        workers = []
        for i in range(num_workers):
            worker = threading.Thread(target=transcription_worker, args=(i+1,), daemon=True)
            worker.start()
            workers.append(worker)
        
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n⏹️ Multi-threaded test stopped")
        
        transcription_active = False
        total_time = time.time() - start_time
        
        # Store results
        self.results['multi'] = {
            'model': 'base.en',
            'workers': num_workers,
            'cpu_threads': 4,
            'total_time': total_time,
            'transcript_count': transcript_count,
            'processing_times': processing_times,
            'avg_processing': np.mean(processing_times) if processing_times else 0,
            'transcripts': all_transcripts
        }
        
        print(f"\n✅ Multi-threaded test completed: {transcript_count} transcriptions in {total_time:.1f}s")
        print("📝 Results saved for comparison")
        
    def print_detailed_comparison(self):
        """Print comprehensive comparison between single and multi-threaded"""
        if 'single' not in self.results or 'multi' not in self.results:
            print("❌ Need both test results to compare")
            return
        
        single = self.results['single']
        multi = self.results['multi']
        
        print("\n" + "="*80)
        print("📊 YOUTUBE CLIP PERFORMANCE COMPARISON")
        print("="*80)
        
        print(f"\n🔧 TEST CONFIGURATION:")
        print(f"{'Metric':<20} {'Single-threaded':<25} {'Multi-threaded':<25} {'Improvement'}")
        print("-" * 80)
        print(f"{'Model':<20} {single['model']:<25} {multi['model']:<25} {'Same ✅'}")
        print(f"{'Workers':<20} {single['workers']:<25} {multi['workers']:<25} {f'{multi['workers']/single['workers']:.1f}x more'}")
        print(f"{'CPU Threads':<20} {single['cpu_threads']:<25} {multi['cpu_threads']:<25} {f'{multi['cpu_threads']/single['cpu_threads']:.1f}x more'}")
        print(f"{'Test Duration':<20} {single['total_time']:.1f}s {'duration':<15} {multi['total_time']:.1f}s {'duration':<15}")
        
        print(f"\n⚡ PERFORMANCE METRICS:")
        print(f"{'Metric':<20} {'Single-threaded':<25} {'Multi-threaded':<25} {'Improvement'}")
        print("-" * 80)
        
        # Throughput comparison
        single_throughput = single['transcript_count'] / single['total_time'] if single['total_time'] > 0 else 0
        multi_throughput = multi['transcript_count'] / multi['total_time'] if multi['total_time'] > 0 else 0
        throughput_improvement = multi_throughput / single_throughput if single_throughput > 0 else 0
        
        print(f"{'Total Transcripts':<20} {single['transcript_count']:<25} {multi['transcript_count']:<25} {multi['transcript_count'] - single['transcript_count']:+d}")
        print(f"{'Transcripts/sec':<20} {single_throughput:.2f} {'trans/sec':<15} {multi_throughput:.2f} {'trans/sec':<15} {throughput_improvement:.1f}x")
        
        # Processing speed comparison
        if single['avg_processing'] > 0 and multi['avg_processing'] > 0:
            speed_improvement = single['avg_processing'] / multi['avg_processing']
            print(f"{'Avg Process Time':<20} {single['avg_processing']:.3f}s {'per chunk':<15} {multi['avg_processing']:.3f}s {'per chunk':<15} {speed_improvement:.1f}x faster")
        
        # Real-time factors
        single_rtf = 3.0 / single['avg_processing'] if single['avg_processing'] > 0 else 0
        multi_rtf = 3.0 / multi['avg_processing'] if multi['avg_processing'] > 0 else 0
        
        if single_rtf > 0 and multi_rtf > 0:
            print(f"{'Real-time Factor':<20} {single_rtf:.1f}x {'real-time':<15} {multi_rtf:.1f}x {'real-time':<15} {multi_rtf/single_rtf:.1f}x better")
        
        print(f"\n🎯 YOUTUBE CLIP ANALYSIS:")
        if throughput_improvement > 2.0:
            print(f"🚀 EXCELLENT: Multi-threading provides {throughput_improvement:.1f}x performance boost!")
            print(f"   📈 {multi['transcript_count'] - single['transcript_count']} more transcriptions captured")
        elif throughput_improvement > 1.5:
            print(f"✅ GOOD: Multi-threading provides {throughput_improvement:.1f}x improvement")
            print(f"   📈 {multi['transcript_count'] - single['transcript_count']} more transcriptions captured")
        elif throughput_improvement > 1.1:
            print(f"⚠️ MODEST: Multi-threading provides {throughput_improvement:.1f}x improvement")
        else:
            print(f"❌ LIMITED: Multi-threading shows minimal improvement ({throughput_improvement:.1f}x)")
        
        # Show transcript samples
        print(f"\n📝 TRANSCRIPT SAMPLES:")
        print(f"\n🔵 Single-threaded (first 3):")
        for i, transcript in enumerate(single['transcripts'][:3]):
            print(f"   {transcript}")
        
        print(f"\n🟢 Multi-threaded (first 3):")
        for i, transcript in enumerate(multi['transcripts'][:3]):
            print(f"   {transcript}")
            
        print("="*80)

def main():
    """Run coordinated YouTube clip comparison test"""
    print("🎬 YOUTUBE CLIP STT PERFORMANCE TEST")
    print("Compare single-threaded vs multi-threaded with same audio")
    print("="*70)
    print("📋 TEST PLAN:")
    print("   1. Single-threaded test (60s)")
    print("   2. Multi-threaded test (60s)")
    print("   3. Performance comparison")
    print("\n⚠️  IMPORTANT: You'll be prompted to rewind your YouTube clip between tests")
    input("\n👆 Press ENTER to begin... ")
    
    test = CoordinatedTest()
    
    # Run both tests with prompts
    test.test_single_threaded(60)
    test.test_multi_threaded(60)
    
    # Show detailed comparison
    test.print_detailed_comparison()

if __name__ == "__main__":
    main()