$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "a3_assistant\pipe\a3_controller.py"
$dst = Join-Path $PSScriptRoot "openwebui_data\pipelines\a3_controller.py"

if (-not (Test-Path $src)) { throw "Source not found: $src" }
if (-not (Test-Path (Split-Path $dst))) { throw "Dst folder not found: $(Split-Path $dst)" }

Copy-Item $src $dst -Force
Write-Host "✅ Published to $dst"

docker restart open-webui | Out-Null
Write-Host "✅ open-webui restarted"
