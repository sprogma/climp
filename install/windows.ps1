param(
    $buildDirectory = "./build",
    $buildLibrary = $true
)

$global:buildLibrary = $buildLibrary


# helping functions --------------------------------------------------------------------------------------------


function Show-Error
{
    param(
        $message
    )
    Write-Host $message -Foreground 'red'
    Write-Error $message -ErrorAction SilentlyContinue
}


function Break-Installation
{
    if (Test-Path $buildDirectory -PathType Container)
    {
        Remove-Item -Recurse -Force $buildDirectory
    }
    Show-Error "Installation Interrupted."
    exit 1
}


function Write-GlobalProgress
{
    param(
        [string]$CurrentActivity,
        [single]$progress
    )
    Write-Host $CurrentActivity "..." -ForegroundColor "green"
    $progress = [Math]::round($progress * 100.0, 1)
    Write-Progress -Id 0 -Activity $CurrentActivity -Status "$progress% Complete:" -PercentComplete $progress
}

function Write-LocalProgress
{
    param(
        [string]$CurrentActivity,
        [single]$progress
    )
    Write-Host $CurrentActivity "..." -ForegroundColor "gray"
    $progress = [Math]::round($progress * 100.0, 1)
    Write-Progress -Id 1 -ParentId 0 -Activity $CurrentActivity -Status "$progress% Complete:" -PercentComplete $progress
}


# installation functions -------------------------------------------------------------------------------------


function Check-SystemStructure
{
    param()

    # powershell
    if ($psVersionTable.PSVersion.Major -lt 3)
    {
        Show-Error "You use too old powershell installation. need version 3.*.* and later"
        Break-Installation
    }

    # check python
    Write-LocalProgress "Checking python installed" 0.0
    
    $res = Invoke-Expression "python -V" 2>$null
    if ($res -eq $null)
    {
        Show-Error "Python installation not found. May be it isn't in path;"
        Write-Host "you must install python to use this program" -ForegroundColor "gray"
        Break-Installation
    }
    try
    {
        $version = $res -split '\.'
        if ($version[0] -lt 2  -or
            ($version[0] -eq 3 -and $version[1] -lt 7))
        {
            Write-Warning "Python version ($res) is less, than 3.7.*"
            $choices = [Management.Automation.Host.ChoiceDescription[]] ( `
            (new-Object Management.Automation.Host.ChoiceDescription "&Yes","Break installation"),
            (new-Object Management.Automation.Host.ChoiceDescription "&No","Continue installation [ignore warning]"));
            $answer = $host.ui.PromptForChoice("Ignore too low version, program may not work.","Break installation?",$choices,0)
            if ($answer -eq 0) {
                Break-Installation
            }
        }
    }
    catch
    {
        Show-Error "Comand 'python -V' returned version in bad format."
        exit 1
    }

    # check python libs
    Write-LocalProgress "Checking python library" 0.05

    $InstallAll = $false

    $libs = Get-Content "$PSScriptRoot/python_libs_win.txt"
    $cnt = 0
    
    $libs | Foreach-Object {
            $lib = $_

            $cnt++;
            Write-LocalProgress "Checking package: $lib" (0.05 + 0.45 * $cnt / $libs.length)
                
            $res = Invoke-Expression "python -m pip show $_" 2>$null
            if (!$res)
            {
                Show-Error "Not installed library $lib."
                if ($InstallAll)
                {
                    & python -m pip install $lib
                    if (!$?)
                    {
                        Show-Error "Error in '& python -m pip install $lib'"
                        Break-Installation
                    }
                }
                else
                {
                    $choices = [Management.Automation.Host.ChoiceDescription[]] (
                        (new-Object Management.Automation.Host.ChoiceDescription "&Break","Break installation"),
                        (new-Object Management.Automation.Host.ChoiceDescription "&Install","Install this library"),
                        (new-Object Management.Automation.Host.ChoiceDescription "Install&All","Install all next not installed libraries"))
                    $answer = $host.ui.PromptForChoice("Library $lib not found.","What to do?",$choices,0)
                    if ($answer -eq 0) 
                    {
                        Break-Installation
                    }
                    else # answer 1 or 2
                    {
                        & python -m pip install $lib
                        if (!$?)
                        {
                            Show-Error "Error in '& python -m pip install $lib'"
                            Break-Installation
                        }
                    }
                    if ($answer -eq 2)
                    {
                        $InstallAll = $true
                    }
                }
            }
        }

    if ($global:buildLibrary)
    {
        Write-LocalProgress "Checking gcc installation" 0.5
        $res = & gcc --version 2>$null
        if (!$?)
        {
            Show-Error "Gcc not installed. May be it isn't in path."
            $choices = [Management.Automation.Host.ChoiceDescription[]] (
                (new-Object Management.Automation.Host.ChoiceDescription "&Break","Break installation"),
                (new-Object Management.Automation.Host.ChoiceDescription "&Not Build Library","You can build library by yourself later. Install other parts"))
            $answer = $host.ui.PromptForChoice("gcc not found","What to do?",$choices,0)
            if ($answer -eq 0) 
            {
                Break-Installation
            }
            else
            {
                $global:buildLibrary = $false
            }
        }
    }
    if ($global:buildLibrary)
    {
        Write-LocalProgress "Checking openCL installation" 0.7
        $res = Invoke-Expression "gcc -l""openCL.dll"" 2>&1"
        if ($res -like "*-lopenCL.dll*")
        {
            Show-Error "gcc not found openCL.dll [if it is installed, you can build library by yourself]"
            $choices = [Management.Automation.Host.ChoiceDescription[]] (
                (new-Object Management.Automation.Host.ChoiceDescription "&Break","Break installation"),
                (new-Object Management.Automation.Host.ChoiceDescription "&Not Build Library","You can build library by yourself later. Install other parts"))
            $answer = $host.ui.PromptForChoice("Opencl.dll not found","What to do?",$choices,0)
            if ($answer -eq 0) 
            {
                Break-Installation
            }
            else
            {
                $global:buildLibrary = $false
            }
        }
    }
    Write-LocalProgress "All checked" 1.0
}


function Prepare-Installation
{
    param()

    # create build directory structure
    Write-LocalProgress "Creating directores" 0.0

    Remove-Item "$buildDirectory" -Force -Recurse 2>&1 | Out-Null
    New-Item -Type Directory "$buildDirectory" -Force | Out-Null

    $cnt = 0
    $dirs = @('code', 'tmp')
    $dirs | Foreach-Object {
        $cnt++
        Write-LocalProgress "Create directory $_" ($cnt/$dirs.length * 0.3 + 0.1)
        New-Item -Type Directory "$buildDirectory/$_" -Force | Out-Null
    }

    # copy code
    Write-LocalProgress "Copy files" 0.4
    Copy-Item "./source/*.py" "$buildDirectory/code" | Out-Null

    # copy scripts
    Write-LocalProgress "Copy scripts" 0.7
    Copy-Item "./install/run_scripts/win/*" "$buildDirectory" | Out-Null

    Write-LocalProgress "All copied" 1.0
}


function Build-SharedLibrary
{
    param()

    Write-LocalProgress "Checking system structure" 0.0
    Show-Error "Not Implemented."
    sleep 1.0
    Break-Installation
}


function End-Installation
{
    param()
}

# Check for system abilities
Write-GlobalProgress "Checking system structure" 0.0
Check-SystemStructure
Write-Host "OK." -ForegroundColor "green"

# Create installation directory
Write-GlobalProgress "Creating installation directory" 0.6
Prepare-Installation
Write-Host "OK." -ForegroundColor "green"

# Build shared library
if ($global:buildLibrary)
{
    Write-GlobalProgress "Building shared library" 0.7
    Build-SharedLibrary
    Write-Host "OK." -ForegroundColor "green"   
}
else
{
    Write-Warning "Not building library..."
}

# Create runable files
Write-GlobalProgress "End intallation" 0.9
End-Installation
Write-Host "OK." -ForegroundColor "green"
Write-GlobalProgress "Finishing" 1.0

Write-Host "Climp music player successfully installed in $buildDirectory directory" -ForegroundColor "green"
