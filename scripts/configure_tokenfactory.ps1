# Store a rotated service key locally without echoing it or contacting a server.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$secureKey = $null
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Windows DPAPI is required.' }
    $repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $secretRoot = Join-Path $repository '.secrets'
    $privateDirectory = Join-Path $secretRoot 'tokenfactory'
    $keyPath = Join-Path $privateDirectory 'api-key.clixml'
    $ancestor = Get-Item -LiteralPath $repository -Force
    while ($null -ne $ancestor) {
        if ($ancestor -isnot [IO.DirectoryInfo] -or ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'The repository must have real directory ancestors.'
        }
        $ancestor = $ancestor.Parent
    }
    foreach ($directory in @($secretRoot, $privateDirectory)) {
        if (Test-Path -LiteralPath $directory) {
            $item = Get-Item -LiteralPath $directory -Force
            if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw 'Secret directories must not be files or reparse points.'
            }
        }
    }
    if (Test-Path -LiteralPath $keyPath) { throw 'Refusing to overwrite an existing credential.' }
    & git -C $repository check-ignore --quiet -- '.secrets/tokenfactory/api-key.clixml'
    if ($LASTEXITCODE -ne 0) { throw 'The credential path must be ignored by Git.' }
    [IO.Directory]::CreateDirectory($privateDirectory) | Out-Null
    $privateAcl = [Security.AccessControl.DirectorySecurity]::new()
    $privateAcl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @(
        [Security.Principal.WindowsIdentity]::GetCurrent().User,
        [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
        [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    )) {
        $privateAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    Set-Acl -LiteralPath $privateDirectory -AclObject $privateAcl
    $secureKey = Read-Host 'Rotated TokenFactory key (private; not sent anywhere)' -AsSecureString
    if ($secureKey.Length -lt 1 -or $secureKey.Length -gt 4096) {
        throw 'A nonempty bounded credential is required.'
    }
    # On Windows, Export-Clixml uses this user's DPAPI context for SecureString.
    # NoClobber preserves any credential created concurrently after the check.
    Export-Clixml -InputObject $secureKey -LiteralPath $keyPath -NoClobber -Encoding UTF8
    Write-Output 'Stored the encrypted key in the ignored, restricted TokenFactory directory.'
    Write-Output 'No API request was made. Rotation and image/quota authorization must be confirmed separately.'
} catch {
    # Do not emit PowerShell's detailed error record or any credential input.
    [Console]::Error.WriteLine('TokenFactory key setup failed. Check Windows, directory permissions, Git exclusion, and whether a credential already exists. No existing key was replaced.')
    exit 1
} finally {
    if ($null -ne $secureKey) { $secureKey.Dispose() }
}
