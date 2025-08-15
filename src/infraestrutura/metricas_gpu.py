# Mock simplificado para metricas_gpu
import logging
import time
from dataclasses import dataclass

class MockClass:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        
    def iniciar(self):
        pass
        
    def parar(self):
        pass

# Classes específicas por arquivo
@dataclass
class MetricaGPU:
    timestamp: float
    gpu_id: int
    utilizacao_gpu: float
    utilizacao_memoria: float
    memoria_total_mb: float
    memoria_usada_mb: float
    memoria_livre_mb: float
    temperatura: float

class ColetorMetricas(MockClass):
    def obter_metricas_gpu(self, gpu_id, janela_segundos=60):
        return [MetricaGPU(time.time(), gpu_id, 50.0, 60.0, 8192.0, 4096.0, 4096.0, 70.0)]
        
    def registrar_inferencia(self, nome_modelo, gpu_id, tempo_ms, tokens):
        pass
        
    def obter_estatisticas_modelo(self, nome_modelo):
        return {"total_inferencias": 1}
