# Deploy the M4L 2.0 DEMO to Fly.io (staging only). Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File deploy\demo\deploy-fly.ps1
# Needs: flyctl installed and signed in (fly auth login). Creates billable resources (1 small VM + 1 GB volume).
# Never touches data/xanh24.db: the image excludes data/ and the demo DB is built from repo sample data on first boot.
param([string]$App = "xanh24-m4l-demo", [string]$Region = "sin")
$ErrorActionPreference = "Stop"

if (-not (Get-Command fly -ErrorAction SilentlyContinue)) { throw "Chưa cài flyctl: iwr https://fly.io/install.ps1 -useb | iex" }
fly auth whoami | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Chưa đăng nhập Fly.io: chạy 'fly auth login'" }

$apps = fly apps list --json | ConvertFrom-Json
if (-not ($apps | Where-Object { $_.Name -eq $App })) {
    fly apps create $App
    if ($LASTEXITCODE -ne 0) { throw "Không tạo được app $App (tên có thể đã có người dùng: chạy lại với -App <tên khác>)" }
}
$volumes = fly volumes list --app $App --json | ConvertFrom-Json
if (-not ($volumes | Where-Object { $_.Name -eq "m4l_demo_data" })) {
    fly volumes create m4l_demo_data --app $App --region $Region --size 1 --yes
}
fly deploy . --config deploy/demo/fly.toml --dockerfile deploy/demo/Dockerfile --app $App --primary-region $Region --ha=false
if ($LASTEXITCODE -ne 0) { throw "Deploy lỗi" }
Write-Host ""
Write-Host "Link demo: https://$App.fly.dev/demo"
