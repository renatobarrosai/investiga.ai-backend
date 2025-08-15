# src/agentes/model_loaders/phi3_loader.py
import logging
import time
import torch
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import gc
import psutil
from dataclasses import dataclass
from PIL import Image
import io
import base64
import numpy as np

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig, AutoProcessor
    import torchvision.transforms as transforms
except ImportError as e:
    logging.error(f"Dependências necessárias não encontradas: {e}")
    raise

@dataclass
class Phi3LoadResult:
    """Resultado do carregamento do modelo Phi-3-Vision"""
    sucesso: bool
    modelo: Optional[Any] = None
    tokenizer: Optional[Any] = None
    processor: Optional[Any] = None  # Para processamento de imagem
    erro: Optional[str] = None
    memoria_alocada_mb: float = 0.0
    tempo_carregamento: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class Phi3Loader:
    """
    Loader especializado para modelo Phi-3-Vision multimodal.
    
    Responsável por:
    - Carregamento otimizado do modelo de visão + linguagem
    - Processamento de imagens e texto simultaneamente
    - Gerenciamento de memória para modelo grande (4GB+)
    - Integração com registry e monitoring
    - Análise multimodal com prompts especializados
    """
    
    def __init__(self, registry=None, monitor_gpu=None):
        self.registry = registry
        self.monitor_gpu = monitor_gpu
        self.logger = logging.getLogger(__name__)
        
        # Controle de instâncias carregadas
        self.modelo_carregado = None
        self.tokenizer_carregado = None
        self.processor_carregado = None
        self.nome_modelo_atual = None
        self.gpu_alocada = None
        
        # Configurações padrão para Phi-3-Vision
        self.config_padrao = {
            "torch_dtype": torch.bfloat16,
            "device_map": "auto",
            "trust_remote_code": True,
            "attn_implementation": "flash_attention_2",  # Se disponível
            "low_cpu_mem_usage": True,
            "use_safetensors": True
        }
        
        # Configurações de processamento de imagem
        self.config_imagem = {
            "max_image_size": 1024,
            "min_image_size": 224,
            "image_format": "RGB",
            "normalize": True,
            "resize_mode": "pad"  # ou "crop"
        }
        
        # Cache de configurações
        self._cache_configs = {}
        
    def carregar_modelo(self, nome_modelo: str, gpu_id: Optional[int] = None,
                       force_reload: bool = False, **kwargs) -> Phi3LoadResult:
        """
        Carrega modelo Phi-3-Vision multimodal
        
        Args:
            nome_modelo: Nome do modelo no registry
            gpu_id: ID da GPU para carregar (None = auto)
            force_reload: Força recarregamento se já carregado
            **kwargs: Configurações adicionais
            
        Returns:
            Phi3LoadResult com status do carregamento
        """
        inicio = time.time()
        
        try:
            # Verificar se já está carregado
            if (not force_reload and self.nome_modelo_atual == nome_modelo 
                and self.modelo_carregado is not None):
                self.logger.info(f"Modelo {nome_modelo} já carregado")
                return Phi3LoadResult(
                    sucesso=True,
                    modelo=self.modelo_carregado,
                    tokenizer=self.tokenizer_carregado,
                    processor=self.processor_carregado,
                    tempo_carregamento=0.0,
                    metadata={"status": "already_loaded"}
                )
            
            # Obter configurações do modelo
            config_modelo = self._obter_config_modelo(nome_modelo)
            if not config_modelo:
                return Phi3LoadResult(
                    sucesso=False,
                    erro=f"Configuração não encontrada para modelo: {nome_modelo}"
                )
            
            # Verificar recursos disponíveis (Phi-3-Vision precisa de mais memória)
            gpu_escolhida = self._escolher_gpu(config_modelo, gpu_id)
            if gpu_escolhida is None:
                return Phi3LoadResult(
                    sucesso=False,
                    erro="Nenhuma GPU disponível com memória suficiente para Phi-3-Vision"
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
            
            # Carregar modelo Phi-3-Vision
            resultado = self._carregar_phi3_vision(config_modelo, gpu_escolhida, **kwargs)
            
            if resultado.sucesso:
                # Armazenar referências
                self.modelo_carregado = resultado.modelo
                self.tokenizer_carregado = resultado.tokenizer
                self.processor_carregado = resultado.processor
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
            
            return Phi3LoadResult(
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
                    'tipo_modelo': metadados.tipo_modelo,
                    'configuracoes': metadados.configuracoes
                }
        
        # Fallback para configurações hard-coded do Phi-3-Vision
        configs_padrao = {
            "phi3-vision-classificador": {
                'nome': "phi3-vision-classificador",
                'caminho': "models/phi-3-vision-128k-instruct",
                'memoria_mb': 4096,
                'tipo_modelo': 'vision',
                'configuracoes': {
                    'max_tokens': 512,
                    'temperature': 0.1,
                    'trust_remote_code': True,
                    'max_image_size': 1024
                }
            }
        }
        
        return configs_padrao.get(nome_modelo)
    
    def _escolher_gpu(self, config_modelo: Dict, gpu_preferida: Optional[int]) -> Optional[int]:
        """Escolhe GPU adequada para Phi-3-Vision (precisa de mais memória)"""
        memoria_necessaria = config_modelo['memoria_mb'] + 512  # Margem extra para visão
        
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
    
    def _carregar_phi3_vision(self, config_modelo: Dict, gpu_id: int, **kwargs) -> Phi3LoadResult:
        """Carrega modelo Phi-3-Vision multimodal"""
        caminho_modelo = config_modelo['caminho']
        configuracoes = config_modelo.get('configuracoes', {})
        
        try:
            # Verificar se o caminho existe
            if not Path(caminho_modelo).exists():
                return Phi3LoadResult(
                    sucesso=False,
                    erro=f"Caminho do modelo não encontrado: {caminho_modelo}"
                )
            
            device = f"cuda:{gpu_id}"
            self.logger.info(f"Carregando Phi-3-Vision de {caminho_modelo} para {device}")
            
            # Configurações de carregamento otimizado
            config_carregamento = self.config_padrao.copy()
            config_carregamento.update(kwargs.get('config_modelo', {}))
            
            # Detectar se Flash Attention está disponível
            try:
                import flash_attn
                self.logger.info("Flash Attention detectado - será usado para otimização")
            except ImportError:
                self.logger.info("Flash Attention não disponível - usando atenção padrão")
                config_carregamento.pop("attn_implementation", None)
            
            # Carregar tokenizer primeiro
            tokenizer = AutoTokenizer.from_pretrained(
                caminho_modelo,
                trust_remote_code=configuracoes.get('trust_remote_code', True),
                padding_side="left"
            )
            
            # Verificar se tokenizer tem pad_token
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Carregar processor para imagens
            try:
                processor = AutoProcessor.from_pretrained(
                    caminho_modelo,
                    trust_remote_code=configuracoes.get('trust_remote_code', True)
                )
            except Exception as e:
                self.logger.warning(f"Processor não encontrado, usando tokenizer: {e}")
                processor = tokenizer
            
            # Carregar modelo principal com otimizações
            modelo = AutoModelForCausalLM.from_pretrained(
                caminho_modelo,
                device_map={"": device},
                **config_carregamento
            )
            
            # Otimizações pós-carregamento
            modelo.eval()
            
            # Configurar para modo de inferência
            if hasattr(modelo, 'config'):
                modelo.config.use_cache = True
            
            # Limpeza de memória
            torch.cuda.empty_cache()
            
            return Phi3LoadResult(
                sucesso=True,
                modelo=modelo,
                tokenizer=tokenizer,
                processor=processor,
                metadata={
                    "device": device,
                    "model_type": "phi3-vision",
                    "config_carregamento": config_carregamento,
                    "model_path": caminho_modelo,
                    "supports_vision": True,
                    "max_image_size": self.config_imagem["max_image_size"]
                }
            )
            
        except Exception as e:
            erro = f"Erro ao carregar Phi-3-Vision: {str(e)}"
            self.logger.error(erro, exc_info=True)
            return Phi3LoadResult(sucesso=False, erro=erro)
    
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
    
    def processar_imagem(self, imagem: Union[str, bytes, Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Processa imagem para uso com o modelo
        
        Args:
            imagem: Imagem em diversos formatos
            
        Returns:
            Dict com imagem processada e metadados
        """
        try:
            # Converter para PIL Image se necessário
            pil_image = self._converter_para_pil(imagem)
            
            if pil_image is None:
                return {
                    "sucesso": False,
                    "erro": "Não foi possível processar a imagem",
                    "imagem_processada": None
                }
            
            # Aplicar transformações necessárias
            imagem_processada = self._aplicar_transformacoes_imagem(pil_image)
            
            return {
                "sucesso": True,
                "imagem_processada": imagem_processada,
                "imagem_original": pil_image,
                "metadata": {
                    "tamanho_original": pil_image.size,
                    "formato": pil_image.format,
                    "modo": pil_image.mode
                }
            }
            
        except Exception as e:
            self.logger.error(f"Erro no processamento de imagem: {e}")
            return {
                "sucesso": False,
                "erro": str(e),
                "imagem_processada": None
            }
    
    def _converter_para_pil(self, imagem: Union[str, bytes, Image.Image, np.ndarray]) -> Optional[Image.Image]:
        """Converte diferentes formatos de imagem para PIL Image"""
        try:
            if isinstance(imagem, Image.Image):
                return imagem
            
            elif isinstance(imagem, str):
                # Pode ser path ou base64
                if imagem.startswith('data:image'):
                    # Base64 data URL
                    header, data = imagem.split(',', 1)
                    image_data = base64.b64decode(data)
                    return Image.open(io.BytesIO(image_data))
                elif Path(imagem).exists():
                    # Path para arquivo
                    return Image.open(imagem)
                else:
                    # Tentar como base64 puro
                    image_data = base64.b64decode(imagem)
                    return Image.open(io.BytesIO(image_data))
            
            elif isinstance(imagem, bytes):
                return Image.open(io.BytesIO(imagem))
            
            elif isinstance(imagem, np.ndarray):
                return Image.fromarray(imagem)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro na conversão de imagem: {e}")
            return None
    
    def _aplicar_transformacoes_imagem(self, imagem: Image.Image) -> Image.Image:
        """Aplica transformações necessárias para o modelo"""
        # Converter para RGB se necessário
        if imagem.mode != self.config_imagem["image_format"]:
            imagem = imagem.convert(self.config_imagem["image_format"])
        
        # Redimensionar se necessário
        max_size = self.config_imagem["max_image_size"]
        if max(imagem.size) > max_size:
            imagem.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        return imagem
    
    def gerar_resposta_multimodal(self, prompt: str, imagem: Optional[Union[str, bytes, Image.Image]] = None,
                                 max_tokens: int = 512, temperature: float = 0.1, **kwargs) -> Dict[str, Any]:
        """
        Gera resposta usando texto e opcionalmente imagem
        
        Args:
            prompt: Texto de entrada
            imagem: Imagem opcional para análise
            max_tokens: Máximo de tokens na resposta
            temperature: Temperatura para sampling
            **kwargs: Parâmetros adicionais
            
        Returns:
            Dict com resposta e metadados
        """
        if self.modelo_carregado is None:
            return {
                "sucesso": False,
                "erro": "Nenhum modelo carregado",
                "resposta": ""
            }
        
        try:
            inicio = time.time()
            
            # Processar imagem se fornecida
            if imagem is not None:
                resultado_imagem = self.processar_imagem(imagem)
                if not resultado_imagem["sucesso"]:
                    return {
                        "sucesso": False,
                        "erro": f"Erro no processamento de imagem: {resultado_imagem['erro']}",
                        "resposta": ""
                    }
                imagem_processada = resultado_imagem["imagem_processada"]
            else:
                imagem_processada = None
            
            # Preparar inputs
            if imagem_processada and self.processor_carregado:
                # Usar processor para combinar texto e imagem
                inputs = self.processor_carregado(
                    text=prompt,
                    images=imagem_processada,
                    return_tensors="pt",
                    padding=True
                ).to(self.modelo_carregado.device)
            else:
                # Apenas texto
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
                    "modelo": self.nome_modelo_atual,
                    "tem_imagem": imagem is not None,
                    "tipo_processamento": "multimodal" if imagem else "texto_apenas"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Erro na geração multimodal: {e}", exc_info=True)
            return {
                "sucesso": False,
                "erro": str(e),
                "resposta": ""
            }
    
    def analisar_imagem(self, imagem: Union[str, bytes, Image.Image], 
                       tipo_analise: str = "geral") -> Dict[str, Any]:
        """
        Análise especializada de imagem com prompts específicos
        
        Args:
            imagem: Imagem para análise
            tipo_analise: Tipo de análise ("geral", "texto", "conteudo", "classificacao")
            
        Returns:
            Dict com resultado da análise
        """
        prompts_analise = {
            "geral": "Descreva esta imagem em detalhes, incluindo objetos, pessoas, texto e contexto visível.",
            "texto": "Extraia e transcreva todo o texto visível nesta imagem, mantendo a formatação quando possível.",
            "conteudo": "Analise o conteúdo desta imagem e identifique: tipo de documento, assunto principal, elementos relevantes.",
            "classificacao": "Classifique esta imagem quanto ao tipo (foto, documento, meme, captura de tela, etc.) e conteúdo principal."
        }
        
        prompt = prompts_analise.get(tipo_analise, prompts_analise["geral"])
        
        return self.gerar_resposta_multimodal(
            prompt=prompt,
            imagem=imagem,
            max_tokens=512,
            temperature=0.1
        )
    
    def descarregar_modelo(self, nome_modelo: Optional[str] = None) -> bool:
        """Descarrega modelo da memória"""
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
                
            if self.processor_carregado is not None:
                del self.processor_carregado
                self.processor_carregado = None
            
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
            "suporte_multimodal": self.processor_carregado is not None,
            "memoria_sistema": {
                "ram_usada_gb": psutil.virtual_memory().used / (1024**3),
                "ram_disponivel_gb": psutil.virtual_memory().available / (1024**3)
            },
            "config_imagem": self.config_imagem
        }
    
    def benchmark_multimodal(self, incluir_imagens: bool = True) -> Dict[str, Any]:
        """Executa benchmark do modelo multimodal"""
        if self.modelo_carregado is None:
            return {"erro": "Nenhum modelo carregado"}
        
        resultados = {"texto_apenas": [], "multimodal": []}
        
        # Testes apenas texto
        prompts_texto = [
            "Analise o conteúdo:",
            "Classifique o tipo:",
            "Extraia informações de:",
            "Identifique elementos em:",
            "Descreva detalhadamente:"
        ]
        
        for prompt in prompts_texto:
            resultado = self.gerar_resposta_multimodal(prompt, max_tokens=100)
            if resultado["sucesso"]:
                resultados["texto_apenas"].append(resultado["metadata"])
        
        # Testes multimodais (se imagens disponíveis)
        if incluir_imagens and self.processor_carregado:
            # Criar imagem de teste simples
            imagem_teste = Image.new('RGB', (256, 256), color='white')
            
            for prompt in prompts_texto[:3]:  # Menos testes para economizar tempo
                resultado = self.gerar_resposta_multimodal(
                    prompt, 
                    imagem=imagem_teste, 
                    max_tokens=100
                )
                if resultado["sucesso"]:
                    resultados["multimodal"].append(resultado["metadata"])
        
        # Calcular estatísticas
        stats = {"modelo": self.nome_modelo_atual}
        
        for tipo, dados in resultados.items():
            if dados:
                tempos = [d["tempo_geracao"] for d in dados]
                tokens_s = [d["tokens_por_segundo"] for d in dados]
                
                stats[f"{tipo}_testes"] = len(dados)
                stats[f"{tipo}_tempo_medio"] = sum(tempos) / len(tempos)
                stats[f"{tipo}_tokens_s_medio"] = sum(tokens_s) / len(tokens_s)
        
        stats["memoria_gpu_mb"] = self._calcular_memoria_modelo()
        
        return stats
    
    def __del__(self):
        """Cleanup automático ao destruir o loader"""
        try:
            if self.modelo_carregado is not None:
                self._descarregar_modelo_atual()
        except:
            pass  # Ignore errors during cleanup
