@echo off
echo.
echo ========================================
echo PRISM v2 - Git Commit & Push
echo ========================================
echo.

cd /d "C:\Users\Laptop\Documents\VSCode Workspace\PRISM"

echo Checking git status...
git status
echo.

echo Adding files...
git add install_requirements.py requirements.txt SETUP.md

echo.
echo Committing changes...
git commit -m "Add: Installation scripts and setup documentation

- install_requirements.py: Automatic dependency installer
- requirements.txt: Package dependencies list
- SETUP.md: Complete setup guide with troubleshooting

These files make it easy for users to install PRISM and get started."

echo.
echo Pushing to GitHub...
git push origin main

echo.
echo ========================================
echo Done! Check your GitHub repository
echo ========================================
echo.
pause
