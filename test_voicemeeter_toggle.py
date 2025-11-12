"""
Hello World - Toggle VoiceMeeter Virtual Input A1 every 15 seconds
"""
import voicemeeterlib
import time

def main():
    print("VoiceMeeter A1 Toggle Test")
    print("Toggling Virtual Input 1 A1 every 15 seconds")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    with voicemeeterlib.api('banana') as vmr:
        virtual_input_1 = vmr.strip[3]  # VoiceMeeter Input (first virtual input)
        
        toggle_state = False
        
        while True:
            try:
                # Toggle A1
                toggle_state = not toggle_state
                virtual_input_1.A1 = toggle_state
                
                # Wait a bit for the change to apply
                time.sleep(0.2)
                actual_state = virtual_input_1.A1
                
                timestamp = time.strftime("%H:%M:%S")
                print(f"{timestamp} - Set A1 to: {toggle_state}, Actual A1: {actual_state}")
                
                # Wait 15 seconds
                time.sleep(15)
                
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    main()
