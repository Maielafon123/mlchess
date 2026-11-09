[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('init', 'backup', 'verify')]
    [string] $Action,
    [Parameter(Mandatory)]
    [string] $ResticPath,
    [Parameter(Mandatory)]
    [string] $SshTarget,
    [string] $BackupRoot = (Join-Path $env:LOCALAPPDATA 'MLChess\Backups'),
    [string] $Snapshot
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security.Cryptography.ProtectedData
$root = [IO.Path]::GetFullPath($BackupRoot)
$keyFile = Join-Path $root 'repository-key.dpapi'
$scope = [Security.Cryptography.DataProtectionScope]::CurrentUser
$repository = Join-Path $root 'postgres-restic'
$restic = (Resolve-Path -LiteralPath $ResticPath).ProviderPath

if ($Action -eq 'init') {
    if (Test-Path -LiteralPath $repository) {
        throw 'The backup repository already exists. Use backup or verify.'
    }
    [IO.Directory]::CreateDirectory($root) | Out-Null
    if (-not (Test-Path -LiteralPath $keyFile)) {
        $key = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
        try {
            $encrypted = [Security.Cryptography.ProtectedData]::Protect($key, $null, $scope)
            $file = [IO.File]::Open($keyFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $file.Write($encrypted, 0, $encrypted.Length) }
            finally { $file.Dispose() }
        } finally { [Array]::Clear($key) }
    }
} elseif (-not (Test-Path -LiteralPath (Join-Path $repository 'config') -PathType Leaf)) {
    throw 'The backup repository has not been initialized.'
}

$secret = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($keyFile), $null, $scope)
$priorPassword = $env:RESTIC_PASSWORD
try {
    $env:RESTIC_PASSWORD = [Convert]::ToBase64String($secret)
    $parameters = @((Join-Path $PSScriptRoot 'offsite_backup.py'), '--restic', $restic, '--repo', $repository, '--ssh', $SshTarget, $Action)
    if ($Snapshot) { $parameters += @('--snapshot', $Snapshot) }
    & python @parameters
    if ($LASTEXITCODE -ne 0) { throw 'The backup operation did not complete.' }
} finally {
    $env:RESTIC_PASSWORD = $priorPassword
    [Array]::Clear($secret)
}
