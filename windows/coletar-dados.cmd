@echo off
setlocal
cd /d "%~dp0"
set "G75_ADB=adb.exe"
if exist "%~dp0adb.exe" set "G75_ADB=%~dp0adb.exe"
if exist "%~dp0platform-tools\adb.exe" set "G75_ADB=%~dp0platform-tools\adb.exe"
"%G75_ADB%" version >nul 2>&1
if errorlevel 1 (
  echo Nao encontrei adb.exe. Copie este arquivo para a pasta platform-tools.
  pause
  exit /b 1
)
echo Conecte somente o Moto G75 por USB e autorize a depuracao na tela dele.
"%G75_ADB%" get-state >nul 2>&1
if errorlevel 1 (
  echo O telefone nao esta autorizado, nao esta conectado ou ha mais de um aparelho.
  echo Verifique o cabo, a depuracao USB e a autorizacao no telefone.
  pause
  exit /b 1
)
set "G75_OUT=%~dp0diagnostico-g75-%RANDOM%-%RANDOM%"
mkdir "%G75_OUT%"
if errorlevel 1 exit /b 1
set "G75_REPORT=%G75_OUT%\aparelho.txt"
echo Diagnostico de leitura do Moto G75 - sem comandos de flash > "%G75_REPORT%"
echo. >> "%G75_REPORT%"
for %%P in (ro.product.model ro.product.device ro.boot.hardware.sku ro.board.platform ro.build.display.id ro.build.fingerprint ro.build.version.release ro.build.version.security_patch ro.carrier ro.boot.slot_suffix ro.boot.vbmeta.device_state) do (
  echo [%%P] >> "%G75_REPORT%"
  "%G75_ADB%" shell getprop %%P >> "%G75_REPORT%" 2>&1
)
echo [kernel] >> "%G75_REPORT%"
"%G75_ADB%" shell uname -r >> "%G75_REPORT%" 2>&1
echo [tamanho de pagina] >> "%G75_REPORT%"
"%G75_ADB%" shell getconf PAGESIZE >> "%G75_REPORT%" 2>&1
echo [SELinux] >> "%G75_REPORT%"
"%G75_ADB%" shell getenforce >> "%G75_REPORT%" 2>&1
echo [nomes de particoes de boot] >> "%G75_REPORT%"
"%G75_ADB%" shell "ls -l /dev/block/by-name/boot* /dev/block/by-name/init_boot* /dev/block/by-name/vendor_boot* /dev/block/by-name/vbmeta*" >> "%G75_REPORT%" 2>&1
echo [configuracao do kernel] >> "%G75_REPORT%"
"%G75_ADB%" pull /proc/config.gz "%G75_OUT%\kernel-config.gz" >> "%G75_REPORT%" 2>&1
echo.
echo Coleta concluida. Pasta: "%G75_OUT%"
echo Envie aparelho.txt e, se existir, kernel-config.gz.
echo Nenhuma particao foi gravada. Nenhum root foi instalado ou removido.
pause
