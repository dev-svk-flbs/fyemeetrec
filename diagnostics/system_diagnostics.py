#!/usr/bin/env python3
"""
System Performance Diagnostics Module
Provides CPU, GPU, Memory, and AI acceleration detection for optimal resource allocation
"""

import subprocess
import json
import psutil
import platform
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class CPUInfo:
    """CPU information and capabilities"""
    brand: str
    cores_physical: int
    cores_logical: int
    frequency_max: float
    frequency_current: float
    architecture: str
    features: List[str]
    usage_percent: float
    temperature: Optional[float] = None

@dataclass
class GPUInfo:
    """GPU information and AI acceleration capabilities"""
    name: str
    driver_version: str
    memory_total: int
    memory_free: int
    cuda_capable: bool
    cuda_version: Optional[str]
    compute_capability: Optional[str]
    usage_percent: float
    temperature: Optional[float] = None

@dataclass
class MemoryInfo:
    """System memory information"""
    total_gb: float
    available_gb: float
    used_gb: float
    usage_percent: float
    swap_total_gb: float
    swap_used_gb: float

@dataclass
class SystemDiagnostics:
    """Complete system diagnostics"""
    cpu: CPUInfo
    gpus: List[GPUInfo]
    memory: MemoryInfo
    os_info: Dict[str, str]
    ai_frameworks: Dict[str, bool]
    recommendations: List[str]

class SystemProfiler:
    """Main system diagnostics class"""
    
    def __init__(self):
        self.cuda_available = self._check_cuda()
        
    def get_cpu_info(self) -> CPUInfo:
        """Get comprehensive CPU information"""
        try:
            # Basic CPU info
            cpu_freq = psutil.cpu_freq()
            cpu_count_physical = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            
            # CPU brand and features via PowerShell
            cpu_details = self._get_cpu_details_powershell()
            
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Temperature (if available)
            temperature = self._get_cpu_temperature()
            
            return CPUInfo(
                brand=cpu_details.get('name', 'Unknown'),
                cores_physical=cpu_count_physical or 1,
                cores_logical=cpu_count_logical or 1,
                frequency_max=cpu_freq.max if cpu_freq else 0,
                frequency_current=cpu_freq.current if cpu_freq else 0,
                architecture=cpu_details.get('architecture', platform.machine()),
                features=cpu_details.get('features', []),
                usage_percent=cpu_usage,
                temperature=temperature
            )
            
        except Exception as e:
            print(f"⚠️ CPU info error: {e}")
            return CPUInfo(
                brand="Unknown", cores_physical=1, cores_logical=1,
                frequency_max=0, frequency_current=0, architecture="Unknown",
                features=[], usage_percent=0
            )
    
    def get_gpu_info(self) -> List[GPUInfo]:
        """Get comprehensive GPU information"""
        gpus = []
        
        # Try NVIDIA GPUs first
        nvidia_gpus = self._get_nvidia_gpus()
        gpus.extend(nvidia_gpus)
        
        # Try Intel/AMD GPUs via PowerShell
        other_gpus = self._get_other_gpus_powershell()
        gpus.extend(other_gpus)
        
        return gpus if gpus else [self._create_fallback_gpu()]
    
    def get_memory_info(self) -> MemoryInfo:
        """Get system memory information"""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return MemoryInfo(
                total_gb=mem.total / (1024**3),
                available_gb=mem.available / (1024**3),
                used_gb=mem.used / (1024**3),
                usage_percent=mem.percent,
                swap_total_gb=swap.total / (1024**3),
                swap_used_gb=swap.used / (1024**3)
            )
            
        except Exception as e:
            print(f"⚠️ Memory info error: {e}")
            return MemoryInfo(0, 0, 0, 0, 0, 0)
    
    def get_ai_framework_support(self) -> Dict[str, bool]:
        """Check AI framework availability"""
        frameworks = {}
        
        # PyTorch CUDA
        try:
            import torch
            frameworks['pytorch'] = True
            frameworks['pytorch_cuda'] = torch.cuda.is_available()
        except ImportError:
            frameworks['pytorch'] = False
            frameworks['pytorch_cuda'] = False
        
        # TensorFlow
        try:
            import tensorflow as tf
            frameworks['tensorflow'] = True
            frameworks['tensorflow_gpu'] = len(tf.config.list_physical_devices('GPU')) > 0
        except ImportError:
            frameworks['tensorflow'] = False
            frameworks['tensorflow_gpu'] = False
        
        # OpenVINO
        try:
            import openvino
            frameworks['openvino'] = True
        except ImportError:
            frameworks['openvino'] = False
        
        # Faster Whisper / CTranslate2
        try:
            import faster_whisper
            frameworks['faster_whisper'] = True
        except ImportError:
            frameworks['faster_whisper'] = False
        
        return frameworks
    
    def generate_recommendations(self, cpu: CPUInfo, gpus: List[GPUInfo], 
                               memory: MemoryInfo, ai_frameworks: Dict[str, bool]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # CPU recommendations
        if cpu.cores_logical >= 8:
            recommendations.append(f"✅ Strong CPU: {cpu.cores_logical} cores - Use parallel processing")
        elif cpu.cores_logical >= 4:
            recommendations.append(f"⚠️ Moderate CPU: {cpu.cores_logical} cores - Use 2-3 worker threads")
        else:
            recommendations.append(f"⚠️ Limited CPU: {cpu.cores_logical} cores - Keep processing minimal")
        
        # GPU recommendations
        cuda_gpus = [gpu for gpu in gpus if gpu.cuda_capable]
        if cuda_gpus:
            best_gpu = max(cuda_gpus, key=lambda g: g.memory_total)
            if best_gpu.memory_total > 6000:  # >6GB VRAM
                recommendations.append(f"🚀 Excellent GPU: {best_gpu.name} - Use GPU acceleration for Whisper")
            elif best_gpu.memory_total > 2000:  # >2GB VRAM
                recommendations.append(f"✅ Good GPU: {best_gpu.name} - Use GPU with smaller models")
            else:
                recommendations.append(f"⚠️ Limited GPU: {best_gpu.name} - Stick to CPU processing")
        else:
            recommendations.append("❌ No CUDA GPU detected - Use optimized CPU processing")
        
        # Memory recommendations
        if memory.total_gb >= 16:
            recommendations.append(f"✅ Plenty of RAM: {memory.total_gb:.1f}GB - Can use larger models")
        elif memory.total_gb >= 8:
            recommendations.append(f"⚠️ Adequate RAM: {memory.total_gb:.1f}GB - Use medium models")
        else:
            recommendations.append(f"⚠️ Limited RAM: {memory.total_gb:.1f}GB - Use small models only")
        
        # Framework recommendations
        if ai_frameworks.get('pytorch_cuda'):
            recommendations.append("🚀 PyTorch CUDA available - Optimal for GPU acceleration")
        if ai_frameworks.get('faster_whisper'):
            recommendations.append("✅ Faster Whisper available - Recommended for STT")
        
        return recommendations
    
    def get_full_diagnostics(self) -> SystemDiagnostics:
        """Get complete system diagnostics"""
        print("🔍 Running system diagnostics...")
        
        cpu = self.get_cpu_info()
        print(f"📊 CPU: {cpu.brand} ({cpu.cores_logical} cores)")
        
        gpus = self.get_gpu_info()
        for gpu in gpus:
            print(f"🎮 GPU: {gpu.name} (CUDA: {gpu.cuda_capable})")
        
        memory = self.get_memory_info()
        print(f"💾 Memory: {memory.available_gb:.1f}GB available of {memory.total_gb:.1f}GB")
        
        ai_frameworks = self.get_ai_framework_support()
        
        os_info = {
            'system': platform.system(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }
        
        recommendations = self.generate_recommendations(cpu, gpus, memory, ai_frameworks)
        
        return SystemDiagnostics(
            cpu=cpu,
            gpus=gpus,
            memory=memory,
            os_info=os_info,
            ai_frameworks=ai_frameworks,
            recommendations=recommendations
        )
    
    # Private helper methods
    def _check_cuda(self) -> bool:
        """Check if CUDA is available"""
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _get_cpu_details_powershell(self) -> Dict[str, Any]:
        """Get detailed CPU info via PowerShell"""
        try:
            cmd = '''
            Get-WmiObject -Class Win32_Processor | Select-Object Name, Architecture, NumberOfCores, NumberOfLogicalProcessors | ConvertTo-Json
            '''
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, text=True, shell=False)
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, list):
                    data = data[0]
                
                return {
                    'name': data.get('Name', 'Unknown').strip(),
                    'architecture': str(data.get('Architecture', 'Unknown')),
                    'features': []  # Could be expanded
                }
        except Exception:
            pass
        
        return {'name': 'Unknown', 'architecture': 'Unknown', 'features': []}
    
    def _get_nvidia_gpus(self) -> List[GPUInfo]:
        """Get NVIDIA GPU information"""
        gpus = []
        try:
            # Try nvidia-ml-py first
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    
                    # Memory info
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    memory_total = mem_info.total // (1024 * 1024)  # MB
                    memory_free = mem_info.free // (1024 * 1024)   # MB
                    
                    # Utilization
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    usage_percent = util.gpu
                    
                    # Temperature
                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    except:
                        temp = None
                    
                    # CUDA capability
                    major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                    compute_capability = f"{major}.{minor}"
                    
                    gpus.append(GPUInfo(
                        name=name,
                        driver_version="Unknown",
                        memory_total=memory_total,
                        memory_free=memory_free,
                        cuda_capable=True,
                        cuda_version=None,
                        compute_capability=compute_capability,
                        usage_percent=usage_percent,
                        temperature=temp
                    ))
                
            except ImportError:
                # Fallback to nvidia-smi
                result = subprocess.run([
                    'nvidia-smi', '--query-gpu=name,memory.total,memory.free,utilization.gpu,temperature.gpu',
                    '--format=csv,noheader,nounits'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = [p.strip() for p in line.split(',')]
                            if len(parts) >= 5:
                                gpus.append(GPUInfo(
                                    name=parts[0],
                                    driver_version="Unknown",
                                    memory_total=int(parts[1]),
                                    memory_free=int(parts[2]),
                                    cuda_capable=True,
                                    cuda_version=None,
                                    compute_capability=None,
                                    usage_percent=float(parts[3]),
                                    temperature=float(parts[4]) if parts[4] != '[Not Supported]' else None
                                ))
                
        except Exception as e:
            print(f"⚠️ NVIDIA GPU detection error: {e}")
        
        return gpus
    
    def _get_other_gpus_powershell(self) -> List[GPUInfo]:
        """Get Intel/AMD GPU info via PowerShell"""
        gpus = []
        try:
            cmd = '''
            Get-WmiObject -Class Win32_VideoController | Where-Object {$_.Name -notmatch "NVIDIA"} | 
            Select-Object Name, AdapterRAM | ConvertTo-Json
            '''
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, text=True, shell=False)
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if not isinstance(data, list):
                    data = [data]
                
                for gpu_data in data:
                    name = gpu_data.get('Name', 'Unknown GPU')
                    if 'Microsoft' not in name and 'Remote' not in name:
                        memory_mb = gpu_data.get('AdapterRAM', 0)
                        if memory_mb:
                            memory_mb = memory_mb // (1024 * 1024)
                        
                        gpus.append(GPUInfo(
                            name=name,
                            driver_version="Unknown",
                            memory_total=memory_mb,
                            memory_free=memory_mb,  # Estimate
                            cuda_capable=False,
                            cuda_version=None,
                            compute_capability=None,
                            usage_percent=0,
                            temperature=None
                        ))
        except Exception:
            pass
        
        return gpus
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature if available"""
        try:
            # Try psutil sensors
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if 'cpu' in name.lower() or 'core' in name.lower():
                            return entries[0].current if entries else None
        except Exception:
            pass
        return None
    
    def _create_fallback_gpu(self) -> GPUInfo:
        """Create fallback GPU info when none detected"""
        return GPUInfo(
            name="Integrated Graphics",
            driver_version="Unknown",
            memory_total=0,
            memory_free=0,
            cuda_capable=False,
            cuda_version=None,
            compute_capability=None,
            usage_percent=0,
            temperature=None
        )


# Convenience functions for easy import/use
def quick_cpu_check() -> CPUInfo:
    """Quick CPU diagnostics"""
    profiler = SystemProfiler()
    return profiler.get_cpu_info()

def quick_gpu_check() -> List[GPUInfo]:
    """Quick GPU diagnostics"""
    profiler = SystemProfiler()
    return profiler.get_gpu_info()

def quick_system_check() -> SystemDiagnostics:
    """Quick full system diagnostics"""
    profiler = SystemProfiler()
    return profiler.get_full_diagnostics()

def print_diagnostics():
    """Print formatted diagnostics to console"""
    diag = quick_system_check()
    
    print("\n" + "="*60)
    print("🖥️  SYSTEM PERFORMANCE DIAGNOSTICS")
    print("="*60)
    
    print(f"\n💻 CPU: {diag.cpu.brand}")
    print(f"   Cores: {diag.cpu.cores_physical} physical, {diag.cpu.cores_logical} logical")
    print(f"   Usage: {diag.cpu.usage_percent}%")
    print(f"   Frequency: {diag.cpu.frequency_current:.0f} MHz")
    
    print(f"\n🎮 GPUs ({len(diag.gpus)}):")
    for i, gpu in enumerate(diag.gpus):
        cuda_status = "✅ CUDA" if gpu.cuda_capable else "❌ No CUDA"
        print(f"   {i+1}. {gpu.name}")
        print(f"      Memory: {gpu.memory_total}MB | {cuda_status}")
        print(f"      Usage: {gpu.usage_percent}%")
    
    print(f"\n💾 Memory:")
    print(f"   Total: {diag.memory.total_gb:.1f}GB")
    print(f"   Available: {diag.memory.available_gb:.1f}GB ({100-diag.memory.usage_percent:.1f}%)")
    
    print(f"\n🤖 AI Frameworks:")
    for framework, available in diag.ai_frameworks.items():
        status = "✅" if available else "❌"
        print(f"   {status} {framework}")
    
    print(f"\n💡 Recommendations:")
    for rec in diag.recommendations:
        print(f"   {rec}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    print_diagnostics()