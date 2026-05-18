# 🌟 PRISM - Persistent, Responsive, Interactive Session Manager

A powerful, production-ready terminal interface for **Gemini CLI** with remote session sharing, automatic persistence, and enterprise-grade security.

```
╔═══════════════════════════════════════════════════════════════════╗
║  PRISM: Turning AI Interactions Into Beautiful, Persistent Works ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## ✨ What's New in v2

### 1. **Context Window Management** 🧠
- **Automatic Turn Truncation**: Keeps conversation within token limits
- **Smart Context Building**: Includes as many recent turns as fit in the budget
- **Token Estimation**: Rough token counting to prevent API limits
- **Status Reporting**: Shows how many turns are included vs. total

```
[Context truncated: showing 8/15 turns]
```

### 2. **Session Recovery** 💾
- **Auto-Save to JSON**: Every conversation is persisted automatically
- **Session Loading**: Resume conversations with `--session SESSION_ID`
- **Session Management**: List all sessions with `prism sessions`
- **Metadata Tracking**: Timestamps, token usage per turn

```bash
# Resume a saved session
prism tui --session 20260518_181234

# List all sessions
prism sessions
```

### 3. **Full-Text Search** 🔍
- **Fast Grep-Style Search**: Search across all turns instantly
- **Context Preview**: See surrounding lines for each match
- **Search Results Display**: Organized view of all matches
- **Easy Access**: Press `Ctrl-/` to search

```
# Search Results for 'authentication' (5 matches)

## Match 1 (Turn 3)
Context:
  ... JWT tokens are used for client ...
  Authentication requires a valid token
  The server verifies each request ...
```

### 4. **Production-Grade Security** 🔐

#### JWT Authentication (if PyJWT installed)
```bash
pip install PyJWT

# Start server with JWT tokens
prism server --host 0.0.0.0 --port 8765 --token "your-secret-key"

# Clients automatically get JWT tokens
prism client YOUR_IP --port 8765 --token "your-secret-key"
```

#### TLS Encryption
```bash
# Generate self-signed certificate (dev only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Start secure server
prism server --host 0.0.0.0 --port 8765 \
  --token "secret" \
  --cert cert.pem \
  --key key.pem

# Connect with TLS
prism client YOUR_IP --port 8765 --token "secret" --tls
```

### 5. **Structured Logging** 📊
- **Rotating Logs**: Automatic log rotation (10MB per file, 5 backups)
- **Debug Information**: Detailed logging for troubleshooting
- **Session Tracking**: Know exactly what's happening
- **Location**: `~/.prism/prism.log`

```
2026-05-18 19:15:23,456 [INFO] PRISM: TUI app created for session: 20260518_191523
2026-05-18 19:15:25,123 [DEBUG] PRISM: Context built with 5/10 turns, ~8523 tokens
2026-05-18 19:15:26,789 [INFO] PRISM: Response saved: /path/to/response.md
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone or copy prism_v2.py to your project
pip install prompt-toolkit wcwidth

# Optional: For JWT token support
pip install PyJWT

# Optional: For TLS support (built-in to Python)
```

### Basic Usage

```bash
# Open the TUI
python prism_v2.py tui

# Or with a specific session
python prism_v2.py tui --session 20260518_181234

# List all sessions
python prism_v2.py sessions

# Start a server for your Mac Mini
python prism_v2.py server --host 0.0.0.0 --port 8765

# Connect from another device
python prism_v2.py client 192.168.1.100 --port 8765
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl-S` or `F5` | Submit prompt to Gemini |
| `Ctrl-/` | **Search conversations** |
| `Ctrl-F` | Focus transcript (scroll mode) |
| `Ctrl-P` | Focus prompt (edit mode) |
| `Ctrl-N` | Clear current prompt |
| `Ctrl-L` | Clear chat transcript |
| `Ctrl-R` | Full reset (prompt + transcript) |
| `PgUp/PgDn` | Scroll transcript |
| `Home/End` | Jump to top/bottom |
| `Ctrl-C` | Exit PRISM |

---

## 📁 Project Structure

```
~/.prism/
├── prism.log           # Structured logging (rotates at 10MB)
├── config.json         # Future: User preferences
└── sessions/
    ├── 20260518_181234.json  # Session data (turns, metadata)
    ├── 20260518_191523.json
    └── ...
```

```
./
├── prism_v2.py         # Main PRISM executable
├── gemini_response_*.md # Individual turn exports (auto-saved)
└── ...
```

---

## 🔧 Advanced Configuration

### Create a Config File

Edit `~/.prism/config.json`:

```json
{
  "max_context_turns": 5,
  "max_tokens": 100000,
  "default_host": "0.0.0.0",
  "default_port": 8765,
  "theme": "dark",
  "auto_save_interval": 30
}
```

### Environment Variables

```bash
# Set default port
export PRISM_PORT=9000

# Enable debug logging
export PRISM_DEBUG=1

# Set home directory
export PRISM_HOME=/custom/path/.prism
```

---

## 💡 Use Cases

### 1. **Personal AI Journal**
- Auto-save every conversation
- Search past insights
- Resume where you left off

```bash
prism tui
# Type queries, they auto-save
prism sessions  # See all your conversations
prism tui --session <id>  # Resume any conversation
```

### 2. **Team Collaboration**
- Run server on powerful Mac Mini
- Multiple team members connect from their machines
- All interactions logged and searchable

```bash
# On Mac Mini
prism server --host 0.0.0.0 --port 8765 \
  --token "team-secret" \
  --cert cert.pem --key key.pem

# On team laptops
prism client 192.168.1.50 --token "team-secret" --tls
```

### 3. **Research & Analysis**
- Search your entire Gemini conversation history
- Context window auto-manages token usage
- Export conversations as markdown

```bash
prism tui
# Search: Ctrl-/ → "machine learning trends"
# Results show all relevant exchanges
```

---

## 🏗️ Architecture Highlights

### Async/Non-Blocking
- TUI remains responsive while Gemini is thinking
- Server handles multiple concurrent clients
- Smooth scrolling and UI updates

### Cross-Platform
- **Linux/macOS**: Full PTY support for true terminal emulation
- **Windows**: Graceful pipe fallback (no native PTY)

### Security
- ✅ JWT tokens (with PyJWT)
- ✅ TLS/SSL encryption
- ✅ Token verification on each connection
- ✅ Structured audit logging

### Smart Context Management
```
Total tokens available: 100,000
Reserved for safety: 5,000
Available for context: 95,000

Turn 10: 5,234 tokens (include)
Turn 9:  6,123 tokens (include)
Turn 8:  4,891 tokens (include)
...
Turn 3:  7,234 tokens (SKIP - would exceed 95k)
```

---

## 📊 What Gets Logged

```
Session Start:
  - TUI app creation with session ID
  - Gemini executable path
  - Auth token configuration

During Operation:
  - Context truncation info (turns included/total)
  - Prompt submissions and responses
  - File saves and session updates
  - Search operations and results

Errors:
  - Gemini executable not found
  - File I/O issues
  - Auth failures
  - Network connection issues
```

---

## 🐛 Troubleshooting

### Logs Not Appearing?
```bash
# Check log file
tail -f ~/.prism/prism.log

# Enable debug output
export PRISM_DEBUG=1
python prism_v2.py tui
```

### Server Connection Issues?
```bash
# Check if server is running
netstat -an | grep 8765

# Verify firewall allows port 8765
# On Mac: System Preferences → Security & Privacy → Firewall

# Check server logs
tail -f ~/.prism/prism.log | grep -i server
```

### Session Not Loading?
```bash
# List available sessions
python prism_v2.py sessions

# Check session file
cat ~/.prism/sessions/20260518_181234.json | python -m json.tool
```

---

## 🎯 Roadmap

### Completed (v2)
- ✅ Context window management
- ✅ Session recovery (JSON-based)
- ✅ Full-text search
- ✅ JWT authentication
- ✅ TLS support
- ✅ Structured logging

### Planned (v3+)
- [ ] Web UI for session browsing
- [ ] Conversation branching ("what-if" scenarios)
- [ ] Markdown/PDF export
- [ ] Team collaboration features
- [ ] Plugin system
- [ ] Multi-provider support (Claude, ChatGPT, etc.)

---

## 📝 Development Notes

### Code Quality
- **Type Hints**: Full type annotations throughout
- **Error Handling**: Comprehensive try/except blocks
- **Logging**: Structured logging for debugging
- **Documentation**: Inline comments for complex logic

### Testing
```bash
# Future: Unit tests for markdown rendering
pytest tests/test_markdown.py

# Integration tests for context management
pytest tests/test_context.py
```

---

## 📄 License & Credits

Built with ❤️ for powerful, persistent AI interactions.

**Dependencies:**
- `prompt-toolkit` - Rich terminal UI
- `PyJWT` - JWT authentication (optional)
- Python 3.10+

---

## 🌟 PRISM Philosophy

> **"Turn every AI interaction into a persistent, searchable, shareable work of art."**

PRISM is designed for:
- 🎯 **Precision**: Surgical edits and exact responses
- 🔄 **Persistence**: Nothing is lost
- 🔍 **Discoverability**: Search your entire history
- 🛡️ **Security**: Production-grade encryption
- 🚀 **Performance**: Non-blocking, async-first

---

## 💬 Questions?

Check the logs:
```bash
tail -f ~/.prism/prism.log
```

All operations are logged with timestamps and context.

---

**Happy Prisming! 🌟✨**
