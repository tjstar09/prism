#!/bin/bash
#
# PRISM v2 Quick Start Script
# Sets up and runs PRISM with all features enabled
#

set -e

echo "🌟 PRISM v2 - Quick Start Setup"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PRISM_HOME="${HOME}/.prism"
SESSION_DIR="${PRISM_HOME}/sessions"
LOG_FILE="${PRISM_HOME}/prism.log"

# Create necessary directories
echo -e "${BLUE}1. Setting up PRISM home directory...${NC}"
mkdir -p "$PRISM_HOME"
mkdir -p "$SESSION_DIR"
echo -e "${GREEN}   ✓ Created ${PRISM_HOME}${NC}"
echo -e "${GREEN}   ✓ Created ${SESSION_DIR}${NC}"
echo ""

# Check Python version
echo -e "${BLUE}2. Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"
if [[ $(echo -e "$python_version\n$required_version" | sort -V | head -n1) == "$required_version" ]]; then
    echo -e "${GREEN}   ✓ Python $python_version (required: 3.10+)${NC}"
else
    echo -e "${RED}   ✗ Python $python_version found, but 3.10+ required${NC}"
    exit 1
fi
echo ""

# Install dependencies
echo -e "${BLUE}3. Installing Python dependencies...${NC}"
pip_packages=("prompt-toolkit" "wcwidth")
for package in "${pip_packages[@]}"; do
    if python3 -c "import $(echo $package | sed 's/-/_/g')" 2>/dev/null; then
        echo -e "${GREEN}   ✓ ${package} already installed${NC}"
    else
        echo -e "${YELLOW}   → Installing ${package}...${NC}"
        pip3 install "$package" -q
        echo -e "${GREEN}   ✓ ${package} installed${NC}"
    fi
done
echo ""

# Optional: Install PyJWT for JWT support
echo -e "${BLUE}4. Optional: JWT Authentication Support${NC}"
if python3 -c "import jwt" 2>/dev/null; then
    echo -e "${GREEN}   ✓ PyJWT already installed (JWT enabled)${NC}"
else
    read -p "   Install PyJWT for JWT token support? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip3 install PyJWT -q
        echo -e "${GREEN}   ✓ PyJWT installed${NC}"
    else
        echo -e "${YELLOW}   ⚠ Skipping PyJWT (will use basic token auth)${NC}"
    fi
fi
echo ""

# Check for Gemini CLI
echo -e "${BLUE}5. Checking for Gemini CLI...${NC}"
if command -v gemini &> /dev/null; then
    gemini_path=$(which gemini)
    echo -e "${GREEN}   ✓ Gemini CLI found at: ${gemini_path}${NC}"
else
    echo -e "${YELLOW}   ⚠ Gemini CLI not found in PATH${NC}"
    echo -e "   Make sure 'gemini' is installed and available in your PATH"
fi
echo ""

# Show session directory
echo -e "${BLUE}6. Session Directory:${NC}"
echo -e "   ${GREEN}${SESSION_DIR}${NC}"
ls -la "$SESSION_DIR" 2>/dev/null | tail -5 || echo "   (empty - new sessions will be created here)"
echo ""

# Show log file
echo -e "${BLUE}7. Log File:${NC}"
echo -e "   ${GREEN}${LOG_FILE}${NC}"
if [ -f "$LOG_FILE" ]; then
    lines=$(wc -l < "$LOG_FILE")
    echo -e "   (${lines} lines)"
fi
echo ""

# Create alias for easy access
echo -e "${BLUE}8. Creating shell alias...${NC}"
ALIAS_NAME="prism"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/prism_v2.py"

if grep -q "alias $ALIAS_NAME=" ~/.bashrc 2>/dev/null; then
    echo -e "${YELLOW}   ⚠ Alias already exists in ~/.bashrc${NC}"
else
    echo "alias $ALIAS_NAME='python3 $SCRIPT_PATH'" >> ~/.bashrc
    echo -e "${GREEN}   ✓ Added alias: ${ALIAS_NAME}${NC}"
fi
echo ""

# Display quick commands
echo -e "${BLUE}9. Quick Commands:${NC}"
echo ""
echo -e "   ${GREEN}TUI Mode:${NC}"
echo -e "   • python3 prism_v2.py tui"
echo -e "   • prism tui  (if alias set up)"
echo ""
echo -e "   ${GREEN}Session Management:${NC}"
echo -e "   • prism sessions                           # List all sessions"
echo -e "   • prism tui --session 20260518_191523      # Resume session"
echo ""
echo -e "   ${GREEN}Server Mode (for Mac Mini):${NC}"
echo -e "   • prism server --host 0.0.0.0 --port 8765 --token 'secret'"
echo ""
echo -e "   ${GREEN}Client Mode (from other devices):${NC}"
echo -e "   • prism client 192.168.1.50 --port 8765 --token 'secret'"
echo ""
echo -e "   ${GREEN}With TLS Encryption:${NC}"
echo -e "   • prism server --host 0.0.0.0 --port 8765 --token 'secret' \\"
echo -e "       --cert cert.pem --key key.pem"
echo -e "   • prism client 192.168.1.50 --port 8765 --token 'secret' --tls"
echo ""

# Keyboard shortcuts
echo -e "${BLUE}10. Keyboard Shortcuts:${NC}"
echo ""
echo -e "   ${GREEN}Ctrl-S or F5${NC}     Submit prompt"
echo -e "   ${GREEN}Ctrl-/${NC}          Search conversations"
echo -e "   ${GREEN}Ctrl-F${NC}          Focus transcript"
echo -e "   ${GREEN}Ctrl-P${NC}          Focus prompt"
echo -e "   ${GREEN}Ctrl-N${NC}          Clear prompt"
echo -e "   ${GREEN}Ctrl-L${NC}          Clear chat"
echo -e "   ${GREEN}Ctrl-R${NC}          Full reset"
echo -e "   ${GREEN}PgUp/PgDn${NC}       Scroll"
echo -e "   ${GREEN}Ctrl-C${NC}          Exit"
echo ""

# Final instructions
echo -e "${GREEN}=================================="
echo "✓ PRISM v2 is ready to use!"
echo "==================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Load the alias:"
echo "   source ~/.bashrc"
echo ""
echo "2. Start PRISM:"
echo "   prism tui"
echo ""
echo "3. Or start a server (for LAN sharing):"
echo "   prism server --host 0.0.0.0 --port 8765 --token 'your-secret-key'"
echo ""
echo "4. Clients can connect from other devices:"
echo "   prism client YOUR_IP_ADDRESS --token 'your-secret-key'"
echo ""
echo -e "${YELLOW}For documentation, see:${NC}"
echo "   • PRISM_README.md - User guide and examples"
echo "   • PRISM_FEATURES.md - Detailed feature documentation"
echo ""
echo "Happy Prisming! 🌟✨"
echo ""
