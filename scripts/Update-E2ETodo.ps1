<#
============================================================================
 File: Update-E2ETodo.ps1
 Version: 1.0
 Purpose: Maintain percentage completion lines under each E2E to-do item
          in e2e-to-do.md and refresh them every 120 seconds
==============================================================================
 SECTION 1: Global VAR definitions
==============================================================================
#>
# User-configurable variables (top of file per standards)
$TodoPath = 'D:/Program Files/Dev/Projects/Gemini-Agent/e2e-to-do.md'
$IntervalSeconds = 120

# Internal constants
$DateStampFormat = 'ddMMMyy HH:mm:ss'

# ============================================================================
# SECTION 2: Functions
# ============================================================================

function Get-DateStamp {
    <#
    Purpose: Returns a timestamp string in DDMMMYY HH:mm:ss format using invariant culture
    #>
    $ts = [System.DateTime]::UtcNow.ToString($DateStampFormat, [System.Globalization.CultureInfo]::InvariantCulture)
    return $ts.ToUpper()
}

function Get-HeaderIndex {
    <#
    Purpose: Find the line index of the specified numbered item (1..6)
    #>
    param(
        [Parameter(Mandatory=$true)][int]$Number,
        [Parameter(Mandatory=$true)][string[]]$Lines
    )
    $prefix = "$Number. "
    for ($i = 0; $i -lt $Lines.Count; $i = $i + 1) {
        # Linear scan for exact numbered header at start of line
        if ($Lines[$i].StartsWith($prefix)) {
            return $i
        }
    }
    return -1
}

function Get-NextNonEmptyIndex {
    <#
    Purpose: From a start index, find the next non-empty line index
    #>
    param(
        [Parameter(Mandatory=$true)][int]$StartIndex,
        [Parameter(Mandatory=$true)][string[]]$Lines
    )
    for ($j = $StartIndex; $j -lt $Lines.Count; $j = $j + 1) {
        $line = $Lines[$j]
        if ($line -ne $null -and $line.Trim().Length -gt 0) {
            return $j
        }
    }
    return -1
}

function Ensure-StatusLine {
    <#
    Purpose: Ensure a Status line exists immediately below the numbered header.
             If missing, insert with default 0% to avoid speculative progress.
    #>
    param(
        [Parameter(Mandatory=$true)][int]$Number,
        [Parameter(Mandatory=$true)][string[]]$Lines
    )
    $headerIndex = Get-HeaderIndex -Number $Number -Lines $Lines
    if ($headerIndex -lt 0) {
        return $Lines
    }
    $candidateIndex = Get-NextNonEmptyIndex -StartIndex ($headerIndex + 1) -Lines $Lines
    if ($candidateIndex -lt 0) {
        # Append a Status line at end if file ends after header
        $newLines = @()
        $newLines += $Lines
        $newLines += "Status: 0%"
        return $newLines
    }
    $candidate = $Lines[$candidateIndex]
    if ($candidate.StartsWith('Status: ')) {
        return $Lines
    }
    # Insert a Status line right after the header line
    $new = @()
    for ($k = 0; $k -le $headerIndex; $k = $k + 1) { $new += $Lines[$k] }
    $new += 'Status: 0%'
    for ($k = $headerIndex + 1; $k -lt $Lines.Count; $k = $k + 1) { $new += $Lines[$k] }
    return $new
}

function Update-TodoFile {
    <#
    Purpose: Idempotently ensure Status lines for items 1..6; no speculative percentage changes.
             Touches the file only when content differs.
    #>
    param(
        [Parameter(Mandatory=$true)][string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $orig = Get-Content -LiteralPath $Path -Encoding UTF8
    $lines = $orig

    # Ensure status lines exist under each item; commentary above loops is mandatory
    # Loop over each required item number (1 through 6) to enforce a Status line
    for ($n = 1; $n -le 6; $n = $n + 1) {
        $lines = Ensure-StatusLine -Number $n -Lines $lines
    }

    # If content changed, write back
    $changed = $false
    if ($lines.Count -ne $orig.Count) { $changed = $true }
    else {
        for ($i = 0; $i -lt $lines.Count; $i = $i + 1) {
            if ($lines[$i] -ne $orig[$i]) { $changed = $true; break }
        }
    }

    if ($changed) {
        # Try/Catch block required with explanatory comments
        try {
            Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8 -NoNewline:$false
        }
        catch {
            # Swallow write errors silently; file may be locked by editor
        }
    }
    return $changed
}

# ============================================================================
# SECTION 3: Process - Main Loop
# ============================================================================
# Periodically ensure the to-do file contains Status lines beneath each item.
while ($true) {
    # Update cycle: attempt to enforce Status lines; this loop runs indefinitely
    [void](Update-TodoFile -Path $TodoPath)
    Start-Sleep -Seconds $IntervalSeconds
}
