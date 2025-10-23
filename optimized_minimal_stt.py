#!/usr/bin/env python3
"""
Optimized Minimal STT - Multi-threaded version
Uses your 16-core CPU with parallel workers and larger model for better performance
"""

import subprocess
import queue
import numpy as np
import threading
import time
from pathlib import Path
from faster_whisper import WhisperModel
from system_diagnostics import quick_system_check

def get_ffmpeg_path():
    script_dir = Path(__file__).parent.absolute()
    ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    return str(ffmpeg_path) if ffmpeg_path.exists() else "ffmpeg"

class OptimizedSTT:
    def __init__(self):
        # Get system info for optimization
        self.system_info = quick_system_check()
        self.setup_optimized_config()
        
        # Queues for parallel processing
        self.audio_queue = queue.Queue(maxsize=6)  # Bounded queue
        self.transcription_active = True
        
        # Performance tracking
        self.start_time = time.time()
        self.transcript_count = 0
        self.processing_times = []
        
        print(f"🚀 OPTIMIZED STT INITIALIZED")
        print(f"🔥 CPU: {self.cpu_cores} cores | Model: {self.model_name} | Workers: {self.num_workers}")
        print("-" * 60)
        
        # Initialize optimized Whisper model
        print("🔄 Loading optimized Faster-Whisper model...")
        self.whisper_model = WhisperModel(
            self.model_name, 
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads
        )
        print(f"✅ Model loaded with {self.cpu_threads} CPU threads")
    
    def setup_optimized_config(self):
        """Configure optimal settings based on system capabilities"""
        cpu = self.system_info.cpu
        memory = self.system_info.memory
        
        self.cpu_cores = cpu.cores_logical
        
        # Optimize based on CPU cores
        if self.cpu_cores >= 12:
            self.num_workers = 4
            self.cpu_threads = 4
        elif self.cpu_cores >= 8:
            self.num_workers = 3  
            self.cpu_threads = 3
        elif self.cpu_cores >= 4:
            self.num_workers = 2
            self.cpu_threads = 2
        else:
            self.num_workers = 1
            self.cpu_threads = 1
        
        # Use base model for fastest loading and processing
        self.model_name = "base.en"    # 74MB - fastest
        self.compute_type = "int8"
        
        print(f"⚙️ Auto-configured: {self.num_workers} workers, {self.cpu_threads} CPU threads, {self.model_name} model")

    def capture_audio(self):
        """FFmpeg audio capture with queue management"""
        cmd = [get_ffmpeg_path(), "-y", "-loglevel", "quiet", "-f", "dshow", 
               "-i", "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)", 
               "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        chunk_size = 16000 * 3 * 2  # 3 seconds
        
        while self.transcription_active:
            chunk = process.stdout.read(chunk_size)
            if chunk:
                audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                
                try:
                    # Non-blocking put with queue management
                    self.audio_queue.put(audio_data, timeout=0.1)
                except queue.Full:
                    # Drop oldest if queue full (stay real-time)
                    try:
                        self.audio_queue.get_nowait()
                        self.audio_queue.put(audio_data, timeout=0.1)
                        print("⚠️ Dropped audio chunk to stay real-time")
                    except (queue.Empty, queue.Full):
                        pass
            else:
                break

    def transcription_worker(self, worker_id):
        """Individual transcription worker thread"""
        buffer = []
        required_samples = 16000 * 3
        worker_count = 0
        
        while self.transcription_active:
            try:
                data = self.audio_queue.get(timeout=0.1)
                buffer.extend(data.flatten())
                
                if len(buffer) >= required_samples:
                    # Process audio chunk
                    audio_chunk = np.array(buffer[:required_samples], dtype=np.float32)
                    buffer = buffer[required_samples:]
                    
                    # Measure processing time
                    process_start = time.time()
                    
                    segments, _ = self.whisper_model.transcribe(
                        audio_chunk, 
                        beam_size=1, 
                        language="en"
                    )
                    
                    process_end = time.time()
                    processing_time = process_end - process_start
                    self.processing_times.append(processing_time)
                    
                    # Output results
                    for segment in segments:
                        text = segment.text.strip()
                        if text:
                            timestamp = time.strftime('%H:%M:%S')
                            worker_count += 1
                            self.transcript_count += 1
                            
                            print(f"💬 [W{worker_id}|{timestamp}|{processing_time:.2f}s] {text}")
            
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Worker {worker_id} error: {e}")
        
        print(f"✅ Worker {worker_id} completed ({worker_count} transcriptions)")

    def run_optimized_test(self, duration=60):
        """Run optimized multi-threaded STT test"""
        print(f"🎤 Starting {duration}s optimized STT test...")
        print(f"🔊 Speak now to test multi-threaded performance...")
        print("-" * 60)
        
        # Start audio capture
        audio_thread = threading.Thread(target=self.capture_audio, daemon=True)
        audio_thread.start()
        
        # Start multiple transcription workers
        workers = []
        for i in range(self.num_workers):
            worker = threading.Thread(target=self.transcription_worker, args=(i+1,), daemon=True)
            worker.start()
            workers.append(worker)
        
        # Run for specified duration
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n⏹️ Test stopped by user")
        
        # Stop all workers
        self.transcription_active = False
        
        # Wait for workers to finish
        for worker in workers:
            worker.join(timeout=2)
        
        # Print performance statistics
        self.print_performance_stats()

    def print_performance_stats(self):
        """Print detailed performance analysis"""
        total_time = time.time() - self.start_time
        
        print("\n" + "=" * 70)
        print("📊 OPTIMIZED STT PERFORMANCE REPORT")
        print("=" * 70)
        
        # Basic stats
        print(f"🎯 Configuration:")
        print(f"   Model: {self.model_name} | Workers: {self.num_workers} | CPU Threads: {self.cpu_threads}")
        print(f"   Total Runtime: {total_time:.1f}s")
        print(f"   Transcriptions: {self.transcript_count}")
        
        # Processing time analysis
        if self.processing_times:
            avg_processing = np.mean(self.processing_times)
            min_processing = np.min(self.processing_times)
            max_processing = np.max(self.processing_times)
            
            print(f"\n⚡ Processing Performance:")
            print(f"   Average: {avg_processing:.3f}s per chunk")
            print(f"   Fastest: {min_processing:.3f}s")
            print(f"   Slowest: {max_processing:.3f}s")
            
            # Real-time factor
            if avg_processing < 1.0:
                realtime_factor = 3.0 / avg_processing  # 3s audio / processing time
                print(f"   🚀 Real-time factor: {realtime_factor:.1f}x (faster than real-time)")
            else:
                print(f"   ⚠️ Processing slower than real-time ({avg_processing:.3f}s > 1.0s)")
        
        # Throughput analysis
        if total_time > 0:
            throughput = self.transcript_count / total_time
            print(f"\n📈 Throughput:")
            print(f"   {throughput:.2f} transcriptions/second")
            print(f"   {throughput * 60:.1f} transcriptions/minute")
        
        # System utilization estimate
        theoretical_max = self.cpu_cores / 2  # Conservative estimate
        if self.processing_times:
            actual_performance = 3.0 / avg_processing if avg_processing > 0 else 0
            utilization = min(100, (actual_performance / theoretical_max) * 100)
            print(f"\n🖥️ System Utilization:")
            print(f"   Estimated CPU usage: {utilization:.1f}%")
            print(f"   Workers efficiency: {self.transcript_count / (self.num_workers * total_time):.2f} trans/worker/sec")
        
        # Comparison to single-threaded
        if self.num_workers > 1:
            speedup_estimate = min(self.num_workers, self.transcript_count / max(1, total_time/3))
            print(f"\n📊 Multi-threading Benefit:")
            print(f"   Estimated speedup: {speedup_estimate:.1f}x vs single thread")
            print(f"   Parallel efficiency: {(speedup_estimate/self.num_workers)*100:.1f}%")
        
        print("=" * 70)


def main():
    """Run optimized STT test"""
    print("🔥 OPTIMIZED MINIMAL STT TESTER")
    print("Leveraging multi-core CPU for maximum performance")
    print("=" * 60)
    
    # Initialize and run optimized STT
    stt = OptimizedSTT()
    stt.run_optimized_test(duration=90)  # 90 second test

if __name__ == "__main__":
    main()