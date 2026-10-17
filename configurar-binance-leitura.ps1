$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Use uma chave HMAC da Binance somente com leitura. Não habilite trading ou saques para esta etapa.'
foreach ($credentialName in @('BINANCE_API_KEY', 'BINANCE_API_SECRET')) {
    $credentialSecure = Read-Host "$credentialName (entrada oculta)" -AsSecureString
    $credentialPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credentialSecure)
    try {
        $credentialValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($credentialPtr)
        [Environment]::SetEnvironmentVariable($credentialName, $credentialValue, 'Process')
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($credentialPtr)
        $credentialValue = $null
    }
}
Write-Host 'Credenciais definidas somente neste terminal. Não foram salvas em arquivo.'
python bot.py wallet-preview
