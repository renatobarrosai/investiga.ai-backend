import asyncio
import logging
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from collections import deque

@dataclass
class StatusComponente:
    """
    Mantém o estado e as métricas de um componente de processamento (nó/worker).
    """
    nome: str
    ativo: bool
    carga_atual: float  # Métrica de carga, pode ser CPU, memória ou tarefas ativas.
    capacidade_maxima: int
    ultima_atividade: float
    metricas_recentes: deque  # Armazena métricas de latência, erro, etc.

class LoadBalancerInteligente:
    """
    Distribui as requisições de processamento entre os diferentes componentes
    (agentes, modelos) de forma inteligente, considerando a carga atual,
    capacidade e saúde de cada um para otimizar a performance e a resiliência.
    """
    def __init__(self):
        """
        Inicializa o balanceador de carga.
        """
        self.logger = logging.getLogger(__name__)
        self.componentes: Dict[str, StatusComponente] = {}
        self.historico_decisoes = deque(maxlen=100)
        
    async def inicializar(self):
        """
        Registra os componentes disponíveis para balanceamento.
        Em um sistema real, isso poderia ser feito via descoberta de serviços.
        """
        # Simulação do registro de componentes disponíveis.
        self.componentes = {
            'recepcionista_worker_1': StatusComponente(
                nome='recepcionista_worker_1',
                ativo=True,
                carga_atual=0.0,
                capacidade_maxima=10,
                ultima_atividade=time.time(),
                metricas_recentes=deque(maxlen=10)
            ),
            'investigador_gpu_1': StatusComponente(
                nome='investigador_gpu_1',
                ativo=True,
                carga_atual=0.0,
                capacidade_maxima=3,
                ultima_atividade=time.time(),
                metricas_recentes=deque(maxlen=10)
            ),
            'investigador_gpu_2': StatusComponente(
                nome='investigador_gpu_2',
                ativo=True,
                carga_atual=0.0,
                capacidade_maxima=3,
                ultima_atividade=time.time(),
                metricas_recentes=deque(maxlen=10)
            )
        }
        self.logger.info(f"Load balancer inicializado com {len(self.componentes)} componentes.")
        
    async def selecionar_componente_otimo(self, tipo_operacao: str, prioridade: int = 5) -> Optional[str]:
        """
        Seleciona o melhor componente para executar uma dada operação,
        baseado em uma estratégia de balanceamento (ex: menor carga).

        Args:
            tipo_operacao (str): O tipo de tarefa a ser executada (ex: "investigacao").
            prioridade (int): A prioridade da requisição.

        Returns:
            Optional[str]: O nome do componente selecionado, ou None se nenhum estiver disponível.
        """
        if not self.componentes:
            await self.inicializar()

        # Filtra componentes ativos e compatíveis com a operação.
        componentes_disponiveis = [
            comp for comp in self.componentes.values() 
            if comp.ativo and tipo_operacao.startswith(comp.nome.split('_')[0])
        ]

        if not componentes_disponiveis:
            self.logger.warning(f"Nenhum componente disponível para a operação '{tipo_operacao}'.")
            return None

        # Estratégia: seleciona o componente com a menor carga atual.
        melhor_componente = min(componentes_disponiveis, key=lambda x: x.carga_atual)
        
        # Registra a decisão para fins de monitoramento e análise.
        self.historico_decisoes.append({
            'timestamp': time.time(),
            'tipo_operacao': tipo_operacao,
            'componente_selecionado': melhor_componente.nome,
            'carga_no_momento': melhor_componente.carga_atual
        })
        
        return melhor_componente.nome
        
    async def registrar_uso_componente(self, nome_componente: str, inicio: float, fim: float, sucesso: bool = True):
        """
        Atualiza o estado de um componente após a execução de uma tarefa.

        Args:
            nome_componente (str): O nome do componente que executou a tarefa.
            inicio (float): Timestamp do início da execução.
            fim (float): Timestamp do fim da execução.
            sucesso (bool): Se a tarefa foi concluída com sucesso.
        """
        if nome_componente in self.componentes:
            comp = self.componentes[nome_componente]
            comp.ultima_atividade = fim
            duracao = fim - inicio
            
            # A métrica de carga é simplificada aqui. Poderia ser mais complexa.
            # Incrementa a carga pela duração da tarefa.
            comp.carga_atual = min(comp.capacidade_maxima, comp.carga_atual + duracao)
            
            # Adiciona métricas de desempenho para futuras decisões.
            comp.metricas_recentes.append({'duracao': duracao, 'sucesso': sucesso})

            # Simula um decaimento da carga ao longo do tempo.
            # Em um sistema real, a carga seria atualizada por um monitor de recursos.
            asyncio.create_task(self._reduzir_carga_componente(nome_componente, duracao))

    async def _reduzir_carga_componente(self, nome_componente: str, reducao: float):
        """
        Simula o decaimento da carga de um componente após um tempo.
        """
        await asyncio.sleep(10) # Espera um tempo antes de reduzir a carga.
        if nome_componente in self.componentes:
            comp = self.componentes[nome_componente]
            comp.carga_atual = max(0, comp.carga_atual - reducao)

    def obter_estatisticas(self) -> Dict[str, Any]:
        """
        Retorna as estatísticas de uso e carga dos componentes.
        """
        return {
            'componentes': {
                nome: {
                    'ativo': comp.ativo,
                    'carga_atual': round(comp.carga_atual, 2),
                    'utilizacao_percentual': round((comp.carga_atual / comp.capacidade_maxima) * 100, 2)
                }
                for nome, comp in self.componentes.items()
            },
            'decisoes_recentes': list(self.historico_decisoes)[-5:]
        }