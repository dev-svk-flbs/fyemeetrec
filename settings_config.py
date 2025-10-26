#!/usr/bin/env python3
"""
Settings Configuration Manager
Handles loading and saving user preferences to settings.config JSON file
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
from logging_config import settings_logger as logger

class SettingsManager:
    def __init__(self):
        self.config_file = Path(__file__).parent / "settings.config"
        self.default_settings = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "monitors": [],
            "user_preferences": {
                "default_monitor_id": 0,
                "auto_delete_days": 30,
                "last_updated": None
            }
        }
    
    def get_ffmpeg_path(self):
        """Get the path to the local FFmpeg executable"""
        script_dir = Path(__file__).parent.absolute()
        ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
        
        if ffmpeg_path.exists():
            return str(ffmpeg_path)
        else:
            return "ffmpeg"
    
    def get_monitor_manufacturers(self):
        """Get monitor manufacturer info using WMI"""
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
                
                # Enhanced manufacturer code mapping
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
                                product_id = manufacturer_part[len(manufacturer_code):]
                                
                                # Use model name if available, otherwise use product ID
                                display_model = model_name if model_name else product_id
                                
                                manufacturers.append({
                                    'instance': instance_name,
                                    'code': manufacturer_code,
                                    'brand': brand,
                                    'model': display_model,
                                    'full_name': f"{brand} {display_model}" if display_model else brand
                                })
                
                return manufacturers
        except Exception as e:
            print(f"WMI lookup failed: {e}")
        
        return []

    def get_native_resolution(self):
        """Get native resolution from GPU driver (bypasses scaling)"""
        try:
            native_res_command = '''
            Get-CimInstance -ClassName Win32_VideoController | 
            Where-Object {$_.CurrentHorizontalResolution -gt 0} | 
            Select-Object CurrentHorizontalResolution, CurrentVerticalResolution | 
            ConvertTo-Json
            '''
            
            result = subprocess.run(['powershell', '-Command', native_res_command], 
                                  capture_output=True, text=True, shell=False)
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                # Handle single monitor case
                if isinstance(data, dict):
                    return data.get('CurrentHorizontalResolution', 1920), \
                           data.get('CurrentVerticalResolution', 1080)
                elif isinstance(data, list) and len(data) > 0:
                    return data[0].get('CurrentHorizontalResolution', 1920), \
                           data[0].get('CurrentVerticalResolution', 1080)
            
            logger.warning("Failed to get native resolution, using default 1920x1080")
            return 1920, 1080
        except Exception as e:
            logger.error(f"Error getting native resolution: {e}")
            return 1920, 1080

    def correct_monitor_scaling(self, monitors_data, native_width, native_height):
        """Apply scaling correction to monitor data"""
        if not monitors_data:
            return []
        
        # Calculate scaling factor from primary monitor
        primary_monitor = next((m for m in monitors_data if m.get('Primary')), monitors_data[0])
        scaling_factor = native_width / primary_monitor['Width'] if primary_monitor['Width'] > 0 else 1.0
        
        logger.info(f"🔍 Scaling detection: Native={native_width}x{native_height}, Reported={primary_monitor['Width']}x{primary_monitor['Height']}, Factor={scaling_factor:.2f}x")
        
        # Apply correction to all monitors
        corrected_monitors = []
        for monitor in monitors_data:
            corrected_monitors.append({
                'WindowsNumber': monitor['WindowsNumber'],
                'DeviceName': monitor['DeviceName'],
                'Primary': monitor['Primary'],
                'X': int(monitor['X'] * scaling_factor),
                'Y': int(monitor['Y'] * scaling_factor),
                'Width': int(monitor['Width'] * scaling_factor),
                'Height': int(monitor['Height'] * scaling_factor)
            })
        
        return corrected_monitors

    def detect_monitors(self):
        """Detect available monitors using PowerShell with Windows' actual numbering"""
        logger.info("🔍 Detecting monitors with Windows numbering...")
        try:
            # Get manufacturer info first
            manufacturer_list = self.get_monitor_manufacturers()
            logger.debug(f"Found {len(manufacturer_list)} manufacturer entries")
            
            # Enhanced PowerShell command to get Windows monitor numbers
            ps_command = r'''
            Add-Type -AssemblyName System.Windows.Forms
            $screens = [System.Windows.Forms.Screen]::AllScreens
            $result = @()
            
            # Sort screens by X position to match Windows display arrangement
            $sortedScreens = $screens | Sort-Object { $_.Bounds.X }
            
            for ($i = 0; $i -lt $sortedScreens.Length; $i++) {
                $screen = $sortedScreens[$i]
                
                # Map based on position - leftmost is Monitor 2, middle is Monitor 3, rightmost is Monitor 1
                $windowsNumber = 1
                if ($screen.Bounds.X -lt -1000) {
                    $windowsNumber = 2  # Far left (Samsung)
                } elseif ($screen.Bounds.X -lt 0) {
                    $windowsNumber = 3  # Left (Koorui) 
                } elseif ($screen.Bounds.X -eq 0) {
                    $windowsNumber = 1  # Center/Primary (Acer)
                } else {
                    $windowsNumber = $i + 1  # Fallback to sequential
                }
                
                $result += [PSCustomObject]@{
                    WindowsNumber = $windowsNumber
                    DeviceName = $screen.DeviceName
                    Primary = $screen.Primary
                    X = $screen.Bounds.X
                    Y = $screen.Bounds.Y
                    Width = $screen.Bounds.Width
                    Height = $screen.Bounds.Height
                }
            }
            
            # Sort by Windows number to maintain consistent ordering
            $result = $result | Sort-Object WindowsNumber
            $result | ConvertTo-Json
            '''
            
            result = subprocess.run([
                'powershell', '-Command', ps_command
            ], capture_output=True, text=True, shell=False)
            
            if result.returncode == 0 and result.stdout.strip():
                monitors_data = json.loads(result.stdout.strip())
                
                # Handle single monitor case
                if isinstance(monitors_data, dict):
                    monitors_data = [monitors_data]
                
                logger.info(f"Raw monitor data: {monitors_data}")
                
                # Get native resolution and apply scaling correction
                native_width, native_height = self.get_native_resolution()
                logger.info(f"🔍 Native resolution from GPU: {native_width}x{native_height}")
                
                # Apply scaling correction if needed
                if monitors_data:
                    primary_monitor = next((m for m in monitors_data if m.get('Primary')), monitors_data[0])
                    reported_width = primary_monitor['Width']
                    
                    if reported_width != native_width and reported_width > 0:
                        scaling_factor = native_width / reported_width
                        logger.info(f"🔧 Scaling detected! Factor: {scaling_factor:.2f}x (Reported: {reported_width}x{primary_monitor['Height']} → Native: {native_width}x{native_height})")
                        
                        # Apply scaling correction to all monitors
                        for monitor in monitors_data:
                            monitor['X'] = int(monitor['X'] * scaling_factor)
                            monitor['Y'] = int(monitor['Y'] * scaling_factor)
                            monitor['Width'] = int(monitor['Width'] * scaling_factor)
                            monitor['Height'] = int(monitor['Height'] * scaling_factor)
                        
                        logger.info(f"✅ Applied scaling correction: {monitors_data}")
                    else:
                        logger.info(f"✅ No scaling correction needed (Native={native_width}, Reported={reported_width})")
                
                # Format monitor info with manufacturer names using Windows numbers
                monitors = []
                for monitor_data in monitors_data:
                    windows_number = monitor_data['WindowsNumber']
                    
                    # Try to get manufacturer info (match by index for now)
                    manufacturer_info = ""
                    mfg_data = None
                    
                    # Find matching manufacturer by trying to correlate with array position
                    monitor_index = len(monitors)  # Current position in our array
                    if monitor_index < len(manufacturer_list):
                        mfg = manufacturer_list[monitor_index]
                        manufacturer_info = f" ({mfg['full_name']})"
                        mfg_data = mfg
                    
                    # Build display name using Windows monitor number
                    display_name = f"Monitor {windows_number}{manufacturer_info}"
                    if monitor_data['Primary']:
                        display_name += " - Primary"
                    display_name += f" - {monitor_data['Width']}x{monitor_data['Height']}"
                    if monitor_data['X'] != 0 or monitor_data['Y'] != 0:
                        display_name += f" at ({monitor_data['X']}, {monitor_data['Y']})"
                    
                    monitors.append({
                        'id': windows_number,  # Use Windows number as ID
                        'windows_number': windows_number,
                        'name': display_name,
                        'device_name': monitor_data['DeviceName'],
                        'primary': monitor_data['Primary'],
                        'x': monitor_data['X'],
                        'y': monitor_data['Y'],
                        'width': monitor_data['Width'],
                        'height': monitor_data['Height'],
                        'manufacturer': mfg_data
                    })
                
                logger.info(f"✅ Detected {len(monitors)} monitors with Windows numbering")
                for monitor in monitors:
                    logger.debug(f"   Monitor {monitor['id']}: {monitor['name']}")
                
                return monitors
            else:
                logger.error(f"PowerShell command failed: {result.stderr}")
                # Fallback
                return [{
                    'id': 1, 
                    'windows_number': 1,
                    'name': 'Primary Monitor (Default) - 1920x1080', 
                    'device_name': 'Primary',
                    'x': 0, 'y': 0, 'width': 1920, 'height': 1080, 'primary': True
                }]
                
        except Exception as e:
            logger.error(f"Error detecting monitors: {e}")
            return [{
                'id': 1, 
                'windows_number': 1,
                'name': 'Primary Monitor (Default) - 1920x1080', 
                'device_name': 'Primary',
                'x': 0, 'y': 0, 'width': 1920, 'height': 1080, 'primary': True
            }]
    
    def load_settings(self):
        """Load settings from config file, return empty structure if doesn't exist"""
        if not self.config_file.exists():
            # Return minimal settings structure - user needs to click "Detect Monitors"
            logger.info("🔧 No settings file found - user needs to detect monitors")
            return {
                "version": "1.0",
                "created_at": None,
                "monitors": [],  # Empty - user must detect
                "user_preferences": {
                    "default_monitor_id": None,
                    "auto_delete_days": 30,
                    "last_updated": None,
                    "monitors_detected": False  # Flag to track if user has detected monitors
                }
            }
        
        try:
            with open(self.config_file, 'r') as f:
                settings = json.load(f)
            
            # Only update monitors if explicitly requested or if file is very old (24+ hours)
            # This prevents slow monitor detection on every settings save
            last_updated = settings["user_preferences"].get("last_updated")
            should_refresh_monitors = False
            
            if last_updated:
                try:
                    from datetime import datetime
                    last_update_time = datetime.fromisoformat(last_updated)
                    hours_since_update = (datetime.now() - last_update_time).total_seconds() / 3600
                    should_refresh_monitors = hours_since_update > 24  # Only refresh after 24 hours
                except:
                    should_refresh_monitors = True
            else:
                should_refresh_monitors = True
            
                if should_refresh_monitors:
                    logger.info("🔄 Refreshing monitor configuration (24+ hours since last update)...")
                    print("🔄 Refreshing monitor configuration (24+ hours since last update)...")
                    current_monitors = self.detect_monitors()
                    if current_monitors != settings.get("monitors", []):
                        logger.info("🔄 Monitor configuration changed - updating...")
                        print("🔄 Monitor configuration changed - updating...")
                        settings["monitors"] = current_monitors
                        
                        # Validate default monitor still exists
                        default_id = settings["user_preferences"]["default_monitor_id"]
                        if not any(m['id'] == default_id for m in current_monitors):
                            # Default monitor no longer exists, reset to primary
                            primary_monitor = next((m for m in current_monitors if m.get('primary')), current_monitors[0])
                            settings["user_preferences"]["default_monitor_id"] = primary_monitor['id']
                            logger.warning(f"⚠️ Default monitor reset to: {primary_monitor['name']} (Windows #{primary_monitor['id']})")
                            print(f"⚠️ Default monitor reset to: {primary_monitor['name']} (Windows #{primary_monitor['id']})")
                        
                        self.save_settings(settings)
            
            return settings
            
        except Exception as e:
            print(f"⚠️ Error loading settings: {e}")
            # Fallback to default settings
            return self.load_settings()  # This will create new settings
    
    def save_settings(self, settings):
        """Save settings to config file"""
        try:
            settings["user_preferences"]["last_updated"] = datetime.now().isoformat()
            
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
            return False
    
    def get_default_monitor(self):
        """Get the default monitor configuration"""
        settings = self.load_settings()
        default_id = settings["user_preferences"]["default_monitor_id"]
        
        # Find the monitor with matching ID
        for monitor in settings["monitors"]:
            if monitor['id'] == default_id:
                return monitor
        
        # Fallback to first monitor if default not found
        if settings["monitors"]:
            return settings["monitors"][0]
        
        return None
    
    def set_default_monitor(self, monitor_id):
        """Set the default monitor by ID"""
        logger.info(f"🔧 Setting default monitor to ID: {monitor_id}")
        
        settings = self.load_settings()
        
        # Log current state
        current_default_id = settings["user_preferences"]["default_monitor_id"]
        logger.info(f"📺 Current default monitor ID: {current_default_id}")
        
        # Validate monitor ID exists
        valid_monitor_ids = [m['id'] for m in settings["monitors"]]
        logger.debug(f"📺 Valid monitor IDs: {valid_monitor_ids}")
        
        if any(m['id'] == monitor_id for m in settings["monitors"]):
            settings["user_preferences"]["default_monitor_id"] = monitor_id
            
            # Get monitor details for logging
            selected_monitor = next(m for m in settings["monitors"] if m['id'] == monitor_id)
            logger.info(f"📺 Selected monitor details:")
            logger.info(f"   ID: {selected_monitor['id']}")
            logger.info(f"   Name: {selected_monitor['name']}")
            logger.info(f"   Position: ({selected_monitor['x']}, {selected_monitor['y']})")
            logger.info(f"   Size: {selected_monitor['width']}x{selected_monitor['height']}")
            
            success = self.save_settings(settings)
            
            if success:
                logger.info(f"✅ Default monitor updated to: {selected_monitor['name']}")
                print(f"✅ Default monitor updated to: {selected_monitor['name']}")
                return True
            else:
                logger.error("❌ Failed to save settings")
                print("❌ Failed to save settings")
                return False
        else:
            logger.error(f"❌ Invalid monitor ID: {monitor_id}")
            logger.error(f"   Available IDs: {valid_monitor_ids}")
            print(f"❌ Invalid monitor ID: {monitor_id}")
            return False
    
    def get_all_monitors(self):
        """Get list of all available monitors"""
        settings = self.load_settings()
        return settings["monitors"]
    
    def detect_and_save_monitors(self):
        """Detect monitors and save to settings (for manual detection button)"""
        logger.info("🔄 Manual monitor detection triggered...")
        
        # Detect current monitors
        detected_monitors = self.detect_monitors()
        
        # Load existing settings or create new
        settings = self.load_settings()
        
        # Update monitors in settings
        settings["monitors"] = detected_monitors
        settings["user_preferences"]["monitors_detected"] = True
        settings["created_at"] = datetime.now().isoformat()
        
        # If no default monitor set, use primary
        if not settings["user_preferences"]["default_monitor_id"]:
            primary_monitor = next((m for m in detected_monitors if m.get('primary')), detected_monitors[0])
            settings["user_preferences"]["default_monitor_id"] = primary_monitor['id']
            logger.info(f"📍 Set default to primary monitor: {primary_monitor['name']} (Windows #{primary_monitor['id']})")
        
        # Save settings
        success = self.save_settings(settings)
        
        if success:
            logger.info(f"✅ Monitor detection completed - {len(detected_monitors)} monitors saved")
            return {
                'success': True,
                'monitors': detected_monitors,
                'message': f'Detected {len(detected_monitors)} monitors successfully'
            }
        else:
            logger.error("❌ Failed to save monitor settings")
            return {
                'success': False,
                'monitors': [],
                'message': 'Failed to save monitor configuration'
            }

    def update_monitor_arrangement(self, monitor_order, primary_monitor_id=None):
        """Update the physical arrangement order of monitors and recalculate positions"""
        logger.info(f"🔄 Updating monitor arrangement: {monitor_order}")
        logger.info(f"🔝 Primary monitor ID: {primary_monitor_id}")
        
        settings = self.load_settings()
        
        if not settings["monitors"]:
            return {
                'success': False,
                'message': 'No monitors detected. Please detect monitors first.'
            }
        
        # Reorder monitors based on user arrangement
        original_monitors = settings["monitors"].copy()
        reordered_monitors = []
        
        for monitor_id in monitor_order:
            # Find monitor with this ID
            monitor = next((m for m in original_monitors if m['id'] == monitor_id), None)
            if monitor:
                reordered_monitors.append(monitor)
        
        # Calculate new positions based on primary monitor selection
        if primary_monitor_id:
            # Find the primary monitor
            primary_monitor = next((m for m in reordered_monitors if m['id'] == primary_monitor_id), None)
            
            if primary_monitor:
                logger.info(f"🔝 Setting {primary_monitor['name']} as primary monitor")
                
                # Update primary flags
                for monitor in reordered_monitors:
                    monitor['primary'] = (monitor['id'] == primary_monitor_id)
                
                # Calculate relative positions (primary is always 0,0)
                primary_index = next(i for i, m in enumerate(reordered_monitors) if m['id'] == primary_monitor_id)
                
                for i, monitor in enumerate(reordered_monitors):
                    if monitor['id'] == primary_monitor_id:
                        # Primary monitor is always at (0,0)
                        monitor['x'] = 0
                        monitor['y'] = 0
                        logger.info(f"📍 Primary monitor {monitor['name']}: (0, 0)")
                        
                        # Update primary monitor name
                        name_parts = monitor['name'].split(' - ')
                        base_name = name_parts[0]  # Monitor X (Brand Model)
                        specs = f"{monitor['width']}x{monitor['height']} - Primary"
                        monitor['name'] = f"{base_name} - {specs}"
                    else:
                        # Calculate relative position based on array position
                        # Each position is 1920 pixels apart horizontally
                        relative_position = i - primary_index
                        monitor['x'] = relative_position * 1920
                        monitor['y'] = 0
                        logger.info(f"📍 Monitor {monitor['name']}: ({monitor['x']}, {monitor['y']})")
                        
                        # Update the display name to reflect new position
                        name_parts = monitor['name'].split(' - ')
                        base_name = name_parts[0]  # Monitor X (Brand Model)
                        specs = f"{monitor['width']}x{monitor['height']}"
                        if monitor['primary']:
                            specs += " - Primary"
                        position_str = f"at ({monitor['x']}, {monitor['y']})" if monitor['x'] != 0 or monitor['y'] != 0 else ""
                        
                        # Rebuild name
                        monitor['name'] = f"{base_name} - {specs}"
                        if position_str:
                            monitor['name'] += f" {position_str}"
        
        # Update settings
        settings["monitors"] = reordered_monitors
        settings["user_preferences"]["last_updated"] = datetime.now().isoformat()
        
        success = self.save_settings(settings)
        
        if success:
            logger.info(f"✅ Monitor arrangement updated successfully")
            return {
                'success': True,
                'message': 'Monitor arrangement saved successfully'
            }
        else:
            logger.error("❌ Failed to save monitor arrangement")
            return {
                'success': False,
                'message': 'Failed to save monitor arrangement'
            }

    def refresh_monitors(self):
        """Force refresh monitor detection and update settings (legacy method)"""
        logger.info("🔄 Force refreshing monitor configuration...")
        return self.detect_and_save_monitors()
    
    def get_auto_delete_days(self):
        """Get auto delete days setting"""
        settings = self.load_settings()
        return settings["user_preferences"].get("auto_delete_days", 30)
    
    def set_auto_delete_days(self, days):
        """Set auto delete days"""
        settings = self.load_settings()
        settings["user_preferences"]["auto_delete_days"] = days
        return self.save_settings(settings)

# Global instance
settings_manager = SettingsManager()