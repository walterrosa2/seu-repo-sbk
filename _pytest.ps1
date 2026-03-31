$ErrorActionPreference = "Stop"

function Get-PythonCandidates {
    $candidates = [System.Collections.Generic.List[string]]::new()

    foreach ($candidate in @(
        (Join-Path $PSScriptRoot "venv312\Scripts\python.exe"),
        (Join-Path $PSScriptRoot "venv\Scripts\python.exe"),
        "C:\Python\python.exe",
        "C:\Python313\python.exe",
        "C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe"
    )) {
        if ((Test-Path $candidate) -and (-not $candidates.Contains($candidate))) {
            $candidates.Add($candidate)
        }
    }

    foreach ($cfgPath in @(
        (Join-Path $PSScriptRoot "venv312\pyvenv.cfg"),
        (Join-Path $PSScriptRoot "venv\pyvenv.cfg")
    )) {
        if (-not (Test-Path $cfgPath)) {
            continue
        }

        $homeLine = Get-Content $cfgPath | Where-Object { $_ -like "home = *" } | Select-Object -First 1
        if (-not $homeLine) {
            continue
        }

        $homeDir = $homeLine.Split("=", 2)[1].Trim()
        $homePython = Join-Path $homeDir "python.exe"
        if ((Test-Path $homePython) -and (-not $candidates.Contains($homePython))) {
            $candidates.Add($homePython)
        }
    }

    return $candidates.ToArray()
}

function Invoke-CommandChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$Quiet
    )

    $quotedArguments = $Arguments | ForEach-Object {
        if ($_ -match '[\s";]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }

    $startParams = @{
        FilePath = $ExecutablePath
        ArgumentList = ([string]::Join(" ", $quotedArguments))
        WorkingDirectory = $PSScriptRoot
        Wait = $true
        NoNewWindow = $true
        PassThru = $true
    }

    $stdoutTemp = $null
    $stderrTemp = $null

    if ($Quiet) {
        $stdoutTemp = Join-Path $env:TEMP ("codex_pytest_probe_stdout_" + [guid]::NewGuid().ToString("N") + ".log")
        $stderrTemp = Join-Path $env:TEMP ("codex_pytest_probe_stderr_" + [guid]::NewGuid().ToString("N") + ".log")
        $startParams["RedirectStandardOutput"] = $stdoutTemp
        $startParams["RedirectStandardError"] = $stderrTemp
    }

    $proc = Start-Process @startParams

    $exitCode = $proc.ExitCode

    if ($Quiet) {
        Remove-Item $stdoutTemp, $stderrTemp -Force -ErrorAction SilentlyContinue
    }

    return $exitCode
}

function Test-AsyncioRuntime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    return (Invoke-CommandChecked -ExecutablePath $PythonExe -Arguments @("-c", "import asyncio") -Quiet) -eq 0
}

function Ensure-PytestVenv {
    $venv312Python = Join-Path $PSScriptRoot "venv312\Scripts\python.exe"
    if (Test-Path $venv312Python) {
        if (Test-AsyncioRuntime -PythonExe $venv312Python) {
            return $venv312Python
        }
        return $null
    }

    $basePython = "C:\Python\python.exe"
    if (-not (Test-Path $basePython)) {
        return $null
    }

    if (-not (Test-AsyncioRuntime -PythonExe $basePython)) {
        return $null
    }

    Write-Host "Criando venv312 para execução de testes..."
    $createExit = Invoke-CommandChecked -ExecutablePath $basePython -Arguments @("-m", "venv", (Join-Path $PSScriptRoot "venv312"))
    if ($createExit -ne 0) {
        throw "Falha ao criar venv312 (exit code $createExit)."
    }

    $venv312Python = Join-Path $PSScriptRoot "venv312\Scripts\python.exe"
    if (-not (Test-Path $venv312Python)) {
        throw "venv312 criado, mas python.exe não foi encontrado."
    }

    $requirementsFile = Join-Path $PSScriptRoot "requirements.txt"
    if (Test-Path $requirementsFile) {
        Write-Host "Instalando dependências em venv312..."
        $pipExit = Invoke-CommandChecked -ExecutablePath $venv312Python -Arguments @("-m", "pip", "install", "-r", $requirementsFile, "pytest")
        if ($pipExit -ne 0) {
            throw "Falha ao instalar dependências no venv312 (exit code $pipExit)."
        }
    }

    return $venv312Python
}

$pythonExe = Ensure-PytestVenv
if (-not $pythonExe) {
    foreach ($candidate in (Get-PythonCandidates)) {
        if (Test-AsyncioRuntime -PythonExe $candidate) {
            $pythonExe = $candidate
            break
        }
    }
}

if (-not $pythonExe) {
    Write-Host ""
    Write-Host "Nenhum runtime Python saudável conseguiu importar 'asyncio'."
    Write-Host "O problema está no ambiente Windows/Winsock, não na suíte de testes."
    Write-Host ""
    Write-Host "Próximos passos recomendados:"
    Write-Host "1. Execute .\_repair_winsock.ps1 em um PowerShell aberto como Administrador."
    Write-Host "2. Reinicie o Windows."
    Write-Host "3. Rode novamente .\_pytest.ps1."
    Write-Host "4. Se ainda falhar, execute 'sfc /scannow' e 'DISM /Online /Cleanup-Image /RestoreHealth' como administrador."
    exit 2
}

Write-Host "Usando Python para testes: $pythonExe"

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

$pytestExit = Invoke-CommandChecked -ExecutablePath $pythonExe -Arguments @("-m", "pytest", "-q")

exit $pytestExit
