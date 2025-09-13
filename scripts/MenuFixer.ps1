#requires -version 5.1

<#+============================================================
    MenuFixer.ps1 - PowerShell 5.1 menu system
============================================================#>

function Show-Menu {
    Clear-Host
    Write-Host '================ MenuFixer ================'
    Write-Host ' 1. Create or update environment variables'
    Write-Host ' 2. Apply .reg files'
    Write-Host ' 3. Create project .vscode folder'
    Write-Host ' 4. Move or mklink folders'
    Write-Host ' 5. Generate folder mapping YAML'
    Write-Host ' 6. Verify drive mappings'
    Write-Host ' 7. Verify subst settings'
    Write-Host ' 8. Manage context menu items'
    Write-Host ' 9. Fix shell window and buffers'
    Write-Host '10. Fix shell command redirections'
    Write-Host '11. Remove features and capabilities'
    Write-Host '12. Fix file associations'
    Write-Host '13. Create redirection files in D:\links'
    Write-Host '14. Install Scoop'
    Write-Host '15. Install Scoop packages'
    Write-Host '16. Check and repair scheduled tasks'
    Write-Host '17. Create new scheduled tasks'
    Write-Host '18. Maintain tools index list'
    Write-Host '19. Remove junk items'
    Write-Host '20. Maintain environment variable list'
    Write-Host '21. Fix Run as Administrator context menu'
    Write-Host ' A. Fix user interface elements'
    Write-Host '22. Fix AppData redirection'
    Write-Host '23. Install .NET'
    Write-Host '24. Fix services'
    Write-Host '25. Remove Edge (keep WebView)'
    Write-Host '26. Fix specific registry values'
    Write-Host '27. Fix PowerShell PackageManagement'
    Write-Host '28. Fix NuGet'
    Write-Host '29. Fix Winget'
    Write-Host '30. Update PowerShell modules'
    Write-Host '31. Fix PATHs'
    Write-Host '32. Fix PowerShell execution policy'
    Write-Host '33. Enable QuickEdit for cmd'
    Write-Host '34. Fix folder view options'
    Write-Host ' Q. Quit'
}

#region Task Functions
function Invoke-EnvVariables        { Write-Host 'TODO: Implement environment variable fixes.' }
function Invoke-ApplyRegFiles       { Write-Host 'TODO: Implement registry file application.' }
function Invoke-CreateVSCodeFolder  { Write-Host 'TODO: Implement .vscode folder creation.' }
function Invoke-MoveOrLinkFolders   { Write-Host 'TODO: Implement folder move or mklink.' }
function Invoke-GenerateYaml        { Write-Host 'TODO: Implement YAML mapping generation.' }
function Invoke-VerifyDrives        { Write-Host 'TODO: Implement drive mapping verification.' }
function Invoke-VerifySubst         { Write-Host 'TODO: Implement subst verification.' }
function Invoke-ManageContextMenu   { Write-Host 'TODO: Implement context menu management.' }
function Invoke-FixShellWindows     { Write-Host 'TODO: Implement shell window fixes.' }
function Invoke-FixRedirections     { Write-Host 'TODO: Implement command redirection fixes.' }
function Invoke-RemoveFeatures      { Write-Host 'TODO: Implement feature removal.' }
function Invoke-FixAssociations     { Write-Host 'TODO: Implement file association fixes.' }
function Invoke-CreateLinkFiles     { Write-Host 'TODO: Implement link file creation.' }
function Invoke-InstallScoop        { Write-Host 'TODO: Implement Scoop installation.' }
function Invoke-InstallScoopPkgs    { Write-Host 'TODO: Implement Scoop package installation.' }
function Invoke-CheckTasks          { Write-Host 'TODO: Implement task verification.' }
function Invoke-CreateTasks         { Write-Host 'TODO: Implement new task creation.' }
function Invoke-MaintainToolsIndex  { Write-Host 'TODO: Implement tools index maintenance.' }
function Invoke-RemoveJunk          { Write-Host 'TODO: Implement junk removal.' }
function Invoke-MaintainEnvList     { Write-Host 'TODO: Implement environment variable list maintenance.' }
function Invoke-FixRunAsAdmin       { Write-Host 'TODO: Implement Run as Administrator fix.' }
function Invoke-FixUI               { Write-Host 'TODO: Implement user interface fixes.' }
function Invoke-FixAppData          { Write-Host 'TODO: Implement AppData redirection fix.' }
function Invoke-InstallDotNet       { Write-Host 'TODO: Implement .NET installation.' }
function Invoke-FixServices         { Write-Host 'TODO: Implement service fixes.' }
function Invoke-RemoveEdge          { Write-Host 'TODO: Implement Edge removal.' }
function Invoke-FixRegistryValues   { Write-Host 'TODO: Implement registry value fixes.' }
function Invoke-FixPkgManagement    { Write-Host 'TODO: Implement PackageManagement fix.' }
function Invoke-FixNuGet            { Write-Host 'TODO: Implement NuGet fix.' }
function Invoke-FixWinget           { Write-Host 'TODO: Implement Winget fix.' }
function Invoke-UpdateModules       { Write-Host 'TODO: Implement module update.' }
function Invoke-FixPaths            { Write-Host 'TODO: Implement PATH fixes.' }
function Invoke-FixExecutionPolicy  { Write-Host 'TODO: Implement execution policy fix.' }
function Invoke-EnableQuickEdit     { Write-Host 'TODO: Implement QuickEdit enablement.' }
function Invoke-FixFolderViews      { Write-Host 'TODO: Implement folder view fixes.' }
#endregion Task Functions

# Main Loop
Do {
    Show-Menu
    $selection = Read-Host 'Select option'
    switch ($selection) {
        '1'  { Invoke-EnvVariables }
        '2'  { Invoke-ApplyRegFiles }
        '3'  { Invoke-CreateVSCodeFolder }
        '4'  { Invoke-MoveOrLinkFolders }
        '5'  { Invoke-GenerateYaml }
        '6'  { Invoke-VerifyDrives }
        '7'  { Invoke-VerifySubst }
        '8'  { Invoke-ManageContextMenu }
        '9'  { Invoke-FixShellWindows }
        '10' { Invoke-FixRedirections }
        '11' { Invoke-RemoveFeatures }
        '12' { Invoke-FixAssociations }
        '13' { Invoke-CreateLinkFiles }
        '14' { Invoke-InstallScoop }
        '15' { Invoke-InstallScoopPkgs }
        '16' { Invoke-CheckTasks }
        '17' { Invoke-CreateTasks }
        '18' { Invoke-MaintainToolsIndex }
        '19' { Invoke-RemoveJunk }
        '20' { Invoke-MaintainEnvList }
        '21' { Invoke-FixRunAsAdmin }
        'A'  { Invoke-FixUI }
        '22' { Invoke-FixAppData }
        '23' { Invoke-InstallDotNet }
        '24' { Invoke-FixServices }
        '25' { Invoke-RemoveEdge }
        '26' { Invoke-FixRegistryValues }
        '27' { Invoke-FixPkgManagement }
        '28' { Invoke-FixNuGet }
        '29' { Invoke-FixWinget }
        '30' { Invoke-UpdateModules }
        '31' { Invoke-FixPaths }
        '32' { Invoke-FixExecutionPolicy }
        '33' { Invoke-EnableQuickEdit }
        '34' { Invoke-FixFolderViews }
        'Q'  { break }
        Default { Write-Host 'Invalid selection' }
    }
    if ($selection -ne 'Q') { Read-Host 'Press Enter to continue' | Out-Null }
} While ($true)

