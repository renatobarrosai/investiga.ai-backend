# src/agentes/model_loaders/gemma_loader.py
import logging
import time
import torch
from typing import Optional, Dict, Any, List
from pathlib import Path
import gc
import psutil
from dataclasses import dataclass

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
    from awq import AutoAWQForCausalLM
except ImportError as e:
    logging.error(f"Dependências necessárias não encontradas: {e}")
    raise

@dataclass
class GemmaLoadResult:
    """Resultado do carregamento do modelo Gemma"""
    sucesso: bool
    modelo: Optional[Any] = None
    tokenizer: Optional[Any] = None
    erro: Optional[str] = None
    memoria_alocada_mb: float = 0.0
    tempo_carregamento: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class GemmaLoader:
    """
    Loader especializado para modelos Gemma-2B com quantização AWQ.
    
    Responsável por:
    - Carregamento otimizado com quantização AWQ
    - Gerenciamento de memória GPU/CPU
    - Integração com registry e monitoring
    - Error handling e recovery
    """
    
    def __init__(self, registry=None, monitor_gpu=None):
        self.registry = registry
        self.monitor_gpu = monitor_gpu
        self.logger = logging.getLogger(__name__)
        
        # Controle de instâncias carregadas
        self.modelo_carregado = None
        self.tokenizer_carregado = None
        self.nome_modelo_atual = None
        self.gpu_alocada = None
        
        # Configurações padrão AWQ
        self.config_awq_padrao = {
            "bits": 4,
            "group_size": 128,
            "zero_point": True,
            "version": "GEMM",
            "use_exllama": True,
            "use_exllama_v2": False,
            "max_input_length": 2048,
            "max_batch_size": 1
        }
        
        # Cache de configurações
        self._cache_configs = {}
        
    def carregar_modelo(self, nome_modelo: str, gpu_id: Optional[int] = None,
                       force_reload: bool = False, **kwargs) -> GemmaLoadResult:
        """
        Carrega modelo Gemma-2B com quantização AWQ
        
        Args:
            nome_modelo: Nome do modelo no registry
            gpu_id: ID da GPU para carregar (None = auto)
            force_reload: Força recarregamento se já carregado
            **kwargs: Configurações adicionais
            
        Returns:
            GemmaLoadResult com status do carregamento
        """
        inicio = time.time()
        
        try:
            # Verificar se já está carregado
            if (not force_reload and self.nome_modelo_atual == nome_modelo 
                and self.modelo_carregado is not None):
                self.logger.info(f"Modelo {nome_modelo} já carregado")
                return GemmaLoadResult(
                    sucesso=True,
                    modelo=self.modelo_carregado,
                    tokenizer=self.tokenizer_carregado,
                    tempo_carregamento=0.0,
                    metadata={"status": "already_loaded"}
                )
            
            # Obter configurações do modelo
            config_modelo = self._obter_config_modelo(nome_modelo)
            if not config_modelo:
                return GemmaLoadResult(
                    sucesso=False,
                    erro=f"Configuração não encontrada para modelo: {nome_modelo}"
                )
            
            # Verificar recursos disponíveis
            gpu_escolhida = self._escolher_gpu(config_modelo, gpu_id)
            if gpu_escolhida is None:
                return GemmaLoadResult(
                    sucesso=False,
                    erro="Nenhuma GPU disponível com memória suficiente"
                )
            
            # Descarregar modelo anterior se necessário
            if self.modelo_carregado is not None:
                self._descarregar_modelo_atual()
            
            # Atualizar status no registry
            if self.registry:
                self.registry.atualizar_status(
                    nome_modelo, 
                    self.registry.StatusModelo.CARREGANDO,
                    gpu_id=gpu_escolhida
                )
            
            # Carregar modelo com AWQ
            resultado = self._carregar_com_awq(config_modelo, gpu_escolhida, **kwargs)
            
            if resultado.sucesso:
                # Armazenar referências
                self.modelo_carregado = resultado.modelo
                self.tokenizer_carregado = resultado.tokenizer
                self.nome_modelo_atual = nome_modelo
                self.gpu_alocada = gpu_escolhida
                
                # Calcular memória alocada
                memoria_mb = self._calcular_memoria_modelo()
                resultado.memoria_alocada_mb = memoria_mb
                
                # Atualizar registry
                if self.registry:
                    self.registry.atualizar_status(
                        nome_modelo,
                        self.registry.StatusModelo.CARREGADO,
                        gpu_id=gpu_escolhida,
                        memoria_alocada_mb=memoria_mb
                    )
                    self.registry.registrar_utilizacao(
                        nome_modelo, 
                        resultado.tempo_carregamento, 
                        True
                    )
                
                self.logger.info(
                    f"Modelo {nome_modelo} carregado com sucesso "
                    f"(GPU: {gpu_escolhida}, Memória: {memoria_mb:.1f}MB, "
                    f"Tempo: {resultado.tempo_carregamento:.2f}s)"
                )
            else:
                # Erro no carregamento
                if self.registry:
                    self.registry.atualizar_status(
                        nome_modelo,
                        self.registry.StatusModelo.ERRO,
                        erro_detalhes=resultado.erro
                    )
                    self.registry.registrar_utilizacao(nome_modelo, 0, False)
            
            resultado.tempo_carregamento = time.time() - inicio
            return resultado
            
        except Exception as e:
            erro = f"Erro inesperado ao carregar {nome_modelo}: {str(e)}"
            self.logger.error(erro, exc_info=True)
            
            if self.registry:
                self.registry.atualizar_status(
                    nome_modelo,
                    self.registry.StatusModelo.ERRO,
                    erro_detalhes=erro
                )
            
            return GemmaLoadResult(
                sucesso=False,
                erro=erro,
                tempo_carregamento=time.time() - inicio
            )
    
    def _obter_config_modelo(self, nome_modelo: str) -> Optional[Dict]:
        """Obtém configuração do modelo do registry ou config"""
        if self.registry:
            metadados = self.registry.obter_metadados(nome_modelo)
            if metadados:
                return {
                    'nome': metadados.nome,
                    'caminho': metadados.caminho,
                    'memoria_mb': metadados.memoria_necessaria_mb,
                    'quantizacao': metadados.quantizacao.value,
                    'configuracoes': metadados.configuracoes
                }
        
        # Fallback para configurações hard-coded
        configs_padrao = {
            "gemma-2b-recepcionista": {
                'nome': "gemma-2b-recepcionista",
                'caminho': "models/gemma-2b-it-awq",
                'memoria_mb': 2048,
                'quantizacao': 'awq',
                'configuracoes': {
                    'max_tokens': 512,
                    'temperature': 0.1,
                    'trust_remote_code': True
                }
            },
            "gemma-2b-apresentador": {
                'nome': "gemma-2b-apresentador",
                'caminho': "models/gemma-2b-it-awq",
                'memoria_mb': 2048,
                'quantizacao': 'awq',
                'configuracoes': {
                    'max_tokens': 1024,
                    'temperature': 0.3,
                    'trust_remote_code': True
                }
            }
        }
        
        return configs_padrao.get(nome_modelo)
    
    def _escolher_gpu(self, config_modelo: Dict, gpu_preferida: Optional[int]) -> Optional[int]:
        """Escolhe GPU adequada para o modelo"""
        memoria_necessaria = config_modelo['memoria_mb']
        
        # Usar GPU preferida se especificada e adequada
        if gpu_preferida is not None and self.monitor_gpu:
            if self.monitor_gpu.memoria_suficiente_para_modelo(gpu_preferida, memoria_necessaria):
                return gpu_preferida
        
        # Buscar GPU com memória suficiente
        if self.monitor_gpu:
            return self.monitor_gpu.obter_gpu_com_memoria_suficiente(memoria_necessaria)
        
        # Fallback: usar CUDA 0 se disponível
        if torch.cuda.is_available():
            return 0
        
        return None
    
    def _carregar_com_awq(self, config_modelo: Dict, gpu_id: int, **kwargs) -> GemmaLoadResult:
        """Carrega modelo usando quantização AWQ"""
        caminho_modelo = config_modelo['caminho']
        configuracoes = config_modelo.get('configuracoes', {})
        
        try:
            # Verificar se o caminho existe
            if not Path(caminho_modelo).exists():
                return GemmaLoadResult(
                    sucesso=False,
                    erro=f"Caminho do modelo não encontrado: {caminho_modelo}"
                )
            
            device = f"cuda:{gpu_id}"
            self.logger.info(f"Carregando modelo AWQ de {caminho_modelo} para {device}")
            
            # Configurações AWQ
            config_awq = self.config_awq_padrao.copy()
            config_awq.update(kwargs.get('config_awq', {}))
            
            # Carregar tokenizer primeiro (mais rápido para detectar problemas)
            tokenizer = AutoTokenizer.from_pretrained(
                caminho_modelo,
                trust_remote_code=configuracoes.get('trust_remote_code', True),
                padding_side="left"
            )
            
            # Verificar se tokenizer tem pad_token
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Carregar modelo com AWQ
            modelo = AutoAWQForCausalLM.from_quantized(
                caminho_modelo,
                device_map={"": device},
                torch_dtype=torch.float16,
                trust_remote_code=configuracoes.get('trust_remote_code', True),
                safetensors=True,
                **config_awq
            )
            
            # Otimizações pós-carregamento
            modelo.eval()
            torch.cuda.empty_cache()
            
            return GemmaLoadResult(
                sucesso=True,
                modelo=modelo,
                tokenizer=tokenizer,
                metadata={
                    "device": device,
                    "quantization": "AWQ",
                    "config_awq": config_awq,
                    "model_path": caminho_modelo
                }
            )
            
        except Exception as e:
            erro = f"Erro ao carregar modelo AWQ: {str(e)}"
            self.logger.error(erro, exc_info=True)
            return GemmaLoadResult(sucesso=False, erro=erro)
    
    def _calcular_memoria_modelo(self) -> float:
        """Calcula memória alocada pelo modelo atual"""
        if not torch.cuda.is_available() or self.gpu_alocada is None:
            return 0.0
        
        try:
            torch.cuda.synchronize()
            memoria_alocada = torch.cuda.memory_allocated(self.gpu_alocada)
            return memoria_alocada / (1024 * 1024)  # MB
        except Exception:
            return 0.0
    
    def descarregar_modelo(self, nome_modelo: Optional[str] = None) -> bool:
        """
        Descarrega modelo da memória
        
        Args:
            nome_modelo: Nome específico ou None para atual
            
        Returns:
            bool: True se descarregado com sucesso
        """
        try:
            if nome_modelo and nome_modelo != self.nome_modelo_atual:
                self.logger.warning(f"Modelo {nome_modelo} não está carregado")
                return False
            
            if self.modelo_carregado is None:
                self.logger.info("Nenhum modelo carregado para descarregar")
                return True
            
            # Atualizar registry antes de descarregar
            if self.registry and self.nome_modelo_atual:
                self.registry.atualizar_status(
                    self.nome_modelo_atual,
                    self.registry.StatusModelo.DESCARREGANDO
                )
            
            sucesso = self._descarregar_modelo_atual()
            
            # Atualizar registry após descarregamento
            if self.registry and self.nome_modelo_atual:
                self.registry.atualizar_status(
                    self.nome_modelo_atual,
                    self.registry.StatusModelo.DESCARREGADO
                )
            
            return sucesso
            
        except Exception as e:
            self.logger.error(f"Erro ao descarregar modelo: {e}", exc_info=True)
            return False
    
    def _descarregar_modelo_atual(self) -> bool:
        """Descarrega o modelo atualmente carregado"""
        try:
            modelo_nome = self.nome_modelo_atual
            
            # Limpar referências
            if self.modelo_carregado is not None:
                del self.modelo_carregado
                self.modelo_carregado = None
            
            if self.tokenizer_carregado is not None:
                del self.tokenizer_carregado
                self.tokenizer_carregado = None
            
            # Limpar cache CUDA
            if torch.cuda.is_available() and self.gpu_alocada is not None:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Forçar garbage collection
            gc.collect()
            
            # Reset variáveis de controle
            self.nome_modelo_atual = None
            self.gpu_alocada = None
            
            self.logger.info(f"Modelo {modelo_nome} descarregado com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro durante descarregamento: {e}", exc_info=True)
            return False
    
    def gerar_resposta(self, prompt: str, max_tokens: int = 512, 
                      temperature: float = 0.1, **kwargs) -> Dict[str, Any]:
        """
        Gera resposta usando o modelo carregado
        
        Args:
            prompt: Texto de entrada
            max_tokens: Máximo de tokens na resposta
            temperature: Temperatura para sampling
            **kwargs: Parâmetros adicionais de geração
            
        Returns:
            Dict com resposta e metadados
        """
        if self.modelo_carregado is None or self.tokenizer_carregado is None:
            return {
                "sucesso": False,
                "erro": "Nenhum modelo carregado",
                "resposta": ""
            }
        
        try:
            inicio = time.time()
            
            # Tokenizar entrada
            inputs = self.tokenizer_carregado(
                prompt, 
                return_tensors="pt", 
                padding=True, 
                truncation=True,
                max_length=2048
            ).to(self.modelo_carregado.device)
            
            # Parâmetros de geração
            generation_config = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer_carregado.pad_token_id,
                "eos_token_id": self.tokenizer_carregado.eos_token_id,
                "top_p": kwargs.get("top_p", 0.9),
                "top_k": kwargs.get("top_k", 50),
                "repetition_penalty": kwargs.get("repetition_penalty", 1.1)
            }
            
            # Gerar resposta
            with torch.no_grad():
                outputs = self.modelo_carregado.generate(
                    inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    **generation_config
                )
            
            # Decodificar resposta
            resposta_completa = self.tokenizer_carregado.decode(
                outputs[0], 
                skip_special_tokens=True
            )
            
            # Extrair apenas a parte nova (resposta)
            resposta = resposta_completa[len(prompt):].strip()
            
            tempo_geracao = time.time() - inicio
            tokens_gerados = len(outputs[0]) - len(inputs.input_ids[0])
            
            return {
                "sucesso": True,
                "resposta": resposta,
                "metadata": {
                    "tempo_geracao": tempo_geracao,
                    "tokens_entrada": len(inputs.input_ids[0]),
                    "tokens_gerados": tokens_gerados,
                    "tokens_por_segundo": tokens_gerados / tempo_geracao if tempo_geracao > 0 else 0,
                    "modelo": self.nome_modelo_atual
                }
            }
            
        except Exception as e:
            self.logger.error(f"Erro na geração: {e}", exc_info=True)
            return {
                "sucesso": False,
                "erro": str(e),
                "resposta": ""
            }
    
    def verificar_status(self) -> Dict[str, Any]:
        """Retorna status atual do loader"""
        return {
            "modelo_carregado": self.nome_modelo_atual,
            "gpu_alocada": self.gpu_alocada,
            "memoria_gpu_mb": self._calcular_memoria_modelo(),
            "disponivel_para_geracao": (
                self.modelo_carregado is not None and 
                self.tokenizer_carregado is not None
            ),
            "memoria_sistema": {
                "ram_usada_gb": psutil.virtual_memory().used / (1024**3),
                "ram_disponivel_gb": psutil.virtual_memory().available / (1024**3)
            }
        }
    
    def benchmark_modelo(self, num_tests: int = 5) -> Dict[str, Any]:
        """Executa benchmark básico do modelo carregado"""
        if self.modelo_carregado is None:
            return {"erro": "Nenhum modelo carregado"}
        
        prompts_teste = [
            "Analise o seguinte texto:",
            "Estruture as informações fornecidas:",
            "Extraia os pontos principais de:",
            "Organize o conteúdo abaixo:",
            "Processe a entrada recebida:"
        ]
        
        resultados = []
        
        for i in range(num_tests):
            prompt = prompts_teste[i % len(prompts_teste)]
            resultado = self.gerar_resposta(prompt, max_tokens=100)
            
            if resultado["sucesso"]:
                resultados.append(resultado["metadata"])
        
        if resultados:
            # Calcular médias
            tempo_medio = sum(r["tempo_geracao"] for r in resultados) / len(resultados)
            tokens_medio = sum(r["tokens_por_segundo"] for r in resultados) / len(resultados)
            
            return {
                "testes_executados": len(resultados),
                "tempo_medio_geracao": tempo_medio,
                "tokens_por_segundo_medio": tokens_medio,
                "modelo": self.nome_modelo_atual,
                "memoria_gpu_mb": self._calcular_memoria_modelo()
            }
        
        return {"erro": "Falha em todos os testes de benchmark"}
    
    def __del__(self):
        """Cleanup automático ao destruir o loader"""
        try:
            if self.modelo_carregado is not None:
                self._descarregar_modelo_atual()
        except:
            pass  # Ignore errors during cleanup
