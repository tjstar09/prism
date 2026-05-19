#!/usr/bin/env python3
"""
PRISM v2 - Git Commit and Push
Commits new setup files to GitHub
"""

import subprocess
import sys
import os

def run_command(cmd, description=""):
    """Run a command and handle output"""
    if description:
        print(f"\n{description}")
        print("-" * 60)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=r"C:\Users\Laptop\Documents\VSCode Workspace\PRISM",
            shell=True,
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("=" * 60)
    print("PRISM v2 - Git Commit & Push")
    print("=" * 60)
    
    os.chdir(r"C:\Users\Laptop\Documents\VSCode Workspace\PRISM")
    
    # Check git status
    print("\n📋 Checking git status...")
    run_command("git status", "")
    
    # Add files
    print("\n📝 Adding new files...")
    if not run_command("git add install_requirements.py requirements.txt SETUP.md prism_v2.py", ""):
        print("❌ Failed to add files")
        return False
    print("✓ Files added")
    
    # Commit
    print("\n💾 Committing changes...")
    commit_msg = """Add: Installation scripts and setup documentation

- install_requirements.py: Automatic dependency installer
- requirements.txt: Package dependencies list
- SETUP.md: Complete setup guide with troubleshooting
- prism_v2.py: Fixed Lexer import fallback

These files make it easy for users to install PRISM and get started."""
    
    cmd = f'git commit -m "{commit_msg}"'
    if not run_command(cmd, ""):
        print("❌ Failed to commit")
        return False
    print("✓ Committed")
    
    # Push
    print("\n🚀 Pushing to GitHub...")
    if not run_command("git push origin main", ""):
        print("❌ Failed to push")
        return False
    print("✓ Pushed to GitHub")
    
    print("\n" + "=" * 60)
    print("✅ Success! Check your GitHub repository")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
