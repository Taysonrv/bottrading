$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$tokenSeguro = Read-Host 'Token do bot Telegram (entrada oculta)' -AsSecureString
$tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSeguro)
try {
    $env:TELEGRAM_BOT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr)
}
$env:TELEGRAM_CHAT_ID = Read-Host 'Seu chat ID privado no Telegram'
Write-Host 'Credenciais definidas somente neste terminal. Não foram salvas em arquivo.'
python bot.py telegram-test
