param(
    [ValidateSet('Install', 'Uninstall', 'Status')][string]$Action = 'Install',
    [string]$PackageRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }),
    [string]$StateHome = (Join-Path $env:LOCALAPPDATA 'ShuanglingCodexPet\PetOnly')
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$names = @('spritesheet.webp', 'pet.json')
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$StateHome = [IO.Path]::GetFullPath($StateHome)
$petDir = Join-Path $CodexHome 'pets\shuangling-white-dragon'
$manifestPath = Join-Path $StateHome 'pet-installation.json'

function Get-BytesHash([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($Data))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}
function Get-FileDigest([string]$Path) { return Get-BytesHash ([IO.File]::ReadAllBytes($Path)) }
function Write-Atomic([string]$Path, [byte[]]$Data) {
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path))
    $temp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllBytes($temp, $Data)
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temp, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temp, $Path) }
    } finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
}
function Write-Json([string]$Path, $Value) {
    $json = ConvertTo-Json -InputObject $Value -Depth 12
    Write-Atomic $Path ((New-Object Text.UTF8Encoding($false)).GetBytes($json))
}
function Read-Json([string]$Path) {
    return ([IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) | ConvertFrom-Json)
}
function Assert-ManagedFiles($Record) {
    if ($Record.schema -ne 1 -or $Record.pet_directory -ne $petDir -or $Record.codex_home -ne $CodexHome) {
        throw 'Installation record belongs to a different location.'
    }
    foreach ($name in $names) {
        $path = Join-Path $petDir $name
        $expected = $Record.installed_hashes.PSObject.Properties[$name].Value
        if (![IO.File]::Exists($path) -or (Get-FileDigest $path) -ne $expected) {
            throw "Pet file changed after installation: $name. Back up your edits before updating or uninstalling."
        }
    }
}
function Restore-Current($Before) {
    foreach ($name in $names) {
        $path = Join-Path $petDir $name
        if ($null -eq $Before[$name]) {
            if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) }
        } elseif (![IO.File]::Exists($path) -or (Get-FileDigest $path) -ne (Get-BytesHash $Before[$name])) {
            Write-Atomic $path $Before[$name]
        }
    }
}

$key = Get-BytesHash ([Text.Encoding]::UTF8.GetBytes($CodexHome.ToLowerInvariant()))
$mutex = New-Object Threading.Mutex($false, ('Local\ShuanglingPet-' + $key.Substring(0, 24)))
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (!$locked) { throw 'Another pet installation is running. Wait for it to finish.' }
    $record = $null
    if ([IO.File]::Exists($manifestPath)) { $record = Read-Json $manifestPath }
    if ($Action -eq 'Status') {
        if ($record) { Assert-ManagedFiles $record }
        Write-Output (ConvertTo-Json @{managed = [bool]$record; pet_directory = $petDir} -Compress)
        exit 0
    }
    if ($record) { Assert-ManagedFiles $record }
    # The old full-suite installer has its own restore record for these files.
    # Do not create two overlapping managers for the same pet.
    $fullManifestPath = Join-Path (Split-Path -Parent $StateHome) 'installation.json'
    if ([IO.File]::Exists($fullManifestPath)) {
        $fullRecord = Read-Json $fullManifestPath
        foreach ($item in $fullRecord.files) {
            if ([IO.Path]::GetFullPath($item.path) -in @((Join-Path $petDir 'pet.json'), (Join-Path $petDir 'spritesheet.webp'))) {
                throw 'This pet is managed by the full suite. Use its existing Uninstall.cmd before switching to pet-only updates.'
            }
        }
    }
    $before = @{}
    foreach ($name in $names) {
        $path = Join-Path $petDir $name
        $before[$name] = $null
        if ([IO.File]::Exists($path)) { $before[$name] = [IO.File]::ReadAllBytes($path) }
    }
    if ($Action -eq 'Uninstall') {
        if (!$record) { throw 'No pet-only installation record found.' }
        $original = @($record.original_files)
        if ($original.Count -ne 2 -or @($original | Select-Object -ExpandProperty name -Unique).Count -ne 2) {
            throw 'Invalid backup record.'
        }
        $backupPrefix = [IO.Path]::GetFullPath((Join-Path $StateHome 'backups')) + [IO.Path]::DirectorySeparatorChar
        foreach ($item in $original) {
            if ($item.name -notin $names) { throw 'Invalid backup filename.' }
            if ($item.existed) {
                $full = [IO.Path]::GetFullPath($item.backup_path)
                if (!$full.StartsWith($backupPrefix, [StringComparison]::OrdinalIgnoreCase) -or
                    ![IO.File]::Exists($full) -or (Get-FileDigest $full) -ne $item.sha256) {
                    throw 'Backup validation failed. Installed pet left unchanged.'
                }
            }
        }
        try {
            foreach ($item in $original) {
                $target = Join-Path $petDir $item.name
                if ($item.existed) { Write-Atomic $target ([IO.File]::ReadAllBytes($item.backup_path)) }
                elseif ([IO.File]::Exists($target)) { [IO.File]::Delete($target) }
            }
            [IO.File]::Delete($manifestPath)
        } catch { Restore-Current $before; throw }
        Write-Output 'Uninstalled pet. Previous files restored; backup history retained.'
        exit 0
    }

    $sourceDir = Join-Path ([IO.Path]::GetFullPath($PackageRoot)) 'pet'
    $sourceManifest = Read-Json (Join-Path $sourceDir 'package-manifest.json')
    if ($sourceManifest.schema -ne 1) { throw 'Unsupported package manifest.' }
    $sources, $hashes = @{}, @{}
    foreach ($name in $names) {
        $sources[$name] = [IO.File]::ReadAllBytes((Join-Path $sourceDir $name))
        $hashes[$name] = Get-BytesHash $sources[$name]
        if ($hashes[$name] -ne $sourceManifest.files.PSObject.Properties[$name].Value) {
            throw "Package checksum failed: $name. Download and extract the complete package again."
        }
    }
    $metadata = [Text.Encoding]::UTF8.GetString($sources['pet.json']).TrimStart([char]0xFEFF) | ConvertFrom-Json
    if ($metadata.id -ne 'shuangling-white-dragon' -or $metadata.spriteVersionNumber -ne 2 -or
        $metadata.spritesheetPath -ne 'spritesheet.webp') { throw 'Unexpected pet metadata.' }
    $webp = $sources['spritesheet.webp']
    if ($webp.Length -lt 12 -or [Text.Encoding]::ASCII.GetString($webp, 0, 4) -ne 'RIFF' -or
        [Text.Encoding]::ASCII.GetString($webp, 8, 4) -ne 'WEBP') { throw 'Invalid WebP header.' }
    if ($record -and $hashes['pet.json'] -eq $record.installed_hashes.'pet.json' -and
        $hashes['spritesheet.webp'] -eq $record.installed_hashes.'spritesheet.webp') {
        Write-Output 'Already up to date.'
        exit 0
    }
    if (!$record) {
        $backup = Join-Path $StateHome ('backups\' + [Guid]::NewGuid().ToString('N'))
        $original = @()
        foreach ($name in $names) {
            $saved = Join-Path $backup $name
            $existed = $null -ne $before[$name]
            $oldHash = $null
            if ($existed) { Write-Atomic $saved $before[$name]; $oldHash = Get-BytesHash $before[$name] }
            $original += @{name = $name; existed = $existed; backup_path = $saved; sha256 = $oldHash}
        }
        $record = [pscustomobject]@{schema = 1; codex_home = $CodexHome; pet_directory = $petDir;
                                  original_files = $original; installed_hashes = $hashes}
    } else { $record.installed_hashes = $hashes }
    try {
        foreach ($name in $names) { Write-Atomic (Join-Path $petDir $name) $sources[$name] }
        foreach ($name in $names) {
            if ((Get-FileDigest (Join-Path $petDir $name)) -ne $hashes[$name]) { throw 'Installed checksum mismatch.' }
        }
        Write-Json $manifestPath $record
    } catch { Restore-Current $before; throw }
    Write-Output 'Installed pet. Refresh the Codex pet list and select Shuangling. Restart Codex if needed.'
} catch {
    [Console]::Error.WriteLine(('ERROR: ' + $_.Exception.Message))
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
