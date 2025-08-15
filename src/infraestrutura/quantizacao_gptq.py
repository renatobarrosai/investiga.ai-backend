# Mock simplificado para quantizacao_gptq
import logging

class MockClass:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        
    def iniciar(self):
        pass
        
    def parar(self):
        pass

# Classes específicas por arquivo
class QuantizadorGPTQ(MockClass):
    def __init__(self, diretorio_base="models"):
        super().__init__()
        from pathlib import Path
        self.diretorio_base = Path(diretorio_base)
        self.diretorio_base.mkdir(exist_ok=True)
