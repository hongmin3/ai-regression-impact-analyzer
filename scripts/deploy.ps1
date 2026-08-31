$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$deployFile = Join-Path $projectRoot ".deploy.env"
if (-not (Test-Path -LiteralPath $deployFile)) { throw ".deploy.env가 없습니다. .deploy.env.example을 복사해 설정하세요." }
$deploy = @{}
Get-Content -LiteralPath $deployFile | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    $deploy[$key] = $value
}
$hostTarget = "$($deploy.DEPLOY_SSH_USER)@$($deploy.DEPLOY_SSH_HOST)"
$directory = $deploy.DEPLOY_TARGET_DIRECTORY
$target = "${hostTarget}:${directory}/"
Set-Location $projectRoot
& "$projectRoot\.venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "테스트 실패로 배포를 중단합니다." }
ssh $hostTarget "test ! -e '$directory' || test -d '$directory'"
ssh $hostTarget "mkdir -p '$directory'"
foreach ($item in @("app", "scripts", "tests", "requirements.txt", "config.yaml", ".env.example", "README.md", "SECURITY.md")) { scp -r -- "$item" $target }
