# Mock simplificado para pool_threads_modelos
import logging
from dataclasses import dataclass
from enum import Enum

class MockClass:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        
    def iniciar(self):
        pass
        
    def parar(self):
        pass

# Classes específicas por arquivo
class TipoOperacao(Enum):
    CARREGAR = "carregar"
    INFERENCIA = "inferencia"

@dataclass
class TarefaModelo:
    id_tarefa: str
    tipo: TipoOperacao
    nome_modelo: str
    funcao: callable
    args: tuple
    kwargs: dict

class PoolThreadsModelos(MockClass):
    def submeter_operacao(self, tarefa):
        return tarefa.id_tarefa
        
    def aguardar_operacao(self, id_tarefa, timeout=None):
        return {"sucesso": True}
        
    def fechar(self):
        pass