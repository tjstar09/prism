# 🚀 PRISM v2 - Quick Setup Guide

## 📦 Installation Steps

### **Step 1: Install Dependencies** (Choose ONE option)

#### Option A: Automatic Installation (Easiest)
```bash
python install_requirements.py
```
This script will install all required packages automatically.

#### Option B: Using requirements.txt
```bash
pip install -r requirements.txt
```

#### Option C: Manual Installation
```bash
pip install prompt-toolkit wcwidth PyJWT
```

---

## ✅ Verify Installation

Check if dependencies are installed:
```bash
python -m pip list | findstr "prompt-toolkit wcwidth"
```

Should show:
```
prompt-toolkit    3.x.x
wcwidth           0.x.x
```

---

## 🎯 Run PRISM v2

After installation, try one of these:

### **Terminal UI Mode** (Interactive)
```bash
python prism_v2.py tui
```

### **Server Mode** (For network sharing)
```bash
python prism_v2.py server --host 0.0.0.0 --port 8765 --token secret123
```

### **Client Mode** (Connect to server)
```bash
python prism_v2.py client 192.168.1.100 --port 8765 --token secret123
```

### **Help**
```bash
python prism_v2.py --help
python prism_v2.py tui --help
python prism_v2.py server --help
```

---

## 📋 Keyboard Shortcuts (TUI Mode)

| Key | Action |
|-----|--------|
| `Ctrl+/` | Open search |
| `Ctrl+S` | Save session |
| `Ctrl+L` | Clear screen |
| `Ctrl+C` | Exit |
| `Tab` | Autocomplete |
| `Enter` | Send message |

---

## ⚙️ Configuration

Session files are stored in:
- Windows: `C:\Users\<YourName>\.prism\sessions\`
- macOS/Linux: `~/.prism/sessions/`

Log files:
- Windows: `C:\Users\<YourName>\.prism\prism.log`
- macOS/Linux: `~/.prism/prism.log`

---

## 🆘 Troubleshooting

### **"prompt_toolkit is required"**
Run: `pip install prompt-toolkit`

### **"wcwidth not found"**
Run: `pip install wcwidth`

### **"ModuleNotFoundError"**
Run: `pip install -r requirements.txt`

### **Port already in use**
Use a different port:
```bash
python prism_v2.py server --port 9999
```

### **Permission denied**
On Linux/macOS:
```bash
chmod +x prism_v2.py
./prism_v2.py tui
```

---

## 📚 Documentation

- **00_START_HERE.md** - Quick start guide
- **PRISM_README.md** - Full user guide
- **PRISM_FEATURES.md** - Technical documentation
- **PRISM_v2_SUMMARY.md** - Architecture details

---

## ✨ That's it!

You're ready to use PRISM v2! 🎉

**Next:** Run `python install_requirements.py` or `pip install -r requirements.txt`
