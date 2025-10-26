# Monitor Detection Guide

## Overview

This document explains how to detect and configure monitors in Windows environments, particularly for multi-monitor setups and screen recording applications. The main challenge is dealing with Windows display scaling that reports incorrect resolutions.

## The Problem: Windows Display Scaling

Windows 10/11 applies display scaling (125%, 150%, 200%) to improve readability on high-DPI displays. However, this causes issues when applications need to know the **actual native resolution** of monitors.

### Example Issue
- **Actual Monitor**: 1920×1080 @ 125% scaling
- **Reported by .NET**: 1536×864 (1920÷1.25)
- **Problem**: Screen recording captures at wrong resolution

## Solution: Multi-Method Detection

Our approach combines multiple Windows APIs to get accurate monitor information:

1. **Native Resolution**: Use WMI/CIM VideoController (bypasses scaling)
2. **Monitor Positions**: Use .NET System.Windows.Forms (accurate positioning)
3. **Manufacturer Info**: Use WMI BasicDisplayParams (brand/model detection)

## PowerShell Commands Reference

### 1. Native Resolution Detection (Bypasses Scaling)

```powershell
# Get actual GPU-reported resolution
Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.CurrentHorizontalResolution -gt 0} | Select-Object CurrentHorizontalResolution, CurrentVerticalResolution, Name

# Alternative using older WMI syntax
Get-WmiObject -Class Win32_VideoController | Select-Object CurrentHorizontalResolution, CurrentVerticalResolution, Name | Where-Object {$_.CurrentHorizontalResolution -gt 0}
```

**Expected Output:**
```
CurrentHorizontalResolution CurrentVerticalResolution Name
--------------------------- ------------------------- ----
                       1920                      1080 AMD Radeon (TM) Graphics
```

### 2. Monitor Position and Scaling Detection

```powershell
# Get monitor positions and scaled dimensions
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens | ForEach-Object { 
    [PSCustomObject]@{ 
        DeviceName = $_.DeviceName
        Primary = $_.Primary
        X = $_.Bounds.X
        Y = $_.Bounds.Y
        Width = $_.Bounds.Width
        Height = $_.Bounds.Height
        WorkingArea = "$($_.WorkingArea.Width)x$($_.WorkingArea.Height)"
    } 
} | Format-Table -AutoSize
```

### 3. Monitor Manufacturer Detection

```powershell
# Get monitor brand and model information
Get-WmiObject -Namespace root\wmi -Class WmiMonitorBasicDisplayParams | Select-Object InstanceName

# More detailed monitor information
Get-WmiObject -Class Win32_DesktopMonitor | Select-Object DeviceID, Name, ScreenWidth, ScreenHeight, MonitorManufacturer, MonitorType
```

**Expected Output:**
```json
[
    {
        "InstanceName": "DISPLAY\\BNQ78C2\\5&1a59f1d1&0&UID256_0"
    },
    {
        "InstanceName": "DISPLAY\\HKC2711\\5&1a59f1d1&0&UID260_0"
    }
]
```

### 4. Combined Detection Script

```powershell
# Complete monitor detection script
function Get-MonitorInfo {
    # Get native resolution
    $nativeRes = Get-CimInstance -ClassName Win32_VideoController | 
                 Where-Object {$_.CurrentHorizontalResolution -gt 0} | 
                 Select-Object -First 1
    
    # Get scaled monitor info
    Add-Type -AssemblyName System.Windows.Forms
    $monitors = [System.Windows.Forms.Screen]::AllScreens
    
    # Get manufacturer info
    $wmiMonitors = Get-WmiObject -Namespace root\wmi -Class WmiMonitorBasicDisplayParams
    
    # Calculate scaling factor
    $scalingFactor = if ($monitors[0].Bounds.Width -gt 0) { 
        $nativeRes.CurrentHorizontalResolution / $monitors[0].Bounds.Width 
    } else { 1.0 }
    
    Write-Host "=== Monitor Detection Results ==="
    Write-Host "Native Resolution: $($nativeRes.CurrentHorizontalResolution)x$($nativeRes.CurrentVerticalResolution)"
    Write-Host "Scaling Factor: $([math]::Round($scalingFactor, 2))x"
    Write-Host ""
    
    $monitors | ForEach-Object -Begin { $i = 0 } -Process {
        $actualWidth = [math]::Round($_.Bounds.Width * $scalingFactor)
        $actualHeight = [math]::Round($_.Bounds.Height * $scalingFactor)
        $actualX = [math]::Round($_.Bounds.X * $scalingFactor)
        $actualY = [math]::Round($_.Bounds.Y * $scalingFactor)
        
        Write-Host "Monitor $($i + 1):"
        Write-Host "  Device: $($_.DeviceName)"
        Write-Host "  Primary: $($_.Primary)"
        Write-Host "  Scaled: $($_.Bounds.Width)x$($_.Bounds.Height) at ($($_.Bounds.X), $($_.Bounds.Y))"
        Write-Host "  Actual: ${actualWidth}x${actualHeight} at ($actualX, $actualY)"
        Write-Host ""
        $i++
    }
}

# Run the detection
Get-MonitorInfo
```

## Manufacturer Code Mapping

Common manufacturer codes found in WMI InstanceName:

| Code | Manufacturer |
|------|--------------|
| ACR  | Acer         |
| AOC  | AOC          |
| ASU  | ASUS         |
| BNQ  | BenQ         |
| DEL  | Dell         |
| GSM  | LG           |
| HKC  | HKC          |
| HP   | HP           |
| LEN  | Lenovo       |
| MSI  | MSI          |
| SAM  | Samsung      |

## Implementation in Python/Flask

### Key Functions in app.py

#### 1. Native Resolution Detection
```python
def get_native_resolution():
    """Get native resolution from GPU driver (bypasses scaling)"""
    native_res_command = '''
    Get-CimInstance -ClassName Win32_VideoController | 
    Where-Object {$_.CurrentHorizontalResolution -gt 0} | 
    Select-Object CurrentHorizontalResolution, CurrentVerticalResolution | 
    ConvertTo-Json
    '''
    that was my office setup. now I am running at my home setup. check  the settings log towards teh end
    
    result = subprocess.run(['powershell', '-Command', native_res_command], 
                          capture_output=True, text=True, shell=False)
    
    if result.returncode == 0:
        data = json.loads(result.stdout.strip())
        return data.get('CurrentHorizontalResolution', 1920), \
               data.get('CurrentVerticalResolution', 1080)
    return 1920, 1080
```

#### 2. Scaling Detection and Correction
```python
def correct_monitor_scaling(monitors_data, native_width, native_height):
    """Apply scaling correction to monitor data"""
    if not monitors_data:
        return []
    
    # Calculate scaling factor from primary monitor
    primary_monitor = next((m for m in monitors_data if m.get('Primary')), monitors_data[0])
    scaling_factor = native_width / primary_monitor['Width'] if primary_monitor['Width'] > 0 else 1.0
    
    # Apply correction to all monitors
    corrected_monitors = []
    for monitor in monitors_data:
        corrected_monitors.append({
            'device_name': monitor['DeviceName'],
            'primary': monitor['Primary'],
            'x': int(monitor['X'] * scaling_factor),
            'y': int(monitor['Y'] * scaling_factor),
            'width': int(monitor['Width'] * scaling_factor),
            'height': int(monitor['Height'] * scaling_factor)
        })
    
    return corrected_monitors
```

## Troubleshooting

### Common Issues

1. **Wrong Resolutions (1536×864 instead of 1920×1080)**
   - **Cause**: Windows display scaling
   - **Solution**: Use `Win32_VideoController` for native resolution

2. **Monitor Positions Off by 25%/50%**
   - **Cause**: Scaled coordinates
   - **Solution**: Apply scaling factor correction

3. **Missing Manufacturer Info**
   - **Cause**: WMI namespace access or driver issues
   - **Solution**: Fallback to generic naming

4. **No Monitors Detected**
   - **Cause**: PowerShell execution policy or .NET assembly loading
   - **Solution**: Check execution policy with `Get-ExecutionPolicy`

### Diagnostic Commands

```powershell
# Check PowerShell execution policy
Get-ExecutionPolicy

# Test .NET assembly loading
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens.Count

# Verify WMI access
Get-WmiObject -Namespace root\wmi -Class WmiMonitorBasicDisplayParams | Measure-Object

# Check video controller detection
Get-CimInstance -ClassName Win32_VideoController | Where-Object {$_.Name -like "*"} | Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution
```

## Best Practices

1. **Always check for scaling**: Compare .NET reported size with native resolution
2. **Use multiple detection methods**: Combine WMI, CIM, and .NET for reliability
3. **Provide fallbacks**: Default to 1920×1080 if detection fails
4. **Cache results**: Monitor configuration rarely changes during app lifetime
5. **Test on multiple systems**: Different GPU drivers may behave differently

## References

- [System.Windows.Forms.Screen Class](https://docs.microsoft.com/en-us/dotnet/api/system.windows.forms.screen)
- [Win32_VideoController WMI Class](https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller)
- [WmiMonitorBasicDisplayParams WMI Class](https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/wmimonitorbasic/ns-wmimonitorbasic-_wmimonitorbasicdisplayparams)

---

**Last Updated**: October 22, 2025  
**Version**: 1.0  
**Tested On**: Windows 10/11 with 125%, 150% scaling