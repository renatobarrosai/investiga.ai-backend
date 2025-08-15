# src/agentes/prompts/prompt_manager.py
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class TipoPrompt(Enum):
    """Tipos de prompt no sistema"""
    ESTRUTURACAO = "estruturacao"          # Recepcionista - estruturar entrada
    VALIDACAO = "validacao"                # Recepcionista - validar parsing
    RESPOSTA_SUCESSO = "resposta_sucesso"  # Apresentador - resultado positivo
    RESPOSTA_INCERTA = "resposta_incerta"  # Apresentador - resultado incerto
    RESPOSTA_FALSO = "resposta_falso"      # Apresentador - resultado negativo
    EXPLICACAO_TECNICA = "explicacao_tecnica" # Apresentador - detalhes técnicos

class ContextoUsuario(Enum):
    """Contextos de interação com usuário"""
    CASUAL = "casual"                    # Linguagem informal, cotidiana
    JORNALISTICO = "jornalistico"        # Contexto de mídia, profissional
    ACADEMICO = "academico"              # Contexto educacional, formal
    INVESTIGATIVO = "investigativo"      # Apuração detalhada, crítica

@dataclass
class PromptTemplate:
    """Template de prompt com metadados"""
    nome: str
    tipo: TipoPrompt
    contexto: ContextoUsuario
    template: str
    variaveis: List[str]
    instrucoes_especiais: Optional[str] = None
    exemplos: Optional[List[Dict]] = None
