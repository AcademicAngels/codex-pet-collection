param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $ScriptDir "install.py"

function Test-PythonCandidate {
    param([string] $Command)

    try {
        & $Command --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

$Candidates = @()
if ($env:PYTHON) {
    $Candidates += $env:PYTHON
}
$Candidates += "D:\IDE\Python\python.exe"
$Candidates += "py"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Candidates += $BundledPython
$Candidates += "python"

foreach ($Candidate in $Candidates) {
    if (-not (Test-PythonCandidate $Candidate)) {
        continue
    }
    & $Candidate $Installer @Args
    exit $LASTEXITCODE
}

Write-Error "Python was not found. Install Python or run scripts/install.py with an explicit Python executable."
