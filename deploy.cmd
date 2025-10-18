@echo off
echo Building...
call npm run build
if errorlevel 1 (
    echo ERROR: build failed.
    exit /b 1
)
REM deploy.cmd - 上传 back/server.py 和 dist/ 到 8.153.195.92:~/psy-part2，保留目录结构
REM 需要 Windows 内置的 OpenSSH 客户端（ssh 和 scp）

setlocal

set "HOST=8.153.195.92"
set "USER=root"
set "REMOTE_DIR=~/psy-part2"

REM 检查 scp 是否可用
where scp >nul 2>&1
if errorlevel 1 (
    echo ERROR: scp not found. Please enable OpenSSH client in Windows Features.
    exit /b 1
)
REM 检查 ssh 是否可用
where ssh >nul 2>&1
if errorlevel 1 (
    echo ERROR: ssh not found. Please enable OpenSSH client in Windows Features.
    exit /b 1
)

REM 创建远程目录
echo Creating remote directories...
ssh %USER%@%HOST% "mkdir -p %REMOTE_DIR%/back" || (
    echo ERROR: failed to create remote directory.
    exit /b 1
)

REM 上传 dist/
echo Uploading dist/ ...
scp -r dist %USER%@%HOST%:%REMOTE_DIR%/ || (
    echo ERROR: upload of dist/ failed.
    exit /b 1
)

REM 上传 back/server.py
echo Uploading back/server.py ...
scp back\server.py %USER%@%HOST%:%REMOTE_DIR%/back/server.py || (
    echo ERROR: upload of back\server.py failed.
    exit /b 1
)

echo Upload complete.
endlocal
exit /b 0