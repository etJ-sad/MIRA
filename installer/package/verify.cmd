@echo off
rem MIRA: checks this machine, like Greenforest's verify.cmd.
rem  1. unit tests (no NPU needed)
rem  2. starts MIRA if needed: model server with both models AVAILABLE on the NPU, web UI
rem  3. NPU check: models compiled for the NPU, demo documents read on the NPU, two questions answered
rem     with sources, one unknown question answered with "Weiss ich nicht". Report in %%LOCALAPPDATA%%\MIRA\logs
rem  4. web UI http://localhost:8080
setlocal
set "H=%~dp0"
set "PY=%H%runtime\python\python.exe"
set "MIRA_DATA_DIR=%LOCALAPPDATA%\MIRA"
set "MIRA_MODELS=%H%models"
set "MIRA_SAMPLES=%H%samples\fz-300"
echo === 1. Unit tests
"%PY%" -I -m pytest -q -p no:cacheprovider "%H%runtime\app\tests" || set FAILED=1
echo.
echo === 2. Start MIRA
powershell -NoProfile -ExecutionPolicy Bypass -File "%H%Start-MIRA.ps1" -NoBrowser || set FAILED=1
echo.
echo === 3. NPU check
"%PY%" -I -m mira.cli check --models "%H%models" || set FAILED=1
echo.
echo === 4. Web UI http://localhost:8080/
powershell -NoProfile -Command "try { $h = Invoke-RestMethod http://localhost:8080/api/health -TimeoutSec 5; 'Web UI OK: MIRA ' + $h.mira + ', LLM ' + $h.llm_model } catch { 'Web UI not reachable'; exit 1 }" || set FAILED=1
echo.
if defined FAILED (echo RESULT: FAILED & exit /b 1)
echo RESULT: OK
