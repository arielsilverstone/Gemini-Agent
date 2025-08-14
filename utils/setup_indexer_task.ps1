<#
.SYNOPSIS
    Sets up a Windows Scheduled Task to run the codebase indexer.
.DESCRIPTION
    Creates a scheduled task that runs the codebase indexer every 10 minutes
    between 8 AM and 10 PM.
#>

# Requires administrator privileges
#Requires -RunAsAdministrator

# Script parameters
$TaskName = "GeminiCodebaseIndexer"
$TaskPath = "\ariel\"
$ScriptPath = "$PSScriptRoot\run_indexer.ps1"
$StartTime = "08:00"
$EndTime = "22:00"
$IntervalMinutes = 10

# Set the working directory to the script's parent directory
$WorkingDirectory = $PSScriptRoot

# Create the scheduled task action with working directory
$Action = New-ScheduledTaskAction -WorkingDirectory $WorkingDirectory `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Create the scheduled task trigger (every 10 minutes between 8 AM and 10 PM)
$Trigger = New-ScheduledTaskTrigger -Once -At $StartTime -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Hours 14)

# Set the task to run with highest privileges and only when user is logged on
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

# Create the task
$Task = Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force

# Export the task XML to file
$XmlPath = Join-Path $PSScriptRoot "$TaskName.xml"
Export-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath | Out-File -FilePath $XmlPath -Encoding utf8

Write-Host "Scheduled task '$TaskPath$TaskName' has been created." -ForegroundColor Green
Write-Host "It will run every $IntervalMinutes minutes between $StartTime and $EndTime." -ForegroundColor Green
Write-Host "Task XML exported to: $XmlPath" -ForegroundColor Cyan
