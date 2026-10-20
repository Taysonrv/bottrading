param(
    [switch]$BaixarHistorico,
    [string]$ProjectRoot = $PSScriptRoot
)
# Separate environment: never delete or recreate the existing .venv.
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$requirementsPath = Join-Path $projectPath 'requirements-spot-data.txt'
if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw 'Arquivo requirements-spot-data.txt ausente. Execute git pull na pasta do bot.'
}
$venvPath = Join-Path $projectPath '.venv-spot'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Test-Path -LiteralPath $venvPath) {
        throw 'A pasta .venv-spot existe, mas esta incompleta. Revise-a; nenhum arquivo foi apagado.'
    }
    $basePython = $null
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $candidate = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate)) {
                $basePython = $candidate
            }
        } catch { $basePython = $null }
    }
    if (-not $basePython) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundledPython) { $basePython = $bundledPython }
    }
    if (-not $basePython) {
        throw 'Python 3.12 nao encontrado. Instale Python 3.12 e execute este script novamente.'
    }
    $baseVersion = & $basePython -c 'import sys; print(sys.version_info.major,sys.version_info.minor,sep=chr(46))'
    if ($LASTEXITCODE -ne 0 -or $baseVersion -ne '3.12') { throw 'Este instalador exige Python 3.12.' }
    & $basePython -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ambiente isolado. Nenhuma dependencia instalada.' }
}
$version = & $pythonPath -c 'import sys; print(sys.version_info.major,sys.version_info.minor,sep=chr(46))'
if ($LASTEXITCODE -ne 0 -or $version -ne '3.12') {
    throw 'A .venv-spot existente nao usa Python 3.12. Ambiente preservado; revise antes de continuar.'
}
Push-Location -LiteralPath $projectPath
try {
    Write-Host 'Instalando dependencias no ambiente .venv-spot (Python 3.12).'
    # Refuse source compilation rather than demanding a compiler toolchain.
    & $pythonPath -m pip install --only-binary=:all: -r $requirementsPath
    if ($LASTEXITCODE -ne 0) { throw 'Instalacao incompleta. Testes e coleta nao serao executados.' }
    & $pythonPath -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependencias inconsistentes. Coleta cancelada.' }
    & $pythonPath -m unittest tests.test_spot_config tests.test_spot_data tests.test_spot_strategy tests.test_spot_risk tests.test_spot_execution tests.test_spot_main -v
    if ($LASTEXITCODE -ne 0) { throw 'Testes falharam. Coleta cancelada.' }
    if ($BaixarHistorico) {
        & $pythonPath -m spot_engine.data --years 2
        if ($LASTEXITCODE -ne 0) { throw 'Coleta publica nao concluida; confira o aviso acima.' }
    }
    Write-Host 'Ambiente pronto. Nenhuma ordem ou processo de trading iniciado.'
    Write-Host 'Para coletar: .\.venv-spot\Scripts\python.exe -m spot_engine.data --years 2'
}
finally { Pop-Location }
