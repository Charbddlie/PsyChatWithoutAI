@echo off
REM download_user_record.cmd - 使用 OpenSSH scp 从远程服务器下载文件到当前目录
REM 不依赖 pscp/Putty，使用系统自带 scp (Windows 10/11 可通过“可选功能”安装 OpenSSH)

setlocal

:: 配置区 - 修改为你的值（或留空以使用交互式密码提示）
set "HOST=8.153.195.92"
set "USER=root"
set "REMOTE_FILE=~/psy-part2/back/data/user_record.tsv"
set "LOCAL_DIR=%CD%"
:: 如果你有私钥，填写路径（例如 C:\Users\you\.ssh\id_rsa），否则留空
set "KEYFILE="

echo.
echo ========== 下载配置 ==========
echo 远程主机: %USER%@%HOST%
echo 远程文件: %REMOTE_FILE%
echo 本地目录: %LOCAL_DIR%
if defined KEYFILE (
    echo 使用密钥: %KEYFILE%
) else (
    echo 未设置密钥 — 将会提示输入密码（交互式）
)
echo ================================
echo.

:: 检查 scp 是否可用
where scp >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 scp。请在“可选功能”中安装 OpenSSH 客户端，或将 scp 的可执行文件加入 PATH。
    echo Windows: 打开“设置 -> 应用 -> 可选功能 -> 添加功能 -> OpenSSH 客户端”
    pause
    exit /b 2
)

:: 使用密钥或交互式模式
if defined KEYFILE (
    scp -i "%KEYFILE%" "%USER%@%HOST%:%REMOTE_FILE%" "%LOCAL_DIR%"\  || goto :scp_fail
) else (
    scp "%USER%@%HOST%:%REMOTE_FILE%" "%LOCAL_DIR%"\  || goto :scp_fail
)

echo 下载成功: %LOCAL_DIR%\user_record.tsv
endlocal
exit /b 0

:scp_fail
echo 下载失败，scp 返回错误码 %ERRORLEVEL%
endlocal
exit /b %ERRORLEVEL%
