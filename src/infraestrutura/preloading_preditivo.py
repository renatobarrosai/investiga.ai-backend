# Mock simplificado para preloading_preditivo
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

class MockClass:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        
    def iniciar(self):
        pass
        
    def parar(self):
        pass

# Classes específicas por arquivo
class AnalisadorPadroes(MockClass):
    def registrar_uso_modelo(self, nome_modelo, timestamp=None):
        pass
        
    def prever_proximos_modelos(self, modelo_atual, limite=3):
        return []

class GerenciadorPreloading(MockClass):
    pass
