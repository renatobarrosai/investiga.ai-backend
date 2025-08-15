# src/infraestrutura/fila_requisicoes.py
import asyncio
import logging
import time
import uuid
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from queue import PriorityQueue, Empty
from collections import deque, defaultdict
import json

class StatusRequisicao(Enum):
    """Status possíveis de uma requisição"""
    PENDENTE = "pendente"
    AGUARDANDO_RECURSO = "aguardando_recurso"
    PROCESSANDO = "processando"
    CONCLUIDA = "concluida"
    ERRO = "erro"
    CANCELADA = "cancelada"
    TIMEOUT = "timeout"

class PrioridadeRequisicao(Enum):
    """Níveis de prioridade para requisições"""
    BAIXA = 1
    NORMAL = 5
    ALTA = 8
    CRITICA = 10

class TipoRequisicao(Enum):
    """Tipos de requisição de processamento"""
    FACT_CHECK_COMPLETO = "fact_check_completo"
    FACT_CHECK_RAPIDO = "fact_check_rapido"
    PROCESSAMENTO_ARQUIVO = "processamento_arquivo"
    ANALISE_CUSTOM = "analise_custom"

@dataclass
class Requisicao:
    """Representação completa de uma requisição no sistema"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conteudo: str = ""
    tipo_conteudo: str = "texto"
    tipo_requisicao: TipoRequisicao = TipoRequisicao.FACT_CHECK_COMPLETO
    prioridade: PrioridadeRequisicao = PrioridadeRequisicao.NORMAL
    
    # Timestamps
    timestamp_criacao: float = field(default_factory=time.time)
    timestamp_inicio: Optional[float] = None
    timestamp_conclusao: Optional[float] = None
    
    # Status e resultados
    status: StatusRequisicao = StatusRequisicao.PENDENTE
    resultado: Optional[Dict[str, Any]] = None
    erro: Optional[str] = None
    progresso: float = 0.0
    
    # Configurações
    timeout: float = 300.0  # 5 minutos default
    max_tentativas: int = 3
    tentativas_realizadas: int = 0
    
    # Callbacks e metadados
    callback: Optional[Callable] = None
    callback_progresso: Optional[Callable] = None
    metadados: Dict[str, Any] = field(default_factory=dict)
    
    # Recursos necessários
    modelos_necessarios: List[str] = field(default_factory=list)
    memoria_estimada_mb: float = 0.0
    gpu_preferida: Optional[int] = None
    
    def __lt__(self, other):
        # Para PriorityQueue - prioridade maior primeiro, depois timestamp mais antigo
        if self.prioridade.value != other.prioridade.value:
            return self.prioridade.value > other.prioridade.value
        return self.timestamp_criacao < other.timestamp_criacao
        
    @property
    def tempo_espera(self) -> float:
        """Tempo que a requisição está esperando"""
        inicio = self.timestamp_inicio or time.time()
        return inicio - self.timestamp_criacao
        
    @property
    def tempo_processamento(self) -> Optional[float]:
        """Tempo de processamento da requisição"""
        if not self.timestamp_inicio:
            return None
        fim = self.timestamp_conclusao or time.time()
        return fim - self.timestamp_inicio
        
    @property
    def tempo_total(self) -> float:
        """Tempo total desde criação"""
        fim = self.timestamp_conclusao or time.time()
        return fim - self.timestamp_criacao

@dataclass
class EstatisticasFila:
    """Estatísticas detalhadas da fila de requisições"""
    total_processadas: int = 0
    total_com_erro: int = 0
    total_timeout: int = 0
    total_canceladas: int = 0
    
    tempo_medio_espera: float = 0.0
    tempo_medio_processamento: float = 0.0
    throughput_por_minuto: float = 0.0
    
    requisicoes_por_tipo: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requisicoes_por_prioridade: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    pico_simultaneas: int = 0
    media_fila_pendente: float = 0.0

class GerenciadorFilas:
    """Gerenciador avançado de filas de requisições com suporte a concorrência inteligente"""
    
    def __init__(self, max_concurrent: int = 3, monitor_gpu=None, agendador_modelos=None):
        self.max_concurrent = max_concurrent
        self.monitor_gpu = monitor_gpu
        self.agendador_modelos = agendador_modelos
        self.logger = logging.getLogger(__name__)
        
        # Filas e controles
        self.fila_pendentes = PriorityQueue()
        self.fila_aguardando_recurso = []  # Lista normal para reprocessamento
        self.requisicoes_ativas: Dict[str, Requisicao] = {}
        self.historico_requisicoes: Dict[str, Requisicao] = {}
        
        # Controles de concorrência
        self.lock_operacoes = threading.RLock()
        self.processadores_ativos = 0
        self.executando = threading.Event()
        
        # Threads de processamento
        self.thread_dispatcher = None
        self.thread_monitor = None
        
        # Estatísticas
        self.estatisticas = EstatisticasFila()
        self.historico_metricas = deque(maxlen=1440)  # 24h de dados (1 min intervals)
        
        # Cache de decisões e otimizações
        self.cache_estimativas = {}  # Cache de estimativas de recursos
        self.padroes_uso = defaultdict(list)  # Padrões de uso por tipo
        
        # Callbacks para eventos
        self.callbacks_eventos = {
            'requisicao_iniciada': [],
            'requisicao_concluida': [],
            'requisicao_erro': [],
            'fila_cheia': [],
            'recursos_insuficientes': []
        }
        
    def adicionar_callback(self, evento: str, callback: Callable):
        """Adiciona callback para eventos da fila"""
        if evento in self.callbacks_eventos:
            self.callbacks_eventos[evento].append(callback)
            
    def _chamar_callbacks(self, evento: str, **kwargs):
        """Chama callbacks registrados para um evento"""
        for callback in self.callbacks_eventos.get(evento, []):
            try:
                callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Erro em callback {evento}: {e}")
                
    def iniciar(self):
        """Inicia o processamento de filas"""
        if self.executando.is_set():
            self.logger.warning("Gerenciador de filas já está executando")
            return
            
        self.executando.set()
        
        # Thread principal de dispatch
        self.thread_dispatcher = threading.Thread(target=self._loop_dispatcher, daemon=True)
        self.thread_dispatcher.start()
        
        # Thread de monitoramento
        self.thread_monitor = threading.Thread(target=self._loop_monitor, daemon=True)
        self.thread_monitor.start()
        
        self.logger.info("Gerenciador de filas iniciado")
        
    def parar(self):
        """Para o processamento de filas"""
        self.executando.clear()
        
        if self.thread_dispatcher:
            self.thread_dispatcher.join(timeout=10.0)
        if self.thread_monitor:
            self.thread_monitor.join(timeout=5.0)
            
        self.logger.info("Gerenciador de filas parado")
        
    async def adicionar_requisicao(self, requisicao: Requisicao) -> str:
        """Adiciona uma nova requisição à fila"""
        # Estimar recursos necessários
        self._estimar_recursos_necessarios(requisicao)
        
        # Adicionar à fila apropriada
        with self.lock_operacoes:
            self.fila_pendentes.put(requisicao)
            self.historico_requisicoes[requisicao.id] = requisicao
            
        # Atualizar estatísticas
        self.estatisticas.requisicoes_por_tipo[requisicao.tipo_requisicao.value] += 1
        self.estatisticas.requisicoes_por_prioridade[requisicao.prioridade.name] += 1
        
        self.logger.info(
            f"Requisição adicionada: {requisicao.id[:8]}... "
            f"(tipo: {requisicao.tipo_requisicao.value}, prioridade: {requisicao.prioridade.name})"
        )
        
        return requisicao.id
        
    def _estimar_recursos_necessarios(self, requisicao: Requisicao):
        """Estima recursos necessários para uma requisição"""
        tipo = requisicao.tipo_requisicao
        
        # Estimativas baseadas no tipo de requisição
        if tipo == TipoRequisicao.FACT_CHECK_COMPLETO:
            requisicao.modelos_necessarios = [
                "gemma-2b-recepcionista",
                "phi3-vision-classificador", 
                "llama3-8b-deconstrutor",
                "llama3-8b-sintetizador",
                "gemma-2b-apresentador"
            ]
            requisicao.memoria_estimada_mb = 8192  # Total estimado
            
        elif tipo == TipoRequisicao.FACT_CHECK_RAPIDO:
            requisicao.modelos_necessarios = [
                "gemma-2b-recepcionista",
                "phi3-vision-classificador"
            ]
            requisicao.memoria_estimada_mb = 4096
            
        elif tipo == TipoRequisicao.PROCESSAMENTO_ARQUIVO:
            # Varia baseado no tipo de arquivo
            if "image" in requisicao.tipo_conteudo:
                requisicao.modelos_necessarios = ["phi3-vision-classificador"]
                requisicao.memoria_estimada_mb = 4096
            else:
                requisicao.modelos_necessarios = ["gemma-2b-recepcionista"]
                requisicao.memoria_estimada_mb = 2048
                
        # Cache da estimativa
        self.cache_estimativas[requisicao.id] = {
            'timestamp': time.time(),
            'estimativa': requisicao.memoria_estimada_mb
        }
        
    def _loop_dispatcher(self):
        """Loop principal de dispatch de requisições"""
        while self.executando.is_set():
            try:
                # Processar requisições aguardando recursos
                self._processar_fila_aguardando()
                
                # Verificar se pode processar novas requisições
                if self.processadores_ativos >= self.max_concurrent:
                    time.sleep(0.5)
                    continue
                    
                # Obter próxima requisição pendente
                try:
                    requisicao = self.fila_pendentes.get(timeout=1.0)
                except Empty:
                    continue
                    
                # Verificar disponibilidade de recursos
                if self._verificar_recursos_disponiveis(requisicao):
                    self._iniciar_processamento(requisicao)
                else:
                    # Mover para fila de aguardando recursos
                    requisicao.status = StatusRequisicao.AGUARDANDO_RECURSO
                    self.fila_aguardando_recurso.append(requisicao)
                    self._chamar_callbacks('recursos_insuficientes', requisicao=requisicao)
                    
            except Exception as e:
                self.logger.error(f"Erro no loop dispatcher: {e}", exc_info=True)
                time.sleep(1.0)
                
    def _processar_fila_aguardando(self):
        """Processa requisições aguardando recursos"""
        if not self.fila_aguardando_recurso:
            return
            
        # Tentar processar requisições aguardando, ordenadas por prioridade
        self.fila_aguardando_recurso.sort(reverse=True)  # Prioridade maior primeiro
        
        processadas = []
        for requisicao in self.fila_aguardando_recurso:
            if self.processadores_ativos >= self.max_concurrent:
                break
                
            if self._verificar_recursos_disponiveis(requisicao):
                self._iniciar_processamento(requisicao)
                processadas.append(requisicao)
                
        # Remover requisições processadas
        for req in processadas:
            self.fila_aguardando_recurso.remove(req)
            
    def _verificar_recursos_disponiveis(self, requisicao: Requisicao) -> bool:
        """Verifica se há recursos suficientes para processar requisição"""
        # Verificar GPU e memória
        if self.monitor_gpu:
            stats = self.monitor_gpu.obter_estatisticas_resumo()
            if stats.get("memoria_livre_sistema", 0) < requisicao.memoria_estimada_mb:
                return False
                
        # Verificar modelos necessários (simulado)
        if self.agendador_modelos:
            # Em implementação real, verificaria se modelos podem ser carregados
            pass
            
        return True
        
    def _iniciar_processamento(self, requisicao: Requisicao):
        """Inicia o processamento de uma requisição"""
        with self.lock_operacoes:
            self.processadores_ativos += 1
            self.requisicoes_ativas[requisicao.id] = requisicao
            
        requisicao.status = StatusRequisicao.PROCESSANDO
        requisicao.timestamp_inicio = time.time()
        
        # Iniciar processamento em thread separada
        thread_proc = threading.Thread(
            target=self._processar_requisicao,
            args=(requisicao,),
            daemon=True
        )
        thread_proc.start()
        
        self._chamar_callbacks('requisicao_iniciada', requisicao=requisicao)
        
    def _processar_requisicao(self, requisicao: Requisicao):
        """Processa uma requisição específica (simulado)"""
        try:
            self.logger.info(f"Iniciando processamento: {requisicao.id[:8]}...")
            
            # Simular progresso de processamento
            for progresso in [0.2, 0.4, 0.6, 0.8, 1.0]:
                if not self.executando.is_set():
                    break
                    
                time.sleep(1.0)  # Simular trabalho
                requisicao.progresso = progresso
                
                if requisicao.callback_progresso:
                    try:
                        requisicao.callback_progresso(requisicao.id, progresso)
                    except Exception as e:
                        self.logger.error(f"Erro em callback de progresso: {e}")
                        
            # Simular resultado
            requisicao.resultado = {
                "status": "sucesso",
                "veredicto": "PROCESSADO_COM_SUCESSO",
                "confianca": 0.85,
                "tempo_processamento": time.time() - requisicao.timestamp_inicio
            }
            
            requisicao.status = StatusRequisicao.CONCLUIDA
            requisicao.timestamp_conclusao = time.time()
            
            self._atualizar_estatisticas(requisicao, sucesso=True)
            self._chamar_callbacks('requisicao_concluida', requisicao=requisicao)
            
            if requisicao.callback:
                try:
                    requisicao.callback(requisicao)
                except Exception as e:
                    self.logger.error(f"Erro em callback de conclusão: {e}")
                    
        except Exception as e:
            requisicao.status = StatusRequisicao.ERRO
            requisicao.erro = str(e)
            requisicao.timestamp_conclusao = time.time()
            
            self._atualizar_estatisticas(requisicao, sucesso=False)
            self._chamar_callbacks('requisicao_erro', requisicao=requisicao, erro=e)
            
            self.logger.error(f"Erro no processamento de {requisicao.id}: {e}")
            
        finally:
            with self.lock_operacoes:
                self.processadores_ativos -= 1
                if requisicao.id in self.requisicoes_ativas:
                    del self.requisicoes_ativas[requisicao.id]
                    
    def _loop_monitor(self):
        """Loop de monitoramento e otimização"""
        while self.executando.is_set():
            try:
                # Verificar timeouts
                self._verificar_timeouts()
                
                # Coletar métricas
                self._coletar_metricas()
                
                # Otimizar filas
                self._otimizar_filas()
                
                time.sleep(30.0)  # Monitoramento a cada 30 segundos
                
            except Exception as e:
                self.logger.error(f"Erro no loop monitor: {e}", exc_info=True)
                time.sleep(30.0)
                
    def _verificar_timeouts(self):
        """Verifica e marca requisições que excederam timeout"""
        agora = time.time()
        requisicoes_timeout = []
        
        with self.lock_operacoes:
            for req_id, requisicao in self.requisicoes_ativas.items():
                if agora - requisicao.timestamp_criacao > requisicao.timeout:
                    requisicoes_timeout.append(req_id)
                    
        for req_id in requisicoes_timeout:
            requisicao = self.requisicoes_ativas.get(req_id)
            if requisicao:
                requisicao.status = StatusRequisicao.TIMEOUT
                requisicao.timestamp_conclusao = agora
                self.estatisticas.total_timeout += 1
                self.logger.warning(f"Timeout na requisição {req_id}")
                
    def _coletar_metricas(self):
        """Coleta métricas para análise de tendências"""
        agora = time.time()
        
        with self.lock_operacoes:
            metricas = {
                'timestamp': agora,
                'fila_pendente': self.fila_pendentes.qsize(),
                'fila_aguardando': len(self.fila_aguardando_recurso),
                'processando': len(self.requisicoes_ativas),
                'processadores_ativos': self.processadores_ativos
            }
            
        self.historico_metricas.append(metricas)
        
        # Atualizar médias
        if len(self.historico_metricas) > 1:
            filas_pendentes = [m['fila_pendente'] for m in self.historico_metricas[-60:]]  # Última hora
            self.estatisticas.media_fila_pendente = sum(filas_pendentes) / len(filas_pendentes)
            
    def _otimizar_filas(self):
        """Otimiza filas baseado em padrões observados"""
        # Implementação simplificada - pode ser expandida com ML
        agora = time.time()
        
        # Reordenar fila aguardando por prioridade dinâmica
        if self.fila_aguardando_recurso:
            # Aumentar prioridade de requisições antigas
            for requisicao in self.fila_aguardando_recurso:
                tempo_espera = agora - requisicao.timestamp_criacao
                if tempo_espera > 300:  # 5 minutos
                    if requisicao.prioridade.value < PrioridadeRequisicao.ALTA.value:
                        requisicao.prioridade = PrioridadeRequisicao.ALTA
                        self.logger.info(f"Aumentando prioridade de {requisicao.id} por tempo de espera")
                        
    def _atualizar_estatisticas(self, requisicao: Requisicao, sucesso: bool):
        """Atualiza estatísticas com base na requisição processada"""
        if sucesso:
            self.estatisticas.total_processadas += 1
        else:
            self.estatisticas.total_com_erro += 1
            
        # Atualizar tempos médios
        if requisicao.tempo_processamento:
            if self.estatisticas.tempo_medio_processamento == 0:
                self.estatisticas.tempo_medio_processamento = requisicao.tempo_processamento
            else:
                self.estatisticas.tempo_medio_processamento = (
                    self.estatisticas.tempo_medio_processamento * 0.8 + 
                    requisicao.tempo_processamento * 0.2
                )
                
        if self.estatisticas.tempo_medio_espera == 0:
            self.estatisticas.tempo_medio_espera = requisicao.tempo_espera
        else:
            self.estatisticas.tempo_medio_espera = (
                self.estatisticas.tempo_medio_espera * 0.8 + 
                requisicao.tempo_espera * 0.2
            )
            
        # Atualizar pico simultâneo
        atual_simultaneas = len(self.requisicoes_ativas)
        if atual_simultaneas > self.estatisticas.pico_simultaneas:
            self.estatisticas.pico_simultaneas = atual_simultaneas
            
    def obter_status_requisicao(self, id_requisicao: str) -> Optional[Requisicao]:
        """Retorna o status de uma requisição específica"""
        return self.historico_requisicoes.get(id_requisicao)
        
    def cancelar_requisicao(self, id_requisicao: str) -> bool:
        """Cancela uma requisição pendente ou aguardando"""
        requisicao = self.historico_requisicoes.get(id_requisicao)
        
        if not requisicao:
            return False
            
        if requisicao.status in [StatusRequisicao.PENDENTE, StatusRequisicao.AGUARDANDO_RECURSO]:
            requisicao.status = StatusRequisicao.CANCELADA
            requisicao.timestamp_conclusao = time.time()
            self.estatisticas.total_canceladas += 1
            
            # Remover da fila aguardando se estiver lá
            if requisicao in self.fila_aguardando_recurso:
                self.fila_aguardando_recurso.remove(requisicao)
                
            self.logger.info(f"Requisição cancelada: {id_requisicao[:8]}...")
            return True
            
        return False
        
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas completas do sistema de filas"""
        with self.lock_operacoes:
            pendentes = self.fila_pendentes.qsize()
            aguardando = len(self.fila_aguardando_recurso)
            ativas = len(self.requisicoes_ativas)
            
        total_processadas = (self.estatisticas.total_processadas + 
                           self.estatisticas.total_com_erro)
        
        return {
            "status_atual": {
                "requisicoes_pendentes": pendentes,
                "requisicoes_aguardando_recurso": aguardando,
                "requisicoes_ativas": ativas,
                "processadores_disponiveis": self.max_concurrent - self.processadores_ativos
            },
            "estatisticas_processamento": {
                "total_processadas": self.estatisticas.total_processadas,
                "total_com_erro": self.estatisticas.total_com_erro,
                "total_timeout": self.estatisticas.total_timeout,
                "total_canceladas": self.estatisticas.total_canceladas,
                "taxa_sucesso": (
                    (self.estatisticas.total_processadas / total_processadas * 100) 
                    if total_processadas > 0 else 0
                ),
                "tempo_medio_espera": self.estatisticas.tempo_medio_espera,
                "tempo_medio_processamento": self.estatisticas.tempo_medio_processamento,
                "throughput_por_minuto": self.estatisticas.throughput_por_minuto
            },
            "distribuicao": {
                "por_tipo": dict(self.estatisticas.requisicoes_por_tipo),
                "por_prioridade": dict(self.estatisticas.requisicoes_por_prioridade)
            },
            "performance": {
                "pico_simultaneas": self.estatisticas.pico_simultaneas,
                "media_fila_pendente": self.estatisticas.media_fila_pendente,
                "max_concurrent_configurado": self.max_concurrent
            }
        }
        
    def listar_requisicoes_ativas(self) -> List[Dict[str, Any]]:
        """Lista requisições atualmente sendo processadas"""
        ativas = []
        
        with self.lock_operacoes:
            for requisicao in self.requisicoes_ativas.values():
                ativas.append({
                    "id": requisicao.id,
                    "tipo": requisicao.tipo_requisicao.value,
                    "prioridade": requisicao.prioridade.name,
                    "progresso": requisicao.progresso,
                    "tempo_processamento": requisicao.tempo_processamento,
                    "status": requisicao.status.value
                })
                
        return ativas
        
    async def aguardar_conclusao(self, id_requisicao: str, timeout: float = 300.0) -> Optional[Requisicao]:
        """Aguarda a conclusão de uma requisição específica"""
        inicio = time.time()
        
        while time.time() - inicio < timeout:
            requisicao = self.obter_status_requisicao(id_requisicao)
            
            if not requisicao:
                return None
                
            if requisicao.status in [
                StatusRequisicao.CONCLUIDA, 
                StatusRequisicao.ERRO, 
                StatusRequisicao.CANCELADA,
                StatusRequisicao.TIMEOUT
            ]:
                return requisicao
                
            await asyncio.sleep(0.1)
            
        return None
