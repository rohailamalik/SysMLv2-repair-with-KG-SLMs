# SysML v2 Repair with Domain-Aware Language Models

This repository contains code for fine-tuning and evaluating small language models (augmented through a rule knowledge graph) for repairing **SysML v2 models** with **syntactic and semantic errors**.

## Overview

The repository supports the full pipeline for:

- Compiling and formatting datasets for model training and evaluation
- Fine-tuning instruction-tuned language models using LoRA
- Testing models on SysML v2 repair tasks
- Analyzing generated repairs against ground-truth models

For each example, SysML v2 code is provided to the model along with:
- Compiler error messages (for syntactic errors), or
- Relevant domain rules (for semantic or uncaught errors)

Semantic errors are not detected by the SysML v2 compiler and therefore require domain knowledge to localize and repair.

## Models

The following instruction-tuned models are considered:

- **Qwen2.5-Coder 1.5B**
- **DeepSeek-Coder 6.7B**

Each base model is evaluated under multiple configurations:
- Without domain rules
- With domain rules appended to prompts
- Fine-tuned to generate repaired SysML v2 code
- Fine-tuned to generate unified diff patches

Fine-tuning is performed separately for code repair and patch generation tasks.

## Dataset and Artifacts

The repository includes code for:
- Dataset synthesis and compilation
- Prompt and response formatting
- Patch creation and application
- Training, testing, and result analysis

**Note:**  
Model weights and datasets are provided as compressed archives and must be extracted into the repository for the code to function correctly.

---

## Repository Structure

- `results/`: Outputs from LoRA fine-tuning and testing across all configurations.
- `knowledge/`: Domain knowledge graphs used for semantic error localization.
- `config.py`: Training and testing configuration parameters.
- `dataset_compilation.ipynb`: Dataset compilation and splitting notebook.
- `formatting.py`: Prompt and response formatting utilities.
- `patching.py`: Unified diff patch creation and application.
- `generate_domain_aware.ipynb`: Semantic error synthesis notebook.
- `training.py`: LoRA fine-tuning script.
- `testing.py`: Autoregressive evaluation script.
- `results_analysis.ipynb`: Results analysis notebook.
- `inference_testing.ipynb`: Interactive inference testing notebook.
- `hpc_run.sh`: Cluster execution script.
- `environment.yml`: Mamba environment specification.

## Citation

If you use this repository in your research, please cite:

```bibtex
@inproceedings{alshami2026sysml,
  title={Automated Semantic Fault Localization in SysML v2: A Human-in-the-Loop Framework Using Knowledge-Graph Augmented LLMs},
  author={Al-Shami, Haitham and Malik, Rohail and Ala-Laurinaho, Riku and Veps{\"a}l{\"a}inen, Jari and Viitala, Raine},
  booktitle={Proceedings of the 36th INCOSE International Symposium},
  year={2026},
  address={Yokohama, Japan},
  month={June},
  date={16}
}
```
