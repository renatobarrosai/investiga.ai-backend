# src/infraestrutura/registro_modelos.py
import json
import logging
import threading
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path

class StatusModelo(Enum):
    """Status possíveis de um modelo"""
    DESCARREGADO = "descarregado"
    CARREGANDO = "carregando"
    CARREGADO = "carregado"
    DESCARREGANDO = "descarregando"
    ERRO = "erro"
    ERRO_MEMORIA = "erro_memoria"
    ERRO_ARQUIVO = "erro_arquivo"

class TipoQuantizacao(Enum):
    """Tipos de quantização suportados"""
    NENHUMA = "nenhuma"
    GPTQ = "gptq"
    AWQ = "awq"
    GGUF = "gguf"

class EspecialidadeModelo(Enum):
    """Especialidades/funções dos modelos"""
    RECEPCIONISTA = "recepcionista"
    CLASSIFICADOR = "classificador"
    SEGURANCA = "seguranca"
    DECONSTRUTOR = "deconstrutor"
    SINTETIZADOR = "sintetizador"
    APRESENTADOR = "apresentador"

@dataclass
class MetadadosModelo:
    """Metadados completos de um modelo"""
    nome: str
    caminho: str
    tipo_modelo: str  # "llm", "vision", "audio"
    memoria_necessaria_mb: float
    quantizacao: TipoQuantizacao
    especialidade: EspecialidadeModelo
    versao: str
    prioridade: int  # 1-10, maior = mais prioritário
    dependencias: List[str]
    configuracoes: Dict[str, Any]
    
    # Metadados de performance (preenchidos dinamicamente)
    ultima_utilizacao: float = 0.0
    total_utilizacoes: int = 0
    tempo_medio_carregamento: float = 0.0
    taxa_sucesso: float = 100.0
    
    # Metadados do arquivo
    tamanho_arquivo_mb: float = 0.0
    hash_arquivo: str = ""
    data_modificacao: float = 0.0

@dataclass
class StatusDetalhado:
    """Status detalhado de um modelo incluindo contexto"""
    status: StatusModelo
    timestamp: float
    gpu_id: Optional[int] = None
    memoria_alocada_mb: float = 0.0
    tempo_no_status: float = 0.0
    erro_detalhes: Optional[str] = None
    processo_id: Optional[int] = None

class RegistroModelos:
    """Registry central para gerenciar metadados e status de todos os modelos"""
    
    def __init__(self, arquivo_config: str = "src/config/modelos.json", 
                 diretorio_cache: str = "cache/modelos"):
        self.arquivo_config = Path(arquivo_config)
        self.diretorio_cache = Path(diretorio_cache)
        self.logger = logging.getLogger(__name__)
        
        # Storage principal
        self.modelos: Dict[str, MetadadosModelo] = {}
        self.status_modelos: Dict[str, StatusDetalhado] = {}
        self.gpu_alocacoes: Dict[str, int] = {}  # modelo -> gpu_id
        
        # Callbacks para mudanças de status
        self.callbacks_status: List[Callable[[str, StatusModelo, StatusModelo], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cache de consultas frequentes
        self._cache_consultas = {}
        self._ultimo_cache_cleanup = time.time()
        
        # Inicialização
        self._inicializar_diretorios()
        self._carregar_configuracao()
        
    def _inicializar_diretorios(self):
        """Cria diretórios necessários"""
        self.arquivo_config.parent.mkdir(parents=True, exist_ok=True)
        self.diretorio_cache.mkdir(parents=True, exist_ok=True)
        
    def adicionar_callback_status(self, callback: Callable[[str, StatusModelo, StatusModelo], None]):
        """Adiciona callback para mudanças de status"""
        self.callbacks_status.append(callback)
        
    def _chamar_callbacks_status(self, nome_modelo: str, status_anterior: StatusModelo, status_novo: StatusModelo):
        """Chama todos os callbacks registrados"""
        for callback in self.callbacks_status:
            try:
                callback(nome_modelo, status_anterior, status_novo)
            except Exception as e:
                self.logger.error(f"Erro em callback de status: {e}")
                
    def _carregar_configuracao(self) -> None:
        """Carrega configuração de modelos do arquivo JSON"""
        try:
            if self.arquivo_config.exists():
                with open(self.arquivo_config, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for nome, dados in config.items():
                    # Converter strings enum de volta para enums
                    if 'quantizacao' in dados:
                        dados['quantizacao'] = TipoQuantizacao(dados['quantizacao'])
                    if 'especialidade' in dados:
                        dados['especialidade'] = EspecialidadeModelo(dados['especialidade'])
                        
                    metadados = MetadadosModelo(**dados)
                    self.registrar_modelo(metadados)
                    
                self.logger.info(f"Carregados {len(self.modelos)} modelos do registry")
            else:
                self.logger.info("Arquivo de configuração não encontrado, criando configuração padrão")
                self._criar_configuracao_padrao()
                
        except Exception as e:
            self.logger.error(f"Erro ao carregar configuração: {e}")
            self._criar_configuracao_padrao()
            
    def _criar_configuracao_padrao(self) -> None:
        """Cria configuração padrão para o sistema"""
        modelos_padrao = [
            MetadadosModelo(
                nome="gemma-2b-recepcionista",
                caminho="models/gemma-2b-it-awq",
                tipo_modelo="llm",
                memoria_necessaria_mb=2048,
                quantizacao=TipoQuantizacao.AWQ,
                especialidade=EspecialidadeModelo.RECEPCIONISTA,
                versao="1.0",
                prioridade=8,
                dependencias=[],
                configuracoes={
                    "max_tokens": 512, 
                    "temperature": 0.1,
                    "trust_remote_code": True
                }
            ),
            MetadadosModelo(
                nome="gemma-2b-apresentador",
                caminho="models/gemma-2b-it-awq",
                tipo_modelo="llm",
                memoria_necessaria_mb=2048,
                quantizacao=TipoQuantizacao.AWQ,
                especialidade=EspecialidadeModelo.APRESENTADOR,
                versao="1.0",
                prioridade=7,
                dependencias=[],
                configuracoes={
                    "max_tokens": 1024, 
                    "temperature": 0.3,
                    "trust_remote_code": True
                }
            ),
            MetadadosModelo(
                nome="phi3-vision-classificador",
                caminho="models/phi-3-vision-128k-instruct",
                tipo_modelo="vision",
                memoria_necessaria_mb=4096,
                quantizacao=TipoQuantizacao.NENHUMA,
                especialidade=EspecialidadeModelo.CLASSIFICADOR,
                versao="1.0",
                prioridade=9,
                dependencias=[],
                configuracoes={
                    "max_tokens": 512,
                    "temperature": 0.1,
                    "trust_remote_code": True
                }
            ),
            MetadadosModelo(
                nome="llama3-8b-deconstrutor",
                caminho="models/llama-3-8b-instruct-gptq",
                tipo_modelo="llm",
                memoria_necessaria_mb=6144,
                quantizacao=TipoQuantizacao.GPTQ,
                especialidade=EspecialidadeModelo.DECONSTRUTOR,
                versao="1.0",
                prioridade=10,
                dependencias=[],
                configuracoes={
                    "max_tokens": 1024, 
                    "temperature": 0.2,
                    "trust_remote_code": True
                }
            ),
            MetadadosModelo(
                nome="llama3-8b-sintetizador",
                caminho="models/llama-3-8b-instruct-gptq",
                tipo_modelo="llm",
                memoria_necessaria_mb=6144,
                quantizacao=TipoQuantizacao.GPTQ,
                especialidade=EspecialidadeModelo.SINTETIZADOR,
                versao="1.0",
                prioridade=10,
                dependencias=[],
                configuracoes={
                    "max_tokens": 2048, 
                    "temperature": 0.3,
                    "trust_remote_code": True
                }
            )
        ]
        
        for modelo in modelos_padrao:
            self.registrar_modelo(modelo)
            
        self._salvar_configuracao()
        
    def registrar_modelo(self, metadados: MetadadosModelo) -> None:
        """Registra um novo modelo no sistema"""
        with self._lock:
            # Verificar se arquivo existe e obter metadados
            self._atualizar_metadados_arquivo(metadados)
            
            self.modelos[metadados.nome] = metadados
            self.status_modelos[metadados.nome] = StatusDetalhado(
                status=StatusModelo.DESCARREGADO,
                timestamp=time.time()
            )
            
            self.logger.info(f"Modelo registrado: {metadados.nome} ({metadados.especialidade.value})")
            
    def _atualizar_metadados_arquivo(self, metadados: MetadadosModelo):
        """Atualiza metadados do arquivo do modelo"""
        try:
            caminho = Path(metadados.caminho)
            if caminho.exists():
                stat = caminho.stat()
                metadados.tamanho_arquivo_mb = stat.st_size / (1024 * 1024)
                metadados.data_modificacao = stat.st_mtime
                
                # Hash simples baseado em tamanho + data de modificação
                metadados.hash_arquivo = f"{stat.st_size}_{int(stat.st_mtime)}"
            else:
                self.logger.warning(f"Arquivo do modelo não encontrado: {caminho}")
        except Exception as e:
            self.logger.error(f"Erro ao obter metadados do arquivo {metadados.caminho}: {e}")
            
    def obter_metadados(self, nome_modelo: str) -> Optional[MetadadosModelo]:
        """Retorna metadados de um modelo específico"""
        with self._lock:
            return self.modelos.get(nome_modelo)
            
    def obter_status(self, nome_modelo: str) -> Optional[StatusDetalhado]:
        """Retorna status detalhado de um modelo"""
        with self._lock:
            if nome_modelo in self.status_modelos:
                status = self.status_modelos[nome_modelo]
                # Atualizar tempo no status atual
                status.tempo_no_status = time.time() - status.timestamp
                return status
            return None
            
    def listar_modelos_por_especialidade(self, especialidade: EspecialidadeModelo) -> List[MetadadosModelo]:
        """Lista todos os modelos de uma especialidade"""
        with self._lock:
            return [
                modelo for modelo in self.modelos.values()
                if modelo.especialidade == especialidade
            ]
            
    def listar_modelos_por_status(self, status: StatusModelo) -> List[str]:
        """Lista modelos por status atual"""
        with self._lock:
            return [
                nome for nome, status_detalhado in self.status_modelos.items()
                if status_detalhado.status == status
            ]
            
    def obter_modelos_carregados(self) -> List[str]:
        """Retorna lista de modelos atualmente carregados"""
        return self.listar_modelos_por_status(StatusModelo.CARREGADO)
        
    def obter_modelos_disponiveis_para_gpu(self, gpu_id: int, memoria_livre_mb: float) -> List[str]:
        """Retorna modelos que podem ser carregados na GPU especificada"""
        with self._lock:
            modelos_compativeis = []
            for nome, metadados in self.modelos.items():
                status = self.status_modelos[nome].status
                
                if (status == StatusModelo.DESCARREGADO and 
                    metadados.memoria_necessaria_mb <= memoria_livre_mb):
                    modelos_compativeis.append(nome)
                    
            # Ordenar por prioridade (maior primeiro)
            modelos_compativeis.sort(
                key=lambda nome: self.modelos[nome].prioridade, 
                reverse=True
            )
            
            return modelos_compativeis
            
    def atualizar_status(self, nome_modelo: str, novo_status: StatusModelo, 
                        gpu_id: Optional[int] = None, memoria_alocada_mb: float = 0.0,
                        erro_detalhes: Optional[str] = None, processo_id: Optional[int] = None) -> None:
        """Atualiza o status de um modelo"""
        with self._lock:
            if nome_modelo not in self.modelos:
                raise ValueError(f"Modelo não registrado: {nome_modelo}")
                
            # Status anterior para callback
            status_anterior = self.status_modelos[nome_modelo].status
            
            # Atualizar status
            self.status_modelos[nome_modelo] = StatusDetalhado(
                status=novo_status,
                timestamp=time.time(),
                gpu_id=gpu_id,
                memoria_alocada_mb=memoria_alocada_mb,
                erro_detalhes=erro_detalhes,
                processo_id=processo_id
            )
            
            # Gerenciar alocações de GPU
            if novo_status == StatusModelo.CARREGADO and gpu_id is not None:
                self.gpu_alocacoes[nome_modelo] = gpu_id
            elif novo_status == StatusModelo.DESCARREGADO and nome_modelo in self.gpu_alocacoes:
                del self.gpu_alocacoes[nome_modelo]
                
            # Log da mudança
            self.logger.info(f"Status atualizado: {nome_modelo} -> {novo_status.value}")
            if erro_detalhes:
                self.logger.error(f"Erro em {nome_modelo}: {erro_detalhes}")
                
            # Chamar callbacks
            if status_anterior != novo_status:
                self._chamar_callbacks_status(nome_modelo, status_anterior, novo_status)
                
    def registrar_utilizacao(self, nome_modelo: str, tempo_carregamento: float = 0.0, sucesso: bool = True):
        """Registra utilização de um modelo para estatísticas"""
        with self._lock:
            if nome_modelo not in self.modelos:
                return
                
            metadados = self.modelos[nome_modelo]
            metadados.ultima_utilizacao = time.time()
            metadados.total_utilizacoes += 1
            
            # Atualizar tempo médio de carregamento
            if tempo_carregamento > 0:
                if metadados.tempo_medio_carregamento == 0:
                    metadados.tempo_medio_carregamento = tempo_carregamento
                else:
                    # Média móvel simples
                    metadados.tempo_medio_carregamento = (
                        metadados.tempo_medio_carregamento * 0.8 + tempo_carregamento * 0.2
                    )
                    
            # Atualizar taxa de sucesso
            if not sucesso:
                # Reduzir taxa de sucesso gradualmente em caso de falha
                metadados.taxa_sucesso = max(0, metadados.taxa_sucesso - 5)
            else:
                # Aumentar taxa de sucesso gradualmente em caso de sucesso
                metadados.taxa_sucesso = min(100, metadados.taxa_sucesso + 1)
                
    def calcular_memoria_total_necessaria(self, nomes_modelos: List[str]) -> float:
        """Calcula memória total necessária para carregar múltiplos modelos"""
        with self._lock:
            total = 0.0
            for nome in nomes_modelos:
                modelo = self.obter_metadados(nome)
                if modelo:
                    total += modelo.memoria_necessaria_mb
            return total
            
    def obter_modelos_por_gpu(self) -> Dict[int, List[str]]:
        """Retorna mapeamento de GPU -> modelos carregados"""
        with self._lock:
            mapeamento = {}
            for nome_modelo, gpu_id in self.gpu_alocacoes.items():
                if gpu_id not in mapeamento:
                    mapeamento[gpu_id] = []
                mapeamento[gpu_id].append(nome_modelo)
            return mapeamento
            
    def obter_estatisticas_uso(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso dos modelos"""
        with self._lock:
            stats = {
                "total_modelos": len(self.modelos),
                "modelos_carregados": len(self.obter_modelos_carregados()),
                "gpus_utilizadas": len(set(self.gpu_alocacoes.values())),
                "memoria_total_alocada": sum(
                    self.status_modelos[nome].memoria_alocada_mb 
                    for nome in self.obter_modelos_carregados()
                ),
                "modelos_por_especialidade": {},
                "uso_por_modelo": {}
            }
            
            # Estatísticas por especialidade
            for especialidade in EspecialidadeModelo:
                modelos_especialidade = self.listar_modelos_por_especialidade(especialidade)
                stats["modelos_por_especialidade"][especialidade.value] = len(modelos_especialidade)
                
            # Uso individual por modelo
            for nome, metadados in self.modelos.items():
                stats["uso_por_modelo"][nome] = {
                    "total_utilizacoes": metadados.total_utilizacoes,
                    "ultima_utilizacao": metadados.ultima_utilizacao,
                    "tempo_medio_carregamento": metadados.tempo_medio_carregamento,
                    "taxa_sucesso": metadados.taxa_sucesso,
                    "status_atual": self.status_modelos[nome].status.value
                }
                
            return stats
            
    def validar_dependencias(self, nome_modelo: str) -> Dict[str, bool]:
        """Valida se todas as dependências de um modelo estão satisfeitas"""
        with self._lock:
            modelo = self.obter_metadados(nome_modelo)
            if not modelo:
                return {"erro": "Modelo não encontrado"}
                
            resultado = {"todas_satisfeitas": True}
            
            for dependencia in modelo.dependencias:
                if dependencia in self.modelos:
                    status = self.status_modelos[dependencia].status
                    satisfeita = status == StatusModelo.CARREGADO
                    resultado[dependencia] = satisfeita
                    if not satisfeita:
                        resultado["todas_satisfeitas"] = False
                else:
                    resultado[dependencia] = False
                    resultado["todas_satisfeitas"] = False
                    
            return resultado
            
    def _salvar_configuracao(self) -> None:
        """Salva configuração atual no arquivo"""
        try:
            self.arquivo_config.parent.mkdir(parents=True, exist_ok=True)
            
            config = {}
            for nome, metadados in self.modelos.items():
                config[nome] = asdict(metadados)
                # Converter enums para strings
                config[nome]['quantizacao'] = metadados.quantizacao.value
                config[nome]['especialidade'] = metadados.especialidade.value
                
            with open(self.arquivo_config, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
            self.logger.debug("Configuração salva com sucesso")
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração: {e}")
            
    def fazer_backup_configuracao(self) -> str:
        """Cria backup da configuração atual"""
        timestamp = int(time.time())
        arquivo_backup = self.arquivo_config.parent / f"modelos_backup_{timestamp}.json"
        
        try:
            self._salvar_configuracao()
            import shutil
            shutil.copy2(self.arquivo_config, arquivo_backup)
            self.logger.info(f"Backup criado: {arquivo_backup}")
            return str(arquivo_backup)
        except Exception as e:
            self.logger.error(f"Erro ao criar backup: {e}")
            raise
