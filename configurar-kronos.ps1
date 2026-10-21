$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$basePython = Join-Path $projectRoot '.venv-spot\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $basePython)) { throw 'Execute configurar-spot.ps1 primeiro.' }
$kronosHome = Join-Path $env:LOCALAPPDATA 'SpotLab\kronos-venv'
$kronosPython = Join-Path $kronosHome 'Scripts\python.exe'
$source = Join-Path $projectRoot 'reports\local\kronos-runtime\source'
$revision = '67b630e67f6a18c9e9be918d9b4337c960db1e9a'
if (-not (Test-Path -LiteralPath $kronosPython)) {
    & $basePython -m venv $kronosHome
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente isolado.' }
}
if (-not (Test-Path -LiteralPath $source)) {
    New-Item -ItemType Directory -Force (Split-Path $source) | Out-Null
    & git clone https://github.com/shiyu-coder/Kronos.git $source
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao obter fonte oficial.' }
    & git -C $source checkout --detach $revision
    if ($LASTEXITCODE -ne 0) { throw 'Revisao revisada nao encontrada.' }
}
$actual = & git -C $source rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $revision) { throw 'Fonte difere da revisao revisada; nao alterada automaticamente.' }
& $kronosPython -m pip install --only-binary=:all: torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyTorch CPU.' }
& $kronosPython -m pip install --only-binary=:all: -r (Join-Path $projectRoot 'requirements-kronos.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias.' }
& $kronosPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependencias inconsistentes.' }
Write-Host 'Kronos preparado separadamente. Nenhuma previsao ou ordem iniciada.'
Write-Host 'Para executar na pasta do projeto:'
Write-Host '& "$env:LOCALAPPDATA\SpotLab\kronos-venv\Scripts\python.exe" -m spot_engine.kronos_lab --samples 4 --horizon 24'
