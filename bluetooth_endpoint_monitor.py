#!/usr/bin/env python3
"""
Reliable Bluetooth Headset Detection using AudioEndpoint
Detects actual connection/disconnection of Bluetooth headsets
"""

import subprocess
import time
import json

def get_bluetooth_headset_endpoints():
    """Get Bluetooth headset AudioEndpoint devices"""
    try:
        ps_command = '''
        Get-PnpDevice -Class AudioEndpoint | Where-Object { 
            ($_.FriendlyName -like "*onn*TWS*" -or $_.FriendlyName -like "*onn*Value*") -and 
            $_.Status -eq "OK" -and
            ($_.FriendlyName -notlike "*Senary*")
        } | Select-Object FriendlyName, Status, InstanceId | ConvertTo-Json
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_command], 
                              capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            devices = json.loads(result.stdout.strip())
            if isinstance(devices, dict):
                devices = [devices]
            return devices
        
    except Exception as e:
        print(f"Error: {e}")
    
    return []

def get_simple_bluetooth_status():
    """Simple check - just count Bluetooth headset endpoints"""
    try:
        ps_command = '''
        (Get-PnpDevice -Class AudioEndpoint | Where-Object { 
            ($_.FriendlyName -like "*Headset*" -or $_.FriendlyName -like "*Headphones*") -and 
            $_.Status -eq "OK" -and
            ($_.FriendlyName -like "*TWS*" -or $_.FriendlyName -like "*onn*" -or $_.FriendlyName -like "*Hands-Free*") -and
            ($_.FriendlyName -notlike "*Senary*")
        }).Count
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_command], 
                              capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            count = int(result.stdout.strip())
            return count > 0
        
    except Exception as e:
        print(f"Error: {e}")
    
    return False

def main():
    """Monitor Bluetooth headset connection/disconnection"""
    print("🎧 Reliable Bluetooth Headset Monitor")
    print("Uses AudioEndpoint detection for accurate results")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    last_connected = None
    while True:
        try:
            bluetooth_connected = get_simple_bluetooth_status()
            endpoints = get_bluetooth_headset_endpoints()
            # Detect state changes
            if last_connected is not None and bluetooth_connected != last_connected:
                print(f"\n⚡ BLUETOOTH STATE CHANGE at {time.strftime('%H:%M:%S')}")
                if bluetooth_connected:
                    print("🎧 BLUETOOTH HEADSET CONNECTED!")
                else:
                    print("🔌 BLUETOOTH HEADSET DISCONNECTED!")
                
                # Configure Virtual Input routing based on Bluetooth state
                configure_virtual_inputs_for_bluetooth(bluetooth_connected)
                
                # Restart audio engine to apply changes
                print("   Restarting VoiceMeeter audio engine...")
                send_ctrl_r_to_voicemeeter()
                print("   ✅ VoiceMeeter audio engine restarted")
            # Show current status
            if bluetooth_connected:
                print(f"✅ {time.strftime('%H:%M:%S')} - Bluetooth headset CONNECTED")
                print(f"   Found {len(endpoints)} AudioEndpoint(s):")
                for endpoint in endpoints:
                    print(f"   • {endpoint['FriendlyName']}")
            else:
                print(f"❌ {time.strftime('%H:%M:%S')} - Bluetooth headset DISCONNECTED")
            last_connected = bluetooth_connected
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n🛑 Stopping monitor...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(1)
    print("✅ Monitor stopped")

def send_ctrl_r_to_voicemeeter():
    """Restart VoiceMeeter audio engine using API"""
    try:
        import voicemeeterlib
        with voicemeeterlib.api('banana') as vmr:
            vmr.command.restart()
    except Exception as e:
        print(f"   ⚠️ Error restarting VoiceMeeter: {e}")

def configure_virtual_inputs_for_bluetooth(bluetooth_connected):
    """Configure Virtual Input routing based on Bluetooth headset status"""
    try:
        import voicemeeterlib
        with voicemeeterlib.api('banana') as vmr:
            # Virtual inputs are strips 3 and 4 in Banana (0-2 are hardware, 3-4 are virtual)
            virtual_input_1 = vmr.strip[3]  # VoiceMeeter Input
            virtual_input_2 = vmr.strip[4]  # VoiceMeeter AUX Input
            
            if bluetooth_connected:
                # Bluetooth headset connected: Route Virtual Inputs to B1
                print("   🎧 Routing Virtual Inputs to B1 (for headphones)")
                virtual_input_1.B1 = True
                virtual_input_2.B1 = True
            else:
                # Bluetooth headset disconnected: Turn off Virtual Inputs to B1
                print("   🔊 Turning off Virtual Inputs to B1 (for speakers)")
                virtual_input_1.B1 = False
                virtual_input_2.B1 = False
            
            print(f"   ✅ Virtual Input → B1 routing: {bluetooth_connected}")
            
    except Exception as e:
        print(f"   ⚠️ Error configuring Virtual Inputs: {e}")

if __name__ == "__main__":
    main()