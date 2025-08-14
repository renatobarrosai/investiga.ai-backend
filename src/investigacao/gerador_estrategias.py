import logging
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

class TipoFonte(Enum):
    """
    Enumera os tipos de fontes de informação que podem ser priorizados
    durante uma busca.
    """
    GOVERNAMENTAL = "gov"
    JORNALISTICA = "news"
    ACADEMICA = "academic"
    ESPECIALIZADA = "specialized"

@dataclass  
class EstrategiaBusca:
    """
    Define um plano detalhado para a execução de buscas na web,
    orientando o `ExecutorBuscas` sobre como e onde procurar as informações.
    """
    queries: List[str]  # Lista de termos de busca a serem executados.
    dominios_prioritarios: List[str]  # Sites a serem priorizados nos resultados.
    tipos_fonte: List[TipoFonte]  # Tipos de fontes a serem buscadas.
    filtros_temporais: Dict[str, str]  # Filtros de data (ex: {"periodo": "ultimo_ano"}).
    palavras_chave_essenciais: List[str]  # Termos que devem estar presentes nos resultados.
    contexto_busca: str  # O contexto geral da alegação (ex: "política", "saúde").

class GeradorEstrategias:
    """
    Componente responsável por analisar uma alegação e criar uma
    estratégia de busca otimizada para encontrar evidências relevantes
    e confiáveis na web.
    """
    def __init__(self):
        """
        Inicializa o gerador de estratégias.
        """
        self.logger = logging.getLogger(__name__)
        
    def gerar_estrategia(self, alegacao: str, tipo_alegacao: str = "factual") -> EstrategiaBusca:
        """
        Cria uma EstrategiaBusca com base no conteúdo e tipo da alegação.

        Args:
            alegacao (str): O texto da alegação a ser investigada.
            tipo_alegacao (str): O tipo da alegação (ex: "factual", "estatística").

        Returns:
            EstrategiaBusca: O plano de busca detalhado.
        """
        # A implementação atual usa uma análise simples baseada em palavras-chave.
        # Um sistema avançado usaria NLP para extrair entidades, tópicos e
        # intenção da alegação para criar uma estratégia muito mais sofisticada.
        
        if any(word in alegacao.lower() for word in ["governo", "ministério", "federal", "lei"]):
            categoria = "politica"
            dominios = ["*.gov.br", "camara.leg.br", "senado.leg.br"]
            tipos = [TipoFonte.GOVERNAMENTAL, TipoFonte.JORNALISTICA]
        elif any(word in alegacao.lower() for word in ["estudo", "pesquisa", "cientistas"]):
            categoria = "ciencia"
            dominios = ["scielo.br", "nature.com", "sciencemag.org"]
            tipos = [TipoFonte.ACADEMICA, TipoFonte.ESPECIALIZADA]
        else:
            categoria = "geral"
            dominios = ["g1.globo.com", "folha.uol.com.br", "estadao.com.br"]
            tipos = [TipoFonte.JORNALISTICA]
            
        # Gera queries de busca, incluindo uma busca pela alegação exata.
        palavras_chave = alegacao.split()
        queries = [
            f'"{alegacao}"',  # Busca exata
            f"{' '.join(palavras_chave[:4])} {categoria}",
            f"{' '.join(palavras_chave[:2])} fonte oficial"
        ]
        
        return EstrategiaBusca(
            queries=queries,
            dominios_prioritarios=dominios,
            tipos_fonte=tipos,
            filtros_temporais={"periodo": "ultimo_ano"},
            palavras_chave_essenciais=palavras_chave[:3],
            contexto_busca=categoria
        )