param(
    [ValidateSet("on", "off", "auto")]
    [string]$Ngrok = "off"
)

$ErrorActionPreference = "Stop"

$ScriptPath = [System.IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
$ProjectRoot = Split-Path -Parent $ScriptPath
Set-Location $ProjectRoot

function Get-PythonExecutable {
    $venvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pyvenvCfg = Join-Path $ProjectRoot "venv\pyvenv.cfg"
    if (Test-Path $pyvenvCfg) {
        $homeLine = Get-Content $pyvenvCfg | Where-Object { $_ -like "home = *" } | Select-Object -First 1
        if ($homeLine) {
            $homeDir = $homeLine.Split("=", 2)[1].Trim()
            $homePython = Join-Path $homeDir "python.exe"
            if (Test-Path $homePython) {
                return $homePython
            }
        }
    }

    return "C:\Python313\python.exe"
}

function Get-PythonCandidates {
    $candidates = [System.Collections.Generic.List[string]]::new()

    $venvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $candidates.Add($venvPython)
    }

    $pyvenvCfg = Join-Path $ProjectRoot "venv\pyvenv.cfg"
    if (Test-Path $pyvenvCfg) {
        $homeLine = Get-Content $pyvenvCfg | Where-Object { $_ -like "home = *" } | Select-Object -First 1
        if ($homeLine) {
            $homeDir = $homeLine.Split("=", 2)[1].Trim()
            $homePython = Join-Path $homeDir "python.exe"
            if ((Test-Path $homePython) -and (-not $candidates.Contains($homePython))) {
                $candidates.Add($homePython)
            }
        }
    }

    $fallbackPython = "C:\Python313\python.exe"
    if ((Test-Path $fallbackPython) -and (-not $candidates.Contains($fallbackPython))) {
        $candidates.Add($fallbackPython)
    }

    return $candidates.ToArray()
}

function Get-SharedSitePackagesCandidates {
    $appDataRoot = [Environment]::GetFolderPath("ApplicationData")
    if ([string]::IsNullOrWhiteSpace($appDataRoot)) {
        return @()
    }

    $root = Join-Path $appDataRoot "Python"
    if (-not (Test-Path $root)) {
        return @()
    }

    return Get-ChildItem -Path $root -Directory -Filter "Python*" |
        ForEach-Object { Join-Path $_.FullName "site-packages" } |
        Where-Object { Test-Path $_ } |
        Select-Object -Unique
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,
        [string[]]$Arguments
    )

    $quotedArguments = $Arguments | ForEach-Object {
        if ($_ -match '[\s";]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }

    $proc = Start-Process -FilePath $ExecutablePath `
        -ArgumentList ([string]::Join(" ", $quotedArguments)) `
        -WorkingDirectory $ProjectRoot `
        -Wait `
        -NoNewWindow `
        -PassThru

    return $proc.ExitCode
}

function Invoke-PythonCommand {
    param(
        [string[]]$Arguments
    )

    return Invoke-ExternalCommand -ExecutablePath $pythonExe -Arguments $Arguments
}

function Test-PythonModules {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ModuleNames,
        [string[]]$AdditionalSitePackages = @()
    )

    $moduleList = ($ModuleNames | ForEach-Object { "'$_'" }) -join ", "
    $siteSetup = ""
    if ($AdditionalSitePackages.Count -gt 0) {
        $siteStatements = $AdditionalSitePackages | ForEach-Object {
            $escapedPath = $_ -replace "\\", "\\\\"
            "site.addsitedir(r'$escapedPath')"
        }
        $siteSetup = "import site; " + ($siteStatements -join "; ") + "; "
    }

    $probeCode = $siteSetup + "import importlib.util, sys; modules = [$moduleList]; missing = [name for name in modules if importlib.util.find_spec(name) is None]; sys.exit(0 if not missing else 1)"
    return (Invoke-ExternalCommand -ExecutablePath $ExecutablePath -Arguments @("-c", $probeCode)) -eq 0
}

function Install-RequirementsIfNeeded {
    $requiredModules = @(
        "streamlit",
        "dotenv",
        "boto3",
        "pydantic_settings",
        "requests",
        "PyPDF2",
        "fitz",            # PyMuPDF
        "PIL",             # Pillow
        "openai",
        "yaml",            # PyYAML
        "pptx",            # python-pptx
        "jinja2",
        "markdown2",
        "bcrypt",
        "pandas"
    )

    if (Test-PythonModules -ExecutablePath $pythonExe -ModuleNames $requiredModules) {
        Remove-Item Env:SBK_SHARED_SITE_PACKAGES -ErrorAction SilentlyContinue
        return
    }

    foreach ($sharedSitePackages in (Get-SharedSitePackagesCandidates)) {
        if (Test-PythonModules -ExecutablePath $pythonExe -ModuleNames $requiredModules -AdditionalSitePackages @($sharedSitePackages)) {
            Write-Host "Ambiente virtual incompleto. Reutilizando site-packages compartilhado: $sharedSitePackages"
            $env:SBK_SHARED_SITE_PACKAGES = $sharedSitePackages
            return
        }
    }

    foreach ($candidate in (Get-PythonCandidates)) {
        if ($candidate -eq $pythonExe) {
            continue
        }

        if (Test-PythonModules -ExecutablePath $candidate -ModuleNames $requiredModules) {
            Write-Host "Ambiente virtual incompleto. Usando Python alternativo já funcional: $candidate"
            $script:pythonExe = $candidate
            Remove-Item Env:SBK_SHARED_SITE_PACKAGES -ErrorAction SilentlyContinue
            return
        }
    }

    $requirementsFile = Join-Path $ProjectRoot "requirements.txt"
    if (-not (Test-Path $requirementsFile)) {
        throw "Arquivo requirements.txt não encontrado em $requirementsFile"
    }

    Write-Host "Dependências ausentes no ambiente virtual. Instalando requirements.txt..."

    $ensurePipExit = Invoke-PythonCommand -Arguments @("-m", "ensurepip", "--upgrade")
    if ($ensurePipExit -ne 0) {
        throw "Falha ao preparar pip no ambiente Python (exit code $ensurePipExit)."
    }

    $installExit = Invoke-PythonCommand -Arguments @("-m", "pip", "install", "-r", $requirementsFile)
    if ($installExit -ne 0) {
        throw "Falha ao instalar dependências do projeto (exit code $installExit)."
    }

    if (-not (Test-PythonModules -ExecutablePath $pythonExe -ModuleNames $requiredModules)) {
        throw "Dependências instaladas, mas o ambiente Python continua incompleto."
    }
}

$pythonExe = Get-PythonExecutable
if (-not (Test-Path $pythonExe)) {
    throw "Python não encontrado em $pythonExe"
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Write-Host "Aviso: .env não encontrado. Existe um .env.example disponível."
}

# Desabilita tracer externo ruidoso apenas no contexto deste processo.
$env:DD_TRACE_ENABLED = "false"
$env:DD_INSTRUMENTATION_TELEMETRY_ENABLED = "false"

switch ($Ngrok) {
    "on" { $env:USE_NGROK = "1" }
    "off" { $env:USE_NGROK = "0" }
    default { }
}

Install-RequirementsIfNeeded

Write-Host "Inicializando aplicação..."
Write-Host "Python: $pythonExe"
Write-Host "Ngrok: $Ngrok"

$exitCode = Invoke-PythonCommand -Arguments @("main.py", "--ngrok", $Ngrok)
exit $exitCode
