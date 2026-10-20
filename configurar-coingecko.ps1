$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$chaveSegura = Read-Host 'CoinGecko Demo API key (entrada oculta)' -AsSecureString
$chavePtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($chaveSegura)
try {
    $env:COINGECKO_DEMO_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($chavePtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($chavePtr)
}
Write-Host 'Validando uma consulta no endpoint oficial. A chave nao sera salva em arquivo.'
python coingecko_feed.py --check-key
if ($LASTEXITCODE -ne 0) { throw 'Validacao CoinGecko falhou. Confira o diagnostico acima; nao envie a chave no chat.' }
Write-Host 'CoinGecko validada. Chave definida somente neste terminal. Execute python iniciar.py.'
