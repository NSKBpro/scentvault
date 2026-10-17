<#
  ScentVault dev tasks for Windows PowerShell (same targets as the Makefile).

    ./tasks.ps1 setup      # venv + npm installs
    ./tasks.ps1 up         # Postgres + Redis in Docker
    ./tasks.ps1 migrate    # alembic upgrade head
    ./tasks.ps1 seed       # reference data   (demo = + demo fragrances)
    ./tasks.ps1 api        # API on :8004     (worker = background jobs)
    ./tasks.ps1 admin      # admin on :5173   (mobile = Expo)
    ./tasks.ps1 types      # regenerate packages/api-types
    ./tasks.ps1 test       # API tests
    ./tasks.ps1 upgrade-v1 # one-time: move your pre-2.0 database to the new schema (see README)
#>
param([Parameter(Position = 0)][string]$Task = "help", [string]$AdminEmail, [string]$AdminPassword)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Api = Join-Path $Root "apps/api"
$Py = Join-Path $Api ".venv/Scripts/python.exe"

function Read-DotEnv {
  $vars = @{}
  $file = Join-Path $Root ".env"
  if (Test-Path $file) {
    Get-Content $file | Where-Object { $_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' } | ForEach-Object {
      $vars[$Matches[1]] = $Matches[2].Trim()
    }
  }
  return $vars
}

function In-Api([scriptblock]$Block) { Push-Location $Api; try { & $Block } finally { Pop-Location } }

switch ($Task) {
  "setup" {
    In-Api { python -m venv .venv; & $Py -m pip install --upgrade pip; & $Py -m pip install -e ".[dev,ml]" }
    Push-Location (Join-Path $Root "apps/admin"); npm ci; Pop-Location
    Push-Location (Join-Path $Root "apps/mobile"); npm ci; Pop-Location
    if (-not (Test-Path (Join-Path $Root ".env"))) { Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env"); Write-Host "Created .env — fill in JWT_SECRET and POSTGRES_PASSWORD." }
  }
  "up"      { docker compose up -d db redis }
  "down"    { docker compose down }
  "migrate" { In-Api { & $Py -m alembic upgrade head } }
  "seed"    { In-Api { & $Py -m seeds.run } }
  "demo"    { In-Api { & $Py -m seeds.run --demo } }
  "admin-user" {
    if (-not $AdminEmail) { throw "Usage: ./tasks.ps1 admin-user -AdminEmail you@example.com -AdminPassword '...'" }
    In-Api { & $Py -m seeds.run --admin $AdminEmail --password $AdminPassword }
  }
  "api"     { In-Api { & $Py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8004 } }
  "worker"  { In-Api { & $Py -m arq app.workers.arq_worker.WorkerSettings } }
  "admin"   { Push-Location (Join-Path $Root "apps/admin"); npm run dev; Pop-Location }
  "mobile"  { Push-Location (Join-Path $Root "apps/mobile"); npx expo start; Pop-Location }
  "types"   { In-Api { & $Py -m scripts.gen_types } }
  "test"    { In-Api { & $Py -m pytest -q } }
  "lint" {
    In-Api { & $Py -m ruff check .; & $Py -m mypy app scripts }
    Push-Location (Join-Path $Root "apps/admin"); npx tsc -b; npx eslint .; Pop-Location
    Push-Location (Join-Path $Root "apps/mobile"); npx tsc --noEmit; Pop-Location
  }
  "upgrade-v1" {
    # One-time move from the pre-2.0 database (same Docker volume) to the 2.0 schema.
    $cfg = Read-DotEnv
    $u = if ($cfg.POSTGRES_USER) { $cfg.POSTGRES_USER } else { "scentvault" }
    $db = if ($cfg.POSTGRES_DB) { $cfg.POSTGRES_DB } else { "scentvault" }
    $pw = $cfg.POSTGRES_PASSWORD
    if (-not $pw) { throw "Set POSTGRES_PASSWORD in .env (the password your existing database uses)." }
    New-Item -ItemType Directory -Force (Join-Path $Root "backups") | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = Join-Path $Root "backups/scentvault_v1_$stamp.dump"
    Write-Host "1/5 Backing up '$db' to $backup"
    # Dump inside the container and copy the file out (piping binary through PowerShell corrupts it).
    docker exec scentvault_db pg_dump -U $u -Fc $db -f /tmp/sv_backup.dump
    docker cp scentvault_db:/tmp/sv_backup.dump $backup
    Write-Host "2/5 Renaming '$db' -> '${db}_legacy' and creating a fresh '$db'"
    docker exec scentvault_db psql -U $u -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();" -c "ALTER DATABASE $db RENAME TO ${db}_legacy;" -c "CREATE DATABASE $db OWNER $u;"
    Write-Host "3/5 Creating the 2.0 schema"
    In-Api { & $Py -m alembic upgrade head }
    Write-Host "4/5 Seeding reference data"
    In-Api { & $Py -m seeds.run }
    Write-Host "5/5 Copying your data"
    In-Api { & $Py -m scripts.migrate_legacy --source "postgresql://${u}:${pw}@localhost:5432/${db}_legacy" --force }
    Write-Host "Done. Old data stays in '${db}_legacy' (drop it when happy). Backup: $backup"
  }
  default { Get-Content $PSCommandPath | Select-Object -First 15 }
}
