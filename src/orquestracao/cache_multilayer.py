import asyncio
import logging
import time
import hashlib
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass

class TipoConteudo(Enum):
    """
    Enumera os diferentes tipos de conteúdo que podem ser armazenados no cache,
    permitindo a aplicação de políticas de cache distintas para cada um.
    """
    RESULTADO_MODELO = "resultado_modelo"
    INVESTIGACAO_WEB = "investigacao_web"
    SINTESE_COMPLETA = "sintese_completa"

@dataclass
class EstatisticasCache:
    """
    Armazena as métricas de desempenho do sistema de cache.
    """
    total_requests: int
    hits_l1: int  # Cache em memória (mais rápido)
    hits_l2: int  # Cache em banco de dados/serviço (intermediário)
    hits_l3: int  # Cache em disco (mais lento)
    misses: int
    taxa_hit_geral: float

class CacheMultiLayer:
    """
    Implementa um sistema de cache com múltiplas camadas (L1, L2, L3)
    para otimizar a performance, armazenando resultados de operações custosas
    em diferentes níveis de velocidade e persistência.
    """
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o cache de múltiplas camadas.

        Args:
            config (Optional[Dict]): Configurações, como limiares de similaridade.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {'similarity_threshold': 0.85}
        
        # Simulação das camadas de cache
        self.l1_memoria = {}  # Dicionário em memória, mais rápido e volátil.
        self.l2_dados = {}    # Simula um cache como Redis, mais persistente.
        self.l3_disco = {}    # Simula um cache em disco, para dados maiores e menos acessados.
        
        self.estatisticas = EstatisticasCache(0, 0, 0, 0, 0, 0.0)
        
    async def get(self, chave: str, tipo_conteudo: TipoConteudo) -> Optional[Any]:
        """
        Tenta recuperar um valor do cache, procurando em cada camada, da mais
        rápida (L1) para a mais lenta (L3).

        Args:
            chave (str): A chave única que identifica o item no cache.
            tipo_conteudo (TipoConteudo): O tipo de conteúdo sendo buscado.

        Returns:
            Optional[Any]: O valor encontrado no cache ou None se for um 'miss'.
        """
        self.estatisticas.total_requests += 1
        
        # Procura no L1 (memória)
        if chave in self.l1_memoria:
            self.estatisticas.hits_l1 += 1
            self._atualizar_taxa_hit()
            return self.l1_memoria[chave]
            
        # Procura no L2 (dados estruturados)
        if chave in self.l2_dados:
            self.estatisticas.hits_l2 += 1
            valor = self.l2_dados[chave]
            self.l1_memoria[chave] = valor  # Promove para L1 para acessos futuros mais rápidos.
            self._atualizar_taxa_hit()
            return valor
            
        # Procura no L3 (disco)
        if chave in self.l3_disco:
            self.estatisticas.hits_l3 += 1
            valor = self.l3_disco[chave]
            # Promove para as camadas superiores
            self.l2_dados[chave] = valor
            self.l1_memoria[chave] = valor
            self._atualizar_taxa_hit()
            return valor
            
        # Cache miss: item não encontrado em nenhuma camada.
        self.estatisticas.misses += 1
        self._atualizar_taxa_hit()
        return None
        
    async def set(self, chave: str, valor: Any, tipo_conteudo: TipoConteudo, ttl: Optional[float] = None) -> bool:
        """
        Armazena um novo valor no cache. Na simulação atual, o valor é
        adicionado a todas as camadas.

        Args:
            chave (str): A chave única para o item.
            valor (Any): O valor a ser armazenado.
            tipo_conteudo (TipoConteudo): O tipo do conteúdo.
            ttl (Optional[float]): Tempo de vida do item no cache (não implementado na simulação).

        Returns:
            bool: True se o armazenamento foi bem-sucedido.
        """
        # Em uma implementação real, a lógica de armazenamento poderia ser
        # mais complexa, decidindo em qual camada armazenar com base no tipo
        # de conteúdo, tamanho e frequência de acesso.
        self.l1_memoria[chave] = valor
        self.l2_dados[chave] = valor
        self.l3_disco[chave] = valor
        return True
        
    async def buscar_similar(self, conteudo: str, tipo_conteudo: TipoConteudo, threshold: float = None) -> Optional[Any]:
        """
        Simula uma busca por similaridade semântica no cache.

        Args:
            conteudo (str): O conteúdo para o qual se busca um item similar.
            tipo_conteudo (TipoConteudo): O tipo de conteúdo da busca.
            threshold (float, optional): Limiar de similaridade.

        Returns:
            Optional[Any]: O valor do item similar encontrado, ou None.
        """
        threshold = threshold or self.config['similarity_threshold']
        
        # A implementação real usaria embeddings vetoriais e busca por similaridade
        # de cossenos. Esta é uma simulação extremamente simplificada usando hash.
        hash_conteudo = hashlib.md5(conteudo.encode()).hexdigest()
        
        for chave, valor in self.l1_memoria.items():
            if isinstance(valor, str):
                hash_existente = hashlib.md5(valor.encode()).hexdigest()
                if hash_conteudo == hash_existente:
                    return valor
                    
        return None
        
    def _atualizar_taxa_hit(self):
        """
        Recalcula a taxa de acerto geral do cache.
        """
        total_hits = self.estatisticas.hits_l1 + self.estatisticas.hits_l2 + self.estatisticas.hits_l3
        if self.estatisticas.total_requests > 0:
            self.estatisticas.taxa_hit_geral = total_hits / self.estatisticas.total_requests
        
    def obter_estatisticas_detalhadas(self) -> Dict[str, Any]:
        """
        Retorna um dicionário com as estatísticas de desempenho de cada camada do cache.
        """
        return {
            'geral': self.estatisticas.__dict__,
            'tamanho_camadas': {
                'l1_memoria': len(self.l1_memoria),
                'l2_dados': len(self.l2_dados),
                'l3_disco': len(self.l3_disco)
            }
        }