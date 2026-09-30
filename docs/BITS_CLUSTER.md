# BITS GPU cluster — R5 inference runbook

Canonical guide for running CalibRead R5 inference on the institute Slurm cluster.
For the underlying research protocol (splits, promotion gate, calibration order), see
[`src/calibread/inference/R5_COMPLETE_RUN.md`](../src/calibread/inference/R5_COMPLETE_RUN.md).

## Credentials and secrets

**Never commit passwords, SSH keys, or account-specific hostnames to git.**

1. Copy the example env file locally (on Windows and on the cluster):

   ```bash
   cp scripts/cluster/cluster.env.example scripts/cluster/cluster.env
   ```

2. Edit `scripts/cluster/cluster.env` with your institute-provided values:

   ```bash
   CLUSTER_USER=your_username
   CLUSTER_HOST=your.cluster.host
   CALIBREAD_ROOT=/nfs_home/users/your_username/your_project_folder
   ```

3. `cluster.env` is gitignored. Use SSH keys or an interactive password prompt — do not
   store passwords in any file.

All cluster scripts read paths from `cluster.env` via `scripts/cluster/common.sh`.

## Paths and etiquette

| Item | Variable / path |
|------|-----------------|
| Project root | `$CALIBREAD_ROOT` (from `cluster.env`) |
| Repository | `$CALIBREAD_ROOT/calibread` |
| Python venv | `$CALIBREAD_ROOT/venv` |
| Ollama binary | `$CALIBREAD_ROOT/bin/ollama` |
| Model weights | `$CALIBREAD_ROOT/ollama_models` |
| Slurm logs | `$CALIBREAD_ROOT/logs/` |

**Rules**

- Login node: edit files and `sbatch` only. No GPU inference on the login node.
- Keep code, data, models, logs, and results inside `$CALIBREAD_ROOT`.
- Do not modify other users' folders, shared modules, or system packages.
- Connect institute **VPN** before SSH from off-campus.

**Hardware (committed Slurm scripts)**

- Partition: `gpu-short` (8 h) or `gpu-long` (12 h)
- GPU: `gpu:a100-80gb:1` (NVIDIA A100 80 GB)

---

## Quick reference — commands from Windows (PowerShell, VPN on)

```powershell
# One-time: create local cluster.env from the example (see above)

# Sync local repo → cluster
cd C:\Users\arvai\Documents\calibread
.\scripts\cluster\sync_from_windows.ps1

# SSH shell (replace with your CLUSTER_USER@CLUSTER_HOST)
ssh $env:CLUSTER_USER@$env:CLUSTER_HOST

# Check disk quota
ssh $env:CLUSTER_USER@$env:CLUSTER_HOST "quota -s"
```

Pull results back (substitute your SSH target and `CALIBREAD_ROOT`):

```powershell
scp -r ${CLUSTER_USER}@${CLUSTER_HOST}:${CALIBREAD_ROOT}/calibread/results/r5/ `
  C:\Users\arvai\Documents\calibread\results\r5\
```

---

## One-time setup

### 1. Copy repository to cluster

```powershell
.\scripts\cluster\sync_from_windows.ps1
```

### 2. Create cluster.env on the login node

```bash
ssh <your-user>@<cluster-host>
cd $CALIBREAD_ROOT/calibread
cp scripts/cluster/cluster.env.example scripts/cluster/cluster.env
# edit cluster.env with your assigned CALIBREAD_ROOT
```

### 3. Install Python + Ollama (login node)

```bash
bash scripts/cluster/setup_login_node.sh
```

This creates `$CALIBREAD_ROOT/venv` (Python **≥ 3.11**) and installs user-local Ollama
**0.34** into `$CALIBREAD_ROOT/bin`.

Optional `~/.bashrc` additions (paths come from your `cluster.env`):

```bash
export CALIBREAD_ROOT="/path/from/cluster/env"
export PATH="$CALIBREAD_ROOT/bin:$PATH"
export OLLAMA_MODELS="$CALIBREAD_ROOT/ollama_models"
```

### 4. Inspect Slurm

```bash
sinfo -o '%P %G %l %D %T'
squeue -u "$USER"
```

---

## Model preparation protocol

CalibRead rejects Ollama instruct models with an **embedded SYSTEM prompt**. Every new
model needs two steps: **pull** (GPU job) then **strip** (login node).

### Step A — Pull weights

```bash
cd $CALIBREAD_ROOT/calibread

sbatch scripts/cluster/pull_model.slurm qwen2.5:14b-instruct-q4_K_M   # ~9 GB
# sbatch scripts/cluster/pull_model.slurm qwen2.5:32b-instruct-q4_K_M  # ~20 GB
```

Monitor:

```bash
squeue -u "$USER"
tail -f $CALIBREAD_ROOT/logs/ollama-pull-<jobid>.out
```

### Step B — Strip embedded SYSTEM layer

```bash
module load python/3.13.7   # if needed

bash scripts/cluster/strip_system_layer.sh \
  calibread-qwen25-14b-instruct-q4 \
  qwen2.5:14b-instruct-q4_K_M
```

The inference config must use the **calibread-** alias, not the raw Ollama tag.

### Suggested models (A100 80 GB)

| Ollama pull tag | Disk | CalibRead alias (example) |
|-----------------|------|---------------------------|
| `qwen2.5:14b-instruct-q4_K_M` | ~9 GB | `calibread-qwen25-14b-instruct-q4` |
| `qwen2.5:14b-instruct-q3_K_M` | ~7 GB | `calibread-qwen25-14b-instruct-q3` |
| `qwen2.5:32b-instruct-q4_K_M` | ~20 GB | `calibread-qwen25-32b-instruct-q4` |
| `qwen2.5:72b-instruct-q4_K_M` | ~47 GB | `calibread-qwen25-72b-instruct-q4` |
| `mixtral:8x22b-instruct-v0.1-q4_K_M` | ~85 GB | `calibread-mixtral-8x22b-instruct-q4` |

Mixtral has no embedded SYSTEM layer in the Ollama manifest; copy the manifest
to a `calibread-` alias instead of using `strip_system_layer.sh`.

Completed full-pipeline records:

- [`r5_qwen25_72b_cluster_run.md`](r5_qwen25_72b_cluster_run.md) (1× GPU)
- [`r5_mixtral_8x22b_cluster_run.md`](r5_mixtral_8x22b_cluster_run.md) (2× GPU)

Sealed-test findings synthesis (both conditions):
[`r5_cluster_sealed_test_findings.md`](r5_cluster_sealed_test_findings.md).

For Mixtral 8×22B q4, use `scripts/cluster/run_inference_2gpu.slurm` or
`scripts/cluster/submit_mixtral_8x22b_full_pipeline.sh`.

```bash
quota -s
du -sh $CALIBREAD_ROOT/ollama_models
```

---

## Inference protocol (R5 development pilot)

```text
validate-config → plan → run → score → report → composition-report
```

Submit all jobs from `$CALIBREAD_ROOT/calibread` so Slurm log paths resolve correctly.

### 1. Validate and plan (login node, no GPU)

```bash
cd $CALIBREAD_ROOT/calibread
module load python/3.13.7
source $CALIBREAD_ROOT/venv/bin/activate
export PYTHONPATH=src

CONFIG=configs/inference/r5_ollama_qwen25_14b_cluster_development_pilot.toml

python -m calibread.inference.cli validate-config "$CONFIG"
python -m calibread.inference.cli plan "$CONFIG"
```

### 2. Submit full pilot (GPU via Slurm)

```bash
sbatch scripts/cluster/run_inference.slurm "$CONFIG"
```

Individual phases:

```bash
bash scripts/cluster/run_r5_phase.sh "$CONFIG" run
bash scripts/cluster/run_r5_phase.sh "$CONFIG" all
```

### 3. Monitor

```bash
squeue -u "$USER"
sacct -j <jobid> --format=JobID,JobName,State,ExitCode,Elapsed
tail -f $CALIBREAD_ROOT/logs/r5-inference-<jobid>.out
```

### 4. Results

```text
results/r5/r5_qwen25_14b_cluster_forced_v1/development_pilot/
```

### 5. Resume after interruption

Resubmit the same `sbatch` command with an unchanged config (`resume = true`).

---

## Promotion checklist

- [ ] `RUN_SUMMARY.json` → `completion_status = complete`
- [ ] Uniform `returned_models` identity / digest
- [ ] No missing token log probabilities
- [ ] Short factual answers; both correct and incorrect answers exist
- [ ] Raw scores finite and not constant
- [ ] Accuracy not at a degenerate floor/ceiling in intended cells

Create **new** phase configs with a new `parent_experiment_id` if promoting.

---

## New model checklist

1. [ ] `sbatch scripts/cluster/pull_model.slurm <ollama-tag>`
2. [ ] `bash scripts/cluster/strip_system_layer.sh <calibread-name> <ollama-tag>`
3. [ ] New inference config (`run_id`, `parent_experiment_id`, `output_dir`, `requested_model`)
4. [ ] `validate-config` + `plan`
5. [ ] `sbatch scripts/cluster/run_inference.slurm <new-config>`

---

## Script reference

| Script | Purpose |
|--------|---------|
| `cluster.env.example` | Template for local `cluster.env` (gitignored) |
| `common.sh` | Loads `cluster.env`, exports paths |
| `setup_login_node.sh` | Python venv + Ollama install |
| `pull_model.slurm` | `ollama pull <tag>` |
| `strip_system_layer.sh` | Remove embedded SYSTEM from manifest |
| `run_inference.slurm` | Full R5 pilot pipeline |
| `run_r5_phase.sh` | Single phase or `all` |
| `sync_from_windows.ps1` | Push local repo to cluster |

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `ssh: Connection timed out` | Connect institute VPN |
| `cluster.env not found` | Copy `cluster.env.example` → `cluster.env` |
| `embedded system prompt` | Run `strip_system_layer.sh`; use `calibread-*` model name |
| `model ... not found` | Complete pull job first |
| `disk quota exceeded` | `quota -s`; remove old models |
| Empty Slurm log | Check `sacct -j <id>` and `.err` log in `$CALIBREAD_ROOT/logs/` |

---

## Keeping local and cluster in sync

```powershell
.\scripts\cluster\sync_from_windows.ps1
```

Never synced via git: `ollama_models/`, `venv/`, `logs/`, `cluster.env`.
