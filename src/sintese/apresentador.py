import logging
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
from .sintetizador import ConclusaoSintese

@dataclass
class RespostaFormatada:
    """
    Encapsula a resposta final de uma checagem de fatos, estruturada
    de forma clara e amigável para o usuário final.
    """
    veredicto_principal: str
    explicacao_simples: str
    detalhes_tecnicos: str
    fontes_citadas: List[Dict]
    proximos_passos: List[str]
    timestamp: str
    disclaimer: str

class ApresentadorResultados:
    """
    Responsável por traduzir os resultados técnicos da síntese em uma
    apresentação final que seja fácil de entender, informativa e acionável
    para o usuário.
    """
    def __init__(self):
        """
        Inicializa o apresentador de resultados.
        """
        self.logger = logging.getLogger(__name__)
        
    def formatar_resposta_final(self, conclusao: ConclusaoSintese, investigacoes: List[Dict], contexto_original: str) -> RespostaFormatada:
        """
        Formata a conclusão da síntese em uma resposta estruturada e amigável.

        Args:
            conclusao (ConclusaoSintese): O objeto de conclusão do sintetizador.
            investigacoes (List[Dict]): Os dados brutos da investigação para extrair fontes.
            contexto_original (str): O texto original da checagem.

        Returns:
            RespostaFormatada: Um objeto com a resposta pronta para ser exibida.
        """
        # Mapeia o veredito técnico para um emoji visual correspondente.
        emojis = {
            "VERDADEIRO": "✅",
            "FALSO": "❌", 
            "PARCIALMENTE_VERDADEIRO": "⚠️",
            "INSUFICIENTE": "❓"
        }
        emoji = emojis.get(conclusao.veredicto, "❓")
        
        # Cria uma explicação textual simples para cada tipo de veredito.
        explicacoes = {
            "VERDADEIRO": "Esta informação foi considerada **correta** com base nas evidências encontradas.",
            "FALSO": "Esta informação foi considerada **falsa** de acordo com fontes confiáveis.",
            "PARCIALMENTE_VERDADEIRO": "Esta informação contém uma mistura de **elementos verdadeiros e falsos**.",
            "INSUFICIENTE": "**Não foi possível encontrar evidências suficientes** para chegar a uma conclusão definitiva."
        }
        explicacao = explicacoes.get(conclusao.veredicto, "A análise foi inconclusiva.")
        
        # Extrai e formata as fontes utilizadas na investigação.
        fontes = self._formatar_fontes(investigacoes)
        
        # Sugere os próximos passos com base no resultado.
        passos = self._sugerir_proximos_passos(conclusao.veredicto)
        
        return RespostaFormatada(
            veredicto_principal=f"{emoji} {conclusao.veredicto.replace('_', ' ')}",
            explicacao_simples=explicacao,
            detalhes_tecnicos=f"A análise foi baseada em {len(investigacoes)} processos de investigação. {conclusao.reasoning}",
            fontes_citadas=fontes,
            proximos_passos=passos,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            disclaimer="Esta análise foi gerada por um sistema automatizado e deve ser usada como uma orientação inicial. Sempre verifique as fontes."
        )

    def _formatar_fontes(self, investigacoes: List[Dict]) -> List[Dict]:
        """
        Extrai, deduz e formata as fontes das investigações.
        """
        fontes_formatadas = []
        fontes_vistas = set()
        for inv in investigacoes:
            for av in inv.get("avaliacoes_credibilidade", []):
                fonte_nome = av.get("fonte")
                if fonte_nome and fonte_nome not in fontes_vistas:
                    # Adiciona um ícone para identificar o tipo de fonte.
                    icone = "🏛️" if ".gov" in fonte_nome else "📰"
                    fontes_formatadas.append({
                        "nome": fonte_nome,
                        "icone": icone,
                        "credibilidade": av.get("score_final", 0)
                    })
                    fontes_vistas.add(fonte_nome)
        return fontes_formatadas

    def _sugerir_proximos_passos(self, veredicto: str) -> List[str]:
        """
        Gera uma lista de ações recomendadas para o usuário.
        """
        if veredicto == "VERDADEIRO":
            return ["A informação pode ser compartilhada com segurança.", "Considere citar as fontes verificadas."]
        elif veredicto == "FALSO":
            return ["Não compartilhe esta informação.", "Ajude a combater a desinformação alertando outras pessoas."]
        else:
            return ["Compartilhe esta informação com cautela, explicando as nuances.", "Incentive a busca por mais informações sobre o tema."]