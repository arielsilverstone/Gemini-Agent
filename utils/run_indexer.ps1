<#
##############################################################################
#                             run_indexer.ps1                                #
# Purpose: Runs the codebase indexer with the specified parameters.          #
##############################################################################
#>

# Set the working directory to the script's directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

# Path to Python executable (use the same one as VS Code)
$pythonExe = (Get-Command python).Source

# Set log file path in utils directory
$logFile = Join-Path $scriptDir "codebase_indexer.log"

# Run the indexer with the specified parameters
& $pythonExe "$scriptDir\codebase_indexer.py" "$projectRoot" -o "$scriptDir\codebase_index.json" -i 600 --log "$logFile"

#
#
# END run_indexer.ps1
