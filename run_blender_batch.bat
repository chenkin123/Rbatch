@echo off
RBatch
echo ---------------------------------------
echo Launching Blender Batch Renderer...
echo ---------------------------------------
python "%~dp0blender_batch.py"
if %errorlevel% neq 0 (
    echo Execution failed!
    pause
)
pause
