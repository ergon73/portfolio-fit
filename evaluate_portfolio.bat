@echo off
chcp 65001 >nul
echo ========================================
echo Запуск оценки портфолио GitHub
echo ========================================
echo.

REM Укажите ваш GitHub username
set GITHUB_USERNAME=ergon73
python enhanced_evaluate_portfolio.py -g %GITHUB_USERNAME% --max-repos 0

echo.
echo ========================================
echo Нажмите любую клавишу для выхода...
pause >nul
