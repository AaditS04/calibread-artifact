# Sync calibread to the BITS cluster home folder.
# Requires VPN/campus network and a local cluster.env (see cluster.env.example).

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir 'cluster.env'
$LocalRoot = 'C:\Users\arvai\Documents\calibread'

if (-not (Test-Path $EnvFile)) {
    throw @"
cluster.env not found. Copy the example and set your SSH target (no passwords in files):

  Copy-Item scripts\cluster\cluster.env.example scripts\cluster\cluster.env

Then edit cluster.env with CLUSTER_USER, CLUSTER_HOST, and CALIBREAD_ROOT.
"@
}

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '^\s*(\w+)=(.*)$') { return }
    $name = $Matches[1].Trim()
    $value = $Matches[2].Trim()
    Set-Variable -Name $name -Value $value -Scope Script
}

if (-not $CLUSTER_USER -or -not $CLUSTER_HOST -or -not $CALIBREAD_ROOT) {
    throw 'cluster.env must set CLUSTER_USER, CLUSTER_HOST, and CALIBREAD_ROOT.'
}

$Cluster = "${CLUSTER_USER}@${CLUSTER_HOST}"
$RemoteRoot = "${CALIBREAD_ROOT}/calibread"

if (-not (Test-Path $LocalRoot)) {
    throw "Local repo not found: $LocalRoot"
}

Write-Host "Syncing $LocalRoot -> ${Cluster}:${RemoteRoot}"
Write-Host 'Use SSH keys or enter credentials when prompted (never store passwords in repo files).'

if (Get-Command wsl -ErrorAction SilentlyContinue) {
    wsl rsync -avz --delete `
        --exclude '.git' `
        --exclude '__pycache__' `
        --exclude '.pytest_cache' `
        --exclude 'results/r5/**/generations.jsonl' `
        --exclude 'scripts/cluster/cluster.env' `
        "/mnt/c/Users/arvai/Documents/calibread/" `
        "${Cluster}:${RemoteRoot}/"
} else {
    scp -r "$LocalRoot" "${Cluster}:${CALIBREAD_ROOT}/"
}

Write-Host 'Done. SSH in and run: cd $CALIBREAD_ROOT/calibread && bash scripts/cluster/setup_login_node.sh'
