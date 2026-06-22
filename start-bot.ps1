# Launcher for Windows Task Scheduler -> starts the bot inside WSL (Ubuntu).
# Set the Task Scheduler action to:
#   Program/script: powershell.exe
#   Arguments:      -ExecutionPolicy Bypass -File "C:\Users\damia\OneDrive\Documents\code\discord_fa\start-bot.ps1"
wsl.exe -d Ubuntu -- bash -lc 'cd "/mnt/c/Users/damia/OneDrive/Documents/code/discord_fa" && exec .venv/bin/python bot.py'
