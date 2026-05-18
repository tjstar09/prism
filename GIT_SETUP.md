# Git Repository Setup for PRISM v2

This guide helps you set up a Git repository for the PRISM project.

## Quick Setup

### Windows
```bash
./setup_git.bat
```

### macOS/Linux
```bash
bash setup_git.sh
```

### Manual Setup

```bash
cd "c:\Users\Laptop\Documents\VSCode Workspace"

# Initialize repository
git init

# Configure user
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Create .gitignore
cat > .gitignore << EOF
__pycache__/
*.pyc
.venv/
.env
*.log
.DS_Store
*.swp
.venv
gemini_response_*.md
EOF

# Add files
git add prism_v2.py
git add 00_START_HERE.md
git add INDEX.md
git add PRISM_README.md
git add PRISM_FEATURES.md
git add PRISM_v2_SUMMARY.md
git add PRISM_SHOWCASE.txt
git add PRISM_QUICKSTART.sh
git add TEST_PRISM_v2.py
git add .gitignore

# Create initial commit
git commit -m "Initial commit: PRISM v2 - Production Release"

# View status
git status
```

## Repository Structure

```
PRISM/
├── prism_v2.py              # Main application
├── 00_START_HERE.md         # Getting started guide
├── INDEX.md                 # File manifest
├── PRISM_README.md          # User guide
├── PRISM_FEATURES.md        # Technical documentation
├── PRISM_v2_SUMMARY.md      # Implementation details
├── PRISM_SHOWCASE.txt       # Creative showcase
├── PRISM_QUICKSTART.sh      # Setup script
├── TEST_PRISM_v2.py         # Test suite
├── setup_git.bat            # Git setup script (Windows)
├── setup_git.sh             # Git setup script (Unix)
├── .gitignore               # Git ignore rules
└── .git/                    # Git metadata (created by init)
```

## Common Git Commands

### View Status
```bash
git status
git log
git log --oneline
git log --graph --oneline --all
```

### Create Branch for Features
```bash
git branch feature-xyz
git checkout feature-xyz
# Make changes, then:
git add .
git commit -m "Add feature xyz"
git checkout main
git merge feature-xyz
```

### Push to Remote (GitHub)

1. Create repository on GitHub
2. Add remote:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/prism.git
   ```

3. Push code:
   ```bash
   git branch -M main
   git push -u origin main
   ```

### Pull Latest Changes
```bash
git pull origin main
```

### View Changes
```bash
git diff HEAD~1 HEAD
git show HEAD
git diff prism_v2.py
```

## Gitignore Rules

The `.gitignore` file excludes:
- `__pycache__/` - Python cache
- `*.pyc` - Compiled Python
- `.venv/` - Virtual environment
- `.env` - Environment variables
- `*.log` - Log files
- `.DS_Store` - macOS files
- `*.swp` - Editor temp files
- `gemini_response_*.md` - Response files (can regenerate)

## First Commit Content

The initial commit includes:

✅ **prism_v2.py** - Main application with all 5 features
✅ **Documentation** - 5 comprehensive guide files
✅ **Setup Script** - PRISM_QUICKSTART.sh for easy installation
✅ **Test Suite** - TEST_PRISM_v2.py for validation
✅ **.gitignore** - Standard Python ignores

## Next Steps

After setting up the repository:

1. **Review commits**: `git log`
2. **Create branches**: `git branch feature-xyz`
3. **Make changes**: Edit files, `git add`, `git commit`
4. **Push to GitHub**: Follow "Push to Remote" section above

## Useful Commands

### Amend Last Commit
```bash
git add .
git commit --amend --no-edit
```

### Reset to Previous Commit
```bash
git reset HEAD~1  # Undo last commit, keep changes
git reset --hard HEAD~1  # Undo last commit, lose changes
```

### Tag Version
```bash
git tag v2.0.0
git push origin v2.0.0
```

### See What Changed
```bash
git diff           # Unstaged changes
git diff --cached  # Staged changes
git diff HEAD~5    # Last 5 commits
```

## Troubleshooting

### Git not found
```bash
# Install Git from https://git-scm.com
```

### Permission denied on setup_git.sh
```bash
chmod +x setup_git.sh
./setup_git.sh
```

### Already initialized
```bash
# If git init fails because .git exists:
rm -rf .git
git init
```

### Reset repository
```bash
# Completely reset (loses all history)
rm -rf .git
git init
```

## Resources

- Git Documentation: https://git-scm.com/doc
- GitHub Guides: https://guides.github.com
- Git Cheat Sheet: https://github.github.com/training-kit/downloads/github-git-cheat-sheet.pdf

---

**PRISM v2 is now under version control!**
