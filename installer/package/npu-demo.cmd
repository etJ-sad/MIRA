@echo off
rem MIRA: makes the NPU work visible. Answers one question after another for 30 s (or the seconds given).
rem Open Task Manager ^> Performance ^> NPU before starting: the NPU graph rises, the CPU stays low.
setlocal
set "H=%~dp0"
set "MIRA_DATA_DIR=%LOCALAPPDATA%\MIRA"
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%Start-MIRA.ps1" -OvmsOnly || exit /b 1
"%H%runtime\python\python.exe" -I -m mira.cli npu-demo %*
