import logging
from typing import List
from dataclasses import dataclass
from .executor_buscas import ResultadoBusca # Importa para anotação de tipo

@dataclass
class Contradicao:
    """
    Representa uma contradição ou divergência identificada entre duas
    ou mais fontes de informação.
    """
    fonte1: str
    fonte2: str
    tipo_contradicao: str  # Ex: "divergencia_numerica", "afirmacao_oposta".
    grau_confianca: float  # Confiança de que é uma contradição real (0.0 a 1.0).
    detalhes: str          # Descrição da contradição encontrada.

class DetectorContradicoes:
    """
    Responsável por analisar um conjunto de resultados de busca e
    identificar inconsistências, divergências ou contradições diretas
    entre as informações apresentadas por diferentes fontes.
    """
    def __init__(self):
        """
        Inicializa o detector de contradições.
        """
        self.logger = logging.getLogger(__name__)
        
    def detectar_contradicoes(self, resultados: List[ResultadoBusca]) -> List[Contradicao]:
        """
        Analisa uma lista de resultados de busca para encontrar contradições.

        Args:
            resultados (List[ResultadoBusca]): A lista de resultados a serem analisados.

        Returns:
            List[Contradicao]: Uma lista de todas as contradições encontradas.
        """
        contradicoes = []
        
        # A implementação atual é uma simulação com uma heurística simples.
        # Um sistema real usaria técnicas de NLP, como Natural Language Inference (NLI),
        # para comparar semanticamente os trechos de texto e identificar
        # relações de contradição, implicação ou neutralidade.
        
        # Heurística: compara a primeira fonte governamental com a primeira não governamental.
        fontes_gov = [r for r in resultados if '.gov.br' in r.fonte]
        fontes_nao_gov = [r for r in resultados if '.gov.br' not in r.fonte]
        
        if fontes_gov and fontes_nao_gov:
            # Simula a detecção de uma contradição se os scores de relevância forem muito diferentes.
            # Isso é uma simplificação; a análise real seria no conteúdo, não nos metadados.
            score_gov = fontes_gov[0].relevancia_score
            score_nao_gov = fontes_nao_gov[0].relevancia_score

            if abs(score_gov - score_nao_gov) > 0.4: # Limiar arbitrário
                contradicoes.append(Contradicao(
                    fonte1=fontes_gov[0].fonte,
                    fonte2=fontes_nao_gov[0].fonte,
                    tipo_contradicao="divergencia_relevancia_inferida",
                    grau_confianca=0.65,
                    detalhes=(f"Fontes governamentais e não governamentais apresentam "
                               f"relevância significativamente diferente para a mesma busca "
                               f"(Scores: {score_gov:.2f} vs {score_nao_gov:.2f}). "
                               f"Isso pode indicar uma divergência de foco ou narrativa.")
                ))
                
        return contradicoes