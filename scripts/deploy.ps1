param(
    [switch]$Restart
)

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
foreach ($item in @("app", "scripts", "tests", "config", "docs", "deploy", "requirements.txt", "config.yaml", ".env.example", "secrets.example.txt", "secrets.example.json", "README.md", "SECURITY.md")) { scp -r -- "$item" $target }

Write-Host "파일 전송 완료. 서버에서 의존성 동기화 중..."
ssh $hostTarget "cd '$directory' && .venv/bin/pip install -q -r requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "서버 의존성 설치 실패." }
Write-Host "의존성 동기화 완료."

if (-not $Restart) {
    Write-Host "파일/의존성만 반영했습니다. 서비스는 재기동하지 않았습니다."
    Write-Host "서버에서 직접 'sudo systemctl restart qa-verification'을 실행하거나, '.\scripts\deploy.ps1 -Restart'로 다시 실행하세요."
    return
}

$secretsFile = Join-Path $projectRoot "secrets.txt"
if (-not (Test-Path -LiteralPath $secretsFile)) { throw "secrets.txt가 없어 -Restart를 쓸 수 없습니다 (SERVER_SUDO_PASSWORD 필요)." }
$sudoLine = Get-Content -LiteralPath $secretsFile | Where-Object { $_ -match '^SERVER_SUDO_PASSWORD=' } | Select-Object -First 1
if (-not $sudoLine) { throw "secrets.txt에 SERVER_SUDO_PASSWORD가 없어 -Restart를 쓸 수 없습니다." }
$sudoPassword = $sudoLine.Substring("SERVER_SUDO_PASSWORD=".Length)

Write-Host "qa-verification 서비스 재기동 중..."
$sudoPassword | ssh $hostTarget "sudo -S -p '' systemctl restart qa-verification"
if ($LASTEXITCODE -ne 0) { throw "서비스 재기동 실패 (sudo 비밀번호 또는 유닛 이름을 확인하세요)." }

Write-Host "헬스체크 중..."
$healthy = $false
$lastResult = ""
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    $lastResult = ssh $hostTarget "curl -fsS http://127.0.0.1:12000/health" 2>$null
    if ($LASTEXITCODE -eq 0 -and $lastResult -match '"status"\s*:\s*"ok"') {
        $healthy = $true
        break
    }
}
if (-not $healthy) { throw "헬스체크 실패. 서버에서 확인: journalctl -u qa-verification -n 50 --no-pager" }
Write-Host "배포 및 재기동 완료: $lastResult"
