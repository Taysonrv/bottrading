$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$chaveSegura = Read-Host 'CoinGecko Demo API key (entrada oculta)' -AsSecureString
$chavePtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($chaveSegura)
try {
    $env:COINGECKO_DEMO_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($chavePtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($chavePtr)
}
Write-Host 'Chave definida somente neste terminal. Execute python iniciar.py. Nao compartilhe a chave.'
