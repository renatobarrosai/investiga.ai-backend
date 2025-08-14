import logging
import time
from typing import Dict
from dataclasses import dataclass

@dataclass
class PerformanceSnapshot:
    nome_modelo: str
    total_requests: int = 0
    latencia_media_ms: float = 100.0
    throughput_tokens_s: float = 50.0
    utilizacao_gpu: float = 60.0
    memoria_mb: float = 2048.0
    requests_com_erro: int = 0
    timestamp: float = 0.0
    uptime_segundos: float = 0.0
    latencia_p95_ms: float = 150.0

class TrackerPerformance:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.contadores = {}
        
    def iniciar(self):
        pass
        
    def parar(self):
        pass
        
    def registrar_request(self, nome_modelo, latencia_ms, tokens, utilizacao_gpu, memoria_mb, sucesso=True):
        if nome_modelo not in self.contadores:
            self.contadores[nome_modelo] = 0
        self.contadores[nome_modelo] += 1
        
    def obter_snapshot(self, nome_modelo):
        count = self.contadores.get(nome_modelo, 0)
        return PerformanceSnapshot(nome_modelo, total_requests=count)
        
    def obter_todos_snapshots(self):
        return {nome: self.obter_snapshot(nome) for nome in self.contadores}
