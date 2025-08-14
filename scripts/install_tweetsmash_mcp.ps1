# Requires: PowerShell 5+ or 7+, write access to Cursor MCP settings file
# Purpose: Install/Update Tweetsmash MCP server entry in Cursor's cline_mcp_settings.json using token from this repo's .env

$ErrorActionPreference = 'Stop'

# Paths
$settingsPath = 'C:\Users\chris\AppData\Roaming\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json'
$envPath = 'C:\Users\chris\TweetSmash\.env'

if (!(Test-Path -LiteralPath $settingsPath)) {
  throw "Settings file not found: $settingsPath"
}
if (!(Test-Path -LiteralPath $envPath)) {
  throw ".env not found at $envPath"
}

# Load settings JSON
$settingsJson = Get-Content -LiteralPath $settingsPath -Raw
$settings = $settingsJson | ConvertFrom-Json

# Ensure mcpServers object exists
if ($null -eq $settings.mcpServers) {
  $settings | Add-Member -NotePropertyName mcpServers -NotePropertyValue (@{})
}

# Extract token from .env
$line = (Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^\s*TWEETSMASH_API_KEY\s*=' } | Select-Object -First 1)
if (-not $line) {
  throw 'TWEETSMASH_API_KEY not found in .env'
}
$token = ($line -replace '^\s*TWEETSMASH_API_KEY\s*=\s*', '').Trim('"').Trim()

if ([string]::IsNullOrWhiteSpace($token)) {
  throw 'Extracted TWEETSMASH_API_KEY is empty after parsing'
}

# Compose server entry (manual STDIO config per https://www.tweetsmash.com/api-docs/mcp-integration)
$server = [PSCustomObject]@{
  autoApprove   = @()
  disabled      = $false
  timeout       = 60
  command       = 'npx'
  args          = @('-y', '@tweetsmash/mcp')
  env           = @{ TWEETSMASH_TOKEN = $token }
  transportType = 'stdio'
}

# Insert/Update
if ($settings.mcpServers.PSObject.Properties.Name -contains 'tweetsmash') {
  $settings.mcpServers.tweetsmash = $server
} else {
  $settings.mcpServers | Add-Member -NotePropertyName 'tweetsmash' -NotePropertyValue $server
}

# Write back
$settings | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $settingsPath -Encoding UTF8

Write-Host "Installed Tweetsmash MCP server in settings: $settingsPath"
