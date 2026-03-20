# SimGenomeSc

Single-cell DNA-seq simulation with SNVs, CNAs, and SVs for **Sc-TUSV-ext**.

Generates synthetic single-cell tumor data: a random clonal phylogenetic tree, per-clone mutation profiles, cell-to-clone assignments, and per-cell VCF files — everything needed to benchmark clonal lineage inference methods.

> Original simulation by Jingyi Wang & Xuecong Fu (TUSV-ext), extended for single-cell by Nishat Anjum Bristy.

---

## Clone & Initialize Submodules

This repository uses **Git submodules** (e.g., [Sc-TUSV-ext](https://github.com/dezade/Sc-TUSV-ext)). After cloning, initialize them:

```bash
git clone https://github.com/dezade/SimGenomeSc.git
cd SimGenomeSc
git submodule update --init --recursive
```

If you've already cloned the repo without submodules:

```bash
git submodule update --init --recursive
```

### Updating Submodules

If you (or someone else) pushed new commits **inside** a submodule (e.g., `Sc-TUSV-ext`), the parent repo must be updated to track the new commit:

```bash
# From the SimGenomeSc root
cd Sc-TUSV-ext
git pull origin main        # pull latest submodule changes
cd ..

git add Sc-TUSV-ext         # stage the updated commit pointer
git commit -m "Update Sc-TUSV-ext submodule to latest"
git push origin main
```

> **Why?** Git tracks submodules as a pinned commit hash. Pushing inside the submodule does **not** auto-update the parent — you must explicitly `git add` the submodule directory and commit.

To pull the latest submodule state that someone else already updated in the parent:

```bash
git pull
git submodule update --recursive
```

---

## Environment Setup (Miniconda)

SimGenomeSc requires **Python 2.7**. The easiest way is a dedicated conda environment.

### 1. Install Miniconda (if not installed)

```bash
# Download (Linux x86_64)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Restart shell, then verify
conda --version
```

# Accept Terms of Service
```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### 2. Create the Environment

```bash
conda create -n simgenome_py2 python=2.7 -y
conda activate simgenome_py2
```

### 3. Install Dependencies

```bash
pip install numpy==1.16.6 pandas==0.24.2 graphviz==0.16 PyVCF==0.6.8 scipy==1.2.3 scikit-learn==0.20.4 biopython==1.76
```

If you plan to run **Sc-TUSV-ext** downstream (ILP solver), also install Gurobi:

```bash
pip install gurobipy==9.5.2
pip install ete2==2.3.10
```

> **Gurobi license**: Sc-TUSV-ext needs a Gurobi academic license. Get one at https://www.gurobi.com/academia/academic-program-and-licenses/ and place it at `~/gurobi.lic`.

### 4. Verify

```bash
conda activate simgenome_py2
python --version          # Python 2.7.18
python sim.py --help      # should print usage
```

### Installed Package Summary

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | 1.16.6 | Matrix operations, copy number profiles |
| pandas | 0.24.2 | DataFrame output (pyclone, fastclone, medicc2) |
| graphviz | 0.16 | Tree DOT file rendering |
| PyVCF | 0.6.8 | VCF file generation |
| scipy | 1.2.3 | Used by downstream tools |
| scikit-learn | 0.20.4 | Clustering in Sc-TUSV-ext |
| biopython | 1.76 | Phylogenetic XML output in Sc-TUSV-ext |
| gurobipy | 9.5.2 | ILP solver (Sc-TUSV-ext only) |
| ete2 | 2.3.10 | Tree manipulation (Sc-TUSV-ext only) |

---

## Quick Start

```bash
conda activate simgenome_py2
cd /path/to/SimGenomeSc

# Minimal test run (~3 seconds)
python sim.py \
  -f 2017_09_18_metadata.vcf \
  -n 3 -N 5 -m 5 \
  -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 \
  -o ./quick_test -p 1 -sto
```

Output will be in `./quick_test/patient1/`.

---

## Command-Line Parameters (Complete Reference)

```
python sim.py -f META -n LEAVES -N CELLS -m SAMPLES -c SVs -cs SNVs -s SV_LEN -o OUTDIR [options]
```

### Required Parameters

| Flag | Long Flag | Description | Example |
|------|-----------|-------------|---------|
| `-f` | `--metadata_file` | VCF metadata template (use the provided `2017_09_18_metadata.vcf`) | `-f 2017_09_18_metadata.vcf` |
| `-n` | `--num_leaves` | Number of **leaf** clones. Total tree nodes = `2n-1` | `-n 3` → 5 nodes |
| `-N` | `--num_cells` | Number of single cells to simulate. **Must be ≥ `2n-1`** | `-N 15` |
| `-m` | `--num_samples` | Number of bulk samples. For single-cell, set to `2n-1` or `N` | `-m 5` |
| `-c` | `--total_number_of_mutations` | Total SV breakpoints across the tree (≈ 2× number of SVs) | `-c 600` |
| `-cs` | `--total_number_of_mutations_snv` | Total SNV mutations across the tree | `-cs 100` |
| `-s` | `--expect_mut_len` | Expected SV length in bp (Poisson parameter) | `-s 5745000` |
| `-o` | `--output_folder` | Output directory (created if doesn't exist) | `-o ./output` |

### Optional Parameters

| Flag | Long Flag | Description | Default |
|------|-----------|-------------|---------|
| `-p` | `--num_patients` | Number of independent patients/replicates | `5` |
| `-rd` | `--read_depth` | Sequencing read depth for stochastic read counts | `50` |
| `-cov` | `--coverage` | Coverage parameter (typically same as `-rd`) | `20` |
| `-err` | `--error` | Error rate (%) in individual clone profiles | `0` |
| `-err2` | `--error2` | Error rate (%) when copying cell profiles | `0` |
| `-sto` | `--stochastic_model` | **Stochastic mode** — adds realistic sampling noise | Flag |
| `-det` | `--deterministic_model` | **Deterministic mode** — no noise, for testing | Flag |
| `-leaf` | `--only_leaf` | Assign cells only to leaf nodes (not internal) | Flag |

### Key Parameter Relationships

```
Tree nodes (clones)     = 2n - 1
Mutations per tree edge = total_mutations / (2n - 2)
Cells per clone         ≈ N / (2n - 1)        (average, random assignment)
Cell constraint         : N ≥ 2n - 1          (at least 1 cell per clone)
```

> **Tip**: `-m` (num_samples) sets the mixture matrix U dimensions. For single-cell mode, set `-m` equal to `2n-1`. The U matrix is `(m × 2n-1)`.

---

## Output Files

```
output_dir/
├── README.md                    # Parameters used
└── patient1/
    ├── T.dot                    # ★ GROUND TRUTH TREE (Graphviz DOT, 1-indexed)
    ├── C.tsv                    # ★ Copy number matrix (N_cells × features)
    ├── Z.tsv                    # ★ Cell-to-clone assignment (N_cells × 2n-1)
    ├── U.tsv                    # Clone mixture/usage matrix (m × 2n-1)
    ├── F.tsv                    # Read frequency matrix
    ├── B.tsv                    # Binary mutation presence per clone
    ├── W.tsv                    # Mutation arrival matrix
    ├── W_SV.tsv, W_SNV.tsv      # SV/SNV-specific arrival matrices
    ├── B_SV.tsv, B_SNV.tsv      # SV/SNV-specific binary presence
    ├── dimension                # "(l, r)" breakpoint and segment counts
    ├── edge_list.pickle         # Tree edges (Python pickle)
    ├── sample/                  # ★ PER-CELL VCF FILES
    │   ├── sample1.vcf          #   Cell 1: CNV + SV + SNV records
    │   ├── sample2.vcf
    │   └── ...sampleN.vcf
    ├── medicc2_input/           # MEDICC2-compatible format
    ├── phylowgs/                # PhyloWGS-compatible format
    ├── pyclone_input/           # PyClone-compatible format
    └── fastclone_input/         # FastClone-compatible format
```

### Matrix Dimensions

| Matrix | Shape | Columns Layout |
|--------|-------|----------------|
| `C.tsv` | `N × (l + g + 2r)` | `[SV breakpoints (l) | SNVs (g) | segments allele-A (r) | segments allele-B (r)]` |
| `Z.tsv` | `N × (2n-1)` | One-hot clone assignment per cell |
| `U.tsv` | `m × (2n-1)` | Clone proportions per sample (rows sum to 1) |
| `T.dot` | `2n-1` nodes | Directed tree, root = node `2n-1`, leaves = `1..n` |

### Tree Structure

- **Leaves** (nodes `1` to `n`): tumor subclones with accumulated mutations
- **Internal nodes** (nodes `n+1` to `2n-2`): ancestral branch points
- **Root** (node `2n-1`): normal/diploid ancestor

View the tree:
```bash
dot -Tpng patient1/T.dot -o tree.png
# or just cat it — it's human-readable
cat patient1/T.dot
```

---

## Example Commands

All commands below assume:
```bash
conda activate simgenome_py2
cd /path/to/SimGenomeSc
META=2017_09_18_metadata.vcf
```

### Performance Benchmarks

Timings measured on Linux (Feb 2026). Runtime scales primarily with SV count (`-c`) and number of clones (`-n`).

| Test | n | N | c | cs | Time |
|------|---|---|---|----|------|
| Smoke Test (det) | 3 | 5 | 30 | 300 | **2s** |
| Quick Stochastic | 3 | 10 | 30 | 300 | **6s** |
| Standard Baseline | 5 | 100 | 600 | 100 | **2m** |
| Multi-patient (p=5) | 5 | 100 | 600 | 100 | **2m13s** |
| Complex tree (n=7) | 7 | 200 | 600 | 100 | **3m** |
| Large tree (n=10) | 10 | 300 | 600 | 100 | **4m** |
| Low mutations | 5 | 100 | 150 | 25 | **19s** |
| Medium mutations | 5 | 100 | 300 | 50 | **52s** |
| Dense cells (N=500) | 5 | 500 | 600 | 100 | **2m** |
| Very dense (N=1000) | 5 | 1000 | 600 | 100 | **2m** |

### Distribution Analysis (Feb 11, 2026)

#### Understanding SimGenomeSc vs Sc-TUSV-ext Output Differences

**IMPORTANT:** SimGenomeSc C.tsv is **GROUND TRUTH** (N_cells × features), while Sc-TUSV-ext example's C.tsv is **INFERENCE OUTPUT** (N_clones × features after clustering). This explains why their distributions differ significantly:

| Metric | SimGenomeSc Output | Sc-TUSV-ext Example |
|--------|-------------------|---------------------|
| C.tsv rows | N cells (raw) | N clones (collapsed) |
| CN range | 0–79 (with amplifications) | 0–2 (normalized) |
| Features | ~300-4600 (all breakpoints) | 52 (segmented regions) |
| Purpose | Ground truth for evaluation | Inference result |

#### Distribution Comparison Table

```
Dataset                        C_shape      CN_range   mean    std     CNV/SV per cell
─────────────────────────────────────────────────────────────────────────────────────
Sc-TUSV-ext REFERENCE          (5, 52)      [0, 2]     0.819   0.395   14/16
─────────────────────────────────────────────────────────────────────────────────────
sctusv_lowmut (m=2,c=5)        (5, 291)     [0, 1]     0.313   0.464    6/4
sctusv_match_v2 (m=3,c=10)     (5, 377)     [0, 6]     0.387   0.598   22/26
sctusvext_match (m=5,c=30)     (5, 520)     [0, 6]     0.477   0.583   64/92
quick_test (m=5,c=5)           (5, 528)     [0, 6]     0.492   0.664   61/84
mut_low (m=9,c=150,N=100)      (100, 866)   [0, 17]    0.947   1.212  253/330
mut_med (m=9,c=300,N=100)      (100, 2268)  [0, 36]    0.968   1.571  658/902
baseline (m=9,c=600,N=100)     (100, 4602)  [0, 79]    1.565   3.931 1357/1774
```

#### Key Findings

1. **Copy Number Range**: SimGenomeSc generates wider CN ranges (0-79) because:
   - Amplifications can stack (e.g., `'amp'` with copy count 5 repeated)
   - Ground truth preserves exact mutation history
   - Sc-TUSV-ext normalizes to 0/1/2 during inference

2. **Feature Count Scaling**: Features scale with `-c` (SV count):
   - `-c 5` → ~300-500 features
   - `-c 150` → ~866 features  
   - `-c 600` → ~4600 features

3. **VCF Structure**: CNV/SV counts per cell scale roughly linearly with `-c`:
   - `-c 5` → 6 CNV, 4 SV
   - `-c 30` → 64 CNV, 92 SV
   - `-c 600` → 1357 CNV, 1774 SV

4. **Clone Balance**: With stochastic assignment, cells distribute ~uniformly across clones:
   - 100 cells / 9 clones ≈ 11.1 cells/clone (std ~3-4 cells)

#### Running Distribution Analysis

```bash
# Analyze all results in experiment_results/SimGenomeSc/
python analyze_distributions.py

# Or specify a custom path
python analyze_distributions.py /path/to/results
```

#### Recommended Parameters to Match Sc-TUSV-ext Scale

To generate data similar in scale to the Sc-TUSV-ext example input (5 cells, ~14 CNV, ~16 SV):

```bash
# Closest match to Sc-TUSV-ext example VCF scale
python sim.py -f 2017_09_18_metadata.vcf -n 3 -N 5 -m 5 \
  -c 10 -cs 10 -s 5745000 -rd 50 -cov 50 \
  -o ./sctusv_scale_match -p 1 -sto
# Produces: ~22 CNV/cell, ~26 SV/cell (close to 14/16 reference)
```

### Smoke Test (~2s)

Smallest possible run to verify everything works:

```bash
python sim.py -f $META -n 3 -N 5 -m 5 -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 -o ./test_smoke -p 1 -det
```

### Quick Stochastic Test (~6s)

Same but with realistic noise:

```bash
python sim.py -f $META -n 3 -N 10 -m 5 -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 -o ./test_stochastic -p 1 -sto
```

### Standard Baseline (Paper Config) (~2m)

The default configuration from the Sc-TUSV-ext paper:

```bash
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./baseline -p 1 -sto
```

### Varying Number of Clones

```bash
# Simple tree (3 leaves → 5 nodes) — ~1m6s
python sim.py -f $META -n 3 -N 50 -m 5 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./clones_n3 -p 1 -sto

# Medium tree (5 leaves → 9 nodes) — ~2m
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./clones_n5 -p 1 -sto

# Complex tree (7 leaves → 13 nodes) — ~3m
python sim.py -f $META -n 7 -N 200 -m 13 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./clones_n7 -p 1 -sto

# Large tree (10 leaves → 19 nodes) — ~4m12s
python sim.py -f $META -n 10 -N 300 -m 19 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./clones_n10 -p 1 -sto
```

### Varying Number of Cells

```bash
# Sparse (just enough cells: N = 2n-1) — ~1m58s
python sim.py -f $META -n 5 -N 9 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cells_N9 -p 1 -sto

# Moderate — ~1m42s
python sim.py -f $META -n 5 -N 50 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cells_N50 -p 1 -sto

# Standard — ~2m
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cells_N100 -p 1 -sto

# Dense — ~2m
python sim.py -f $META -n 5 -N 500 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cells_N500 -p 1 -sto

# Very Dense — ~2m8s
python sim.py -f $META -n 5 -N 1000 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cells_N1000 -p 1 -sto
```

### Varying Coverage / Read Depth

Coverage doesn't significantly affect runtime (~2m each):

```bash
# Ultra-low coverage (3x) — ~1m52s
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 3 -cov 3 -o ./cov_3x -p 1 -sto

# Low coverage (5x) — ~2m7s
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 5 -cov 5 -o ./cov_5x -p 1 -sto

# Medium coverage (10x) — ~2m1s
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 10 -cov 10 -o ./cov_10x -p 1 -sto

# Standard coverage (50x) — ~2m
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./cov_50x -p 1 -sto
```

### Varying Mutation Burden

**Mutation count (`-c`) is the primary driver of runtime:**

```bash
# Low mutations (25 SNVs, 150 SVs) — ~19s
python sim.py -f $META -n 5 -N 100 -m 9 -c 150 -cs 25 -s 5745000 \
  -rd 50 -cov 50 -o ./mut_low -p 1 -sto

# Medium mutations (50 SNVs, 300 SVs) — ~52s
python sim.py -f $META -n 5 -N 100 -m 9 -c 300 -cs 50 -s 5745000 \
  -rd 50 -cov 50 -o ./mut_med -p 1 -sto

# High mutations (100 SNVs, 600 SVs) — ~2m
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./mut_high -p 1 -sto

# Very high mutations (200 SNVs, 1200 SVs) — ⚠️ may fail with KeyError
python sim.py -f $META -n 5 -N 100 -m 9 -c 1200 -cs 200 -s 5745000 \
  -rd 50 -cov 50 -o ./mut_vhigh -p 1 -sto
```

### With Cell-Level Noise / Error

⚠️ **Note:** Error injection (`-err`) may cause sporadic failures due to edge cases in mutation generation.

```bash
# 5% clone profile error
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -err 5 -o ./err_5pct -p 1 -sto

# 10% clone profile error + 5% copy error
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -err 10 -err2 5 -o ./err_10_5 -p 1 -sto
```

### Multiple Patients (Replicates)

```bash
# 5 independent patients with same parameters — ~10m (5× single patient time)
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./multi_patient -p 5 -sto
# Output: multi_patient/patient1/, patient2/, ..., patient5/
```

### Leaf-Only Cell Assignment

Cells assigned only to leaf clones (not internal/ancestral nodes):

```bash
# ~2m
python sim.py -f $META -n 5 -N 100 -m 9 -c 600 -cs 100 -s 5745000 \
  -rd 50 -cov 50 -o ./leaf_only -p 1 -sto -leaf
```

### For DataGeneration Pipeline (ML Training Data)

These are the configs used by the `DataGeneration/generate_dataset.py` pipeline:

```bash
# Trivial case (exactly 1 cell per clone, good for debugging) — ~7s
python sim.py -f $META -n 3 -N 5 -m 5 -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 -o ./pipeline_trivial -p 1 -sto

# Non-trivial case (multiple cells per clone, realistic clustering) — ~7s
python sim.py -f $META -n 3 -N 15 -m 5 -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 -o ./pipeline_nontrivial -p 1 -sto

# Larger tree for harder inference — ~12s
python sim.py -f $META -n 5 -N 30 -m 9 -c 30 -cs 300 -s 5745000 \
  -rd 50 -cov 50 -o ./pipeline_n5 -p 1 -sto
```

---

## Parameter Selection Guide
### How to choose `-m` (num_samples)?

`-m` sets the rows of the mixture matrix `U (m × 2n-1)`. For single-cell mode:

| Scenario | Recommended `-m` | Reason |
|----------|-------------------|--------|
| Standard single-cell | `2n - 1` | One sample per clone, natural mapping |
| Match paper experiments | Same as `-N` | Paper used `-m 100 -N 100` |
| Minimal | `2n - 1` | Smallest valid value |

### How to choose `-N` (num_cells)?

| Scenario | `-N` | Cells per clone |
|----------|------|-----------------|
| Trivial (no clustering) | `2n - 1` | Exactly 1 |
| Minimal clustering | `2 × (2n-1)` | ~2 |
| Standard | `~20 × n` | ~10 per leaf |
| Dense | `~100 × n` | ~50 per leaf |

### How to choose `-c` and `-cs` (mutations)?

The paper uses a ~6:1 ratio for SV breakpoints to SNVs:

| Mutation Level | `-cs` (SNVs) | `-c` (SV breakpoints) | Muts/edge (n=5) |
|----------------|-------------|----------------------|-----------------|
| Minimal test | 10 | 30 | ~5 |
| Low | 25 | 150 | ~22 |
| Medium | 50 | 300 | ~44 |
| Standard | 100 | 600 | ~88 |
| High | 200 | 1200 | ~175 |

### When to use `-det` vs `-sto`?

| Mode | Flag | Use Case |
|------|------|----------|
| **Deterministic** | `-det` | Testing, debugging, verifying pipeline correctness |
| **Stochastic** | `-sto` | Production runs, realistic data, training ML models |

Stochastic mode adds Poisson-distributed read depths and binomial-sampled variant allele counts, simulating real sequencing noise.

---

## Downstream: Running Sc-TUSV-ext on Output

After simulation, feed the per-cell VCFs to Sc-TUSV-ext (included as a submodule at `Sc-TUSV-ext/`):

```bash
conda activate simgenome_py2

python Sc-TUSV-ext/sc-tusv-ext.py \
  -i ./output/patient1/sample/ \
  -o ./sctusvext_output/ \
  -n 3 \
  -c 10 -m 1000 -r 2 -t 2 -p 8 -x 34 \
  -d Sc-TUSV-ext/data/2017_09_18_metadata.vcf \
  -col
```

This produces `C_phasing_full.tsv` (C_obs) — the observed clone-level copy number matrix used as features for phylogeny inference.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Number of cells should be >= number of clones` | `-N` < `2n-1` | Increase `-N` |
| `ImportError: No module named vcf` | Missing PyVCF | `pip install PyVCF` |
| `ImportError: No module named graphviz` | Missing graphviz | `pip install graphviz` |
| `need more than 2 values to unpack` | Old deterministic bug | Use the bug-fixed `sim.py` in `sowdha/SimGenomeSc/` |
| Simulation hangs | Large `-c` with many SVs | Reduce SV count or expected size |
| `IndexError` in `add_additional_cell_copies` | Old Z matrix bug when N > 2n-1 | Use the bug-fixed `sim.py` |

---

## Documentation

- **[INSTRUCTIONS.md](INSTRUCTIONS.md)** — In-depth parameter guide and output format details
- **[experiment_parameters.json](experiment_parameters.json)** — Exact paper experiment configurations with findings

---

## Reference

> Bristy et al. (2025). *Sc-TUSV-ext: Single-cell clonal lineage inference from SNVs, CNAs, and SVs*

Original TUSV simulation by Jingyi Wang and Xuecong Fu, extended for single-cell by Nishat Anjum Bristy.
