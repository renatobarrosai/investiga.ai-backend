# src/infraestrutura/tracker_performance.py
import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque
from collections import deque, defaultdict
from enum import Enum
import statistics

class TipoOperacao(Enum):
    """Tipos de operação que podem ser rastreadas"""
    LOADING_MODELO = "loading_modelo"
    INFERENCIA = "inferencia"
    QUANTIZACAO = "quantizacao"
    UNLOADING_MODELO = "unloading_modelo"

@dataclass
class RegistroPerformance:
    """Registro individual de performance de uma operação"""
    timestamp: float
    nome_modelo: str
    tipo_operacao: TipoOperacao
    latencia_ms: float
    tokens_processados: int
    utilizacao_gpu: float
    memoria_mb: float
    sucesso: bool
    detalhes: Dict = field(default_factory=dict)

@dataclass
class EstatisticasModelo:
    """Estatísticas agregadas de um modelo específico"""
    nome_modelo: str
    total_requests: int = 0
    requests_sucesso: int = 0
    requests_erro: int = 0
    latencia_media_ms: float = 0.0
    latencia_p95_ms: float = 0.0
    latencia_p99_ms: float = 0.0
    throughput_tokens_s: float = 0.0
    utilizacao_gpu_media: float = 0.0
    memoria_media_mb: float = 0.0
    uptime_segundos: float = 0.0
    primeira_request: float = 0.0
    ultima_request: float = 0.0
    
    @property
    def taxa_sucesso(self) -> float:
        return (self.requests_sucesso / self.total_requests * 100) if self.total_requests > 0 else 0.0
    
    @property
    def requests_por_minuto(self) -> float:
        if self.uptime_segundos > 0:
            return (self.total_requests / self.uptime_segundos) * 60
        return 0.0

class TrackerPerformance:
    """
    Sistema avançado de tracking de performance para modelos de IA
    Monitora latência, throughput, utilização de recursos e padrões de uso
    """
    
    def __init__(self, max_registros: int = 10000, janela_estatisticas_min: int = 60):
        self.logger = logging.getLogger(__name__)
        self.max_registros = max_registros
        self.janela_estatisticas = janela_estatisticas_min * 60  # Converter para segundos
        
        # Armazenamento de dados
        self.registros: Deque[RegistroPerformance] = deque(maxlen=max_registros)
        self.estatisticas_por_modelo: Dict[str, EstatisticasModelo] = {}
        self.metricas_por_tipo: Dict[TipoOperacao, List[RegistroPerformance]] = defaultdict(list)
        
        # Cache de estatísticas calculadas
        self._cache_estatisticas = {}
        self._ultimo_calculo_cache = 0
        self._intervalo_cache = 30  # Recalcular cache a cada 30 segundos
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Tracking de modelos ativos
        self.modelos_carregados = {}  # modelo -> timestamp de loading
        
    def iniciar(self):
        """Inicializa o tracker de performance"""
        self.logger.info("Tracker de performance iniciado")
        
    def parar(self):
        """Para o tracker e limpa recursos"""
        with self._lock:
            self.logger.info(f"Tracker parado. Total de registros: {len(self.registros)}")
            
    def registrar_loading_modelo(self, nome_modelo: str, tempo_loading_s: float, 
                                memoria_alocada_mb: float, sucesso: bool = True):
        """Registra o carregamento de um modelo"""
        if sucesso:
            self.modelos_carregados[nome_modelo] = time.time()
            
        self._registrar_operacao(
            nome_modelo=nome_modelo,
            tipo_operacao=TipoOperacao.LOADING_MODELO,
            latencia_ms=tempo_loading_s * 1000,
            tokens_processados=0,
            utilizacao_gpu=0.0,  # Será preenchido pelo monitor GPU se disponível
            memoria_mb=memoria_alocada_mb,
            sucesso=sucesso,
            detalhes={"tempo_loading_s": tempo_loading_s}
        )
        
    def registrar_unloading_modelo(self, nome_modelo: str, tempo_unloading_s: float = 0.0):
        """Registra o descarregamento de um modelo"""
        if nome_modelo in self.modelos_carregados:
            tempo_ativo = time.time() - self.modelos_carregados[nome_modelo]
            del self.modelos_carregados[nome_modelo]
            
            self._registrar_operacao(
                nome_modelo=nome_modelo,
                tipo_operacao=TipoOperacao.UNLOADING_MODELO,
                latencia_ms=tempo_unloading_s * 1000,
                tokens_processados=0,
                utilizacao_gpu=0.0,
                memoria_mb=0.0,
                sucesso=True,
                detalhes={
                    "tempo_unloading_s": tempo_unloading_s,
                    "tempo_ativo_s": tempo_ativo
                }
            )
        
    def registrar_inferencia(self, nome_modelo: str, latencia_ms: float, 
                           tokens_entrada: int, tokens_saida: int,
                           utilizacao_gpu: float, memoria_mb: float, 
                           sucesso: bool = True, detalhes: Dict = None):
        """Registra uma operação de inferência"""
        total_tokens = tokens_entrada + tokens_saida
        
        self._registrar_operacao(
            nome_modelo=nome_modelo,
            tipo_operacao=TipoOperacao.INFERENCIA,
            latencia_ms=latencia_ms,
            tokens_processados=total_tokens,
            utilizacao_gpu=utilizacao_gpu,
            memoria_mb=memoria_mb,
            sucesso=sucesso,
            detalhes={
                "tokens_entrada": tokens_entrada,
                "tokens_saida": tokens_saida,
                "tokens_por_segundo": (total_tokens / latencia_ms * 1000) if latencia_ms > 0 else 0,
                **(detalhes or {})
            }
        )
        
    def registrar_quantizacao(self, nome_modelo: str, tempo_quantizacao_s: float,
                            tamanho_original_mb: float, tamanho_quantizado_mb: float,
                            sucesso: bool = True):
        """Registra uma operação de quantização"""
        reducao_percentual = ((tamanho_original_mb - tamanho_quantizado_mb) / tamanho_original_mb * 100) if tamanho_original_mb > 0 else 0
        
        self._registrar_operacao(
            nome_modelo=nome_modelo,
            tipo_operacao=TipoOperacao.QUANTIZACAO,
            latencia_ms=tempo_quantizacao_s * 1000,
            tokens_processados=0,
            utilizacao_gpu=0.0,
            memoria_mb=tamanho_quantizado_mb,
            sucesso=sucesso,
            detalhes={
                "tempo_quantizacao_s": tempo_quantizacao_s,
                "tamanho_original_mb": tamanho_original_mb,
                "tamanho_quantizado_mb": tamanho_quantizado_mb,
                "reducao_percentual": reducao_percentual
            }
        )
        
    def _registrar_operacao(self, nome_modelo: str, tipo_operacao: TipoOperacao,
                          latencia_ms: float, tokens_processados: int,
                          utilizacao_gpu: float, memoria_mb: float,
                          sucesso: bool, detalhes: Dict = None):
        """Registra uma operação no sistema de tracking"""
        with self._lock:
            registro = RegistroPerformance(
                timestamp=time.time(),
                nome_modelo=nome_modelo,
                tipo_operacao=tipo_operacao,
                latencia_ms=latencia_ms,
                tokens_processados=tokens_processados,
                utilizacao_gpu=utilizacao_gpu,
                memoria_mb=memoria_mb,
                sucesso=sucesso,
                detalhes=detalhes or {}
            )
            
            # Adicionar aos registros principais
            self.registros.append(registro)
            
            # Adicionar ao tracking por tipo
            self.metricas_por_tipo[tipo_operacao].append(registro)
            
            # Manter apenas registros recentes por tipo
            limite_tempo = time.time() - self.janela_estatisticas
            self.metricas_por_tipo[tipo_operacao] = [
                r for r in self.metricas_por_tipo[tipo_operacao] 
                if r.timestamp >= limite_tempo
            ]
            
            # Invalidar cache de estatísticas
            self._cache_estatisticas.clear()
            
            # Atualizar estatísticas do modelo
            self._atualizar_estatisticas_modelo(nome_modelo, registro)
            
    def _atualizar_estatisticas_modelo(self, nome_modelo: str, registro: RegistroPerformance):
        """Atualiza estatísticas agregadas de um modelo"""
        if nome_modelo not in self.estatisticas_por_modelo:
            self.estatisticas_por_modelo[nome_modelo] = EstatisticasModelo(
                nome_modelo=nome_modelo,
                primeira_request=registro.timestamp
            )
            
        stats = self.estatisticas_por_modelo[nome_modelo]
        stats.total_requests += 1
        stats.ultima_request = registro.timestamp
        
        if registro.sucesso:
            stats.requests_sucesso += 1
        else:
            stats.requests_erro += 1
            
        # Calcular uptime
        if stats.primeira_request > 0:
            stats.uptime_segundos = registro.timestamp - stats.primeira_request
            
    def obter_snapshot_modelo(self, nome_modelo: str) -> Optional[EstatisticasModelo]:
        """Retorna snapshot atual das estatísticas de um modelo"""
        with self._lock:
            if nome_modelo not in self.estatisticas_por_modelo:
                return None
                
            # Recalcular estatísticas detalhadas
            self._recalcular_estatisticas_modelo(nome_modelo)
            
            return self.estatisticas_por_modelo[nome_modelo]
            
    def _recalcular_estatisticas_modelo(self, nome_modelo: str):
        """Recalcula estatísticas detalhadas de um modelo"""
        stats = self.estatisticas_por_modelo[nome_modelo]
        
        # Filtrar registros recentes do modelo
        limite_tempo = time.time() - self.janela_estatisticas
        registros_recentes = [
            r for r in self.registros 
            if r.nome_modelo == nome_modelo and r.timestamp >= limite_tempo
        ]
        
        if not registros_recentes:
            return
            
        # Filtrar apenas inferências para métricas de performance
        inferencias = [r for r in registros_recentes if r.tipo_operacao == TipoOperacao.INFERENCIA and r.sucesso]
        
        if inferencias:
            latencias = [r.latencia_ms for r in inferencias]
            tokens_por_segundo = [
                r.tokens_processados / (r.latencia_ms / 1000) 
                for r in inferencias if r.latencia_ms > 0 and r.tokens_processados > 0
            ]
            utilizacoes_gpu = [r.utilizacao_gpu for r in inferencias]
            memorias = [r.memoria_mb for r in inferencias]
            
            # Calcular estatísticas
            if latencias:
                stats.latencia_media_ms = statistics.mean(latencias)
                if len(latencias) > 1:
                    stats.latencia_p95_ms = statistics.quantiles(latencias, n=20)[18]  # 95th percentile
                    stats.latencia_p99_ms = statistics.quantiles(latencias, n=100)[98]  # 99th percentile
                else:
                    stats.latencia_p95_ms = stats.latencia_media_ms
                    stats.latencia_p99_ms = stats.latencia_media_ms
                    
            if tokens_por_segundo:
                stats.throughput_tokens_s = statistics.mean(tokens_por_segundo)
                
            if utilizacoes_gpu:
                stats.utilizacao_gpu_media = statistics.mean(utilizacoes_gpu)
                
            if memorias:
                stats.memoria_media_mb = statistics.mean(memorias)
                
    def obter_todos_snapshots(self) -> Dict[str, EstatisticasModelo]:
        """Retorna snapshots de todos os modelos"""
        with self._lock:
            snapshots = {}
            for nome_modelo in self.estatisticas_por_modelo:
                snapshots[nome_modelo] = self.obter_snapshot_modelo(nome_modelo)
            return snapshots
            
    def obter_metricas_por_tipo(self, tipo_operacao: TipoOperacao, 
                              ultimos_minutos: int = None) -> Dict:
        """Retorna métricas agregadas por tipo de operação"""
        with self._lock:
            if ultimos_minutos:
                limite_tempo = time.time() - (ultimos_minutos * 60)
                registros = [
                    r for r in self.metricas_por_tipo[tipo_operacao]
                    if r.timestamp >= limite_tempo
                ]
            else:
                registros = list(self.metricas_por_tipo[tipo_operacao])
                
            if not registros:
                return {"tipo": tipo_operacao.value, "total_operacoes": 0}
                
            sucessos = sum(1 for r in registros if r.sucesso)
            latencias = [r.latencia_ms for r in registros if r.sucesso]
            
            metricas = {
                "tipo": tipo_operacao.value,
                "total_operacoes": len(registros),
                "operacoes_sucesso": sucessos,
                "taxa_sucesso": (sucessos / len(registros) * 100) if registros else 0,
                "latencia_media_ms": statistics.mean(latencias) if latencias else 0,
                "latencia_min_ms": min(latencias) if latencias else 0,
                "latencia_max_ms": max(latencias) if latencias else 0
            }
            
            if tipo_operacao == TipoOperacao.INFERENCIA:
                tokens_processados = [r.tokens_processados for r in registros if r.sucesso and r.tokens_processados > 0]
                if tokens_processados and latencias:
                    throughput = [
                        tokens / (lat / 1000) 
                        for tokens, lat in zip(tokens_processados, latencias) 
                        if lat > 0
                    ]
                    if throughput:
                        metricas["throughput_tokens_s"] = statistics.mean(throughput)
                        
            return metricas
            
    def obter_modelos_ativos(self) -> Dict[str, float]:
        """Retorna modelos atualmente carregados e há quanto tempo"""
        with self._lock:
            agora = time.time()
            return {
                modelo: agora - timestamp 
                for modelo, timestamp in self.modelos_carregados.items()
            }
            
    def obter_relatorio_performance(self, ultimos_minutos: int = 60) -> Dict:
        """Gera relatório completo de performance"""
        with self._lock:
            limite_tempo = time.time() - (ultimos_minutos * 60)
            registros_periodo = [r for r in self.registros if r.timestamp >= limite_tempo]
            
            if not registros_periodo:
                return {"periodo_minutos": ultimos_minutos, "sem_dados": True}
                
            relatorio = {
                "periodo_minutos": ultimos_minutos,
                "total_operacoes": len(registros_periodo),
                "operacoes_por_tipo": {},
                "modelos_utilizados": {},
                "performance_geral": {}
            }
            
            # Operações por tipo
            for tipo in TipoOperacao:
                metricas_tipo = self.obter_metricas_por_tipo(tipo, ultimos_minutos)
                if metricas_tipo["total_operacoes"] > 0:
                    relatorio["operacoes_por_tipo"][tipo.value] = metricas_tipo
                    
            # Performance por modelo
            modelos_periodo = set(r.nome_modelo for r in registros_periodo)
            for modelo in modelos_periodo:
                snapshot = self.obter_snapshot_modelo(modelo)
                if snapshot:
                    relatorio["modelos_utilizados"][modelo] = {
                        "requests": snapshot.total_requests,
                        "taxa_sucesso": snapshot.taxa_sucesso,
                        "latencia_media_ms": snapshot.latencia_media_ms,
                        "throughput_tokens_s": snapshot.throughput_tokens_s
                    }
                    
            # Performance geral
            sucessos = sum(1 for r in registros_periodo if r.sucesso)
            latencias_sucesso = [r.latencia_ms for r in registros_periodo if r.sucesso]
            
            relatorio["performance_geral"] = {
                "taxa_sucesso_geral": (sucessos / len(registros_periodo) * 100) if registros_periodo else 0,
                "latencia_media_geral": statistics.mean(latencias_sucesso) if latencias_sucesso else 0,
                "modelos_ativos": len(self.modelos_carregados),
                "operacoes_por_minuto": len(registros_periodo) / ultimos_minutos if ultimos_minutos > 0 else 0
            }
            
            return relatorio
