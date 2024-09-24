if ($PSVersionTable.PSVersion.Major -lt 4)
{
    Write-Warning "This version of powershell is unsupported. use powershell 3+ istead."
    Exit 1
}

py ($PSScriptRoot + "\release\music_player.py")
