# src/infraestrutura/monitor_gpu.py
import psutil
import GPUtil
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from threading import Thread, Event

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

class MonitorGPU:
    """Monitor em tempo real do uso de GPU com thresholds configuráveis"""
    
    def __init__(self, intervalo_atualizacao: float = 1.0):
        self.intervalo_atualizacao = intervalo_atualizacao
        self.logger = logging.getLogger(__name__)
        self.executando = Event()
        self.thread_monitor = None
        self.status_atual: Dict[int, StatusGPU] = {}
        
        # Thresholds configuráveis
        self.threshold_memoria_critico = 90.0  # %
        self.threshold_memoria_alto = 75.0     # %
        self.threshold_utilizacao_alto = 85.0  # %
        
    def iniciar_monitoramento(self) -> None:
        """Inicia o monitoramento contínuo da GPU"""
        if self.thread_monitor and self.thread_monitor.is_alive():
            self.logger.warning("Monitor já está executando")
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
        
    def _loop_monitoramento(self) -> None:
        """Loop principal de monitoramento"""
        while self.executando.is_set():
            try:
                self._atualizar_status()
                self._verificar_thresholds()
                time.sleep(self.intervalo_atualizacao)
            except Exception as e:
                self.logger.error(f"Erro no monitoramento GPU: {e}")
                
    def _atualizar_status(self) -> None:
        """Atualiza o status atual de todas as GPUs"""
        gpus = GPUtil.getGPUs()
        
        for gpu in gpus:
            status = StatusGPU(
                id_gpu=gpu.id,
                utilizacao_percentual=gpu.load * 100,
                memoria_usada_mb=gpu.memoryUsed,
                memoria_total_mb=gpu.memoryTotal,
                memoria_livre_mb=gpu.memoryFree,
                temperatura_celsius=gpu.temperature
            )
            
            self.status_atual[gpu.id] = status
            
    def _verificar_thresholds(self) -> None:
        """Verifica thresholds e emite alertas quando necessário"""
        for id_gpu, status in self.status_atual.items():
            uso_memoria = 100 - status.memoria_disponivel_percentual
            
            if uso_memoria >= self.threshold_memoria_critico:
                self.logger.critical(
                    f"GPU {id_gpu}: Memória crítica {uso_memoria:.1f}%"
                )
            elif uso_memoria >= self.threshold_memoria_alto:
                self.logger.warning(
                    f"GPU {id_gpu}: Memória alta {uso_memoria:.1f}%"
                )
                
            if status.utilizacao_percentual >= self.threshold_utilizacao_alto:
                self.logger.warning(
                    f"GPU {id_gpu}: Utilização alta {status.utilizacao_percentual:.1f}%"
                )
                
    def obter_status_gpu(self, id_gpu: int) -> Optional[StatusGPU]:
        """Retorna o status atual de uma GPU específica"""
        return self.status_atual.get(id_gpu)
        
    def obter_gpu_menos_utilizada(self) -> Optional[int]:
        """Retorna o ID da GPU com menor utilização de memória"""
        if not self.status_atual:
            return None
            
        gpu_otima = min(
            self.status_atual.items(),
            key=lambda x: x[1].memoria_usada_mb
        )
        
        return gpu_otima[0]
        
    def memoria_suficiente_para_modelo(self, id_gpu: int, memoria_necessaria_mb: float) -> bool:
        """Verifica se há memória suficiente para carregar um modelo"""
        status = self.obter_status_gpu(id_gpu)
        if not status:
            return False
            
        return status.memoria_livre_mb >= memoria_necessaria_mb
