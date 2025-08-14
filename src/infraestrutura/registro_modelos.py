# src/infraestrutura/registro_modelos.py
import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path

class StatusModelo(Enum):
    """Status possíveis de um modelo"""
    DESCARREGADO = "descarregado"
    CARREGANDO = "carregando"
    CARREGADO = "carregado"
    ERRO = "erro"

class TipoQuantizacao(Enum):
    """Tipos de quantização suportados"""
    NENHUMA = "nenhuma"
    GPTQ = "gptq"
    AWQ = "awq"
    GGUF = "gguf"

@dataclass
class MetadadosModelo:
    """Metadados completos de um modelo"""
    nome: str
    caminho: str
    tipo_modelo: str  # "llm", "vision", "audio"
    memoria_necessaria_mb: float
    quantizacao: TipoQuantizacao
    especialidade: str  # "recepcionista", "deconstrutor", etc.
    versao: str
    prioridade: int  # 1-10, maior = mais prioritário
    dependencias: List[str]
    configuracoes: Dict[str, any]
    
class RegistroModelos:
    """Registry central para gerenciar metadados de todos os modelos"""
    
    def __init__(self, arquivo_config: str = "config/modelos.json"):
        self.arquivo_config = Path(arquivo_config)
        self.logger = logging.getLogger(__name__)
        self.modelos: Dict[str, MetadadosModelo] = {}
        self.status_modelos: Dict[str, StatusModelo] = {}
        self.gpu_alocacoes: Dict[str, int] = {}  # modelo -> gpu_id
        
        self._carregar_configuracao()
        
    def _carregar_configuracao(self) -> None:
        """Carrega configuração de modelos do arquivo JSON"""
        try:
            if self.arquivo_config.exists():
                with open(self.arquivo_config, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for nome, dados in config.items():
                    self.registrar_modelo(MetadadosModelo(**dados))
                    
                self.logger.info(f"Carregados {len(self.modelos)} modelos do registry")
            else:
                self._criar_configuracao_padrao()
                
        except Exception as e:
            self.logger.error(f"Erro ao carregar configuração: {e}")
            self._criar_configuracao_padrao()
            
    def _criar_configuracao_padrao(self) -> None:
        """Cria configuração padrão para o sistema"""
        modelos_padrao = {
            "gemma-2b-recepcionista": MetadadosModelo(
                nome="gemma-2b-recepcionista",
                caminho="models/gemma-2b-it-quantized",
                tipo_modelo="llm",
                memoria_necessaria_mb=2048,
                quantizacao=TipoQuantizacao.AWQ,
                especialidade="recepcionista",
                versao="1.0",
                prioridade=8,
                dependencias=[],
                configuracoes={"max_tokens": 512, "temperature": 0.1}
            ),
            "llama-3-8b-deconstrutor": MetadadosModelo(
                nome="llama-3-8b-deconstrutor",
                caminho="models/llama-3-8b-quantized",
                tipo_modelo="llm",
                memoria_necessaria_mb=6144,
                quantizacao=TipoQuantizacao.GPTQ,
                especialidade="deconstrutor",
                versao="1.0",
                prioridade=9,
                dependencias=[],
                configuracoes={"max_tokens": 1024, "temperature": 0.2}
            ),
            "phi-3-vision-classificador": MetadadosModelo(
                nome="phi-3-vision-classificador",
                caminho="models/phi-3-vision-128k",
                tipo_modelo="vision",
                memoria_necessaria_mb=4096,
                quantizacao=TipoQuantizacao.NENHUMA,
                especialidade="classificador",
                versao="1.0",
                prioridade=7,
                dependencias=[],
                configuracoes={"max_tokens": 256}
            )
        }
        
        for modelo in modelos_padrao.values():
            self.registrar_modelo(modelo)
            
        self._salvar_configuracao()
        
    def registrar_modelo(self, metadados: MetadadosModelo) -> None:
        """Registra um novo modelo no sistema"""
        self.modelos[metadados.nome] = metadados
        self.status_modelos[metadados.nome] = StatusModelo.DESCARREGADO
        
        self.logger.info(f"Modelo registrado: {metadados.nome}")
        
    def obter_metadados(self, nome_modelo: str) -> Optional[MetadadosModelo]:
        """Retorna metadados de um modelo específico"""
        return self.modelos.get(nome_modelo)
        
    def listar_modelos_por_especialidade(self, especialidade: str) -> List[MetadadosModelo]:
        """Lista todos os modelos de uma especialidade"""
        return [
            modelo for modelo in self.modelos.values()
            if modelo.especialidade == especialidade
        ]
        
    def obter_modelos_carregados(self) -> List[str]:
        """Retorna lista de modelos atualmente carregados"""
        return [
            nome for nome, status in self.status_modelos.items()
            if status == StatusModelo.CARREGADO
        ]
        
    def atualizar_status(self, nome_modelo: str, status: StatusModelo, id_gpu: Optional[int] = None) -> None:
        """Atualiza o status de um modelo"""
        if nome_modelo not in self.modelos:
            raise ValueError(f"Modelo não registrado: {nome_modelo}")
            
        self.status_modelos[nome_modelo] = status
        
        if status == StatusModelo.CARREGADO and id_gpu is not None:
            self.gpu_alocacoes[nome_modelo] = id_gpu
        elif status == StatusModelo.DESCARREGADO and nome_modelo in self.gpu_alocacoes:
            del self.gpu_alocacoes[nome_modelo]
            
        self.logger.info(f"Status atualizado: {nome_modelo} -> {status.value}")
        
    def calcular_memoria_total_necessaria(self, nomes_modelos: List[str]) -> float:
        """Calcula memória total necessária para carregar múltiplos modelos"""
        total = 0.0
        for nome in nomes_modelos:
            modelo = self.obter_metadados(nome)
            if modelo:
                total += modelo.memoria_necessaria_mb
        return total
        
    def _salvar_configuracao(self) -> None:
        """Salva configuração atual no arquivo"""
        try:
            self.arquivo_config.parent.mkdir(parents=True, exist_ok=True)
            
            config = {
                nome: asdict(metadados) 
                for nome, metadados in self.modelos.items()
            }
            
            # Converter enums para strings
            for dados in config.values():
                dados['quantizacao'] = dados['quantizacao'].value
                
            with open(self.arquivo_config, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração: {e}")