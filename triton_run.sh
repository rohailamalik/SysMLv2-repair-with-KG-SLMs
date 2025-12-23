#!/bin/bash
#SBATCH --time=6:00:00
#SBATCH --mem=100G
#SBATCH --gpus=1
#SBATCH --gres=min-vram:40g,min-cuda-cc:80
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

module load mamba
source activate sysml_fix

export HF_HOME=/scratch/work/$USER/hf
export TOKENIZERS_PARALLELISM=false

srun python training.py --model qwen_coder_1p5b --type code
srun python training.py --model qwen_coder_1p5b --type patch
srun python testing.py --model qwen_coder_1p5b --type fine_tuned_code
srun python testing.py --model qwen_coder_1p5b --type fine_tuned_patch
srun python testing.py --model qwen_coder_1p5b --type baseline
srun python testing.py --model qwen_coder_1p5b --type rag_only