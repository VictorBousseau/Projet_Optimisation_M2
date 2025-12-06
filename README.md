# Optimization Project: Video Caching

This project solves the hashcode 2017 qualification round problem using Gurobi optimization.

## Prerequisites

- Python 3.13 or compatible
- Gurobi Optimizer license (academic or commercial)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/VictorBousseau/Projet_Optimisation_M2.git
    cd Projet_Optimisation_M2
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the script by providing the path to a dataset file:

```bash
python videos.py path/to/dataset.in
```

### Example

To run with the provided example dataset:

```bash
python videos.py data/example.in
```

The script will generate:
- `videos.mps`: The Gurobi model file.
- `videos.out`: The solution file.
