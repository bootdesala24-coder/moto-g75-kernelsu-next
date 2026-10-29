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
echo Conecte somente o Moto G75 e autorize a depuracao USB.
"%G75_ADB%" get-state >nul 2>&1
if errorlevel 1 (
  echo Verifique o cabo, a depuracao USB e a autorizacao no telefone.
  pause
  exit /b 1
)
"%G75_ADB%" shell getprop ro.boot.hardware.sku | findstr /x /c:"XT2437-1" >nul
if errorlevel 1 (
  echo O aparelho conectado nao informou o SKU XT2437-1 esperado.
  pause
  exit /b 1
)
set "G75_OUT=%~dp0conferencia-boot-%RANDOM%-%RANDOM%"
mkdir "%G75_OUT%"
if errorlevel 1 exit /b 1
set "G75_REPORT=%G75_OUT%\conferencia-boot.txt"
echo Leitura de identificacao e hashes do boot do Moto G75 > "%G75_REPORT%"
for %%P in (ro.boot.hardware.sku ro.build.display.id ro.boot.slot_suffix) do (
  echo [%%P] >> "%G75_REPORT%"
  "%G75_ADB%" shell getprop %%P >> "%G75_REPORT%" 2>&1
)
echo.
echo O Magisk pode pedir permissao para Shell. Autorize na tela do telefone.
echo O acesso root sera usado para ler os hashes das particoes boot_a e boot_b.
"%G75_ADB%" shell "su -c 'id'" > "%G75_OUT%\root-check.txt" 2>&1
type "%G75_OUT%\root-check.txt" >> "%G75_REPORT%"
findstr /c:"uid=0" "%G75_OUT%\root-check.txt" >nul
if errorlevel 1 (
  echo Nao foi possivel obter acesso root pelo Magisk.
  echo Envie o relatorio: "%G75_REPORT%"
  pause
  exit /b 1
)
echo [sha256 das particoes boot] >> "%G75_REPORT%"
"%G75_ADB%" shell "su -c 'sha256sum /dev/block/by-name/boot_a /dev/block/by-name/boot_b'" >> "%G75_REPORT%" 2>&1
if errorlevel 1 (
  echo A leitura dos hashes retornou erro. Envie o relatorio para verificacao.
) else (
  echo Consulta concluida. O relatorio precisa ser comparado com a imagem enviada.
)
echo Envie este arquivo: "%G75_REPORT%"
echo Nenhuma particao foi gravada e o telefone nao foi reiniciado.
pause
