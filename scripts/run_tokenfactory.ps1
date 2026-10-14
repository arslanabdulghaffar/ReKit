# Explicit authorized operations. Decrypt only for a local check or owned child.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Discover', 'Catalog', 'Quota', 'Qualify', 'Diagnose', 'CheckCredential')]
    [string]$Action,
    [switch]$Authorized
)

$ErrorActionPreference = 'Stop'
$secureKey = $null
$keyPointer = [IntPtr]::Zero
$child = $null
$startInfo = $null
$result = 1

function Assert-PrivateAccess([string]$Path, [bool]$RequireProtected = $false) {
    $permitted = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value,
                   'S-1-5-18', 'S-1-5-32-544')
    $acl = Get-Acl -LiteralPath $Path
    if ($RequireProtected -and -not $acl.AreAccessRulesProtected) {
        throw 'The credential directory must have protected access rules.'
    }
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $permitted) {
        throw 'Unexpected private file owner.'
    }
    foreach ($rule in $acl.Access) {
        if ($rule.AccessControlType -eq 'Allow' -and
            $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin $permitted) {
            throw 'Unexpected private access rule.'
        }
    }
}

try {
    if ($Action -ne 'CheckCredential' -and -not $Authorized) { throw 'Explicit prior authorization is required.' }
    if ($env:OS -ne 'Windows_NT') { throw 'Windows DPAPI is required.' }
    $repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $privateDirectory = Join-Path $repository '.secrets\tokenfactory'
    $keyPath = Join-Path $privateDirectory 'api-key.clixml'
    $outputDirectory = Join-Path $privateDirectory 'qualification'
    foreach ($target in @($privateDirectory, $outputDirectory)) {
        $ancestor = [IO.DirectoryInfo]::new($target)
        while ($null -ne $ancestor) {
            if ($ancestor.Exists -and ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw 'Real directory ancestors are required.'
            }
            $ancestor = $ancestor.Parent
        }
    }
    $keyItem = Get-Item -LiteralPath $keyPath -Force
    if ($keyItem.PSIsContainer -or ($keyItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $keyItem.Length -gt 65536) {
        throw 'Invalid private credential file.'
    }
    foreach ($ignoredPath in @('.secrets/tokenfactory/api-key.clixml',
                               '.secrets/tokenfactory/qualification/discovery.json',
                               '.secrets/tokenfactory/qualification/catalog-discovery.json',
                               '.secrets/tokenfactory/qualification/quota-discovery.json',
                               '.secrets/tokenfactory/qualification/synthetic-first.json',
                               '.secrets/tokenfactory/qualification/synthetic-diagnostic.json',
                               '.secrets/tokenfactory/qualification/dashboard-evidence.json',
                               '.secrets/tokenfactory/qualification/generation-attempts.sqlite3',
                               '.secrets/tokenfactory/qualification/generation-attempts.sqlite3-journal',
                               '.secrets/tokenfactory/qualification/generation-attempts.sqlite3-wal',
                               '.secrets/tokenfactory/qualification/generation-attempts.sqlite3-shm')) {
        & git -C $repository check-ignore --quiet -- $ignoredPath
        if ($LASTEXITCODE -ne 0) { throw 'Each private file must be ignored by Git.' }
    }
    # Setup already protected this parent. Validate it rather than rewriting an
    # existing descriptor, which can require privileges absent from this session.
    Assert-PrivateAccess $privateDirectory $true
    Assert-PrivateAccess $keyPath
    if ($Action -ne 'CheckCredential') { [IO.Directory]::CreateDirectory($outputDirectory) | Out-Null }
    if (Test-Path -LiteralPath $outputDirectory) { Assert-PrivateAccess $outputDirectory }
    foreach ($receiptName in @('discovery.json', 'catalog-discovery.json', 'quota-discovery.json',
                               'synthetic-first.json', 'synthetic-diagnostic.json', 'dashboard-evidence.json', 'generation-attempts.sqlite3',
                               'generation-attempts.sqlite3-journal', 'generation-attempts.sqlite3-wal',
                               'generation-attempts.sqlite3-shm')) {
        $receiptPath = Join-Path $outputDirectory $receiptName
        if (Test-Path -LiteralPath $receiptPath) {
            $receiptItem = Get-Item -LiteralPath $receiptPath -Force
            if ($receiptItem.PSIsContainer -or ($receiptItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw 'Invalid private artifact.'
            }
            Assert-PrivateAccess $receiptPath
        }
    }
    $secureKey = Import-Clixml -LiteralPath $keyPath
    if ($secureKey -isnot [Security.SecureString] -or $secureKey.Length -lt 1 -or $secureKey.Length -gt 4096) {
        throw 'Invalid private credential.'
    }
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    for ($index = 0; $index -lt $secureKey.Length; $index++) {
        $character = [Runtime.InteropServices.Marshal]::ReadInt16($keyPointer, $index * 2)
        if ($character -lt 33 -or $character -gt 126) { throw 'Invalid private credential characters.' }
    }
    if ($Action -eq 'CheckCredential') {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        $keyPointer = [IntPtr]::Zero
        $result = 0
        Write-Output 'TokenFactory local credential setup verified. No inference process or network request was started; account access and quota remain unverified.'
    } else {
        $startInfo = [Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = Join-Path $repository '.venv\Scripts\python.exe'
        if ($Action -eq 'Diagnose') {
            $startInfo.Arguments = 'evaluation/run_tokenfactory_qualification.py --authorized-diagnostic'
            $receiptRelativePath = '.secrets/tokenfactory/qualification/synthetic-diagnostic.json'
        } elseif ($Action -eq 'Qualify') {
            $startInfo.Arguments = 'evaluation/run_tokenfactory_qualification.py --authorized-synthetic'
            $receiptRelativePath = '.secrets/tokenfactory/qualification/synthetic-first.json'
        } elseif ($Action -eq 'Quota') {
            $startInfo.Arguments = 'evaluation/tokenfactory_discovery.py --authorized-official-quota'
            $receiptRelativePath = '.secrets/tokenfactory/qualification/quota-discovery.json'
        } elseif ($Action -eq 'Catalog') {
            $startInfo.Arguments = 'evaluation/tokenfactory_discovery.py --catalog-after-unusable-usage'
            $receiptRelativePath = '.secrets/tokenfactory/qualification/catalog-discovery.json'
        } else {
            $startInfo.Arguments = 'evaluation/tokenfactory_discovery.py --authorized-discovery'
            $receiptRelativePath = '.secrets/tokenfactory/qualification/discovery.json'
        }
        $startInfo.WorkingDirectory = $repository
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        # Never modify the parent PowerShell environment or put the key in argv.
        $startInfo.EnvironmentVariables['REKIT_INFERENCE_API_KEY'] = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        $keyPointer = [IntPtr]::Zero
        $child = [Diagnostics.Process]::Start($startInfo)
        $startInfo.EnvironmentVariables.Remove('REKIT_INFERENCE_API_KEY')
        # Hidden children still need valid output handles. Drain both streams
        # concurrently without decoding, retaining, or echoing untrusted output.
        $stdoutDrain = $child.StandardOutput.BaseStream.CopyToAsync([IO.Stream]::Null)
        $stderrDrain = $child.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null)
        $child.WaitForExit()
        [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdoutDrain, $stderrDrain))
        $result = $child.ExitCode
        Write-Output ('TokenFactory ' + $Action + ' finished with exit code ' + $result + '. Receipt path: ' + $receiptRelativePath)
    }
} catch {
    [Console]::Error.WriteLine('TokenFactory operation did not complete. Check the encrypted local setup and sanitized receipt. No credential details are logged.')
} finally {
    if ($keyPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
    if ($null -ne $startInfo) { $startInfo.EnvironmentVariables.Remove('REKIT_INFERENCE_API_KEY') }
    if ($null -ne $secureKey -and $secureKey -is [IDisposable]) { $secureKey.Dispose() }
    if ($null -ne $child) {
        try {
            if (-not $child.HasExited) {
                # Windows PowerShell 5 lacks Process.Kill(entireProcessTree).
                # This PID is the process owned by this invocation, never user input.
                $stopInfo = [Diagnostics.ProcessStartInfo]::new()
                $stopInfo.FileName = Join-Path $env:SystemRoot 'System32\taskkill.exe'
                $stopInfo.Arguments = '/PID ' + $child.Id + ' /T /F'
                $stopInfo.UseShellExecute = $false
                $stopInfo.CreateNoWindow = $true
                $stopInfo.RedirectStandardOutput = $true
                $stopInfo.RedirectStandardError = $true
                $stopper = [Diagnostics.Process]::Start($stopInfo)
                try {
                    if (-not $stopper.WaitForExit(5000)) { $stopper.Kill() }
                } finally { $stopper.Dispose() }
            }
        } catch {
            [Console]::Error.WriteLine('Owned discovery process cleanup could not be confirmed; do not retry automatically.')
        } finally { $child.Dispose() }
    }
}
exit $result
