# src/config/model_configs.py
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from .configuracoes import ConfiguracoesSistema

@dataclass
class ConfiguracaoModelo:
    """Configuração específica de um modelo"""
    nome: str
    caminho: str
    tipo_modelo: str  # "llm", "vision", "audio"
    quantizacao: str  # "gptq", "awq", "nenhuma"
    especialidade: str
    
    # Recursos necessários
    memoria_mb: float
    gpu_minima: int = 0  # GPU mínima requerida (por compute capability)
    
    # Configurações de inferência
    max_tokens: int = 512
    temperature: float = 0.1
    top_p: float = 0.95
    top_k: int = 50
    repetition_penalty: float = 1.1
    
    # Configurações específicas do modelo
    trust_remote_code: bool = True
    torch_dtype: str = "auto"
    device_map: str = "auto"
    low_cpu_mem_usage: bool = True
    
    # Configurações de quantização
    quantization_config: Dict[str, Any] = field(default_factory=dict)
    
    # Configurações de loading
    loading_timeout: float = 300.0
    retry_attempts: int = 3
    preload_weights: bool = False
    
    # Metadados
    versao: str = "1.0"
    descricao: str = ""
    tags: List[str] = field(default_factory=list)

# Configurações específicas por tipo de quantização
QUANTIZATION_CONFIGS = {
    "gptq": {
        "bits": 4,
        "group_size": 128,
        "damp_percent": 0.1,
        "desc_act": False,
        "static_groups": False,
        "true_sequential": True,
        "model_seqlen": 2048,
        "use_cuda_fp16": True,
        "use_triton": True,
        "inject_fused_attention": True,
        "inject_fused_mlp": True,
        "use_safetensors": True,
        "warmup_autotune": True
    },
    "awq": {
        "bits": 4,
        "group_size": 128,
        "zero_point": True,
        "version": "GEMM",
        "use_exllama": True,
        "exllama_config": {
            "version": 1,
            "max_input_len": 2048,
            "max_batch_size": 1
        }
    }
}

# Configurações base por especialidade
ESPECIALIDADE_CONFIGS = {
    "recepcionista": {
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
        "repetition_penalty": 1.05,
        "tags": ["estruturacao", "entrada", "parsing"]
    },
    "classificador": {
        "max_tokens": 256,
        "temperature": 0.1,
        "top_p": 0.85,
        "repetition_penalty": 1.1,
        "tags": ["classificacao", "multimodal", "analise"]
    },
    "seguranca": {
        "max_tokens": 128,
        "temperature": 0.05,
        "top_p": 0.8,
        "repetition_penalty": 1.2,
        "tags": ["seguranca", "deteccao", "protecao"]
    },
    "deconstrutor": {
        "max_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.9,
        "repetition_penalty": 1.1,
        "tags": ["reasoning", "extracao", "logica"]
    },
    "sintetizador": {
        "max_tokens": 2048,
        "temperature": 0.3,
        "top_p": 0.92,
        "repetition_penalty": 1.05,
        "tags": ["sintese", "analise", "conclusao"]
    },
    "apresentador": {
        "max_tokens": 1024,
        "temperature": 0.3,
        "top_p": 0.95,
        "repetition_penalty": 1.0,
        "tags": ["apresentacao", "formatacao", "comunicacao"]
    }
}

def criar_config_modelo(nome: str, caminho: str, tipo_modelo: str, 
                       quantizacao: str, especialidade: str, 
                       memoria_mb: float, **kwargs) -> ConfiguracaoModelo:
    """Factory function para criar configuração de modelo"""
    
    # Configurações base da especialidade
    config_especialidade = ESPECIALIDADE_CONFIGS.get(especialidade, {})
    
    # Configurações de quantização
    config_quant = QUANTIZATION_CONFIGS.get(quantizacao, {})
    
    # Merge de todas as configurações
    config = ConfiguracaoModelo(
        nome=nome,
        caminho=caminho,
        tipo_modelo=tipo_modelo,
        quantizacao=quantizacao,
        especialidade=especialidade,
        memoria_mb=memoria_mb,
        quantization_config=config_quant,
        **config_especialidade,
        **kwargs
    )
    
    return config

# Obter configurações do sistema
_config_sistema = ConfiguracoesSistema.carregar_do_ambiente()

# ============================================================================
# CONFIGURAÇÕES DOS MODELOS DO SISTEMA
# ============================================================================

MODEL_CONFIGS = {
    "gemma-2b-recepcionista": criar_config_modelo(
        nome="gemma-2b-recepcionista",
        caminho=os.getenv("GEMMA_2B_PATH", f"{_config_sistema.diretorio_modelos}/gemma-2b-it-awq"),
        tipo_modelo="llm",
        quantizacao="awq",
        especialidade="recepcionista",
        memoria_mb=2048,
        descricao="Gemma-2B otimizado para recepção e estruturação de entradas do usuário",
        versao="1.0"
    ),
    
    "gemma-2b-apresentador": criar_config_modelo(
        nome="gemma-2b-apresentador", 
        caminho=os.getenv("GEMMA_2B_PATH", f"{_config_sistema.diretorio_modelos}/gemma-2b-it-awq"),
        tipo_modelo="llm",
        quantizacao="awq",
        especialidade="apresentador",
        memoria_mb=2048,
        descricao="Gemma-2B otimizado para apresentação e formatação de resultados",
        versao="1.0"
    ),
    
    "gemma-2b-seguranca": criar_config_modelo(
        nome="gemma-2b-seguranca",
        caminho=os.getenv("GEMMA_2B_SECURITY_PATH", f"{_config_sistema.diretorio_modelos}/gemma-2b-security-finetuned"),
        tipo_modelo="llm", 
        quantizacao="awq",
        especialidade="seguranca",
        memoria_mb=2048,
        descricao="Gemma-2B fine-tuned para detecção de ameaças e segurança",
        versao="1.0-ft",
        tags=["fine-tuned", "security", "brazilian-threats"]
    ),
    
    "phi3-vision-classificador": criar_config_modelo(
        nome="phi3-vision-classificador",
        caminho=os.getenv("PHI3_VISION_PATH", f"{_config_sistema.diretorio_modelos}/phi-3-vision-128k-instruct"),
        tipo_modelo="vision",
        quantizacao="nenhuma",
        especialidade="classificador", 
        memoria_mb=4096,
        gpu_minima=6,  # Requer GPU mais moderna
        torch_dtype="bfloat16",
        descricao="Phi-3-Vision para classificação multimodal e análise visual",
        versao="1.0",
        # Configurações específicas de visão
        max_image_size=1024,
        vision_feature_layer=-2,
        vision_feature_select_strategy="default"
    ),
    
    "llama3-8b-deconstrutor": criar_config_modelo(
        nome="llama3-8b-deconstrutor",
        caminho=os.getenv("LLAMA3_8B_PATH", f"{_config_sistema.diretorio_modelos}/llama-3-8b-instruct-gptq"),
        tipo_modelo="llm",
        quantizacao="gptq", 
        especialidade="deconstrutor",
        memoria_mb=6144,
        gpu_minima=8,  # Requer GPU com mais VRAM
        descricao="Llama-3-8B quantizado para deconstrução e extração de alegações",
        versao="1.0"
    ),
    
    "llama3-8b-sintetizador": criar_config_modelo(
        nome="llama3-8b-sintetizador",
        caminho=os.getenv("LLAMA3_8B_PATH", f"{_config_sistema.diretorio_modelos}/llama-3-8b-instruct-gptq"),
        tipo_modelo="llm",
        quantizacao="gptq",
        especialidade="sintetizador", 
        memoria_mb=6144,
        gpu_minima=8,
        descricao="Llama-3-8B quantizado para síntese e análise de evidências",
        versao="1.0"
    )
}

# ============================================================================
# CONFIGURAÇÕES POR AMBIENTE
# ============================================================================

class ConfiguracoesAmbiente:
    """Configurações específicas por ambiente de execução"""
    
    @staticmethod
    def desenvolvimento():
        """Configurações para ambiente de desenvolvimento"""
        configs = MODEL_CONFIGS.copy()
        
        # Reduzir timeouts e recursos para desenvolvimento
        for config in configs.values():
            config.loading_timeout = 120.0  # 2 minutos
            config.memoria_mb *= 0.8  # Reduzir 20% da memória
            config.max_tokens = min(config.max_tokens, 512)  # Limitar tokens
            
        return configs
    
    @staticmethod
    def producao():
        """Configurações para ambiente de produção"""
        configs = MODEL_CONFIGS.copy()
        
        # Otimizações para produção
        for config in configs.values():
            config.loading_timeout = 600.0  # 10 minutos
            config.retry_attempts = 5
            config.preload_weights = True  # Preload para performance
            
        return configs
    
    @staticmethod
    def aws():
        """Configurações para deployment na AWS"""
        configs = ConfiguracoesAmbiente.producao()
        
        # Otimizações específicas para AWS
        for config in configs.values():
            config.device_map = "auto"
            config.low_cpu_mem_usage = True
            
            # Usar paths do S3 se disponível
            s3_path = os.getenv(f"S3_{config.nome.upper().replace('-', '_')}_PATH")
            if s3_path:
                config.caminho = s3_path
                
        return configs

# ============================================================================
# CONFIGURAÇÕES DE PIPELINE
# ============================================================================

PIPELINE_CONFIGS = {
    "fact_check_completo": {
        "modelos_necessarios": [
            "gemma-2b-recepcionista",
            "phi3-vision-classificador", 
            "llama3-8b-deconstrutor",
            "llama3-8b-sintetizador",
            "gemma-2b-apresentador"
        ],
        "sequencia_carregamento": [
            "gemma-2b-recepcionista",  # Sempre primeiro
            "phi3-vision-classificador",  # Para classificação
            "llama3-8b-deconstrutor",  # Para reasoning
            "llama3-8b-sintetizador",  # Para síntese
            "gemma-2b-apresentador"  # Para apresentação
        ],
        "modelos_opcionais": ["gemma-2b-seguranca"],
        "memoria_total_mb": 16384,
        "timeout_pipeline": 900.0  # 15 minutos
    },
    
    "fact_check_rapido": {
        "modelos_necessarios": [
            "gemma-2b-recepcionista",
            "phi3-vision-classificador"
        ],
        "sequencia_carregamento": [
            "gemma-2b-recepcionista",
            "phi3-vision-classificador"
        ],
        "modelos_opcionais": [],
        "memoria_total_mb": 6144,
        "timeout_pipeline": 300.0  # 5 minutos
    },
    
    "processamento_arquivo": {
        "modelos_necessarios": [
            "phi3-vision-classificador",
            "gemma-2b-recepcionista"
        ],
        "sequencia_carregamento": [
            "phi3-vision-classificador",  # Primeiro para análise
            "gemma-2b-recepcionista"  # Para estruturação
        ],
        "modelos_opcionais": ["gemma-2b-seguranca"],
        "memoria_total_mb": 6144,
        "timeout_pipeline": 600.0  # 10 minutos
    }
}

# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def obter_config_modelo(nome_modelo: str, ambiente: str = "desenvolvimento") -> Optional[ConfiguracaoModelo]:
    """Obtém configuração de um modelo específico para um ambiente"""
    ambiente_configs = {
        "desenvolvimento": ConfiguracoesAmbiente.desenvolvimento(),
        "producao": ConfiguracoesAmbiente.producao(),
        "aws": ConfiguracoesAmbiente.aws()
    }
    
    configs = ambiente_configs.get(ambiente, ConfiguracoesAmbiente.desenvolvimento())
    return configs.get(nome_modelo)

def obter_config_pipeline(tipo_pipeline: str) -> Optional[Dict]:
    """Obtém configuração de um pipeline específico"""
    return PIPELINE_CONFIGS.get(tipo_pipeline)

def validar_config_modelo(config: ConfiguracaoModelo) -> List[str]:
    """Valida uma configuração de modelo e retorna lista de erros"""
    erros = []
    
    # Validar caminho
    if not config.caminho:
        erros.append("Caminho do modelo não especificado")
    elif not Path(config.caminho).exists() and not config.caminho.startswith(("s3://", "http")):
        erros.append(f"Caminho do modelo não encontrado: {config.caminho}")
    
    # Validar memória
    if config.memoria_mb <= 0:
        erros.append("Memória necessária deve ser maior que 0")
    
    # Validar configurações de inferência
    if config.max_tokens <= 0:
        erros.append("max_tokens deve ser maior que 0")
    
    if not 0 <= config.temperature <= 2:
        erros.append("temperature deve estar entre 0 e 2")
        
    if not 0 <= config.top_p <= 1:
        erros.append("top_p deve estar entre 0 e 1")
    
    # Validar quantização
    if config.quantizacao not in ["gptq", "awq", "nenhuma"]:
        erros.append(f"Tipo de quantização inválido: {config.quantizacao}")
    
    return erros

def calcular_memoria_pipeline(tipo_pipeline: str, ambiente: str = "desenvolvimento") -> float:
    """Calcula memória total necessária para um pipeline"""
    config_pipeline = obter_config_pipeline(tipo_pipeline)
    if not config_pipeline:
        return 0.0
    
    configs_ambiente = {
        "desenvolvimento": ConfiguracoesAmbiente.desenvolvimento(),
        "producao": ConfiguracoesAmbiente.producao(),
        "aws": ConfiguracoesAmbiente.aws()
    }
    
    configs = configs_ambiente.get(ambiente, ConfiguracoesAmbiente.desenvolvimento())
    
    memoria_total = 0.0
    for nome_modelo in config_pipeline["modelos_necessarios"]:
        config_modelo = configs.get(nome_modelo)
        if config_modelo:
            memoria_total += config_modelo.memoria_mb
    
    return memoria_total

def obter_modelos_por_especialidade(especialidade: str, ambiente: str = "desenvolvimento") -> List[ConfiguracaoModelo]:
    """Obtém todos os modelos de uma especialidade específica"""
    configs_ambiente = {
        "desenvolvimento": ConfiguracoesAmbiente.desenvolvimento(),
        "producao": ConfiguracoesAmbiente.producao(), 
        "aws": ConfiguracoesAmbiente.aws()
    }
    
    configs = configs_ambiente.get(ambiente, ConfiguracoesAmbiente.desenvolvimento())
    
    return [
        config for config in configs.values() 
        if config.especialidade == especialidade
    ]

# ============================================================================
# CONFIGURAÇÕES ESPECÍFICAS DE HARDWARE
# ============================================================================

HARDWARE_REQUIREMENTS = {
    "gpu_minima": {
        "compute_capability": 6.1,  # Pascal e superior
        "memoria_mb": 8192,  # 8GB mínimo
        "driver_version": "470.0"
    },
    "gpu_recomendada": {
        "compute_capability": 8.0,  # Ampere e superior  
        "memoria_mb": 16384,  # 16GB recomendado
        "driver_version": "520.0"
    },
    "cpu_minimo": {
        "cores": 4,
        "ram_gb": 16,
        "arquitetura": "x86_64"
    },
    "storage": {
        "espaco_modelos_gb": 50,  # 50GB para todos os modelos
        "tipo_recomendado": "SSD",
        "iops_minimo": 1000
    }
}

def verificar_compatibilidade_hardware() -> Dict[str, bool]:
    """Verifica se o hardware atual é compatível com os requisitos"""
    # Implementação simplificada - seria expandida com verificações reais
    return {
        "gpu_compativel": True,  # Verificação real da GPU
        "memoria_suficiente": True,  # Verificação real da memória
        "storage_suficiente": True,  # Verificação real do storage
        "driver_compativel": True  # Verificação real do driver
    }
