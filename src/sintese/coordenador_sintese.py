import asyncio
import logging
from typing import Dict, List, Any
from .sintetizador import SintetizadorCompleto, ConclusaoSintese
from .apresentador import ApresentadorResultados, RespostaFormatada

class CoordenadorSintese:
    """
    Orquestra a fase final do processo de checagem, coordenando a
    consolidação das evidências e a formatação do resultado final
    para o usuário.
    """
    def __init__(self):
        """
        Inicializa o coordenador da síntese com seus componentes.
        """
        self.logger = logging.getLogger(__name__)
        self.sintetizador = SintetizadorCompleto()
        self.apresentador = ApresentadorResultados()
        
    async def processar_sintese_completa(self, alegacoes: List, investigacoes: List[Dict], contexto_original: str) -> Dict[str, Any]:
        """
        Executa o pipeline completo da fase de síntese.

        Esta função primeiro usa o Sintetizador para consolidar as evidências
        e chegar a um veredito. Em seguida, passa esse resultado para o
        Apresentador para formatar uma resposta clara e compreensível.

        Args:
            alegacoes (List): A lista de alegações que foram investigadas.
            investigacoes (List[Dict]): Os resultados da investigação para cada alegação.
            contexto_original (str): O conteúdo original que iniciou a checagem.

        Returns:
            Dict[str, Any]: Um dicionário contendo tanto a conclusão da síntese
                            quanto a resposta final formatada.
        """
        resultado = {
            "timestamp": asyncio.get_event_loop().time(),
            "alegacoes_analisadas": len(alegacoes),
            "investigacoes_realizadas": len(investigacoes)
        }
        
        try:
            # Etapa 1: Sintetizar as evidências para chegar a uma conclusão.
            self.logger.info("Iniciando a síntese das evidências coletadas.")
            conclusao_sintetizada = self.sintetizador.sintetizar_evidencias(alegacoes, investigacoes)
            resultado["conclusao_sintese"] = conclusao_sintetizada.__dict__
            
            # Etapa 2: Formatar a conclusão em uma resposta amigável.
            self.logger.info("Formatando a resposta final para apresentação.")
            resposta_formatada = self.apresentador.formatar_resposta_final(
                conclusao_sintetizada, investigacoes, contexto_original
            )
            resultado["resposta_formatada"] = resposta_formatada.__dict__
            
            resultado["status"] = "sintese_completa_com_sucesso"
            self.logger.info(f"Síntese finalizada. Veredicto: {conclusao_sintetizada.veredicto}")
            
        except Exception as e:
            self.logger.error(f"Ocorreu um erro durante a fase de síntese: {e}", exc_info=True)
            resultado["status"] = "erro_na_sintese"
            resultado["erro"] = str(e)
            
        return resultado