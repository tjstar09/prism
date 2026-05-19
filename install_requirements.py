#!/usr/bin/env python3
"""
PRISM Installation Helper
Installs all required dependencies for PRISM v2
"""

import subprocess
import sys

def install_packages():
    """Install required packages using pip"""
    packages = [
        "prompt-toolkit",
        "wcwidth",
    ]
    
    print("=" * 60)
    print("PRISM v2 - Dependency Installation")
    print("=" * 60)
    print()
    
    for package in packages:
        print(f"Installing {package}...", end=" ", flush=True)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓ Done")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed")
            print(f"Error: {e}")
            return False
    
    print()
    print("=" * 60)
    print("Verifying installation...")
    print("=" * 60)
    
    try:
        result = subprocess.check_output(
            [sys.executable, "-m", "pip", "list"],
            text=True
        )
        
        for package in packages:
            if package.lower() in result.lower():
                # Extract version
                for line in result.split('\n'):
                    if package.lower() in line.lower():
                        print(f"✓ {line.strip()}")
                        break
        
        print()
        print("=" * 60)
        print("Installation successful!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Run: python prism_v2.py tui")
        print("2. Or: python prism_v2.py server")
        print()
        return True
    except Exception as e:
        print(f"Error verifying installation: {e}")
        return False

if __name__ == "__main__":
    success = install_packages()
    sys.exit(0 if success else 1)
