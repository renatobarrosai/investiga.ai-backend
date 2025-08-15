# src/infraestrutura/agendador_modelos.py
import asyncio
import logging
import time
import threading
from typing import Optional, Dict, List, Callable, Tuple, Any
from threading import Thread, Event, RLock
from dataclasses import dataclass
from enum import Enum
import heapq
from collections import defaultdict, deque

class PrioridadeOperacao(Enum):
    """Prioridades para operações de modelo"""
    BAIXA = 1
    NORMAL = 5
    ALTA = 8
    CRITICA = 10

class TipoOperacao(Enum):
    """Tipos de operação que podem ser agendadas"""
    CARREGAR = "carregar"
    DESCARREGAR = "descarregar"
    RELOAD = "reload"
    PRELOAD = "preload"

@dataclass
class OperacaoModelo:
    """Representa uma operação agendada para um modelo"""
    id_operacao: str
    nome_modelo: str
    tipo: TipoOperacao
    prioridade: PrioridadeOperacao
    timestamp_criacao: float
    gpu_preferida: Optional[int] = None
    callback: Optional[Callable] = None
    timeout: float = 300.0  # 5 minutos default
    tentativas_max: int = 3
    tentativas_realizadas: int = 0
    metadados: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadados is None:
            self.metadados = {}
    
    def __lt__(self, other):
        # Para heap queue - prioridade maior primeiro, depois timestamp mais antigo
        if self.prioridade.value != other.prioridade.value:
            return self.prioridade.value > other.prioridade.value
        return self.timestamp_criacao < other.timestamp_criacao

@dataclass
class EstatisticasAgendador:
    """Estatísticas do agendador"""
    operacoes_executadas: int = 0
    operacoes_falharam: int = 0
    tempo_medio_execucao: float = 0.0
    modelos_carregados_simultaneos_max: int = 0
    gpu_utilizacao_pico: float = 0.0
    operacoes_por_tipo: Dict[str, int] = None
    
    def __post_init__(self):
        if self.operacoes_por_tipo is None:
            self.operacoes_por_tipo = defaultdict(int)

class AgendadorModelos:
    """
    Gerencia o ciclo de vida de modelos de IA, agendando o carregamento e
    descarregamento de modelos em GPUs de forma otimizada e inteligente
    """
    
    def __init__(self, monitor_gpu, registro, max_operacoes_simultaneas: int = 2):
        self.monitor_gpu = monitor_gpu
        self.registro = registro
        self.max_operacoes_simultaneas = max_operacoes_simultaneas
        self.logger = logging.getLogger(__name__)
        
        # Controle de execução
        self.executando = Event()
        self.thread_scheduler = None
        self.thread_monitor = None
        
        # Filas de operação
        self.fila_operacoes = []  # Heap queue baseada em prioridade
        self.operacoes_executando = {}  # id_operacao -> OperacaoModelo
        self.operacoes_concluidas = deque(maxlen=1000)  # Histórico
        
        # Thread safety
        self._lock = RLock()
        
        # Cache e otimizações
        self.cache_decisoes = {}  # Cache de decisões de scheduling
        self.historico_uso = defaultdict(list)  # Histórico de uso por modelo
        self.previsoes_uso = {}  # Previsões de uso futuro
        
        # Configurações adaptáveis
        self.tempo_inatividade_descarregar = 300.0  # 5 minutos
        self.margem_seguranca_memoria = 512.0  # MB
        self.fator_preloading = 0.7  # Threshold para preloading preditivo
        
        # Estatísticas
        self.estatisticas = EstatisticasAgendador()
        
        # Callbacks para eventos
        self.callbacks_eventos = {
            'pre_carregamento': [],
            'pos_carregamento': [],
            'pre_descarregamento': [],
            'pos_descarregamento': [],
            'erro_operacao': [],
            'memoria_insuficiente': []
        }
        
    def adicionar_callback(self, evento: str, callback: Callable):
        """Adiciona callback para eventos do agendador"""
        if evento in self.callbacks_eventos:
            self.callbacks_eventos[evento].append(callback)
            
    def _chamar_callbacks(self, evento: str, **kwargs):
        """Chama callbacks registrados para um evento"""
        for callback in self.callbacks_eventos.get(evento, []):
            try:
                callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Erro em callback {evento}: {e}")
        
    def iniciar_monitoramento(self):
        """Inicia o loop principal do agendador em threads separadas"""
        if self.executando.is_set():
            self.logger.warning("Agendador já está executando")
            return
            
        self.executando.set()
        
        # Thread para processamento de operações
        self.thread_scheduler = Thread(target=self._loop_scheduler, daemon=True)
        self.thread_scheduler.start()
        
        # Thread para monitoramento e otimizações
        self.thread_monitor = Thread(target=self._loop_monitor, daemon=True)
        self.thread_monitor.start()
        
        self.logger.info("Agendador de modelos iniciado")
        
    def parar_monitoramento(self):
        """Para o loop principal do agendador"""
        self.executando.clear()
        
        # Aguardar threads terminarem
        if self.thread_scheduler:
            self.thread_scheduler.join(timeout=10.0)
        if self.thread_monitor:
            self.thread_monitor.join(timeout=5.0)
            
        self.logger.info("Agendador de modelos parado")
        
    def solicitar_modelo(self, nome_modelo: str, prioridade: PrioridadeOperacao = PrioridadeOperacao.NORMAL,
                        gpu_preferida: Optional[int] = None, callback: Optional[Callable] = None,
                        timeout: float = 300.0) -> str:
        """
        Solicita o carregamento de um modelo
        
        Returns:
            str: ID da operação agendada
        """
        id_operacao = f"load_{nome_modelo}_{int(time.time()*1000)}"
        
        operacao = OperacaoModelo(
            id_operacao=id_operacao,
            nome_modelo=nome_modelo,
            tipo=TipoOperacao.CARREGAR,
            prioridade=prioridade,
            timestamp_criacao=time.time(),
            gpu_preferida=gpu_preferida,
            callback=callback,
            timeout=timeout
        )
        
        with self._lock:
            heapq.heappush(self.fila_operacoes, operacao)
            
        self.logger.info(f"Modelo {nome_modelo} solicitado com prioridade {prioridade.name}")
        return id_operacao
        
    def descarregar_modelo(self, nome_modelo: str, prioridade: PrioridadeOperacao = PrioridadeOperacao.NORMAL,
                          callback: Optional[Callable] = None) -> str:
        """
        Solicita o descarregamento de um modelo
        
        Returns:
            str: ID da operação agendada
        """
        id_operacao = f"unload_{nome_modelo}_{int(time.time()*1000)}"
        
        operacao = OperacaoModelo(
            id_operacao=id_operacao,
            nome_modelo=nome_modelo,
            tipo=TipoOperacao.DESCARREGAR,
            prioridade=prioridade,
            timestamp_criacao=time.time(),
            callback=callback,
            timeout=60.0  # Descarregamento é mais rápido
        )
        
        with self._lock:
            heapq.heappush(self.fila_operacoes, operacao)
            
        self.logger.info(f"Descarregamento de {nome_modelo} solicitado")
        return id_operacao
        
    def preload_preditivo(self, nome_modelo: str, probabilidade: float):
        """Agenda preloading preditivo baseado em probabilidade de uso"""
        if probabilidade > self.fator_preloading:
            id_operacao = f"preload_{nome_modelo}_{int(time.time()*1000)}"
            
            operacao = OperacaoModelo(
                id_operacao=id_operacao,
                nome_modelo=nome_modelo,
                tipo=TipoOperacao.PRELOAD,
                prioridade=PrioridadeOperacao.BAIXA,
                timestamp_criacao=time.time(),
                metadados={"probabilidade": probabilidade}
            )
            
            with self._lock:
                heapq.heappush(self.fila_operacoes, operacao)
                
            self.logger.debug(f"Preload preditivo agendado para {nome_modelo} (prob: {probabilidade:.2f})")
            
    def _loop_scheduler(self):
        """Loop principal do scheduler - processa operações na fila"""
        while self.executando.is_set():
            try:
                # Verificar se pode executar mais operações
                if len(self.operacoes_executando) >= self.max_operacoes_simultaneas:
                    time.sleep(0.5)
                    continue
                    
                # Obter próxima operação
                with self._lock:
                    if not self.fila_operacoes:
                        time.sleep(1.0)
                        continue
                        
                    operacao = heapq.heappop(self.fila_operacoes)
                    
                # Verificar se operação ainda é válida
                if not self._validar_operacao(operacao):
                    continue
                    
                # Executar operação
                self._executar_operacao(operacao)
                
            except Exception as e:
                self.logger.error(f"Erro no loop scheduler: {e}", exc_info=True)
                time.sleep(1.0)
                
    def _loop_monitor(self):
        """Loop de monitoramento - otimizações e limpeza automática"""
        while self.executando.is_set():
            try:
                # Verificar timeouts
                self._verificar_timeouts()
                
                # Descarregamento automático por inatividade
                self._verificar_inatividade()
                
                # Otimização de memória
                self._otimizar_memoria()
                
                # Preloading preditivo
                self._executar_preloading_preditivo()
                
                # Limpeza de cache
                self._limpar_caches()
                
                time.sleep(30.0)  # Monitoramento a cada 30 segundos
                
            except Exception as e:
                self.logger.error(f"Erro no loop monitor: {e}", exc_info=True)
                time.sleep(30.0)
                
    def _validar_operacao(self, operacao: OperacaoModelo) -> bool:
        """Valida se uma operação ainda deve ser executada"""
        # Verificar se modelo existe
        metadados = self.registro.obter_metadados(operacao.nome_modelo)
        if not metadados:
            self.logger.warning(f"Modelo não encontrado: {operacao.nome_modelo}")
            return False
            
        # Verificar estado atual
        status = self.registro.obter_status(operacao.nome_modelo)
        if not status:
            return False
            
        # Validações específicas por tipo
        if operacao.tipo == TipoOperacao.CARREGAR:
            if status.status.value in ['carregado', 'carregando']:
                self.logger.debug(f"Modelo {operacao.nome_modelo} já carregado/carregando")
                return False
                
        elif operacao.tipo == TipoOperacao.DESCARREGAR:
            if status.status.value in ['descarregado', 'descarregando']:
                self.logger.debug(f"Modelo {operacao.nome_modelo} já descarregado/descarregando")
                return False
                
        return True
        
    def _executar_operacao(self, operacao: OperacaoModelo):
        """Executa uma operação em thread separada"""
        with self._lock:
            self.operacoes_executando[operacao.id_operacao] = operacao
            
        # Executar em thread separada para não bloquear scheduler
        thread_operacao = Thread(
            target=self._processar_operacao, 
            args=(operacao,), 
            daemon=True
        )
        thread_operacao.start()
        
    def _processar_operacao(self, operacao: OperacaoModelo):
        """Processa uma operação específica"""
        inicio = time.time()
        sucesso = False
        erro = None
        
        try:
            self.logger.info(f"Executando {operacao.tipo.value} do modelo {operacao.nome_modelo}")
            
            if operacao.tipo == TipoOperacao.CARREGAR:
                sucesso = self._carregar_modelo(operacao)
            elif operacao.tipo == TipoOperacao.DESCARREGAR:
                sucesso = self._descarregar_modelo(operacao)
            elif operacao.tipo == TipoOperacao.PRELOAD:
                sucesso = self._preload_modelo(operacao)
            elif operacao.tipo == TipoOperacao.RELOAD:
                sucesso = self._reload_modelo(operacao)
                
        except Exception as e:
            erro = str(e)
            self.logger.error(f"Erro ao executar {operacao.tipo.value} de {operacao.nome_modelo}: {e}")
            self._chamar_callbacks('erro_operacao', operacao=operacao, erro=e)
            
        finally:
            duracao = time.time() - inicio
            
            # Remover das operações em execução
            with self._lock:
                if operacao.id_operacao in self.operacoes_executando:
                    del self.operacoes_executando[operacao.id_operacao]
                    
            # Atualizar estatísticas
            self._atualizar_estatisticas(operacao.tipo, duracao, sucesso)
            
            # Registrar no histórico
            operacao.metadados.update({
                'duracao': duracao,
                'sucesso': sucesso,
                'erro': erro,
                'timestamp_conclusao': time.time()
            })
            self.operacoes_concluidas.append(operacao)
            
            # Chamar callback se fornecido
            if operacao.callback:
                try:
                    operacao.callback(sucesso, operacao.nome_modelo, erro)
                except Exception as e:
                    self.logger.error(f"Erro em callback: {e}")
                    
            self.logger.info(f"Operação {operacao.tipo.value} de {operacao.nome_modelo} concluída: {'sucesso' if sucesso else 'falha'}")
            
    def _carregar_modelo(self, operacao: OperacaoModelo) -> bool:
        """Executa carregamento de modelo"""
        metadados = self.registro.obter_metadados(operacao.nome_modelo)
        if not metadados:
            return False
            
        # Escolher GPU
        gpu_id = self._escolher_gpu(metadados, operacao.gpu_preferida)
        if gpu_id is None:
            self.logger.warning(f"Nenhuma GPU disponível para {operacao.nome_modelo}")
            self._chamar_callbacks('memoria_insuficiente', modelo=operacao.nome_modelo)
            return False
            
        try:
            # Atualizar status para carregando
            self.registro.atualizar_status(
                operacao.nome_modelo, 
                self.registro.StatusModelo.CARREGANDO,
                gpu_id=gpu_id
            )
            
            self._chamar_callbacks('pre_carregamento', modelo=operacao.nome_modelo, gpu_id=gpu_id)
            
            # Simular carregamento (aqui seria a integração real com model loaders)
            time.sleep(2.0)  # Simula tempo de carregamento
            
            # Atualizar status para carregado
            self.registro.atualizar_status(
                operacao.nome_modelo,
                self.registro.StatusModelo.CARREGADO,
                gpu_id=gpu_id,
                memoria_alocada_mb=metadados.memoria_necessaria_mb
            )
            
            # Registrar utilização
            self.registro.registrar_utilizacao(operacao.nome_modelo, 2.0, True)
            
            self._chamar_callbacks('pos_carregamento', modelo=operacao.nome_modelo, gpu_id=gpu_id)
            
            return True
            
        except Exception as e:
            # Atualizar status para erro
            self.registro.atualizar_status(
                operacao.nome_modelo,
                self.registro.StatusModelo.ERRO,
                erro_detalhes=str(e)
            )
            raise
            
    def _descarregar_modelo(self, operacao: OperacaoModelo) -> bool:
        """Executa descarregamento de modelo"""
        try:
            status = self.registro.obter_status(operacao.nome_modelo)
            gpu_id = status.gpu_id if status else None
            
            # Atualizar status para descarregando
            self.registro.atualizar_status(
                operacao.nome_modelo,
                self.registro.StatusModelo.DESCARREGANDO
            )
            
            self._chamar_callbacks('pre_descarregamento', modelo=operacao.nome_modelo, gpu_id=gpu_id)
            
            # Simular descarregamento
            time.sleep(0.5)
            
            # Atualizar status para descarregado
            self.registro.atualizar_status(
                operacao.nome_modelo,
                self.registro.StatusModelo.DESCARREGADO
            )
            
            self._chamar_callbacks('pos_descarregamento', modelo=operacao.nome_modelo, gpu_id=gpu_id)
            
            return True
            
        except Exception as e:
            self.registro.atualizar_status(
                operacao.nome_modelo,
                self.registro.StatusModelo.ERRO,
                erro_detalhes=str(e)
            )
            raise
            
    def _preload_modelo(self, operacao: OperacaoModelo) -> bool:
        """Executa preload preditivo apenas se há recursos suficientes"""
        # Verificar disponibilidade de recursos sem impactar operações prioritárias
        metadados = self.registro.obter_metadados(operacao.nome_modelo)
        if not metadados:
            return False
            
        gpu_id = self._escolher_gpu(metadados, margem_extra=1024)  # Margem maior para preload
        if gpu_id is None:
            # Não há recursos suficientes, cancelar preload
            return False
            
        # Executar como carregamento normal
        return self._carregar_modelo(operacao)
        
    def _reload_modelo(self, operacao: OperacaoModelo) -> bool:
        """Executa reload (descarregar + carregar)"""
        # Primeiro descarregar
        if not self._descarregar_modelo(operacao):
            return False
            
        # Aguardar um momento
        time.sleep(1.0)
        
        # Depois carregar
        return self._carregar_modelo(operacao)
        
    def _escolher_gpu(self, metadados, gpu_preferida: Optional[int] = None, margem_extra: float = 0) -> Optional[int]:
        """Escolhe a GPU mais adequada para um modelo"""
        memoria_necessaria = metadados.memoria_necessaria_mb + self.margem_seguranca_memoria + margem_extra
        
        # Se GPU preferida especificada, tentar usá-la primeiro
        if gpu_preferida is not None:
            if self.monitor_gpu.memoria_suficiente_para_modelo(gpu_preferida, memoria_necessaria):
                return gpu_preferida
                
        # Caso contrário, procurar GPU com mais memória livre
        return self.monitor_gpu.obter_gpu_com_memoria_suficiente(memoria_necessaria)
        
    def _verificar_timeouts(self):
        """Verifica e cancela operações que excederam timeout"""
        agora = time.time()
        operacoes_timeout = []
        
        with self._lock:
            for id_op, operacao in self.operacoes_executando.items():
                if agora - operacao.timestamp_criacao > operacao.timeout:
                    operacoes_timeout.append(id_op)
                    
        for id_op in operacoes_timeout:
            self.logger.warning(f"Timeout na operação {id_op}")
            # Aqui poderia implementar lógica de cancelamento
            
    def _verificar_inatividade(self):
        """Verifica modelos inativos para descarregamento automático"""
        agora = time.time()
        modelos_carregados = self.registro.obter_modelos_carregados()
        
        for nome_modelo in modelos_carregados:
            metadados = self.registro.obter_metadados(nome_modelo)
            if metadados and metadados.ultima_utilizacao > 0:
                tempo_inativo = agora - metadados.ultima_utilizacao
                
                if tempo_inativo > self.tempo_inatividade_descarregar:
                    self.logger.info(f"Descarregando {nome_modelo} por inatividade ({tempo_inativo:.0f}s)")
                    self.descarregar_modelo(nome_modelo, PrioridadeOperacao.BAIXA)
                    
    def _otimizar_memoria(self):
        """Otimiza uso de memória descarregando modelos menos prioritários se necessário"""
        # Implementação simplificada - pode ser expandida
        stats_gpu = self.monitor_gpu.obter_estatisticas_resumo()
        if stats_gpu.get("percentual_memoria_usada", 0) > 85:
            # Memória alta, procurar modelos para descarregar
            modelos_carregados = self.registro.obter_modelos_carregados()
            
            # Ordenar por última utilização (mais antigo primeiro)
            modelos_ordenados = []
            for nome in modelos_carregados:
                metadados = self.registro.obter_metadados(nome)
                if metadados:
                    modelos_ordenados.append((metadados.ultima_utilizacao, nome, metadados.prioridade))
                    
            modelos_ordenados.sort()  # Mais antigo e menor prioridade primeiro
            
            # Descarregar até liberar memória suficiente
            for _, nome_modelo, prioridade in modelos_ordenados:
                if stats_gpu.get("percentual_memoria_usada", 0) < 70:
                    break
                    
                if prioridade < 8:  # Não descarregar modelos de alta prioridade
                    self.logger.info(f"Descarregando {nome_modelo} para otimização de memória")
                    self.descarregar_modelo(nome_modelo, PrioridadeOperacao.NORMAL)
                    
    def _executar_preloading_preditivo(self):
        """Executa preloading baseado em padrões de uso"""
        # Implementação simplificada - pode usar ML para previsões mais sofisticadas
        agora = time.time()
        
        for nome_modelo, historico in self.historico_uso.items():
            if len(historico) < 3:  # Poucos dados para previsão
                continue
                
            # Calcular padrão de uso recente
            usos_recentes = [h for h in historico if agora - h < 3600]  # Última hora
            
            if len(usos_recentes) >= 2:
                # Se usado frequentemente na última hora, preload
                probabilidade = min(len(usos_recentes) / 10.0, 0.9)
                
                status = self.registro.obter_status(nome_modelo)
                if status and status.status.value == 'descarregado':
                    self.preload_preditivo(nome_modelo, probabilidade)
                    
    def _limpar_caches(self):
        """Limpa caches antigos para economizar memória"""
        agora = time.time()
        
        # Limpar cache de decisões antigas (mais de 1 hora)
        chaves_antigas = [
            k for k, v in self.cache_decisoes.items() 
            if agora - v.get('timestamp', 0) > 3600
        ]
        for chave in chaves_antigas:
            del self.cache_decisoes[chave]
            
    def _atualizar_estatisticas(self, tipo_operacao: TipoOperacao, duracao: float, sucesso: bool):
        """Atualiza estatísticas do agendador"""
        with self._lock:
            if sucesso:
                self.estatisticas.operacoes_executadas += 1
                
                # Atualizar tempo médio (média móvel)
                if self.estatisticas.tempo_medio_execucao == 0:
                    self.estatisticas.tempo_medio_execucao = duracao
                else:
                    self.estatisticas.tempo_medio_execucao = (
                        self.estatisticas.tempo_medio_execucao * 0.8 + duracao * 0.2
                    )
            else:
                self.estatisticas.operacoes_falharam += 1
                
            self.estatisticas.operacoes_por_tipo[tipo_operacao.value] += 1
            
    def obter_status_operacoes(self) -> Dict:
        """Retorna status atual das operações"""
        with self._lock:
            return {
                "fila_pendente": len(self.fila_operacoes),
                "executando": len(self.operacoes_executando),
                "concluidas_recentes": len(self.operacoes_concluidas),
                "operacoes_executando": [
                    {
                        "id": op.id_operacao,
                        "modelo": op.nome_modelo,
                        "tipo": op.tipo.value,
                        "duracao": time.time() - op.timestamp_criacao
                    }
                    for op in self.operacoes_executando.values()
                ]
            }
            
    def obter_estatisticas(self) -> Dict:
        """Retorna estatísticas detalhadas do agendador"""
        with self._lock:
            return {
                "operacoes_executadas": self.estatisticas.operacoes_executadas,
                "operacoes_falharam": self.estatisticas.operacoes_falharam,
                "taxa_sucesso": (
                    self.estatisticas.operacoes_executadas / 
                    (self.estatisticas.operacoes_executadas + self.estatisticas.operacoes_falharam) * 100
                ) if (self.estatisticas.operacoes_executadas + self.estatisticas.operacoes_falharam) > 0 else 0,
                "tempo_medio_execucao": self.estatisticas.tempo_medio_execucao,
                "operacoes_por_tipo": dict(self.estatisticas.operacoes_por_tipo),
                "configuracoes": {
                    "max_operacoes_simultaneas": self.max_operacoes_simultaneas,
                    "tempo_inatividade_descarregar": self.tempo_inatividade_descarregar,
                    "margem_seguranca_memoria": self.margem_seguranca_memoria,
                    "fator_preloading": self.fator_preloading
                }
            }
