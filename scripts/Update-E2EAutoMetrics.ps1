<#
============================================================================
 File: Update-E2EAutoMetrics.ps1
 Version: 1.0
 Purpose: Update only the Auto Metrics section in e2e-to-do.md every 120 seconds
          with objective data (timestamp and scenario file count/list).
          This script NEVER alters any Status lines.
============================================================================
#>
# ============================================================================
# SECTION 1: Global VAR definitions
# ============================================================================
# User-configurable variables (top of file per standards)
$TodoPath = 'D:/Program Files/Dev/Projects/Gemini-Agent/e2e-to-do.md'
$ScenariosDir = 'D:/Program Files/Dev/Projects/Gemini-Agent/tests/e2e/scenarios'
$IntervalSeconds = 120
$BeginMarker = '# BEGIN AUTO METRICS'
$EndMarker = '# END AUTO METRICS'
$DateFormat = 'ddMMMyy HH:mm:ss'

# ============================================================================
# SECTION 2: Functions
# ============================================================================

function Get-DateStamp {
    <#
    Purpose: Return current UTC timestamp formatted as DDMMMYY HH:mm:ss in uppercase.
    #>
    $ts = [System.DateTime]::UtcNow.ToString($DateFormat, [System.Globalization.CultureInfo]::InvariantCulture)
    return $ts.ToUpper()
}

function Get-ScenarioFiles {
    <#
    Purpose: Return list of .json scenario files under the scenarios directory.
    #>
    if (-not (Test-Path -LiteralPath $ScenariosDir)) { return @() }
    $files = Get-ChildItem -LiteralPath $ScenariosDir -Filter *.json -File -ErrorAction SilentlyContinue
    if ($null -eq $files) { return @() }
    # Convert to relative file names for readability
    $names = @()
    foreach ($f in $files) {
        # Each iteration collects file names; high comment frequency maintained
        $names += $f.Name
    }
    return ($names | Sort-Object)
}

function Build-AutoMetricsContent {
    <#
    Purpose: Build the lines of the Auto Metrics section between the markers.
    #>
    $ts = Get-DateStamp
    $scenarioFiles = Get-ScenarioFiles
    $count = $scenarioFiles.Count

    $lines = @()
    $lines += $BeginMarker
    $lines += 'Auto Metrics (read-only): objective info only; Status lines above are not modified by automation.'
    $lines += ('Last update (UTC): ' + $ts)
    $lines += ('Scenario files present under tests/e2e/scenarios/: ' + $count)
    $lines += 'Files:'
    if ($count -gt 0) {
        # Loop to list each file with a dash prefix
        foreach ($name in $scenarioFiles) {
            $lines += ('- ' + $name)
        }
    }
    else {
        $lines += '- None'
    }
    $lines += $EndMarker
    return $lines
}

function Update-AutoMetricsSection {
    <#
    Purpose: Replace the content between markers with rebuilt Auto Metrics content.
             Create the section if markers are missing. Only this section is changed.
    #>
    if (-not (Test-Path -LiteralPath $TodoPath)) { return $false }
    $orig = Get-Content -LiteralPath $TodoPath -Encoding UTF8
    $beginIndex = -1
    $endIndex = -1

    # Find marker indices with a simple linear scan
    for ($i = 0; $i -lt $orig.Count; $i = $i + 1) {
        $line = $orig[$i]
        if ($line -eq $BeginMarker) { $beginIndex = $i }
        if ($line -eq $EndMarker) { $endIndex = $i }
    }

    $metrics = Build-AutoMetricsContent

    if ($beginIndex -ge 0 -and $endIndex -ge 0 -and $endIndex -gt $beginIndex) {
        # Replace existing section
        $new = @()
        for ($j = 0; $j -lt $beginIndex; $j = $j + 1) { $new += $orig[$j] }
        foreach ($m in $metrics) { $new += $m }
        for ($j = $endIndex + 1; $j -lt $orig.Count; $j = $j + 1) { $new += $orig[$j] }

        # Write changes only if content differs
        $changed = $false
        if ($new.Count -ne $orig.Count) { $changed = $true }
        else {
            for ($k = 0; $k -lt $new.Count; $k = $k + 1) {
                if ($new[$k] -ne $orig[$k]) { $changed = $true; break }
            }
        }
        if ($changed) {
            try {
                Set-Content -LiteralPath $TodoPath -Value $new -Encoding UTF8 -NoNewline:$false
            }
            catch {
                # Error handling: ignore transient write errors (file may be locked)
            }
            return $true
        }
        return $false
    }
    else {
        # Append section at end if markers missing
        $appended = @()
        $appended += $orig
        foreach ($m in $metrics) { $appended += $m }
        try {
            Set-Content -LiteralPath $TodoPath -Value $appended -Encoding UTF8 -NoNewline:$false
        }
        catch {
            # Error handling: ignore transient write errors
        }
        return $true
    }
}

# ============================================================================
# SECTION 3: Process - Main Loop
# ============================================================================
# Periodically rebuild only the Auto Metrics section. This loop is intentionally simple
# and never alters Status lines or any other part of the file.
while ($true) {
    [void](Update-AutoMetricsSection)
    Start-Sleep -Seconds $IntervalSeconds
}
