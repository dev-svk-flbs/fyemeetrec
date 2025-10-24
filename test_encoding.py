#!/usr/bin/env python3
"""
Test script for hotkey listener encoding issues
"""

import sys
import os

def test_encoding():
    """Test console encoding capabilities"""
    print("Testing console encoding...")
    
    # Test basic ASCII
    try:
        print("ASCII test: Hello World")
        print("✓ ASCII works")
    except Exception as e:
        print(f"✗ ASCII failed: {e}")
    
    # Test UTF-8 emojis
    emojis_to_test = ["🎹", "🎬", "⏹️", "✅", "❌", "⚠️"]
    
    for emoji in emojis_to_test:
        try:
            print(f"{emoji} Emoji test")
            print(f"✓ {emoji} works")
        except UnicodeEncodeError as e:
            print(f"✗ {emoji} failed: {e}")
            print(f"  Fallback: [EMOJI] works")
        except Exception as e:
            print(f"✗ {emoji} unexpected error: {e}")
    
    # Test the safe_print function
    print("\nTesting safe_print function:")
    
    # Import the safe_print function
    sys.path.append(os.path.dirname(__file__))
    try:
        from hotkey_listener import safe_print
        safe_print("Safe print test with emoji", "🎹")
        safe_print("Safe print test with ASCII", "[INFO]")
        print("✓ safe_print function works")
    except Exception as e:
        print(f"✗ safe_print failed: {e}")

if __name__ == "__main__":
    test_encoding()