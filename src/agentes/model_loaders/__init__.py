# src/agentes/model_loaders/__init__.py

"""
Módulo de carregadores especializados para diferentes tipos de modelos.

Este pacote contém loaders otimizados para:
- Gemma-2B com quantização AWQ (recepcionista, apresentador, segurança)
- Phi-3-Vision para análise multimodal (classificador)
- Llama-3-8B com quantização GPTQ (deconstrutor, sintetizador)

Cada loader é responsável por:
- Carregamento otimizado com quantização específica
- Gerenciamento de memória GPU/CPU
- Integração com registry e monitoring
- Error handling e recovery
- Geração de respostas com parâmetros otimizados
"""

from .gemma_loader import GemmaLoader, GemmaLoadResult

# Imports condicionais para loaders que serão implementados
try:
    # Será implementado na próxima etapa
    # from .phi3_loader import Phi3Loader, Phi3LoadResult
    pass
except ImportError:
    pass

try:
    # Será implementado na Fase 3
    # from .llama3_loader import Llama3Loader, Llama3LoadResult  
    pass
except ImportError:
    pass

__all__ = [
    'GemmaLoader',
    'GemmaLoadResult',
    # 'Phi3Loader',
    # 'Phi3LoadResult', 
    # 'Llama3Loader',
    # 'Llama3LoadResult'
]

# Metadata do módulo
__version__ = "1.0.0"
__author__ = "Investiga.AI Team"
__description__ = "Loaders especializados para modelos de IA do sistema de fact-checking"
