param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [int]$Port=8769
)
$ErrorActionPreference='Stop'
$sourceRoot=$PSScriptRoot
$resolvedData=(Resolve-Path -LiteralPath $DataDir).Path
$python=Join-Path $sourceRoot '.venv-spot\Scripts\python.exe'
$pythonWindowless=Join-Path $sourceRoot '.venv-spot\Scripts\pythonw.exe'
if(-not(Test-Path -LiteralPath $pythonWindowless)){throw 'pythonw não encontrado em .venv-spot.'}
# This explicit launcher starts PAPER only. No automatic login trigger or engine retry.
Push-Location $sourceRoot
try {
    & $python -c 'import sys; from pathlib import Path; from operar import preflight; preflight(Path(sys.argv[1]),int(sys.argv[2]),engine="portfolio")' $resolvedData $Port
    if($LASTEXITCODE -ne 0){throw 'Pré-verificação recusada; nada iniciado.'}
} finally {Pop-Location}
$taskName='SpotLab-Paper-'+(Split-Path $resolvedData -Leaf)
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Tarefa já existe; confira o estado no Agendador. Não sobrescrita.'}
$account=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments='-u "'+(Join-Path $sourceRoot 'operar.py')+'" --engine portfolio --data-dir "'+$resolvedData+'" --port '+$Port+' --start'
$action=New-ScheduledTaskAction -Execute $pythonWindowless -Argument $arguments -WorkingDirectory $sourceRoot
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 25) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal=New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$task=New-ScheduledTask -Action $action -Settings $settings -Principal $principal -Description 'Início explícito PAPER sem console. Sem retry do trading ou renovação de saldo/prazo.'
Register-ScheduledTask -TaskName $taskName -InputObject $task | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output ('Início solicitado: '+$taskName)
Write-Output ('Painel: http://127.0.0.1:'+$Port+'/#terminal')
Write-Output ('Código de acesso será registrado em '+(Join-Path $resolvedData 'reports\local\system-dashboard.log'))
Write-Output 'Pode fechar este terminal. Confirme RUNNING no painel. PC deve permanecer ligado, acordado e com este usuário conectado.'
