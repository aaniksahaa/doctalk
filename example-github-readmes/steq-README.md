# STEQ: Species Tree Estimation using Quartet Distances

**STEQ** is a statistically consistent, quartet-based summary method for species tree inference. Given a collection of gene trees in Newick format, STEQ estimates pairwise inter-taxa distances based on quartet topologies across all gene trees, aggregates them using a configurable central tendency measure, and infers the species tree from the resulting distance matrix using a distance-based tree-building algorithm.

> **Platform:** Developed and tested on **Linux (Ubuntu/Debian)**.


## Prerequisites

| Dependency | Required | Install Command (Ubuntu/Debian) |
|------------|----------|-------------------------------|
| **flex** | Yes | `sudo apt-get install -y flex` |
| **g++** | Yes | `sudo apt-get install -y g++` |
| **libfl-dev** | Yes | `sudo apt-get install -y libfl-dev` |

> **Note:** The pre-built `STEQ.out` binary is included in the repository. If it works on your system, no compilation is needed — the run script detects this automatically. The above dependencies are only required if recompilation is triggered.

### Install All Prerequisites (One Command)

```bash
sudo apt-get update && sudo apt-get install -y flex g++ libfl-dev
```

### Verify

```bash
flex --version
g++ --version
```


---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/prottoysaha99/STEQ
cd STEQ

# Run on the included example dataset (37 taxa, 200 gene trees)
./run_steq.sh -i all_gt_37.tre -o out_37.tre
```

That's it. The wrapper script handles compilation (if needed) and execution automatically.

---

## Usage

### Using the Wrapper Script (Recommended)

```bash
./run_steq.sh -i <gene_trees> -o <species_tree> [OPTIONS]
```

### Examples

```bash
# Basic run with default settings (Mean + FastME_BAL)
./run_steq.sh -i all_gt_37.tre -o out_37.tre

# Use Median distances and Neighbor Joining
./run_steq.sh -i all_gt_37.tre -o out_37.tre -c 1 -f 1

# Use Mode distances with Unweighted NJ
./run_steq.sh -i all_gt_37.tre -o out_37.tre -c 2 -f 2

# Trimmed Mean (Normal Distribution ±2σ)
./run_steq.sh -i all_gt_37.tre -o out_37.tre -c 3

# Save the intermediate distance matrix
./run_steq.sh -i all_gt_37.tre -o out_37.tre -m distance_matrix.txt

# Force rebuild of the STEQ binary
./run_steq.sh -i all_gt_37.tre -o out_37.tre --rebuild

# Show all options
./run_steq.sh --help
```

---

## Command-Line Parameters

### Required

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-i` | `--input <file>` | Input gene trees file (Newick format, one tree per line) |
| `-o` | `--output <file>` | Output species tree file |

### Options

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| `-c` | `--central-tendency <type>` | Central tendency measure for distance aggregation (see below) | `0` (Mean) |
| `-f` | `--fastme-type <type>` | Distance-based tree construction method (see below) | `0` (FastME_BAL) |
| `-m` | `--matrix <file>` | Path for the intermediate distance matrix file | Temp file (auto-cleaned) |
| | `--rebuild` | Force recompilation of STEQ even if the binary exists | Off |
| `-h` | `--help` | Show help message and exit | — |

### Central Tendency Types (`-c`)

| Value | Name | Description |
|-------|------|-------------|
| `0` | **Mean** | Arithmetic mean of quartet distances (default) |
| `1` | **Median** | Median of quartet distances |
| `2` | **Mode** | Mode (most frequent value) of quartet distances |
| `3` | **Trimmed Mean** | Mean after removing outliers beyond ±2 standard deviations |

### Tree Construction Methods (`-f`)

| Value | Name | Description |
|-------|------|-------------|
| `0` | **FastME_BAL** | Balanced Minimum Evolution via FastME (default) |
| `1` | **FastME_NJ** | Neighbor Joining via FastME |
| `2` | **FastME_UNJ** | Unweighted Neighbor Joining via FastME |

> **Note:** If the distance matrix is incomplete (i.e., some taxa pairs never co-occur in any gene tree), BIONJ is used automatically regardless of the `-f` flag.

---

## Input Format

The input file should contain gene trees in **Newick format**, one tree per line. Branch lengths are optional. Trees may contain overlapping but not necessarily identical taxon sets.

**Example** (excerpt from `all_gt_37.tre`):

```
(((MON:0.037,MAC:0.034):0.070,(...)):0.270,GAL:0.409);
((ORN:0.209,((MAC:0.059,MON:0.225):0.008,...)):0.175,GAL:0.326);
```

The included example file `all_gt_37.tre` contains **200 gene trees** over **37 mammalian taxa**.

---

## Output Format

The output is a single species tree in **Newick format** with branch lengths, written to the file specified by `-o`.

---

## Direct Invocation (Advanced)

For users who prefer to bypass the wrapper script:

```bash
# 1. Build (if needed) — run from the Summarizer/ directory
cd Summarizer
flex -o _steq_temp.c STEQ.l
g++ _steq_temp.c -lfl -o STEQ.out
rm -f _steq_temp.c

# 2. Ensure binaries are executable
chmod +x ../Binaries/fastme-2.1.5-linux64
chmod +x ../Binaries/BIONJ

# 3. Run (must be invoked from the Summarizer/ directory)
./STEQ.out <input_file> <central_tendency> <matrix_output> <tree_output> <fastme_type>

# Example:
./STEQ.out ../all_gt_37.tre 0 ../out_matrix.txt ../out_tree.tre 0
```

> **Important:** `STEQ.out` must be run from the `Summarizer/` directory because it references `../Binaries/` internally.

---

## Project Structure

```
STEQ/
├── run_steq.sh                  # Main wrapper script (recommended entry point)
├── cmd.txt                      # Example commands reference
├── all_gt_37.tre                # Example dataset (37 taxa, 200 gene trees)
├── Summarizer/
│   ├── STEQ.l                   # Core STEQ implementation (Flex lexer + C++)
│   ├── STEQ.out                 # Pre-built STEQ binary
│   ├── GeneTree.cpp             # Gene tree data structure and quartet distance computation
│   ├── Central_Tendency.cpp     # Central tendency functions (mean, median, mode, trimmed mean)
│   ├── bipartition.l            # Bipartition decomposition utility
│   └── LexToOut                 # Legacy build helper script
├── Binaries/
│   ├── fastme-2.1.5-linux64     # FastME distance-based tree builder
│   ├── BIONJ                    # BIONJ tree builder (for incomplete matrices)
│   ├── ASTRID                   # ASTRID species tree method
│   ├── astral.5.7.3.jar         # ASTRAL species tree method
│   └── phylonet_v2_4.jar        # PhyloNet
├── Decomposition/               # Tree decomposition utilities (PRD, DCM)
│   ├── PRD.py
│   ├── prd_decomp.py
│   ├── extract_subsets.pl
│   └── ...
└── GTM/                         # Guide Tree Merger
    ├── gtm.py
    ├── treeutils.py
    └── example/
```

---

## How It Works

1. **Parse gene trees** — Each gene tree (Newick format) is parsed using a Flex-based lexer. Non-binary trees are detected and skipped.

2. **Compute quartet distances** — For every pair of taxa, STEQ collects quartet-based distance measurements across all gene trees in which both taxa are present. The distance is computed by traversing internal nodes on the path between the two taxa and accumulating a score based on the descendant counts in each subtree partition.

3. **Aggregate distances** — The per-gene-tree distance measurements for each taxon pair are aggregated using the chosen central tendency measure (mean, median, mode, or trimmed mean).

4. **Build distance matrix** — A pairwise distance matrix over all taxa is constructed.

5. **Infer species tree** — The species tree is inferred from the distance matrix using a distance-based tree construction algorithm:
   - **Complete matrix** → FastME (BAL, NJ, or UNJ as specified)
   - **Incomplete matrix** → BIONJ (handles missing entries)

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `flex: command not found` | Flex not installed | `sudo apt-get install -y flex` |
| `g++: command not found` | G++ not installed | `sudo apt-get install -y g++` |
| `cannot find -lfl` | libfl-dev not installed | `sudo apt-get install -y libfl-dev` |
| `STEQ.out` not executable | File permissions | `chmod +x Summarizer/STEQ.out` |
| Empty output / no tree produced | Malformed input file | Ensure Newick format, one tree per line, semicolon-terminated |
| `Non-Binary Tree` messages | Input contains multifurcating trees | Non-binary trees are skipped automatically; ensure enough binary trees remain |
| `Cannot open specified file` | Input path not found | Check the file path; use absolute paths if unsure |

---

## Citation

If you use STEQ in your research, please cite:

> *STEQ: Species Tree Estimation using Quartet Distances*

---

## License

Please refer to the repository for license information.
