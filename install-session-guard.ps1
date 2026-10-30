param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [int]$Port=8769
)
$ErrorActionPreference='Stop'
$sourceRoot=$PSScriptRoot
$resolvedData=(Resolve-Path -LiteralPath $DataDir).Path
$planPath=Join-Path $resolvedData 'reports\local\portfolio\plan.json'
$plan=Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$deadline=[DateTimeOffset]::FromUnixTimeMilliseconds([long]$plan.end_ms)
if($deadline -le [DateTimeOffset]::UtcNow){throw 'Sessão encerrada. O guardião não estende o prazo.'}
if($Port -lt 1024 -or $Port -gt 65535){throw 'Porta inválida.'}
$python=Join-Path $sourceRoot '.venv-spot\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Ambiente .venv-spot não encontrado.'}
$taskName='SpotLab-Guard-'+(Split-Path $resolvedData -Leaf)
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Tarefa já existe; não sobrescrita.'}
$account=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments='-u "'+(Join-Path $sourceRoot 'session_guard.py')+'" --data-dir "'+$resolvedData+'" --port '+$Port+' --watch'
$action=New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $sourceRoot
$once=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$logon=New-ScheduledTaskTrigger -AtLogOn -User $account
$limit=($deadline-[DateTimeOffset]::UtcNow)+[TimeSpan]::FromMinutes(2)
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit $limit -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal=New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$task=New-ScheduledTask -Action $action -Trigger @($once,$logon) -Settings $settings -Principal $principal -Description 'Guardião PAPER limitado ao prazo da sessão. Recupera só painel; não reinicia trading, saldo ou prazo.'
Register-ScheduledTask -TaskName $taskName -InputObject $task | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output ('Tarefa instalada: '+$taskName)
Write-Output 'Executa somente enquanto este usuário estiver conectado. Não impede suspensão. O prazo original continua valendo.'
