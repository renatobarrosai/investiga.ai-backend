import logging
from dataclasses import dataclass
from typing import List
from .executor_buscas import ResultadoBusca # Importa para anotação de tipo

@dataclass
class AvaliacaoCredibilidade:
    """
    Armazena a avaliação de credibilidade de uma única fonte, detalhando
    os fatores que contribuíram para a sua pontuação final.
    """
    score_autoridade: float      # Pontuação baseada na autoridade e reputação do domínio.
    score_atualidade: float      # Pontuação baseada na data de publicação do conteúdo.
    score_transparencia: float   # Pontuação baseada na clareza sobre autoria e fontes.
    score_final: float           # A pontuação de credibilidade consolidada (0.0 a 1.0).
    fatores_positivos: List[str] # Fatores específicos que aumentaram a credibilidade.
    fatores_negativos: List[str] # Fatores específicos que diminuíram a credibilidade.

class AvaliadorCredibilidade:
    """
    Avalia a credibilidade de uma fonte de informação (um site, um documento)
    com base em um conjunto de heurísticas e critérios, como autoridade do
    domínio, transparência, data de publicação e outros indicadores.
    """
    def __init__(self):
        """
        Inicializa o avaliador de credibilidade.
        """
        self.logger = logging.getLogger(__name__)
        
    def avaliar_fonte(self, resultado: ResultadoBusca) -> AvaliacaoCredibilidade:
        """
        Calcula um score de credibilidade para um resultado de busca.

        Args:
            resultado (ResultadoBusca): O resultado de busca a ser avaliado.

        Returns:
            AvaliacaoCredibilidade: Um objeto com a pontuação detalhada.
        """
        # A implementação atual usa uma heurística simples baseada no domínio da fonte.
        # Um sistema real poderia usar uma lista de domínios conhecidos (ex: NewsGuard),
        # analisar o conteúdo da página em busca de indicadores de transparência
        # (ex: "sobre nós", "política editorial") e verificar a data de publicação.
        
        fatores_positivos = []
        fatores_negativos = []

        # Avaliação de autoridade baseada no domínio.
        if '.gov.br' in resultado.fonte or '.leg.br' in resultado.fonte:
            score_autoridade = 0.95
            fatores_positivos.append("Fonte governamental oficial, alta autoridade.")
        elif any(domain in resultado.fonte for domain in ['folha.uol.com.br', 'estadao.com.br', 'g1.globo.com']):
            score_autoridade = 0.85
            fatores_positivos.append("Veículo de imprensa tradicional e estabelecido.")
        elif any(domain in resultado.fonte for domain in ['.edu.br', '.org.br']):
            score_autoridade = 0.75
            fatores_positivos.append("Domínio de organização ou educacional.")
        else:
            score_autoridade = 0.50
            fatores_negativos.append("Domínio genérico ou desconhecido, requer cautela.")
            
        # Simulação de outras avaliações.
        score_atualidade = 0.80  # Mock - um sistema real extrairia a data da página.
        score_transparencia = 0.75  # Mock - um sistema real buscaria por autoria clara.
        
        # Cálculo do score final com pesos diferentes para cada critério.
        score_final = (score_autoridade * 0.5 + score_atualidade * 0.3 + score_transparencia * 0.2)
        
        return AvaliacaoCredibilidade(
            score_autoridade=score_autoridade,
            score_atualidade=score_atualidade,
            score_transparencia=score_transparencia,
            score_final=round(score_final, 2),
            fatores_positivos=fatores_positivos,
            fatores_negativos=fatores_negativos
        )