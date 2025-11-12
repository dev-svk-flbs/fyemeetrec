#!/usr/bin/env python3
"""
Reliable Bluetooth Headset Detection using AudioEndpoint
Detects actual connection/disconnection of Bluetooth headsets
"""

import subprocess
import time
import json
from logging_config import setup_logging

# Setup logging
logger = setup_logging("bluetooth_monitor")

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
        logger.error(f"Error getting Bluetooth endpoints: {e}")
    
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
        logger.error(f"Error checking Bluetooth status: {e}")
    
    return False

def main():
    """Main monitoring loop"""
    logger.info(" Reliable Bluetooth Headset Monitor")
    logger.info("Uses AudioEndpoint detection for accurate results")
    logger.info("Press Ctrl+C to stop")
    logger.info("-" * 50)
    
    last_connected = False
    
    while True:
        try:
            endpoints = get_bluetooth_headset_endpoints()
            bluetooth_connected = len(endpoints) > 0
            
            if bluetooth_connected != last_connected:
                logger.info(f"\n BLUETOOTH STATE CHANGE at {time.strftime('%H:%M:%S')}")
                if bluetooth_connected:
                    logger.info(" BLUETOOTH HEADSET CONNECTED!")
                else:
                    logger.info(" BLUETOOTH HEADSET DISCONNECTED!")
                
                # VoiceMeeter integration
                try:
                    # Restart VoiceMeeter audio engine
                    logger.info("   Restarting VoiceMeeter audio engine...")
                    send_ctrl_r_to_voicemeeter()
                    logger.info("    VoiceMeeter audio engine restarted")
                    configure_virtual_inputs_for_bluetooth(bluetooth_connected)
                except:
                    pass  # VoiceMeeter may not be installed
                
                if bluetooth_connected:
                    logger.info(f" {time.strftime('%H:%M:%S')} - Bluetooth headset CONNECTED")
                    logger.info(f"   Found {len(endpoints)} AudioEndpoint(s):")
                    for endpoint in endpoints:
                        logger.info(f"   • {endpoint['FriendlyName']}")
                else:
                    logger.info(f" {time.strftime('%H:%M:%S')} - Bluetooth headset DISCONNECTED")
            last_connected = bluetooth_connected
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("\n Stopping monitor...")
            break
        except Exception as e:
            logger.error(f" Error in monitoring loop: {e}", exc_info=True)
            time.sleep(1)
    logger.info(" Monitor stopped")

def send_ctrl_r_to_voicemeeter():
    """Restart VoiceMeeter audio engine using API"""
    try:
        import voicemeeterlib
        with voicemeeterlib.api('banana') as vmr:
            vmr.command.restart()
    except Exception as e:
        logger.warning(f"    Error restarting VoiceMeeter: {e}")

def configure_virtual_inputs_for_bluetooth(bluetooth_connected):
    """Configure Virtual Input routing based on Bluetooth headset status"""
    try:
        import voicemeeterlib
        import time
        
        with voicemeeterlib.api('banana') as vmr:
            # Virtual inputs are strips 3 and 4 in Banana (0-2 are hardware, 3-4 are virtual)
            virtual_input_1 = vmr.strip[3]  # VoiceMeeter Input
            virtual_input_2 = vmr.strip[4]  # VoiceMeeter AUX Input
            
            if bluetooth_connected:
                # Bluetooth headset connected: Route Virtual Inputs to B1
                logger.info("    Routing Virtual Inputs to B1 (for headphones)")
                # Turn OFF A1 first, then turn ON B1
                virtual_input_1.A1 = False
                virtual_input_2.A1 = False
                time.sleep(0.1)
                virtual_input_1.B1 = True
                virtual_input_2.B1 = True
            else:
                # Bluetooth headset disconnected: Turn off Virtual Inputs to B1
                logger.info("    Turning off Virtual Inputs to B1 (for speakers)")
                # Turn OFF B1 first, then turn ON A1
                virtual_input_1.B1 = False
                virtual_input_2.B1 = False
                time.sleep(0.1)
                virtual_input_1.A1 = True
                virtual_input_2.A1 = True
            
            # Wait for settings to apply
            time.sleep(0.2)
            
            # Verify and log the actual state
            logger.info(f"    Virtual Input 1 - A1: {virtual_input_1.A1}, B1: {virtual_input_1.B1}")
            logger.info(f"    Virtual Input 2 - A1: {virtual_input_2.A1}, B1: {virtual_input_2.B1}")
            
    except Exception as e:
        logger.warning(f"    Error configuring Virtual Inputs: {e}")

if __name__ == "__main__":
    main()
