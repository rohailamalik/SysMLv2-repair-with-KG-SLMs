MODEL_CONFIGS = {
    "qwen_coder_1p5b": {
        "model_name": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "learning_rate": 5e-5,
        "batch_size": 8,
        "grad_accum": 2,
        "epochs": 3,
    },

    "starcoder2_3b": {
        "model_name": "bigcode/starcoder2-3b",
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "learning_rate": 3e-5,
        "batch_size": 4,
        "grad_accum": 4,
        "epochs": 3,
    },

    "deepseek_coder_6p7b": {
        "model_name": "deepseek-ai/deepseek-coder-6.7b-base",
        "lora_r": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "learning_rate": 2e-5,
        "batch_size": 2,
        "grad_accum": 8,
        "epochs": 3,
    }
}

TRAIN_TYPES = ["code", "patch"]
TEST_TYPES = ["baseline", "rag_only", "fine_tuned_code", "fine_tuned_patch"]
MAX_GEN_TOKEN_LENGTH = 2048
TEST_BATCH_SIZE = 64