@echo off
setlocal
set "G75_PACKAGE_DIR=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $base=$env:G75_PACKAGE_DIR; foreach($line in Get-Content -LiteralPath (Join-Path $base 'SHA256SUMS.txt')) { if($line -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$') { throw 'Linha invalida no manifesto' }; $wanted=$Matches[1]; $name=$Matches[2]; if($name.Contains('..')) { throw 'Nome invalido' }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $base $name)).Hash.ToLower(); if($actual -ne $wanted) { throw ('Hash diferente: '+$name) }; Write-Host ('OK '+$name) }; Write-Host 'ARQUIVOS_CONFERIDOS'; exit 0 } catch { Write-Host ('ERRO: '+$_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo Nao instale. Confira se o ZIP foi extraido por completo.
    exit /b 1
)
exit /b 0
