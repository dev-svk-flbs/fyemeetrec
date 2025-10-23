#!/usr/bin/env python3
"""
STT Performance Comparison Test
Compares original vs optimized versions side by side
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

class STTComparison:
    def __init__(self):
        self.results = {}
    
    def test_original_version(self, duration=30):
        """Test original single-threaded version"""
        print("🔍 TESTING ORIGINAL VERSION (Single-threaded)")
        print("-" * 50)
        
        # Initialize original setup
        audio_queue = queue.Queue()
        transcription_active = True
        whisper_model = WhisperModel("base.en", compute_type="int8")
        
        start_time = time.time()
        transcript_count = 0
        processing_times = []
        
        def capture_audio():
            cmd = [get_ffmpeg_path(), "-y", "-loglevel", "quiet", "-f", "dshow", 
                   "-i", "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)", 
                   "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            chunk_size = 16000 * 3 * 2
            
            while transcription_active:
                chunk = process.stdout.read(chunk_size)
                if chunk:
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    audio_queue.put(audio_data)
                else:
                    break

        def transcribe():
            nonlocal transcript_count, processing_times
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
                                print(f"💬 [ORIG|{timestamp}|{processing_time:.3f}s] {text}")
                        
                except queue.Empty:
                    continue
        
        # Run test
        audio_thread = threading.Thread(target=capture_audio, daemon=True)
        transcribe_thread = threading.Thread(target=transcribe, daemon=True)
        
        audio_thread.start()
        transcribe_thread.start()
        
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n⏹️ Original test stopped")
        
        transcription_active = False
        total_time = time.time() - start_time
        
        # Store results
        self.results['original'] = {
            'model': 'base.en',
            'workers': 1,
            'cpu_threads': 1,
            'total_time': total_time,
            'transcript_count': transcript_count,
            'processing_times': processing_times,
            'avg_processing': np.mean(processing_times) if processing_times else 0
        }
        
        print(f"✅ Original test completed: {transcript_count} transcriptions in {total_time:.1f}s")
    
    def test_optimized_version(self, duration=30):
        """Test optimized multi-threaded version"""
        print("\n🚀 TESTING OPTIMIZED VERSION (Multi-threaded)")
        print("-" * 50)
        
        # Initialize optimized setup
        audio_queue = queue.Queue(maxsize=6)
        transcription_active = True
        whisper_model = WhisperModel("base.en", compute_type="int8", cpu_threads=4)
        
        start_time = time.time()
        transcript_count = 0
        processing_times = []
        num_workers = 4
        
        def capture_audio():
            cmd = [get_ffmpeg_path(), "-y", "-loglevel", "quiet", "-f", "dshow", 
                   "-i", "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)", 
                   "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            chunk_size = 16000 * 3 * 2
            
            while transcription_active:
                chunk = process.stdout.read(chunk_size)
                if chunk:
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    try:
                        audio_queue.put(audio_data, timeout=0.1)
                    except queue.Full:
                        try:
                            audio_queue.get_nowait()
                            audio_queue.put(audio_data, timeout=0.1)
                        except (queue.Empty, queue.Full):
                            pass
                else:
                    break

        def transcription_worker(worker_id):
            nonlocal transcript_count, processing_times
            buffer = []
            required_samples = 16000 * 3
            worker_count = 0
            
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
                                worker_count += 1
                                print(f"💬 [OPT-W{worker_id}|{timestamp}|{processing_time:.3f}s] {text}")
                
                except queue.Empty:
                    continue
        
        # Run test with multiple workers
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
            print("\n⏹️ Optimized test stopped")
        
        transcription_active = False
        total_time = time.time() - start_time
        
        # Store results
        self.results['optimized'] = {
            'model': 'base.en',
            'workers': num_workers,
            'cpu_threads': 4,
            'total_time': total_time,
            'transcript_count': transcript_count,
            'processing_times': processing_times,
            'avg_processing': np.mean(processing_times) if processing_times else 0
        }
        
        print(f"✅ Optimized test completed: {transcript_count} transcriptions in {total_time:.1f}s")
    
    def print_comparison(self):
        """Print detailed comparison between versions"""
        if 'original' not in self.results or 'optimized' not in self.results:
            print("❌ Need both test results to compare")
            return
        
        orig = self.results['original']
        opt = self.results['optimized']
        
        print("\n" + "="*80)
        print("📊 PERFORMANCE COMPARISON REPORT")
        print("="*80)
        
        print(f"\n🔧 CONFIGURATION:")
        print(f"{'Metric':<20} {'Original':<25} {'Optimized':<25} {'Improvement'}")
        print("-" * 80)
        print(f"{'Model':<20} {orig['model']:<25} {opt['model']:<25} {'Same model ✅' if orig['model'] == opt['model'] else 'Different'}")
        print(f"{'Workers':<20} {orig['workers']:<25} {opt['workers']:<25} {f'{opt['workers']/orig['workers']:.1f}x more'}")
        print(f"{'CPU Threads':<20} {orig['cpu_threads']:<25} {opt['cpu_threads']:<25} {f'{opt['cpu_threads']/orig['cpu_threads']:.1f}x more'}")
        
        print(f"\n⚡ PERFORMANCE METRICS:")
        print(f"{'Metric':<20} {'Original':<25} {'Optimized':<25} {'Improvement'}")
        print("-" * 80)
        
        # Throughput comparison
        orig_throughput = orig['transcript_count'] / orig['total_time'] if orig['total_time'] > 0 else 0
        opt_throughput = opt['transcript_count'] / opt['total_time'] if opt['total_time'] > 0 else 0
        throughput_improvement = opt_throughput / orig_throughput if orig_throughput > 0 else 0
        
        print(f"{'Transcripts/sec':<20} {orig_throughput:.2f} {'transcripts/sec':<15} {opt_throughput:.2f} {'transcripts/sec':<15} {throughput_improvement:.1f}x faster")
        
        # Processing speed comparison
        if orig['avg_processing'] > 0 and opt['avg_processing'] > 0:
            speed_improvement = orig['avg_processing'] / opt['avg_processing']
            print(f"{'Avg Process Time':<20} {orig['avg_processing']:.3f}s {'per chunk':<15} {opt['avg_processing']:.3f}s {'per chunk':<15} {speed_improvement:.1f}x faster")
        
        # Real-time factors
        orig_rtf = 3.0 / orig['avg_processing'] if orig['avg_processing'] > 0 else 0
        opt_rtf = 3.0 / opt['avg_processing'] if opt['avg_processing'] > 0 else 0
        
        if orig_rtf > 0:
            print(f"{'Real-time Factor':<20} {orig_rtf:.1f}x {'real-time':<15} {opt_rtf:.1f}x {'real-time':<15} {opt_rtf/orig_rtf:.1f}x better")
        
        print(f"\n🎯 OVERALL ASSESSMENT:")
        if throughput_improvement > 2.0:
            print(f"🚀 EXCELLENT: {throughput_improvement:.1f}x performance boost!")
        elif throughput_improvement > 1.5:
            print(f"✅ GOOD: {throughput_improvement:.1f}x performance improvement")
        elif throughput_improvement > 1.1:
            print(f"⚠️ MODEST: {throughput_improvement:.1f}x improvement")
        else:
            print(f"❌ NEEDS WORK: Limited improvement ({throughput_improvement:.1f}x)")
        
        print("="*80)

def main():
    """Run comparison test"""
    print("🔥 STT PERFORMANCE COMPARISON")
    print("Testing Original vs Optimized versions")
    print("="*60)
    
    comparison = STTComparison()
    
    # Test both versions (30 seconds each)
    comparison.test_original_version(30)
    time.sleep(2)  # Brief pause between tests
    comparison.test_optimized_version(30)
    
    # Show comparison
    comparison.print_comparison()

if __name__ == "__main__":
    main()