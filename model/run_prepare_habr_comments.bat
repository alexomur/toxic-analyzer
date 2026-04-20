@echo off
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%.venv312\Scripts\python.exe"

if not exist "%PY%" (
  echo [prepare-habr-comments] Creating Python 3.12 virtual environment...
  py -3.12 -m venv "%ROOT%.venv312" || goto :error
)

echo [prepare-habr-comments] Installing project dependencies...
"%PY%" -m pip install --upgrade pip || goto :error
"%PY%" -m pip install -e "%ROOT%" || goto :error

if defined HF_TOKEN (
  echo [prepare-habr-comments] Using HF_TOKEN from environment.
) else (
  echo [prepare-habr-comments] HF_TOKEN is not set. Downloads may be slower.
)

echo [prepare-habr-comments] Starting download and cleaning run...
"%PY%" -m toxic_analyzer.prepare_habr_comments --config "%ROOT%configs\habr_comments.toml" %*
if errorlevel 1 goto :error

echo [prepare-habr-comments] Finished successfully.
echo Output file: %ROOT%data\processed\habr_comments_russian_annotation_pool.jsonl
echo Report file: %ROOT%artifacts\habr_comments_preparation_report.json
echo Progress file: %ROOT%artifacts\habr_comments_preparation_progress.json
pause
exit /b 0

:error
echo [prepare-habr-comments] Failed.
pause
exit /b 1
