# src/infraestrutura/monitor_gpu.py
import GPUtil
import time
import logging
import threading
from dataclasses import dataclass
from typing import Dict, Optional, List, Callable
from threading import Thread, Event
from collections import deque

@dataclass
class StatusGPU:
    """Status atual da GPU com métricas de utilização"""
    id_gpu: int
    utilizacao_percentual: float
    memoria_usada_mb: float
    memoria_total_mb: float
    memoria_livre_mb: float
    temperatura_celsius: float
    
    @property
    def memoria_disponivel_percentual(self) -> float:
        return (self.memoria_livre_mb / self.memoria_total_mb) * 100

@dataclass
class HistoricoGPU:
    """Histórico de métricas GPU para análise de tendências"""
    timestamps: deque
    utilizacao: deque
    memoria_usage: deque
    temperatura: deque
    
    def __init__(self, max_len: int = 100):
        self.timestamps = deque(maxlen=max_len)
        self.utilizacao = deque(maxlen=max_len)
        self.memoria_usage = deque(maxlen=max_len)
        self.temperatura = deque(maxlen=max_len)

class MonitorGPU:
    """Monitor em tempo real do uso de GPU com thresholds configuráveis e alerting"""
    
    def __init__(self, intervalo_atualizacao: float = 1.0):
        self.intervalo_atualizacao = intervalo_atualizacao
        self.logger = logging.getLogger(__name__)
        self.executando = Event()
        self.thread_monitor = None
        self.status_atual: Dict[int, StatusGPU] = {}
        self.historico: Dict[int, HistoricoGPU] = {}
        
        # Thresholds configuráveis
        self.threshold_memoria_critico = 90.0  # %
        self.threshold_memoria_alto = 75.0     # %
        self.threshold_utilizacao_alto = 85.0  # %
        self.threshold_temperatura_critico = 85.0  # °C
        self.threshold_temperatura_alto = 75.0     # °C
        
        # Sistema de callbacks para alertas
        self.callbacks_alerta: List[Callable] = []
        
        # Lock para thread safety
        self._lock = threading.Lock()
        
        # Cache de GPUs disponíveis
        self._gpus_disponiveis = None
        self._ultima_verificacao_gpus = 0
        
    def adicionar_callback_alerta(self, callback: Callable[[str, Dict], None]):
        """Adiciona callback para ser chamado quando alertas forem disparados"""
        self.callbacks_alerta.append(callback)
        
    def configurar_thresholds(self, 
                            memoria_critico: float = None,
                            memoria_alto: float = None, 
                            utilizacao_alto: float = None,
                            temperatura_critico: float = None,
                            temperatura_alto: float = None):
        """Configura thresholds de alerta"""
        if memoria_critico is not None:
            self.threshold_memoria_critico = memoria_critico
        if memoria_alto is not None:
            self.threshold_memoria_alto = memoria_alto
        if utilizacao_alto is not None:
            self.threshold_utilizacao_alto = utilizacao_alto
        if temperatura_critico is not None:
            self.threshold_temperatura_critico = temperatura_critico
        if temperatura_alto is not None:
            self.threshold_temperatura_alto = temperatura_alto
            
        self.logger.info(f"Thresholds atualizados: Mem={self.threshold_memoria_alto}%/{self.threshold_memoria_critico}%, "
                        f"GPU={self.threshold_utilizacao_alto}%, Temp={self.threshold_temperatura_alto}°C/{self.threshold_temperatura_critico}°C")
        
    def iniciar_monitoramento(self) -> None:
        """Inicia o monitoramento contínuo da GPU"""
        if self.thread_monitor and self.thread_monitor.is_alive():
            self.logger.warning("Monitor já está executando")
            return
            
        # Verificação inicial de GPUs disponíveis
        try:
            gpus_disponiveis = self._obter_gpus_disponiveis()
            if not gpus_disponiveis:
                self.logger.error("Nenhuma GPU detectada no sistema")
                return
                
            self.logger.info(f"GPUs detectadas: {[gpu.id for gpu in gpus_disponiveis]}")
            
            # Inicializa histórico para cada GPU
            for gpu in gpus_disponiveis:
                self.historico[gpu.id] = HistoricoGPU()
                
        except Exception as e:
            self.logger.error(f"Erro ao verificar GPUs disponíveis: {e}")
            return
            
        self.executando.set()
        self.thread_monitor = Thread(target=self._loop_monitoramento, daemon=True)
        self.thread_monitor.start()
        self.logger.info("Monitor GPU iniciado")
        
    def parar_monitoramento(self) -> None:
        """Para o monitoramento da GPU"""
        self.executando.clear()
        if self.thread_monitor:
            self.thread_monitor.join(timeout=5.0)
        self.logger.info("Monitor GPU parado")
        
    def _obter_gpus_disponiveis(self) -> List:
        """Obtém lista de GPUs disponíveis com cache"""
        agora = time.time()
        if (self._gpus_disponiveis is None or 
            agora - self._ultima_verificacao_gpus > 60):  # Cache por 1 minuto
            try:
                self._gpus_disponiveis = GPUtil.getGPUs()
                self._ultima_verificacao_gpus = agora
            except Exception as e:
                self.logger.error(f"Erro ao obter GPUs: {e}")
                return []
        return self._gpus_disponiveis or []
        
    def _loop_monitoramento(self) -> None:
        """Loop principal de monitoramento"""
        while self.executando.is_set():
            try:
                self._atualizar_status()
                self._verificar_thresholds()
                time.sleep(self.intervalo_atualizacao)
            except Exception as e:
                self.logger.error(f"Erro no monitoramento GPU: {e}")
                time.sleep(self.intervalo_atualizacao * 2)  # Backoff em caso de erro
                
    def _atualizar_status(self) -> None:
        """Atualiza o status atual de todas as GPUs"""
        try:
            gpus = self._obter_gpus_disponiveis()
            timestamp = time.time()
            
            with self._lock:
                for gpu in gpus:
                    # Calcular temperatura (GPUtil às vezes retorna None)
                    temperatura = gpu.temperature if gpu.temperature is not None else 0.0
                    
                    status = StatusGPU(
                        id_gpu=gpu.id,
                        utilizacao_percentual=gpu.load * 100,
                        memoria_usada_mb=gpu.memoryUsed,
                        memoria_total_mb=gpu.memoryTotal,
                        memoria_livre_mb=gpu.memoryFree,
                        temperatura_celsius=temperatura
                    )
                    
                    self.status_atual[gpu.id] = status
                    
                    # Adicionar ao histórico
                    if gpu.id in self.historico:
                        hist = self.historico[gpu.id]
                        hist.timestamps.append(timestamp)
                        hist.utilizacao.append(status.utilizacao_percentual)
                        hist.memoria_usage.append(100 - status.memoria_disponivel_percentual)
                        hist.temperatura.append(status.temperatura_celsius)
                        
        except Exception as e:
            self.logger.error(f"Erro ao atualizar status GPU: {e}")
            
    def _verificar_thresholds(self) -> None:
        """Verifica thresholds e emite alertas quando necessário"""
        with self._lock:
            for id_gpu, status in self.status_atual.items():
                uso_memoria = 100 - status.memoria_disponivel_percentual
                
                # Alertas de memória
                if uso_memoria >= self.threshold_memoria_critico:
                    self._emitir_alerta("CRITICO", "MEMORIA", {
                        "gpu_id": id_gpu,
                        "uso_memoria": uso_memoria,
                        "threshold": self.threshold_memoria_critico,
                        "memoria_livre_mb": status.memoria_livre_mb
                    })
                elif uso_memoria >= self.threshold_memoria_alto:
                    self._emitir_alerta("ALTO", "MEMORIA", {
                        "gpu_id": id_gpu,
                        "uso_memoria": uso_memoria,
                        "threshold": self.threshold_memoria_alto,
                        "memoria_livre_mb": status.memoria_livre_mb
                    })
                
                # Alertas de utilização
                if status.utilizacao_percentual >= self.threshold_utilizacao_alto:
                    self._emitir_alerta("ALTO", "UTILIZACAO", {
                        "gpu_id": id_gpu,
                        "utilizacao": status.utilizacao_percentual,
                        "threshold": self.threshold_utilizacao_alto
                    })
                
                # Alertas de temperatura
                if status.temperatura_celsius >= self.threshold_temperatura_critico:
                    self._emitir_alerta("CRITICO", "TEMPERATURA", {
                        "gpu_id": id_gpu,
                        "temperatura": status.temperatura_celsius,
                        "threshold": self.threshold_temperatura_critico
                    })
                elif status.temperatura_celsius >= self.threshold_temperatura_alto:
                    self._emitir_alerta("ALTO", "TEMPERATURA", {
                        "gpu_id": id_gpu,
                        "temperatura": status.temperatura_celsius,
                        "threshold": self.threshold_temperatura_alto
                    })
                    
    def _emitir_alerta(self, severidade: str, tipo: str, dados: Dict):
        """Emite alerta através de logging e callbacks"""
        mensagem = f"GPU {dados['gpu_id']}: {tipo} {severidade}"
        
        if tipo == "MEMORIA":
            detalhes = f"{dados['uso_memoria']:.1f}% (>{dados['threshold']}%) - {dados['memoria_livre_mb']:.0f}MB livres"
        elif tipo == "UTILIZACAO":
            detalhes = f"{dados['utilizacao']:.1f}% (>{dados['threshold']}%)"
        elif tipo == "TEMPERATURA":
            detalhes = f"{dados['temperatura']:.1f}°C (>{dados['threshold']}°C)"
        else:
            detalhes = str(dados)
            
        mensagem_completa = f"{mensagem}: {detalhes}"
        
        # Log com nível apropriado
        if severidade == "CRITICO":
            self.logger.critical(mensagem_completa)
        else:
            self.logger.warning(mensagem_completa)
            
        # Chamar callbacks registrados
        for callback in self.callbacks_alerta:
            try:
                callback(mensagem, dados)
            except Exception as e:
                self.logger.error(f"Erro em callback de alerta: {e}")
                
    def obter_status_gpu(self, id_gpu: int) -> Optional[StatusGPU]:
        """Retorna o status atual de uma GPU específica"""
        with self._lock:
            return self.status_atual.get(id_gpu)
            
    def obter_todos_status(self) -> Dict[int, StatusGPU]:
        """Retorna status de todas as GPUs"""
        with self._lock:
            return self.status_atual.copy()
        
    def obter_gpu_menos_utilizada(self) -> Optional[int]:
        """Retorna o ID da GPU com menor utilização de memória"""
        with self._lock:
            if not self.status_atual:
                return None
                
            gpu_otima = min(
                self.status_atual.items(),
                key=lambda x: x[1].memoria_usada_mb
            )
            
            return gpu_otima[0]
            
    def obter_gpu_com_memoria_suficiente(self, memoria_necessaria_mb: float) -> Optional[int]:
        """Retorna GPU com memória suficiente para carregar modelo"""
        with self._lock:
            for id_gpu, status in self.status_atual.items():
                if status.memoria_livre_mb >= memoria_necessaria_mb:
                    return id_gpu
            return None
        
    def memoria_suficiente_para_modelo(self, id_gpu: int, memoria_necessaria_mb: float) -> bool:
        """Verifica se há memória suficiente para carregar um modelo"""
        status = self.obter_status_gpu(id_gpu)
        if not status:
            return False
            
        return status.memoria_livre_mb >= memoria_necessaria_mb
        
    def obter_historico_gpu(self, id_gpu: int, janela_minutos: int = 10) -> Optional[Dict]:
        """Retorna histórico de uma GPU específica"""
        with self._lock:
            if id_gpu not in self.historico:
                return None
                
            hist = self.historico[id_gpu]
            agora = time.time()
            limite_tempo = agora - (janela_minutos * 60)
            
            # Filtrar dados dentro da janela de tempo
            dados_filtrados = {
                'timestamps': [],
                'utilizacao': [],
                'memoria_usage': [],
                'temperatura': []
            }
            
            for i, timestamp in enumerate(hist.timestamps):
                if timestamp >= limite_tempo:
                    dados_filtrados['timestamps'].append(timestamp)
                    dados_filtrados['utilizacao'].append(hist.utilizacao[i])
                    dados_filtrados['memoria_usage'].append(hist.memoria_usage[i])
                    dados_filtrados['temperatura'].append(hist.temperatura[i])
                    
            return dados_filtrados
            
    def obter_estatisticas_resumo(self) -> Dict:
        """Retorna estatísticas resumidas de todas as GPUs"""
        with self._lock:
            if not self.status_atual:
                return {"erro": "Nenhuma GPU monitorada"}
                
            stats = {
                "total_gpus": len(self.status_atual),
                "gpus_disponiveis": [],
                "memoria_total_sistema": 0,
                "memoria_usada_sistema": 0,
                "temperatura_maxima": 0,
                "utilizacao_media": 0
            }
            
            utilizacoes = []
            for id_gpu, status in self.status_atual.items():
                stats["gpus_disponiveis"].append(id_gpu)
                stats["memoria_total_sistema"] += status.memoria_total_mb
                stats["memoria_usada_sistema"] += status.memoria_usada_mb
                stats["temperatura_maxima"] = max(stats["temperatura_maxima"], status.temperatura_celsius)
                utilizacoes.append(status.utilizacao_percentual)
                
            if utilizacoes:
                stats["utilizacao_media"] = sum(utilizacoes) / len(utilizacoes)
                
            stats["memoria_livre_sistema"] = stats["memoria_total_sistema"] - stats["memoria_usada_sistema"]
            stats["percentual_memoria_usada"] = (stats["memoria_usada_sistema"] / stats["memoria_total_sistema"]) * 100 if stats["memoria_total_sistema"] > 0 else 0
            
            return stats
