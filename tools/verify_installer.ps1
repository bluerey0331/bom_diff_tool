param(
    [Parameter(Mandatory)] [string] $Installer,
    [string] $TestRoot = $env:RUNNER_TEMP,
    [string] $ResultPath
)

$ErrorActionPreference = 'Stop'
$setup = (Resolve-Path -LiteralPath $Installer).Path
$directory = Join-Path (Resolve-Path -LiteralPath $TestRoot).Path ('bom-install-' + [Guid]::NewGuid().ToString('N'))
$app = Join-Path $directory 'app'
$links = Join-Path ([Environment]::GetFolderPath('Programs')) 'BOM Diff Tool'
$existing = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BOMDiffTool_is1',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BOMDiffTool_is1',
    $links
)
if ($existing | Where-Object { Test-Path -LiteralPath $_ }) {
    throw 'An existing installation or shortcut folder prevents an isolated test.'
}
New-Item -ItemType Directory -Path $directory | Out-Null

function Invoke-CheckedProcess($FilePath, $Arguments) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $directory -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$(Split-Path $FilePath -Leaf) returned $($process.ExitCode)"
    }
}

try {
    Invoke-CheckedProcess $setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$app`"")
    if (@(Get-ChildItem -LiteralPath $links -Filter '*.lnk').Count -ne 2) {
        throw 'Expected two Start menu shortcuts.'
    }
    $originalLocalAppData = $env:LOCALAPPDATA
    try {
        $env:LOCALAPPDATA = $directory
        foreach ($name in @('BOM Diff Tool.exe', 'BOM Diff Tool (English).exe')) {
            $output = Join-Path $directory ($name + '.xlsx')
            $old = Join-Path $app 'samples/demo_old_bom.xlsx'
            $new = Join-Path $app 'samples/demo_new_bom.xlsx'
            Invoke-CheckedProcess (Join-Path $app $name) @('--cli', '--old', "`"$old`"", '--new', "`"$new`"", '--output', "`"$output`"")
            if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
                throw "The demo did not produce an Excel report for $name."
            }
        }
    } finally {
        $env:LOCALAPPDATA = $originalLocalAppData
    }
} finally {
    $uninstaller = Join-Path $app 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        Invoke-CheckedProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
        if (Test-Path -LiteralPath $links) {
            throw 'The uninstaller did not remove the test shortcuts.'
        }
    }
}
Write-Output 'Installer, both demo runs, and uninstall verified.'
if ($ResultPath) {
    [ordered]@{
        status = 'passed'
        windows_version = [Environment]::OSVersion.VersionString
        installer_sha256 = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
        checks = @('installation', 'Start menu shortcuts', 'Japanese and English CLI Excel exports', 'uninstall')
    } | ConvertTo-Json | Set-Content -LiteralPath $ResultPath -Encoding utf8
}
