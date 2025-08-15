import asyncio
import logging
from typing import Dict, Any
from .gerador_estrategias import GeradorEstrategias
from .executor_buscas import ExecutorBuscas
from .avaliador_credibilidade import AvaliadorCredibilidade
from .detector_contradicoes import DetectorContradicoes

class CoordenadorInvestigacao:
    """
    Orquestra o processo completo de investigação de uma alegação,
    desde a criação da estratégia de busca até a detecção de contradições
    nas fontes encontradas.
    """
    
    def __init__(self):
        """
        Inicializa o coordenador com todos os componentes necessários
        para a fase de investigação.
        """
        self.logger = logging.getLogger(__name__)
        self.gerador_estrategia = GeradorEstrategias()
        self.executor_busca = ExecutorBuscas() 
        self.avaliador_credibilidade = AvaliadorCredibilidade()
        self.detector_contradicoes = DetectorContradicoes()
        
    async def investigar_alegacao(self, alegacao: str) -> Dict[str, Any]:
        """
        Executa o pipeline de investigação de ponta a ponta para uma única alegação.

        O fluxo de trabalho é o seguinte:
        1. Gerar uma estratégia de busca otimizada.
        2. Executar as buscas na web com base na estratégia.
        3. Avaliar a credibilidade de cada fonte encontrada.
        4. Analisar os resultados em conjunto para detectar contradições.

        Args:
            alegacao (str): O texto da alegação a ser investigada.

        Returns:
            Dict[str, Any]: Um dicionário consolidado com todos os resultados
                            da investigação.
        """
        
        resultado = {
            "alegacao_investigada": alegacao,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            # Etapa 1: Gerar a estratégia de busca.
            self.logger.info(f"Gerando estratégia de busca para a alegação: '{alegacao[:50]}...'")
            estrategia = self.gerador_estrategia.gerar_estrategia(alegacao)
            resultado["estrategia_utilizada"] = estrategia.__dict__
            
            # Etapa 2: Executar as buscas na web.
            self.logger.info("Executando buscas na web...")
            resultados_busca = await self.executor_busca.executar_busca_completa(estrategia)
            resultado["total_resultados_busca"] = len(resultados_busca)
            
            # Etapa 3: Avaliar a credibilidade das fontes encontradas.
            self.logger.info(f"Avaliando a credibilidade de {len(resultados_busca)} fontes.")
            avaliacoes = []
            for res_busca in resultados_busca:
                avaliacao = self.avaliador_credibilidade.avaliar_fonte(res_busca)
                avaliacoes.append(avaliacao.__dict__)
            resultado["avaliacoes_credibilidade"] = avaliacoes
            
            # Etapa 4: Detectar contradições entre as fontes.
            self.logger.info("Detectando contradições entre as evidências.")
            contradicoes = self.detector_contradicoes.detectar_contradicoes(resultados_busca)
            resultado["contradicoes_detectadas"] = [c.__dict__ for c in contradicoes]
            
            resultado["status"] = "investigacao_concluida_com_sucesso"
            self.logger.info("Investigação concluída com sucesso.")
            
        except Exception as e:
            self.logger.error(f"Erro durante a investigação da alegação: {e}", exc_info=True)
            resultado["status"] = "erro_na_investigacao"
            resultado["erro"] = str(e)
            
        return resultado