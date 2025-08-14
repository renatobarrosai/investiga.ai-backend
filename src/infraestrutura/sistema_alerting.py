import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class SeveridadeAlerta(Enum):
    """Define os níveis de severidade para um alerta."""
    INFO = "info"
    ATENCAO = "atencao"
    CRITICO = "critico"

@dataclass
class Alerta:
    """Representa uma notificação de alerta gerada pelo sistema."""
    id: str
    tipo: str  # Categoria do alerta (ex: "recursos", "performance", "seguranca").
    severidade: SeveridadeAlerta
    titulo: str
    mensagem: str
    timestamp: float
    metadados: Optional[Dict] = None

class SistemaAlerting:
    """
    Gerencia a geração e o despacho de alertas sobre o estado do sistema.
    Pode ser integrado a sistemas de notificação como Slack, PagerDuty ou e-mail.
    """
    def __init__(self, *args, **kwargs):
        """
        Inicializa o sistema de alertas.
        """
        self.logger = logging.getLogger(__name__)
        self.alertas_ativos: List[Alerta] = []
        
    def iniciar(self):
        """
        Inicia o serviço de alertas, estabelecendo conexões se necessário.
        """
        self.logger.info("Sistema de Alertas iniciado.")
        pass
        
    def parar(self):
        """
        Para o serviço de alertas.
        """
        self.logger.info("Sistema de Alertas parado.")
        pass
        
    def emitir_alerta(self, tipo: str, severidade: SeveridadeAlerta, titulo: str, mensagem: str, metadados: Optional[Dict] = None) -> str:
        """
        Cria e emite um novo alerta.

        Args:
            tipo (str): A categoria do alerta.
            severidade (SeveridadeAlerta): O nível de urgência.
            titulo (str): Um título curto para o alerta.
            mensagem (str): A descrição detalhada do alerta.
            metadados (Optional[Dict]): Dados adicionais para contexto.

        Returns:
            str: O ID único do alerta gerado.
        """
        alerta_id = f"alerta-{int(time.time())}"
        alerta = Alerta(
            id=alerta_id,
            tipo=tipo,
            severidade=severidade,
            titulo=titulo,
            mensagem=mensagem,
            timestamp=time.time(),
            metadados=metadados
        )
        self.alertas_ativos.append(alerta)
        
        # Em uma implementação real, aqui o alerta seria enviado para
        # um canal de notificação (ex: post em um webhook do Slack).
        self.logger.log(
            logging.WARNING if severidade != SeveridadeAlerta.INFO else logging.INFO,
            f"ALERTA EMITIDO [{severidade.value.upper()}]: {titulo} - {mensagem}"
        )
        
        return alerta_id
        
    def obter_alertas_ativos(self) -> List[Alerta]:
        """
        Retorna a lista de alertas que estão atualmente ativos.
        """
        return self.alertas_ativos