# src/infraestrutura/coordenador_quantizacao.py
import logging
from typing import Dict, List, Optional
from .quantizacao_gptq import QuantizadorGPTQ
from .quantizacao_awq import QuantizadorAWQ
from .benchmark_quantizacao import BenchmarkQuantizacao
from .storage_modelos import GerenciadorStorageModelos

class CoordenadorQuantizacao:
    """
    Orquestra o fluxo de quantização de modelos, desde a aplicação da
    técnica de quantização até o armazenamento e versionamento do modelo otimizado.
    """
    
    def __init__(self):
        """
        Inicializa o coordenador com todas as dependências necessárias para o processo.
        """
        self.quantizador_gptq = QuantizadorGPTQ()
        self.quantizador_awq = QuantizadorAWQ()
        self.benchmark = BenchmarkQuantizacao()
        self.storage = GerenciadorStorageModelos()
        self.logger = logging.getLogger(__name__)
        
    def processar_modelo_completo(
        self,
        modelo_origem: str,
        nome_modelo: str,
        tipo_quantizacao: str,
        bits: int = 4
    ) -> Optional[str]:
        """
        Executa o pipeline completo de otimização de um modelo.

        O processo inclui:
        1. Quantização do modelo usando a técnica especificada (GPTQ ou AWQ).
        2. Avaliação (benchmark) do modelo quantizado para medir performance e qualidade.
        3. Armazenamento do modelo otimizado e seus metadados de benchmark.

        Args:
            modelo_origem (str): O identificador ou caminho do modelo base.
            nome_modelo (str): Nome para identificar o modelo após a quantização.
            tipo_quantizacao (str): A técnica a ser aplicada ('gptq' or 'awq').
            bits (int): A precisão de bits para a quantização (ex: 4).

        Returns:
            Optional[str]: O ID da versão do modelo armazenado em caso de sucesso,
                           ou None se ocorrer algum erro.
        """
        
        try:
            # Etapa 1: Quantização do modelo
            caminho_quantizado = f"temp/{nome_modelo}_{tipo_quantizacao}_{bits}bit"
            
            if tipo_quantizacao == "gptq":
                sucesso = self.quantizador_gptq.quantizar_llama_3_8b(
                    modelo_origem, caminho_quantizado, bits
                )
                carregador = self.quantizador_gptq.carregar_modelo_quantizado_gptq
            elif tipo_quantizacao == "awq":
                sucesso = self.quantizador_awq.quantizar_gemma_2b(
                    modelo_origem, caminho_quantizado, bits
                )
                carregador = self.quantizador_awq.carregar_modelo_quantizado_awq
            else:
                raise ValueError(f"Tipo de quantização inválido: {tipo_quantizacao}")
                
            if not sucesso:
                self.logger.error("Falha na etapa de quantização.")
                return None
                
            # Etapa 2: Benchmark de performance e qualidade
            resultado_benchmark = self.benchmark.executar_benchmark_completo(
                caminho_quantizado, tipo_quantizacao, carregador
            )
            
            # Etapa 3: Armazenamento e versionamento do modelo
            metadados = {
                "qualidade_score": resultado_benchmark.qualidade_score,
                "perplexidade": resultado_benchmark.perplexidade,
                "throughput": resultado_benchmark.throughput_tokens_por_segundo,
                "memoria_mb": resultado_benchmark.memoria_mb
            }
            id_versao = self.storage.armazenar_modelo_quantizado(
                caminho_quantizado,
                nome_modelo,
                tipo_quantizacao,
                bits,
                metadados
            )
            
            self.logger.info(f"Processo de quantização e armazenamento concluído com sucesso. ID da versão: {id_versao}")
            return id_versao
            
        except Exception as e:
            self.logger.error(f"Erro durante o processo de coordenação da quantização: {e}", exc_info=True)
            return None