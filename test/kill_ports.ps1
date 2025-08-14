<#
.SYNOPSIS
    Kills all processes using ports in the specified range.
.DESCRIPTION
    This script finds and terminates all processes using TCP ports within the specified range.
    It requires administrative privileges to terminate processes.
.NOTES
    Author: Cascade
    Date:   2025-08-03
#>

#Requires -RunAsAdministrator

# Define port range
$startPort = 9000
$endPort = 9150

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Searching for processes using ports $startPort-$endPort..."

# Get all TCP connections in the specified port range
$connections = Get-NetTCPConnection -State Listen | Where-Object { 
    $_.LocalPort -ge $startPort -and $_.LocalPort -le $endPort 
}

if ($connections) {
    Write-Host "Found the following processes:"
    $connections | ForEach-Object {
        $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "- Port $($_.LocalPort): $($process.ProcessName) (PID: $($process.Id))"
            try {
                Stop-Process -Id $process.Id -Force -ErrorAction Stop
                Write-Host "  Successfully terminated process $($process.Id)" -ForegroundColor Green
            } catch {
                Write-Host "  Failed to terminate process $($process.Id): $_" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "No processes found using ports $startPort-$endPort" -ForegroundColor Yellow
}

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Port cleanup complete"
