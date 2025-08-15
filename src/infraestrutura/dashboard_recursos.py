# dashboard_recursos.py

import logging

class MockClass:
    """
    Classe de mock para simular o comportamento de classes reais em ambientes de teste.
    """
    def __init__(self, *args, **kwargs):
        """
        Inicializa a classe de mock e configura o logger.
        """
        self.logger = logging.getLogger(__name__)
        
    def iniciar(self):
        """
        Simula o início de um serviço ou processo.
        """
        pass
        
    def parar(self):
        """
        Simula a parada de um serviço ou processo.
        """
        pass

class DashboardRecursos(MockClass):
    """
    Gerencia a exibição de métricas de recursos e performance em um dashboard.
    """
    def __init__(self, coletor_metricas, tracker_performance, porta=8080):
        """
        Inicializa o dashboard de recursos.

        Args:
            coletor_metricas: Objeto responsável pela coleta de métricas.
            tracker_performance: Objeto para rastrear a performance.
            porta (int): Porta para expor o dashboard.
        """
        super().__init__()
        self.porta = porta