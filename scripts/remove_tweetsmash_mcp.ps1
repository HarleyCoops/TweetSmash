# Purpose: Safely remove only the 'tweetsmash' MCP server entry and restore all others untouched.
# It creates a timestamped backup before making any change.

$ErrorActionPreference = 'Stop'

$settingsPath = 'C:\Users\chris\AppData\Roaming\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json'

if (!(Test-Path -LiteralPath $settingsPath)) {
  throw "Settings file not found: $settingsPath"
}

# Backup current settings
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = "$settingsPath.$timestamp.bak"
Copy-Item -LiteralPath $settingsPath -Destination $backupPath -Force

# Load JSON
$settingsJson = Get-Content -LiteralPath $settingsPath -Raw
$settings = $settingsJson | ConvertFrom-Json

if ($null -eq $settings.mcpServers) {
  throw 'mcpServers object not found in settings JSON'
}

# Remove only the 'tweetsmash' entry if present
if ($settings.mcpServers.PSObject.Properties.Name -contains 'tweetsmash') {
  [void]$settings.mcpServers.PSObject.Properties.Remove('tweetsmash')
}

# Write back JSON
$newJson = $settings | ConvertTo-Json -Depth 100
Set-Content -LiteralPath $settingsPath -Value $newJson -Encoding UTF8

Write-Host ("Removed 'tweetsmash' entry. Backup saved at: {0}" -f $backupPath)
Write-Host "Servers now configured:"
$settings.mcpServers.PSObject.Properties.Name | Sort-Object | ForEach-Object { Write-Host ("- {0}" -f $_) }
