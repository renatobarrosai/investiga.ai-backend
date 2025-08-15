import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque

class TipoMetrica(Enum):
    """Define os tipos de métricas que podem ser registradas."""
    CONTADOR = "contador"  # Um valor que só aumenta.
    GAUGE = "gauge"      # Um valor que pode aumentar ou diminuir.

class SeveridadeAlerta(Enum):
    """Define os níveis de severidade para os alertas."""
    BAIXA = "baixa"
    ALTA = "alta"
    CRITICA = "critica"

@dataclass
class Metrica:
    """Representa um único ponto de dados de monitoramento."""
    nome: str
    tipo: TipoMetrica
    valor: float
    timestamp: float
    tags: Dict[str, str]  # Metadados para contextualizar a métrica.

@dataclass
class RegraAlerta:
    """Define uma condição que, se atendida, dispara um alerta."""
    nome: str
    metrica: str          # Nome da métrica a ser observada.
    condicao: str         # Operador de comparação (ex: ">", "<").
    threshold: float      # O valor limiar para a condição.
    severidade: SeveridadeAlerta

@dataclass
class Alerta:
    """Representa um alerta ativo no sistema."""
    id: str
    regra: str
    metrica: str
    valor_atual: float
    severidade: SeveridadeAlerta
    timestamp: float

class MonitoringAvancado:
    """
    Sistema de monitoramento e alerta que coleta métricas de desempenho,
    avalia regras e dispara alertas quando os limiares são ultrapassados.
    """
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o sistema de monitoramento.

        Args:
            config (Optional[Dict]): Configurações externas para o monitor.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        self.metricas = defaultdict(lambda: deque(maxlen=100)) # Armazena séries temporais de métricas.
        self.regras_alerta = {}
        self.alertas_ativos = {}
        self.historico_alertas = deque(maxlen=200) # Mantém um histórico dos últimos alertas.
        self.monitor_ativo = False
        
    async def inicializar(self):
        """
        Ativa o monitoramento e registra as regras de alerta padrão.
        """
        self.monitor_ativo = True
        
        # Adiciona uma regra de alerta padrão como exemplo.
        self.adicionar_regra_alerta(RegraAlerta(
            nome="uso_cpu_alto",
            metrica="cpu_percent",
            condicao=">",
            threshold=85.0,
            severidade=SeveridadeAlerta.ALTA
        ))
        
        self.logger.info("Sistema de monitoramento avançado inicializado.")
        
    async def registrar_metrica(self, metrica: Metrica):
        """
        Registra uma nova métrica de forma assíncrona e verifica se algum alerta deve ser disparado.
        """
        if not self.monitor_ativo:
            return
            
        self.metricas[metrica.nome].append(metrica)
        await self._verificar_alertas(metrica)
        
    def registrar_metrica_sync(self, nome: str, valor: float, tipo: TipoMetrica = TipoMetrica.GAUGE, tags: Dict[str, str] = None):
        """
        Versão síncrona para registrar uma métrica. Útil para contextos não-assíncronos.
        """
        if not self.monitor_ativo:
            return
            
        metrica = Metrica(
            nome=nome,
            tipo=tipo,
            valor=valor,
            timestamp=time.time(),
            tags=tags or {}
        )
        self.metricas[nome].append(metrica)
        # A verificação de alertas não é chamada aqui para evitar bloqueio.
        
    async def _verificar_alertas(self, metrica: Metrica):
        """
        Verifica a métrica recém-chegada contra todas as regras de alerta relevantes.
        """
        for regra in self.regras_alerta.values():
            if regra.metrica == metrica.nome:
                if self._avaliar_condicao(metrica.valor, regra):
                    await self._disparar_alerta(regra, metrica)
                    
    def _avaliar_condicao(self, valor: float, regra: RegraAlerta) -> bool:
        """
        Avalia se o valor de uma métrica satisfaz a condição de uma regra.
        """
        if regra.condicao == ">":
            return valor > regra.threshold
        elif regra.condicao == "<":
            return valor < regra.threshold
        # Outras condições (ex: "==") podem ser adicionadas aqui.
        return False
        
    async def _disparar_alerta(self, regra: RegraAlerta, metrica: Metrica):
        """
        Cria e registra um novo alerta, adicionando-o à lista de alertas ativos e ao histórico.
        """
        alerta_id = f"{regra.nome}_{int(time.time())}"
        if regra.nome in [a.regra for a in self.alertas_ativos.values()]:
            # Evita alertas duplicados para a mesma regra em um curto período.
            return

        alerta = Alerta(
            id=alerta_id,
            regra=regra.nome,
            metrica=metrica.nome,
            valor_atual=metrica.valor,
            severidade=regra.severidade,
            timestamp=time.time()
        )
        
        self.alertas_ativos[alerta_id] = alerta
        self.historico_alertas.append(alerta)
        
        self.logger.warning(f"ALERTA DISPARADO: {regra.nome} | Métrica: {metrica.nome}={metrica.valor} | Severidade: {regra.severidade.value}")
        
    def adicionar_regra_alerta(self, regra: RegraAlerta):
        """
        Adiciona uma nova regra de alerta ao sistema.
        """
        self.regras_alerta[regra.nome] = regra
        self.logger.info(f"Nova regra de alerta adicionada: '{regra.nome}'")
        
    def obter_alertas_ativos(self) -> List[Alerta]:
        """
        Retorna uma lista de todos os alertas atualmente ativos.
        """
        return list(self.alertas_ativos.values())
        
    def obter_dashboard_dados(self) -> Dict[str, Any]:
        """
        Fornece um resumo dos dados de monitoramento, ideal para um painel de controle.
        """
        return {
            'timestamp': time.time(),
            'alertas': {
                'ativos': len(self.alertas_ativos),
                'total_historico': len(self.historico_alertas)
            },
            'metricas': {
                'tipos_coletados': len(self.metricas),
                'total_registros': sum(len(serie) for serie in self.metricas.values())
            }
        }