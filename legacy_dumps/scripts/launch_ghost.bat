@echo off
TITLE Ghost Agent (Self-Booting)

:: --- CONFIGURATION ---
:: Set your Conda path (Using the one you found earlier)
set CONDA_ROOT=D:\AI_Assistant\conda

:: --- ACTIVATION ---
:: Activate the environment
call "%CONDA_ROOT%\Scripts\activate.bat" ai-gpu

:: --- LAUNCH ---
:: We ONLY launch the agent. The agent will launch the Server and Dashboard for us.
echo Launching Ghost Agent (with Auto-Bootloader)...
python ghost_agent.py

:: Keep window open for errors
pause