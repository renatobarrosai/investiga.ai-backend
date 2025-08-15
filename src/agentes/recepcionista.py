import logging
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class EntradaEstruturada:
    """
    Representa os dados de entrada após o processamento inicial,
    organizando as informações de forma estruturada para as próximas etapas.
    """
    conteudo_original: str  # O texto ou dado bruto recebido.
    tipo_conteudo: str  # O tipo de mídia (ex: "texto", "imagem", "áudio").
    alegacoes_detectadas: List[str]  # Alegações preliminares identificadas.
    urls_encontradas: List[str]  # Lista de URLs extraídas do conteúdo.
    contexto_detalhado: str  # Informações contextuais adicionais.
    prioridade_verificacao: int  # Nível de prioridade para a checagem (1-10).
    metadata: Dict  # Metadados diversos (origem, data, etc.).

class ProcessadorRecepcionista:
    """
    Atua como a porta de entrada do sistema, recebendo as requisições
    brutas, limpando-as e estruturando-as em um formato padronizado
    para o restante do pipeline de análise.
    """
    def __init__(self, *args):
        """
        Inicializa o processador recepcionista.
        """
        self.logger = logging.getLogger(__name__)
        
    def processar_entrada(self, conteudo: str) -> EntradaEstruturada:
        """
        Analisa o conteúdo bruto, extrai informações essenciais como URLs
        e formata os dados na estrutura `EntradaEstruturada`.

        Args:
            conteudo (str): O dado de entrada a ser processado.

        Returns:
            EntradaEstruturada: Um objeto com os dados devidamente organizados.
        """
        import re
        # Utiliza uma expressão regular para encontrar todas as URLs no texto.
        urls = re.findall(r'http[s]?://[^\s]+', conteudo)
        
        # Cria e retorna o objeto estruturado.
        # A implementação atual é um mock, representando uma análise superficial.
        return EntradaEstruturada(
            conteudo_original=conteudo,
            tipo_conteudo="texto",  # Assume que a entrada é sempre texto.
            alegacoes_detectadas=[conteudo[:100]],  # Pega os primeiros 100 caracteres como alegação.
            urls_encontradas=urls,
            contexto_detalhado="Conteúdo processado pelo Recepcionista.",
            prioridade_verificacao=5,  # Prioridade padrão.
            metadata={}  # Metadados vazios por padrão.
        )
