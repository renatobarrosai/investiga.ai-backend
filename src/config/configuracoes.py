# src/config/configuracoes.py
import os
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ConfiguracaoGPU:
    """
    Define os parâmetros para o monitoramento e gerenciamento de GPUs.
    """
    intervalo_atualizacao: float = 1.0  # Frequência de atualização dos dados da GPU (em segundos)
    threshold_memoria_critico: float = 90.0  # Limite percentual de memória para alertas críticos
    threshold_memoria_alto: float = 75.0  # Limite percentual de memória para alertas de uso alto
    threshold_utilizacao_alto: float = 85.0  # Limite percentual de utilização para alertas
    margem_seguranca_memoria: float = 512.0  # Memória (MB) a ser mantida livre como margem de segurança

@dataclass
class ConfiguracaoScheduler:
    """
    Define as regras de funcionamento para o agendador de modelos.
    """
    tempo_inatividade_descarregar: float = 300.0  # Tempo (segundos) para descarregar um modelo inativo
    max_modelos_simultaneos: int = 3  # Número máximo de modelos carregados ao mesmo tempo

@dataclass
class ConfiguracaoFilas:
    """
    Parâmetros para o sistema de filas de requisições.
    """
    max_concurrent: int = 3  # Número máximo de requisições processadas simultaneamente
    timeout_padrao: float = 300.0  # Tempo de espera padrão para uma requisição (em segundos)

@dataclass
class ConfiguracoesSistema:
    """
    Agrega todas as configurações do sistema, fornecendo um ponto central de acesso.
    """
    gpu: ConfiguracaoGPU = ConfiguracaoGPU()
    scheduler: ConfiguracaoScheduler = ConfiguracaoScheduler()
    filas: ConfiguracaoFilas = ConfiguracaoFilas()
    
    # Estrutura de diretórios
    diretorio_modelos: str = "models"
    diretorio_cache: str = "cache"
    diretorio_logs: str = "logs"
    
    # Configurações de logging
    nivel_log: str = "INFO"
    arquivo_log: str = "logs/sistema.log"
    
    @classmethod
    def carregar_do_ambiente(cls) -> 'ConfiguracoesSistema':
        """
        Cria uma instância de configuração, sobrepondo os valores padrão
        com aqueles definidos em variáveis de ambiente, se existirem.

        Returns:
            ConfiguracoesSistema: Uma instância do objeto de configurações.
        """
        config = cls()
        
        # Carrega configurações da GPU a partir de variáveis de ambiente
        config.gpu.threshold_memoria_critico = float(
            os.getenv('GPU_THRESHOLD_CRITICO', config.gpu.threshold_memoria_critico)
        )
        config.gpu.threshold_memoria_alto = float(
            os.getenv('GPU_THRESHOLD_ALTO', config.gpu.threshold_memoria_alto)
        )
        
        # Carrega configurações do Scheduler
        config.scheduler.tempo_inatividade_descarregar = float(
            os.getenv('SCHEDULER_TEMPO_INATIVIDADE', config.scheduler.tempo_inatividade_descarregar)
        )
        
        # Carrega configurações das Filas
        config.filas.max_concurrent = int(
            os.getenv('FILAS_MAX_CONCURRENT', config.filas.max_concurrent)
        )
        
        return config