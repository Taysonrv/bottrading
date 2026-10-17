$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'STOP')) {
    throw 'STOP está acionado. Revise o motivo antes de usar python bot.py resume.'
}
$pythonExec = (Get-Command python -ErrorAction Stop).Source
$watchProcess = Start-Process -FilePath $pythonExec -ArgumentList @('-u', 'bot.py', 'watch') `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $PSScriptRoot 'watch-output.log') `
    -RedirectStandardError (Join-Path $PSScriptRoot 'watch-error.log')
Start-Sleep -Seconds 2
if ($watchProcess.HasExited) {
    throw 'O acompanhamento não permaneceu ativo. Consulte watch-error.log; pode existir outro processo usando a trava.'
}
Write-Host "Observação iniciada em segundo plano. PID: $($watchProcess.Id). Nenhuma ordem será criada."
Write-Host 'Para desligar: python bot.py stop. O computador precisa permanecer ligado.'
