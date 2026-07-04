param(
    [int]$PrNumber = 2,
    [string]$Tag = "v1.2.0-industrial",
    [int]$PollIntervalSeconds = 15
)

Write-Host "Auto-release helper"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is required. Install and authenticate first."
    exit 1
}

# Ensure authenticated
gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "gh not authenticated. Run 'gh auth login' first."
    exit 1
}

Write-Host "Scheduling auto-merge for PR #$PrNumber (will merge when checks pass)..."
gh pr merge $PrNumber --auto --merge 2>$null

# Poll for merge
while ($true) {
    $pr = gh pr view $PrNumber --json number,title,merged,mergeState 2>$null | ConvertFrom-Json
    if ($pr.merged -eq $true) {
        Write-Host "PR #$PrNumber merged."
        break
    }
    Write-Host "PR not merged yet (state: $($pr.mergeState)). Waiting $PollIntervalSeconds s..."
    Start-Sleep -Seconds $PollIntervalSeconds
}

# Update local main branch
Write-Host "Fetching latest main..."
git fetch origin
git checkout main
git pull origin main

# Create annotated tag
Write-Host "Creating tag $Tag..."
git tag -a $Tag -m "Native hybrid release: hash-chain validation and native kernels"
git push origin $Tag

# Create GitHub release (will trigger CI workflow to build wheel on release)
Write-Host "Creating GitHub release $Tag..."
if (-Not (Test-Path -Path RELEASE_CHECKLIST.md)) {
    Write-Warning "RELEASE_CHECKLIST.md not found; creating minimal notes."
    $tmp = New-TemporaryFile
    "Release $Tag" | Out-File $tmp
    gh release create $Tag --title $Tag --notes-file $tmp
    Remove-Item $tmp
} else {
    gh release create $Tag --title $Tag --notes-file RELEASE_CHECKLIST.md
}

Write-Host "Release created. CI workflows triggered for release publishing."
Write-Host "Done."

