$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Este script precisa ser executado como Administrador."
    Write-Host "Abra um PowerShell como administrador e rode novamente: .\_repair_winsock.ps1"
    exit 1
}

$netshExe = Join-Path $env:WINDIR "System32\netsh.exe"
if (-not (Test-Path $netshExe)) {
    throw "netsh.exe não encontrado em $netshExe"
}

$proc = Start-Process -FilePath $netshExe `
    -ArgumentList "winsock reset" `
    -WorkingDirectory $PSScriptRoot `
    -Wait `
    -NoNewWindow `
    -PassThru

if ($proc.ExitCode -ne 0) {
    throw "Falha ao executar 'netsh winsock reset' (exit code $($proc.ExitCode))."
}

Write-Host ""
Write-Host "Winsock resetado com sucesso."
Write-Host "Reinicie o Windows antes de rodar novamente .\_pytest.ps1."
