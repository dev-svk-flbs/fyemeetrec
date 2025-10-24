#!/usr/bin/env python3
"""
Verify Windows Monitor Positions
Shows exactly what Windows reports for each monitor position
"""

import subprocess
import json
from pathlib import Path

def get_detailed_monitor_info():
    """Get detailed monitor information from Windows"""
    print("🔍 Querying Windows for monitor positions...")
    
    # Get monitor positions from Windows
    ps_command = '''
    Add-Type -AssemblyName System.Windows.Forms
    $screens = [System.Windows.Forms.Screen]::AllScreens
    $result = @()
    for ($i = 0; $i -lt $screens.Length; $i++) {
        $screen = $screens[$i]
        $result += [PSCustomObject]@{
            Index = $i
            DeviceName = $screen.DeviceName
            Primary = $screen.Primary
            X = $screen.Bounds.X
            Y = $screen.Bounds.Y
            Width = $screen.Bounds.Width
            Height = $screen.Bounds.Height
            Left = $screen.Bounds.Left
            Right = $screen.Bounds.Right
            Top = $screen.Bounds.Top
            Bottom = $screen.Bounds.Bottom
        }
    }
    $result | ConvertTo-Json
    '''
    
    try:
        result = subprocess.run([
            'powershell', '-Command', ps_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0:
            monitors_data = json.loads(result.stdout.strip())
            if isinstance(monitors_data, dict):
                monitors_data = [monitors_data]
            
            print(f"\n📺 Windows Reports {len(monitors_data)} Monitors:")
            print("=" * 80)
            
            for monitor in monitors_data:
                print(f"🖥️  Monitor {monitor['Index']} ({'PRIMARY' if monitor['Primary'] else 'SECONDARY'})")
                print(f"   Device: {monitor['DeviceName']}")
                print(f"   Position: ({monitor['X']}, {monitor['Y']})")
                print(f"   Size: {monitor['Width']}x{monitor['Height']}")
                print(f"   Bounds: Left={monitor['Left']}, Right={monitor['Right']}, Top={monitor['Top']}, Bottom={monitor['Bottom']}")
                print()
            
            # Now compare with manufacturer info
            print("\n🔍 Getting manufacturer information...")
            manufacturer_info = get_manufacturer_info()
            
            print("\n📊 COMPARISON TABLE:")
            print("=" * 100)
            print(f"{'Index':<6} {'Position':<12} {'Size':<12} {'Primary':<8} {'Manufacturer':<20} {'Model':<15}")
            print("-" * 100)
            
            for i, monitor in enumerate(monitors_data):
                manufacturer = "Unknown"
                model = "Unknown"
                if i < len(manufacturer_info):
                    mfg = manufacturer_info[i]
                    manufacturer = mfg.get('brand', 'Unknown')
                    model = mfg.get('model', 'Unknown')
                
                position = f"({monitor['X']}, {monitor['Y']})"
                size = f"{monitor['Width']}x{monitor['Height']}"
                primary = "YES" if monitor['Primary'] else "NO"
                
                print(f"{i:<6} {position:<12} {size:<12} {primary:<8} {manufacturer:<20} {model:<15}")
            
            return monitors_data
            
    except Exception as e:
        print(f"❌ Error getting monitor info: {e}")
        return []

def get_manufacturer_info():
    """Get manufacturer info separately"""
    try:
        wmi_command = '''Get-WmiObject -Namespace root\\wmi -Class WmiMonitorID | ForEach-Object {
            $mfgCode = ($_.ManufacturerName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join '';
            $modelName = ($_.UserFriendlyName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join '';
            [PSCustomObject]@{
                InstanceName = $_.InstanceName;
                ManufacturerCode = $mfgCode;
                ModelName = $modelName
            }
        } | ConvertTo-Json'''
        
        result = subprocess.run([
            'powershell', '-Command', wmi_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            wmi_data = json.loads(result.stdout.strip())
            if isinstance(wmi_data, dict):
                wmi_data = [wmi_data]
            
            manufacturer_codes = {
                'LEN': 'Lenovo', 'HKC': 'Koorui', 'ACR': 'Acer', 'SAM': 'Samsung',
                'DEL': 'Dell', 'AOC': 'AOC', 'BNQ': 'BenQ', 'ASU': 'ASUS',
                'MSI': 'MSI', 'GSM': 'LG', 'LG': 'LG', 'HP': 'HP', 'YCT': 'Unknown'
            }
            
            manufacturers = []
            for item in wmi_data:
                instance_name = item.get('InstanceName', '')
                model_name = item.get('ModelName', '').strip()
                
                if 'DISPLAY\\' in instance_name:
                    parts = instance_name.split('\\')
                    if len(parts) > 1:
                        manufacturer_part = parts[1]
                        manufacturer_code = None
                        
                        for code in manufacturer_codes.keys():
                            if manufacturer_part.startswith(code):
                                manufacturer_code = code
                                break
                        
                        if manufacturer_code:
                            brand = manufacturer_codes[manufacturer_code]
                            display_model = model_name if model_name else manufacturer_part[len(manufacturer_code):]
                            
                            manufacturers.append({
                                'instance': instance_name,
                                'code': manufacturer_code,
                                'brand': brand,
                                'model': display_model
                            })
            
            return manufacturers
    except Exception as e:
        print(f"⚠️ Could not get manufacturer info: {e}")
    
    return []

def main():
    """Main verification function"""
    print("🔍 MONITOR POSITION VERIFICATION")
    print("=" * 50)
    print("This will show exactly what Windows reports for monitor positions")
    print("and help us understand why FFmpeg might be recording the wrong monitor.")
    print()
    
    monitors = get_detailed_monitor_info()
    
    if monitors:
        print("\n🤔 ANALYSIS:")
        print("=" * 50)
        
        # Check for duplicate positions
        positions = [(m['X'], m['Y']) for m in monitors]
        duplicates = [pos for pos in set(positions) if positions.count(pos) > 1]
        
        if duplicates:
            print("⚠️  WARNING: Found duplicate monitor positions!")
            for pos in duplicates:
                matching_monitors = [i for i, m in enumerate(monitors) if (m['X'], m['Y']) == pos]
                print(f"   Position {pos} is used by monitors: {matching_monitors}")
                print("   This explains why FFmpeg might record the wrong monitor!")
        else:
            print("✅ All monitors have unique positions")
        
        # Show which monitor is at the recorded position
        target_position = (-1920, 0)
        matching_monitor = None
        for i, monitor in enumerate(monitors):
            if (monitor['X'], monitor['Y']) == target_position:
                matching_monitor = i
                break
        
        if matching_monitor is not None:
            print(f"\n🎯 Monitor at position {target_position} (where FFmpeg recorded):")
            monitor = monitors[matching_monitor]
            print(f"   Index: {matching_monitor}")
            print(f"   Device: {monitor['DeviceName']}")
            print(f"   Primary: {'YES' if monitor['Primary'] else 'NO'}")
            print(f"   This is the monitor that FFmpeg actually recorded!")
        else:
            print(f"\n❌ No monitor found at position {target_position}")
            print("   This suggests a different issue...")
    
    print(f"\n💡 SOLUTION:")
    print("If you see duplicate positions above, go to Windows Settings > Display")
    print("and drag the monitors to ensure each has a unique position that matches")
    print("your physical setup.")

if __name__ == "__main__":
    main()