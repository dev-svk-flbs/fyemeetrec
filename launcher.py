#!/usr/bin/env python3
"""
Master Launcher for Audio Recording System
Launches and manages all services:
- Flask Web App (app.py)
- Hotkey Listener (hotkey_listener.py)
- WebSocket Client (websocket_client.py)
- Bluetooth Monitor (bluetooth_endpoint_monitor.py)
"""

import os
import sys
import time
import subprocess
import signal
import threading
import queue
from pathlib import Path
from datetime import datetime
from logging_config import setup_logging

# Setup logging
logger = setup_logging("launcher")

class ServiceManager:
    """Manages multiple services as subprocesses"""
    
    def __init__(self):
        self.services = {}
        self.running = False
        self.script_dir = Path(__file__).parent.absolute()
        self.python_exe = sys.executable
        
    def start_service(self, name, script_path, color_code="37"):
        """
        Start a service as a subprocess
        
        Args:
            name: Service name (for logging)
            script_path: Path to Python script
            color_code: ANSI color code for console output
        """
        try:
            logger.info(f" Starting {name}...")
            
            # Start process with output redirection
            process = subprocess.Popen(
                [self.python_exe, str(script_path)],
                cwd=str(self.script_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Create output reader thread
            output_queue = queue.Queue()
            output_thread = threading.Thread(
                target=self._read_output,
                args=(process, name, color_code, output_queue),
                daemon=True
            )
            output_thread.start()
            
            self.services[name] = {
                'process': process,
                'script': script_path,
                'thread': output_thread,
                'queue': output_queue,
                'color': color_code,
                'start_time': time.time()
            }
            
            logger.info(f" {name} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f" Failed to start {name}: {e}")
            return False
    
    def _read_output(self, process, name, color_code, output_queue):
        """Read output from process and display with prefix"""
        ansi_reset = "\033[0m"
        ansi_color = f"\033[{color_code}m"
        
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    # Remove trailing newline
                    line = line.rstrip('\n\r')
                    
                    # Add to queue for potential log aggregation
                    output_queue.put(line)
                    
                    # Print with colored prefix
                    prefix = f"{ansi_color}[{name:12}]{ansi_reset}"
                    print(f"{prefix} {line}", flush=True)
        except Exception as e:
            logger.error(f"Error reading output from {name}: {e}")
        finally:
            process.stdout.close()
    
    def stop_service(self, name):
        """Stop a specific service"""
        if name not in self.services:
            logger.warning(f" Service {name} not running")
            return False
        
        try:
            service = self.services[name]
            process = service['process']
            
            logger.info(f" Stopping {name}...")
            
            # Try graceful shutdown first
            if process.poll() is None:  # Still running
                if os.name == 'nt':  # Windows
                    process.send_signal(signal.CTRL_C_EVENT)
                else:  # Linux/Mac
                    process.send_signal(signal.SIGINT)
                
                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                    logger.info(f" {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    logger.warning(f" {name} did not stop gracefully, forcing...")
                    process.kill()
                    process.wait()
                    logger.info(f" {name} force stopped")
            else:
                logger.info(f" {name} already stopped")
            
            del self.services[name]
            return True
            
        except Exception as e:
            logger.error(f" Error stopping {name}: {e}")
            return False
    
    def stop_all(self):
        """Stop all running services"""
        logger.info(" Stopping all services...")
        
        # Stop in reverse order
        service_names = list(self.services.keys())
        for name in reversed(service_names):
            self.stop_service(name)
        
        logger.info(" All services stopped")
    
    def check_services(self):
        """Check status of all services"""
        for name, service in list(self.services.items()):
            process = service['process']
            if process.poll() is not None:  # Process has terminated
                exit_code = process.returncode
                uptime = int(time.time() - service['start_time'])
                
                logger.warning(f" {name} terminated unexpectedly!")
                logger.warning(f"   Exit code: {exit_code}")
                logger.warning(f"   Uptime: {uptime}s")
                
                # Remove from services dict
                del self.services[name]
    
    def get_status(self):
        """Get status of all services"""
        status = {}
        for name, service in self.services.items():
            process = service['process']
            uptime = int(time.time() - service['start_time'])
            status[name] = {
                'running': process.poll() is None,
                'pid': process.pid,
                'uptime': uptime
            }
        return status
    
    def run(self):
        """Main run loop"""
        self.running = True
        
        logger.info("=" * 70)
        logger.info(" AUDIO RECORDING SYSTEM - MASTER LAUNCHER")
        logger.info("=" * 70)
        logger.info(f" Working directory: {self.script_dir}")
        logger.info(f" Python: {self.python_exe}")
        logger.info("=" * 70)
        
        # Start all services
        services_to_start = [
            ("FLASK-APP", self.script_dir / "app.py", "92"),  # Bright green
            ("HOTKEY", self.script_dir / "hotkey_listener.py", "93"),  # Bright yellow
            ("WEBSOCKET", self.script_dir / "websocket_client.py", "96"),  # Bright cyan
            ("BLUETOOTH", self.script_dir / "bluetooth_endpoint_monitor.py", "95"),  # Bright magenta
        ]
        
        for name, script, color in services_to_start:
            if script.exists():
                self.start_service(name, script, color)
                time.sleep(0.5)  # Stagger startup
            else:
                logger.warning(f" Script not found: {script}")
        
        logger.info("=" * 70)
        logger.info(" All services started!")
        logger.info(" Press Ctrl+C to stop all services")
        logger.info("=" * 70)
        logger.info("")
        
        # Monitor services
        try:
            while self.running:
                self.check_services()
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            logger.info("\n Shutdown signal received...")
        except Exception as e:
            logger.error(f" Error in main loop: {e}", exc_info=True)
        finally:
            self.stop_all()
            logger.info(" Launcher stopped")

def main():
    """Main entry point"""
    manager = ServiceManager()
    
    try:
        manager.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
