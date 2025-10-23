#!/usr/bin/env python3
"""
Quick system diagnostics test
Run this to check your system's AI/ML performance capabilities
"""

from system_diagnostics import print_diagnostics, quick_system_check

def main():
    """Run comprehensive system diagnostics"""
    
    # Simple formatted output
    print_diagnostics()
    
    # Get structured data for programmatic use
    diag = quick_system_check()
    
    # Example: Check if system is ready for GPU acceleration
    cuda_gpus = [gpu for gpu in diag.gpus if gpu.cuda_capable]
    if cuda_gpus:
        best_gpu = max(cuda_gpus, key=lambda g: g.memory_total)
        print(f"\n🚀 OPTIMIZATION RECOMMENDATION:")
        if best_gpu.memory_total > 4000:
            print(f"   Use GPU acceleration with {best_gpu.name}")
            print(f"   Recommended: WhisperModel(device='cuda', compute_type='float16')")
        else:
            print(f"   Limited GPU memory ({best_gpu.memory_total}MB)")
            print(f"   Recommended: WhisperModel(device='cuda', compute_type='int8')")
    else:
        print(f"\n⚡ CPU OPTIMIZATION RECOMMENDATION:")
        if diag.cpu.cores_logical >= 8:
            print(f"   Use {min(diag.cpu.cores_logical//2, 4)} parallel workers")
            print(f"   Recommended: WhisperModel(cpu_threads=4)")
        else:
            print(f"   Use 2 parallel workers maximum")
            print(f"   Recommended: WhisperModel(cpu_threads=2)")

if __name__ == "__main__":
    main()