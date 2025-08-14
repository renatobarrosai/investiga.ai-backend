# src/infraestrutura/fila_requisicoes.py
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from queue import PriorityQueue
from threading import Lock

class StatusRequisicao(Enum):
    """Status possíveis de uma requisição"""
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDA = "concluida"
    ERRO = "erro"
    CANCELADA = "cancelada"

class PrioridadeRequisicao(Enum):
    """Níveis de prioridade para requisições"""
    BAIXA = 1
    NORMAL = 5
    ALTA = 8
    CRITICA = 10

@dataclass
class Requisicao:
    """Representação de uma requisição no sistema"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conteudo: str = ""
    tipo_conteudo: str = "texto"
    prioridade: PrioridadeRequisicao = PrioridadeRequisicao.NORMAL
    timestamp_criacao: float = field(default_factory=time.time)
    timestamp_inicio: Optional[float] = None
    timestamp_conclusao: Optional[float] = None
    status: StatusRequisicao = StatusRequisicao.PENDENTE
    resultado: Optional[Dict[str, Any]] = None
    erro: Optional[str] = None
    callback: Optional[Callable] = None
    
    def __lt__(self, other):
        # Prioridade mais alta primeiro, depois timestamp mais antigo
        if self.prioridade.value != other.prioridade.value:
            return self.prioridade.value > other.prioridade.value
        return self.timestamp_criacao < other.timestamp_criacao
        
    @property
    def tempo_espera(self) -> float:
        """Tempo que a requisição está esperando"""
        inicio = self.timestamp_inicio or time.time()
        return inicio - self.timestamp_criacao
        
    @property
    def tempo_processamento(self) -> Optional[float]:
        """Tempo de processamento da requisição"""
        if not self.timestamp_inicio:
            return None
        fim = self.timestamp_conclusao or time.time()
        return fim - self.timestamp_inicio

class GerenciadorFilas:
    """Gerenciador de filas de requisições com suporte a concorrência"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger(__name__)
        
        # Filas e controles
        self.fila_pendentes = PriorityQueue()
        self.requisicoes_ativas: Dict[str, Requisicao] = {}
        self.historico_requisicoes: Dict[str, Requisicao] = {}
        
        # Controles de concorrência
        self.lock_operacoes = Lock()
        self.processadores_ativos = 0
        
        # Métricas
        self.total_processadas = 0
        self.total_com_erro = 0
        self.tempo_medio_processamento = 0.0
        
    async def adicionar_requisicao(self, requisicao: Requisicao) -> str:
        """Adiciona uma nova requisição à fila"""
        with self.lock_operacoes:
            self.fila_pendentes.put(requisicao)
            self.historico_requisicoes[requisicao.id] = requisicao
            
        self.logger.info(
            f"Requisição adicionada: {requisicao.id[:8]}... "
            f"(prioridade: {requisicao.prioridade.name})"
        )
        
        return requisicao.id
        
    async def processar_proxima_requisicao(self, processador: Callable) -> Optional[Requisicao]:
        """Processa a próxima requisição da fila"""
        if self.processadores_ativos >= self.max_concurrent:
            return None
            
        try:
            requisicao = self.fila_pendentes.get_nowait()
        except:
            return None
            
        with self.lock_operacoes:
            self.processadores_ativos += 1
            self.requisicoes_ativas[requisicao.id] = requisicao
            
        # Atualiza status
        requisicao.status = StatusRequisicao.PROCESSANDO
        requisicao.timestamp_inicio = time.time()
        
        try:
            self.logger.info(f"Iniciando processamento: {requisicao.id[:8]}...")
            
            # Executa o processador
            resultado = await processador(requisicao)
            
            # Marca como concluída
            requisicao.status = StatusRequisicao.CONCLUIDA
            requisicao.resultado = resultado
            requisicao.timestamp_conclusao = time.time()
            
            self._atualizar_metricas(requisicao)
            
            if requisicao.callback:
                try:
                    await requisicao.callback(requisicao)
                except Exception as e:
                    self.logger.error(f"Erro no callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"Erro no processamento: {e}")
            requisicao.status = StatusRequisicao.ERRO
            requisicao.erro = str(e)
            requisicao.timestamp_conclusao = time.time()
            
            self.total_com_erro += 1
            
        finally:
            with self.lock_operacoes:
                self.processadores_ativos -= 1
                if requisicao.id in self.requisicoes_ativas:
                    del self.requisicoes_ativas[requisicao.id]
                    
        return requisicao
        
    def obter_status_requisicao(self, id_requisicao: str) -> Optional[Requisicao]:
        """Retorna o status de uma requisição específica"""
        return self.historico_requisicoes.get(id_requisicao)
        
    def cancelar_requisicao(self, id_requisicao: str) -> bool:
        """Cancela uma requisição pendente"""
        requisicao = self.historico_requisicoes.get(id_requisicao)
        
        if not requisicao:
            return False
            
        if requisicao.status == StatusRequisicao.PENDENTE:
            requisicao.status = StatusRequisicao.CANCELADA
            self.logger.info(f"Requisição cancelada: {id_requisicao[:8]}...")
            return True
            
        return False
        
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema de filas"""
        with self.lock_operacoes:
            pendentes = self.fila_pendentes.qsize()
            ativas = len(self.requisicoes_ativas)
            
        return {
            "requisicoes_pendentes": pendentes,
            "requisicoes_ativas": ativas,
            "processadores_disponiveis": self.max_concurrent - self.processadores_ativos,
            "total_processadas": self.total_processadas,
            "total_com_erro": self.total_com_erro,
            "taxa_sucesso": (
                (self.total_processadas - self.total_com_erro) / max(self.total_processadas, 1)
            ) * 100,
            "tempo_medio_processamento": self.tempo_medio_processamento
        }
        
    def listar_requisicoes_ativas(self) -> List[Dict[str, Any]]:
        """Lista requisições atualmente sendo processadas"""
        ativas = []
        
        for requisicao in self.requisicoes_ativas.values():
            ativas.append({
                "id": requisicao.id,
                "tipo_conteudo": requisicao.tipo_conteudo,
                "prioridade": requisicao.prioridade.name,
                "tempo_processamento": requisicao.tempo_processamento,
                "status": requisicao.status.value
            })
            
        return ativas
        
    def _atualizar_metricas(self, requisicao: Requisicao) -> None:
        """Atualiza métricas do sistema"""
        self.total_processadas += 1
        
        if requisicao.tempo_processamento:
            # Atualiza média móvel do tempo de processamento
            novo_tempo = requisicao.tempo_processamento
            self.tempo_medio_processamento = (
                (self.tempo_medio_processamento * (self.total_processadas - 1) + novo_tempo)
                / self.total_processadas
            )
            
        self.logger.info(
            f"Requisição concluída: {requisicao.id[:8]}... "
            f"(tempo: {requisicao.tempo_processamento:.2f}s)"
        )
        
    async def aguardar_conclusao(self, id_requisicao: str, timeout: float = 300.0) -> Optional[Requisicao]:
        """Aguarda a conclusão de uma requisição específica"""
        inicio = time.time()
        
        while time.time() - inicio < timeout:
            requisicao = self.obter_status_requisicao(id_requisicao)
            
            if not requisicao:
                return None
                
            if requisicao.status in [StatusRequisicao.CONCLUIDA, StatusRequisicao.ERRO, StatusRequisicao.CANCELADA]:
                return requisicao
                
            await asyncio.sleep(0.1)
            
        return None
