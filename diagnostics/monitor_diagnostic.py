#!/usr/bin/env python3
"""
Windows Monitor Position Diagnostic
Deep dive into Windows monitor positioning and FFmpeg behavior
"""

import subprocess
import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from logging_config import get_logger

logger = get_logger("monitor_diagnostic")

def get_detailed_monitor_info():
    """Get detailed monitor information using multiple methods"""
    
    print("🔍 WINDOWS MONITOR POSITION DIAGNOSTIC")
    print("=" * 60)
    
    # Method 1: PowerShell Screen Information
    ps_command = '''
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { 
        [PSCustomObject]@{ 
            DeviceName = $_.DeviceName
            Primary = $_.Primary
            X = $_.Bounds.X
            Y = $_.Bounds.Y
            Width = $_.Bounds.Width
            Height = $_.Bounds.Height
            WorkingAreaX = $_.WorkingArea.X
            WorkingAreaY = $_.WorkingArea.Y
            WorkingAreaWidth = $_.WorkingArea.Width
            WorkingAreaHeight = $_.WorkingArea.Height
        } 
    } | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run([
            'powershell', '-Command', ps_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            screen_data = json.loads(result.stdout.strip())
            if isinstance(screen_data, dict):
                screen_data = [screen_data]
            
            print("📺 PowerShell Screen Detection:")
            for i, screen in enumerate(screen_data):
                print(f"   Screen {i}:")
                print(f"     Device: {screen['DeviceName']}")
                print(f"     Primary: {screen['Primary']}")
                print(f"     Position: ({screen['X']}, {screen['Y']})")
                print(f"     Size: {screen['Width']}x{screen['Height']}")
                print(f"     Working Area: ({screen['WorkingAreaX']}, {screen['WorkingAreaY']}) {screen['WorkingAreaWidth']}x{screen['WorkingAreaHeight']}")
                print()
                
    except Exception as e:
        print(f"❌ PowerShell screen detection failed: {e}")
    
    # Method 2: WMI Monitor Information
    wmi_command = '''
    Get-WmiObject -Namespace root\\wmi -Class WmiMonitorID | ForEach-Object {
        $mfgCode = ($_.ManufacturerName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join ''
        $modelName = ($_.UserFriendlyName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join ''
        $serialNumber = ($_.SerialNumberID | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join ''
        [PSCustomObject]@{
            InstanceName = $_.InstanceName
            ManufacturerCode = $mfgCode
            ModelName = $modelName
            SerialNumber = $serialNumber
        }
    } | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run([
            'powershell', '-Command', wmi_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            wmi_data = json.loads(result.stdout.strip())
            if isinstance(wmi_data, dict):
                wmi_data = [wmi_data]
            
            print("🔍 WMI Monitor Detection:")
            for i, monitor in enumerate(wmi_data):
                print(f"   Monitor {i}:")
                print(f"     Instance: {monitor.get('InstanceName', 'N/A')}")
                print(f"     Manufacturer: {monitor.get('ManufacturerCode', 'N/A')}")
                print(f"     Model: {monitor.get('ModelName', 'N/A')}")
                print(f"     Serial: {monitor.get('SerialNumber', 'N/A')}")
                print()
                
    except Exception as e:
        print(f"❌ WMI monitor detection failed: {e}")
    
    # Method 3: Display Configuration via PowerShell
    display_config_command = '''
    Add-Type -TypeDefinition @"
        using System;
        using System.Runtime.InteropServices;
        public class DisplayConfig {
            [DllImport("user32.dll")]
            public static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumProc lpfnEnum, IntPtr dwData);
            
            [DllImport("user32.dll")]
            public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO lpmi);
            
            public delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);
            
            [StructLayout(LayoutKind.Sequential)]
            public struct RECT {
                public int Left, Top, Right, Bottom;
            }
            
            [StructLayout(LayoutKind.Sequential)]
            public struct MONITORINFO {
                public int cbSize;
                public RECT rcMonitor;
                public RECT rcWork;
                public uint dwFlags;
            }
        }
"@
    
    $monitors = @()
    $callback = {
        param($hMonitor, $hdcMonitor, $lprcMonitor, $dwData)
        
        $monitorInfo = New-Object DisplayConfig+MONITORINFO
        $monitorInfo.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($monitorInfo)
        
        if ([DisplayConfig]::GetMonitorInfo($hMonitor, [ref]$monitorInfo)) {
            $script:monitors += [PSCustomObject]@{
                Left = $monitorInfo.rcMonitor.Left
                Top = $monitorInfo.rcMonitor.Top
                Right = $monitorInfo.rcMonitor.Right
                Bottom = $monitorInfo.rcMonitor.Bottom
                Width = $monitorInfo.rcMonitor.Right - $monitorInfo.rcMonitor.Left
                Height = $monitorInfo.rcMonitor.Bottom - $monitorInfo.rcMonitor.Top
                Primary = ($monitorInfo.dwFlags -band 1) -eq 1
                WorkLeft = $monitorInfo.rcWork.Left
                WorkTop = $monitorInfo.rcWork.Top
                WorkRight = $monitorInfo.rcWork.Right
                WorkBottom = $monitorInfo.rcWork.Bottom
            }
        }
        return $true
    }
    
    [DisplayConfig]::EnumDisplayMonitors([IntPtr]::Zero, [IntPtr]::Zero, $callback, [IntPtr]::Zero)
    $monitors | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run([
            'powershell', '-Command', display_config_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            display_data = json.loads(result.stdout.strip())
            if isinstance(display_data, dict):
                display_data = [display_data]
            
            print("🖥️ Windows Display Configuration:")
            for i, display in enumerate(display_data):
                print(f"   Display {i}:")
                print(f"     Position: ({display['Left']}, {display['Top']}) to ({display['Right']}, {display['Bottom']})")
                print(f"     Size: {display['Width']}x{display['Height']}")
                print(f"     Primary: {display['Primary']}")
                print(f"     Work Area: ({display['WorkLeft']}, {display['WorkTop']}) to ({display['WorkRight']}, {display['WorkBottom']})")
                print()
                
    except Exception as e:
        print(f"❌ Display configuration detection failed: {e}")
    
    print("🎯 ANALYSIS:")
    print("Look for monitors with identical X positions - this causes FFmpeg confusion!")
    print("Each monitor should have a unique X coordinate for proper screen capture.")

if __name__ == "__main__":
    get_detailed_monitor_info()