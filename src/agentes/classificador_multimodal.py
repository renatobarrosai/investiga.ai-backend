# src/agentes/classificador_multimodal.py
import logging
import time
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from PIL import Image
import base64
import io

from .model_loaders.phi3_loader import Phi3Loader
from .prompts import gerenciador_prompts, obter_prompt, obter_config_geracao, validar_json_output

@dataclass
class ClassificacaoConteudo:
    """
    Armazena o resultado da classificação de um conteúdo, identificando
    suas características e recomendando o fluxo de processamento adequado.
    """
    tipo_principal: str  # A categoria primária do conteúdo (ex: "notícia", "meme", "depoimento").
    modalidades_detectadas: List[str]  # Mídias presentes (ex: ["texto", "imagem"]).
    necessita_processamento_visual: bool  # True se houver elementos visuais a analisar.
    necessita_processamento_audio: bool  # True se houver áudio a ser processado.
    complexidade_visual: int  # Nível de complexidade da imagem (1-10).
    recomendacao_pipeline: str  # Sugestão do pipeline mais adequado (ex: "texto_simples", "visual_ocr").
    elementos_detectados: dict  # Dicionário com elementos específicos encontrados (ex: rostos, logos).
    confianca_classificacao: float  # Confiança do modelo na classificação (0.0 a 1.0).
    
    # Novos campos para integração com modelo real
    processamento_sucesso: bool = True
    tempo_processamento: float = 0.0
    modelo_usado: Optional[str] = None
    analise_visual: Dict[str, Any] = field(default_factory=dict)
    texto_extraido: Optional[str] = None
    metadata_imagem: Dict[str, Any] = field(default_factory=dict)

class ClassificadorMultimodal:
    """
    Analisa o conteúdo de entrada para determinar sua natureza,
    identificando as diferentes mídias presentes (texto, imagem, etc.)
    e suas características, a fim de direcionar o processamento para
    os agentes especializados corretos.
    
    EVOLUÍDO PARA USAR PHI-3-VISION:
    - Integração com Phi3Loader para análise real de imagens
    - Processamento multimodal (texto + imagem)
    - OCR e extração de texto de imagens
    - Classificação inteligente baseada em prompts
    - Fallback para processamento básico
    """
    
    def __init__(self, registry=None, monitor_gpu=None, contexto_padrao="casual"):
        """
        Inicializa o classificador multimodal com Phi-3-Vision.
        
        Args:
            registry: Registry de modelos para integração
            monitor_gpu: Monitor de GPU para otimização
            contexto_padrao: Contexto padrão para prompts
        """
        self.logger = logging.getLogger(__name__)
        self.contexto_padrao = contexto_padrao
        
        # Integração com modelo real
        self.phi3_loader = Phi3Loader(registry=registry, monitor_gpu=monitor_gpu)
        self.modelo_carregado = False
        self.nome_modelo = "phi3-vision-classificador"
        
        # Controle de fallback
        self.usar_modelo_real = True
        self.tentativas_carregamento = 0
        self.max_tentativas = 3
        
        # Configurações de análise
        self.config_analise = {
            "timeout_processamento": 30.0,
            "max_image_size": 1024,
            "formatos_suportados": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"],
            "analise_detalhada": True,
            "extrair_texto": True
        }
        
        # Estatísticas
        self.stats = {
            "total_classificacoes": 0,
            "sucessos_modelo_real": 0,
            "fallbacks_basicos": 0,
            "classificacoes_com_imagem": 0,
            "tempo_medio_processamento": 0.0
        }
        
        # Cache de classificações recentes
        self._cache_classificacoes = {}
        self._cache_max_size = 100
        
        # Inicialização
        self._inicializar_modelo()
        
    def _inicializar_modelo(self):
        """Inicializa o modelo Phi-3-Vision para classificação"""
        try:
            self.logger.info("Inicializando modelo Phi-3-Vision para classificador...")
            
            resultado = self.phi3_loader.carregar_modelo(
                nome_modelo=self.nome_modelo,
                force_reload=False
            )
            
            if resultado.sucesso:
                self.modelo_carregado = True
                self.logger.info(f"Modelo {self.nome_modelo} carregado com sucesso")
                self.logger.info(f"Memória alocada: {resultado.memoria_alocada_mb:.1f}MB")
                self.logger.info(f"Suporte multimodal: {resultado.processor is not None}")
            else:
                self.logger.warning(f"Falha ao carregar modelo: {resultado.erro}")
                self.logger.info("Modo fallback ativado - classificação básica disponível")
                self.modelo_carregado = False
                
        except Exception as e:
            self.logger.error(f"Erro na inicialização do modelo: {e}")
            self.modelo_carregado = False
    
    def classificar_conteudo(self, conteudo: str, imagem: Optional[Union[Image.Image, str, bytes]] = None,
                           contexto: Optional[str] = None, analise_detalhada: bool = True) -> ClassificacaoConteudo:
        """
        Processa o conteúdo textual e, opcionalmente, uma imagem para
        classificá-los e determinar o melhor fluxo de análise.

        Args:
            conteudo (str): O conteúdo textual da entrada.
            imagem (Optional): A imagem associada, se houver.
            contexto (str, optional): Contexto específico para classificação
            analise_detalhada (bool): Se deve fazer análise detalhada da imagem

        Returns:
            ClassificacaoConteudo: Um objeto com os detalhes da classificação.
        """
        inicio = time.time()
        self.stats["total_classificacoes"] += 1
        
        if imagem is not None:
            self.stats["classificacoes_com_imagem"] += 1
        
        contexto_usado = contexto or self.contexto_padrao
        
        try:
            # Gerar chave de cache
            cache_key = self._gerar_chave_cache(conteudo, imagem is not None)
            if cache_key in self._cache_classificacoes:
                self.logger.debug("Usando classificação do cache")
                resultado = self._cache_classificacoes[cache_key]
                resultado.tempo_processamento = time.time() - inicio
                return resultado
            
            # Tentar classificação com modelo real
            if self.modelo_carregado and self.usar_modelo_real:
                resultado = self._classificar_com_modelo(conteudo, imagem, contexto_usado, analise_detalhada)
                if resultado:
                    self.stats["sucessos_modelo_real"] += 1
                    resultado.tempo_processamento = time.time() - inicio
                    self._atualizar_estatisticas_tempo(resultado.tempo_processamento)
                    
                    # Armazenar no cache
                    self._adicionar_ao_cache(cache_key, resultado)
                    return resultado
            
            # Fallback para classificação básica
            self.logger.info("Usando classificação básica (fallback)")
            resultado = self._classificar_basico(conteudo, imagem)
            self.stats["fallbacks_basicos"] += 1
            resultado.tempo_processamento = time.time() - inicio
            self._atualizar_estatisticas_tempo(resultado.tempo_processamento)
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na classificação: {e}", exc_info=True)
            # Em caso de erro total, retornar classificação mínima
            return self._criar_classificacao_erro(conteudo, imagem, str(e), time.time() - inicio)
    
    def _classificar_com_modelo(self, conteudo: str, imagem: Optional[Union[Image.Image, str, bytes]], 
                               contexto: str, analise_detalhada: bool) -> Optional[ClassificacaoConteudo]:
        """Classifica usando modelo Phi-3-Vision"""
        try:
            # Determinar tipo de análise baseado na presença de imagem
            if imagem is not None:
                # Análise multimodal
                return self._analise_multimodal(conteudo, imagem, contexto, analise_detalhada)
            else:
                # Análise apenas texto
                return self._analise_texto(conteudo, contexto)
                
        except Exception as e:
            self.logger.error(f"Erro na classificação com modelo: {e}")
            return None
    
    def _analise_multimodal(self, conteudo: str, imagem: Union[Image.Image, str, bytes],
                           contexto: str, analise_detalhada: bool) -> Optional[ClassificacaoConteudo]:
        """Análise combinada de texto e imagem"""
        try:
            # Primeiro: analisar a imagem
            resultado_imagem = self.phi3_loader.analisar_imagem(imagem, "classificacao")
            
            if not resultado_imagem["sucesso"]:
                self.logger.error(f"Falha na análise de imagem: {resultado_imagem['erro']}")
                return None
            
            descricao_imagem = resultado_imagem["resposta"]
            
            # Segundo: extrair texto da imagem se solicitado
            texto_extraido = ""
            if self.config_analise["extrair_texto"]:
                resultado_ocr = self.phi3_loader.analisar_imagem(imagem, "texto")
                if resultado_ocr["sucesso"]:
                    texto_extraido = resultado_ocr["resposta"]
            
            # Terceiro: análise combinada com prompt especializado
            prompt_classificacao = self._criar_prompt_multimodal(conteudo, descricao_imagem, texto_extraido, contexto)
            
            config_geracao = {"max_tokens": 512, "temperature": 0.1}
            resposta = self.phi3_loader.gerar_resposta_multimodal(
                prompt=prompt_classificacao,
                **config_geracao
            )
            
            if not resposta["sucesso"]:
                self.logger.error(f"Falha na geração de classificação: {resposta.get('erro')}")
                return None
            
            # Validar e extrair JSON da resposta
            validacao = validar_json_output(resposta["resposta"], "classificacao_multimodal")
            
            if not validacao["valido"]:
                self.logger.warning(f"Output de classificação inválido: {validacao['erro']}")
                # Tentar extrair informações básicas da resposta textual
                return self._extrair_classificacao_do_texto(resposta["resposta"], conteudo, imagem)
            
            dados_classificacao = validacao["dados"]
            
            # Converter para ClassificacaoConteudo
            return self._converter_para_classificacao_multimodal(
                dados_classificacao, conteudo, imagem, descricao_imagem, 
                texto_extraido, resposta["metadata"]
            )
            
        except Exception as e:
            self.logger.error(f"Erro na análise multimodal: {e}")
            return None
    
    def _analise_texto(self, conteudo: str, contexto: str) -> Optional[ClassificacaoConteudo]:
        """Análise apenas de texto"""
        try:
            # Usar prompt de classificação textual
            prompt_template = "classificacao_conteudo_texto" if contexto == "casual" else "classificacao_conteudo_formal"
            
            # Criar prompt se não existir (fallback)
            prompt = f"""Classifique o seguinte conteúdo de texto:

CONTEÚDO:
{conteudo}

Analise e retorne em JSON:
{{
    "tipo_principal": "noticia|depoimento|pergunta|afirmacao|artigo|meme|citacao",
    "modalidades_detectadas": ["texto"],
    "complexidade_textual": 1-10,
    "elementos_detectados": {{"urls": [], "mencoes": [], "hashtags": []}},
    "recomendacao_pipeline": "texto_simples|texto_complexo|investigacao_completa",
    "confianca": 0.0-1.0,
    "caracteristicas": ["formal", "informal", "tecnico", "opinativo", "factual"]
}}"""
            
            config_geracao = {"max_tokens": 256, "temperature": 0.1}
            resposta = self.phi3_loader.gerar_resposta_multimodal(
                prompt=prompt,
                **config_geracao
            )
            
            if not resposta["sucesso"]:
                return None
            
            # Validar JSON
            validacao = validar_json_output(resposta["resposta"], "classificacao_texto")
            
            if validacao["valido"]:
                dados = validacao["dados"]
                return self._converter_para_classificacao_texto(dados, conteudo, resposta["metadata"])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro na análise de texto: {e}")
            return None
    
    def _criar_prompt_multimodal(self, conteudo: str, descricao_imagem: str, 
                                texto_extraido: str, contexto: str) -> str:
        """Cria prompt especializado para análise multimodal"""
        prompt = f"""Analise este conteúdo multimodal e classifique-o:

TEXTO FORNECIDO:
{conteudo}

DESCRIÇÃO DA IMAGEM:
{descricao_imagem}

TEXTO EXTRAÍDO DA IMAGEM:
{texto_extraido or "Nenhum texto detectado"}

Classifique este conteúdo considerando TANTO o texto quanto a imagem.

Retorne em JSON:
{{
    "tipo_principal": "noticia|meme|captura_tela|documento|foto|infografico|depoimento",
    "modalidades_detectadas": ["texto", "imagem"],
    "necessita_processamento_visual": true/false,
    "complexidade_visual": 1-10,
    "elementos_detectados": {{
        "tem_texto_imagem": true/false,
        "tipo_imagem": "foto|documento|grafico|meme|captura",
        "elementos_visuais": ["texto", "graficos", "pessoas", "objetos"]
    }},
    "recomendacao_pipeline": "multimodal_completo|ocr_focus|visual_analysis|texto_simples",
    "confianca_classificacao": 0.0-1.0,
    "texto_extraido_relevante": true/false
}}"""
        
        return prompt
    
    def _converter_para_classificacao_multimodal(self, dados: Dict, conteudo: str, imagem,
                                               descricao_imagem: str, texto_extraido: str,
                                               metadata_geracao: Dict) -> ClassificacaoConteudo:
        """Converte dados JSON para ClassificacaoConteudo (multimodal)"""
        
        elementos = dados.get("elementos_detectados", {})
        
        return ClassificacaoConteudo(
            tipo_principal=dados.get("tipo_principal", "multimodal"),
            modalidades_detectadas=dados.get("modalidades_detectadas", ["texto", "imagem"]),
            necessita_processamento_visual=dados.get("necessita_processamento_visual", True),
            necessita_processamento_audio=False,  # Phi-3-Vision não processa áudio
            complexidade_visual=dados.get("complexidade_visual", 5),
            recomendacao_pipeline=dados.get("recomendacao_pipeline", "multimodal_completo"),
            elementos_detectados=elementos,
            confianca_classificacao=dados.get("confianca_classificacao", 0.8),
            
            # Campos específicos do modelo real
            processamento_sucesso=True,
            modelo_usado=self.nome_modelo,
            analise_visual={
                "descricao_imagem": descricao_imagem,
                "tipo_imagem": elementos.get("tipo_imagem", "desconhecido"),
                "elementos_visuais": elementos.get("elementos_visuais", [])
            },
            texto_extraido=texto_extraido if dados.get("texto_extraido_relevante", False) else None,
            metadata_imagem={
                "formato_detectado": "imagem_fornecida",
                "processamento_sucesso": True,
                "tempo_geracao": metadata_geracao.get("tempo_geracao", 0),
                "modelo": self.nome_modelo
            }
        )
    
    def _converter_para_classificacao_texto(self, dados: Dict, conteudo: str, 
                                          metadata_geracao: Dict) -> ClassificacaoConteudo:
        """Converte dados JSON para ClassificacaoConteudo (apenas texto)"""
        
        return ClassificacaoConteudo(
            tipo_principal=dados.get("tipo_principal", "texto"),
            modalidades_detectadas=["texto"],
            necessita_processamento_visual=False,
            necessita_processamento_audio=False,
            complexidade_visual=1,
            recomendacao_pipeline=dados.get("recomendacao_pipeline", "texto_simples"),
            elementos_detectados=dados.get("elementos_detectados", {}),
            confianca_classificacao=dados.get("confianca", 0.7),
            
            # Campos específicos do modelo real
            processamento_sucesso=True,
            modelo_usado=self.nome_modelo,
            analise_visual={},
            texto_extraido=None,
            metadata_imagem={}
        )
    
    def _extrair_classificacao_do_texto(self, resposta_texto: str, conteudo: str, 
                                      imagem) -> ClassificacaoConteudo:
        """Extrai classificação básica de resposta textual quando JSON falha"""
        # Análise simples de palavras-chave na resposta
        resposta_lower = resposta_texto.lower()
        
        # Detectar tipo principal
        if any(palavra in resposta_lower for palavra in ["meme", "humor", "piada"]):
            tipo_principal = "meme"
        elif any(palavra in resposta_lower for palavra in ["documento", "texto", "escrito"]):
            tipo_principal = "documento"
        elif any(palavra in resposta_lower for palavra in ["foto", "fotografia", "imagem"]):
            tipo_principal = "foto"
        elif any(palavra in resposta_lower for palavra in ["captura", "screenshot", "tela"]):
            tipo_principal = "captura_tela"
        else:
            tipo_principal = "multimodal"
        
        # Detectar complexidade
        complexidade = 5
        if any(palavra in resposta_lower for palavra in ["simples", "básico", "fácil"]):
            complexidade = 3
        elif any(palavra in resposta_lower for palavra in ["complexo", "detalhado", "difícil"]):
            complexidade = 8
        
        return ClassificacaoConteudo(
            tipo_principal=tipo_principal,
            modalidades_detectadas=["texto", "imagem"] if imagem else ["texto"],
            necessita_processamento_visual=imagem is not None,
            necessita_processamento_audio=False,
            complexidade_visual=complexidade,
            recomendacao_pipeline="multimodal_completo" if imagem else "texto_simples",
            elementos_detectados={"analise_textual": True},
            confianca_classificacao=0.6,  # Menor confiança para fallback
            
            processamento_sucesso=True,
            modelo_usado=self.nome_modelo,
            analise_visual={"descricao_imagem": resposta_texto[:200]} if imagem else {},
            texto_extraido=None
        )
    
    def _classificar_basico(self, conteudo: str, imagem: Optional[Union[Image.Image, str, bytes]]) -> ClassificacaoConteudo:
        """
        Classificação básica (fallback) sem modelo de IA.
        Usa heurísticas simples para manter funcionalidade mínima.
        """
        # Análise básica do texto
        tipo_principal = self._detectar_tipo_basico_texto(conteudo)
        
        # Análise da imagem se presente
        modalidades = ["texto"]
        necessita_visual = False
        complexidade_visual = 1
        
        if imagem is not None:
            modalidades.append("imagem")
            necessita_visual = True
            complexidade_visual = 5  # Assume complexidade média
        
        # Determinar pipeline recomendado
        if imagem is not None:
            pipeline = "multimodal_completo"
        elif len(conteudo) > 500:
            pipeline = "texto_complexo"
        else:
            pipeline = "texto_simples"
        
        return ClassificacaoConteudo(
            tipo_principal=tipo_principal,
            modalidades_detectadas=modalidades,
            necessita_processamento_visual=necessita_visual,
            necessita_processamento_audio=False,
            complexidade_visual=complexidade_visual,
            recomendacao_pipeline=pipeline,
            elementos_detectados={
                "metodo_classificacao": "heuristico_basico",
                "tem_imagem": imagem is not None
            },
            confianca_classificacao=0.5,  # Confiança baixa para método básico
            
            processamento_sucesso=True,
            modelo_usado=None,
            analise_visual={},
            texto_extraido=None
        )
    
    def _detectar_tipo_basico_texto(self, conteudo: str) -> str:
        """Detecta tipo de conteúdo usando heurísticas simples"""
        conteudo_lower = conteudo.lower()
        
        # Palavras-chave para diferentes tipos
        if any(palavra in conteudo_lower for palavra in ["breaking", "notícia", "jornal", "reportagem"]):
            return "noticia"
        elif any(palavra in conteudo_lower for palavra in ["kkkk", "hahaha", "meme", "engraçado"]):
            return "meme"
        elif any(palavra in conteudo_lower for palavra in ["eu vi", "eu estava", "presenciei"]):
            return "depoimento"
        elif any(palavra in conteudo_lower for palavra in ["segundo", "de acordo com", "conforme"]):
            return "citacao"
        elif "?" in conteudo:
            return "pergunta"
        elif len(conteudo) > 500:
            return "artigo"
        else:
            return "afirmacao"
    
    def _gerar_chave_cache(self, conteudo: str, tem_imagem: bool) -> str:
        """Gera chave para cache de classificações"""
        import hashlib
        
        # Hash do conteúdo + flag de imagem
        conteudo_para_hash = f"{conteudo}_{tem_imagem}"
        return hashlib.md5(conteudo_para_hash.encode()).hexdigest()[:16]
    
    def _adicionar_ao_cache(self, chave: str, classificacao: ClassificacaoConteudo):
        """Adiciona classificação ao cache"""
        # Limitar tamanho do cache
        if len(self._cache_classificacoes) >= self._cache_max_size:
            # Remover entrada mais antiga
            oldest_key = next(iter(self._cache_classificacoes))
            del self._cache_classificacoes[oldest_key]
        
        self._cache_classificacoes[chave] = classificacao
    
    def _criar_classificacao_erro(self, conteudo: str, imagem, erro: str, tempo: float) -> ClassificacaoConteudo:
        """Cria classificação mínima em caso de erro total"""
        return ClassificacaoConteudo(
            tipo_principal="erro",
            modalidades_detectadas=["texto"] + (["imagem"] if imagem else []),
            necessita_processamento_visual=imagem is not None,
            necessita_processamento_audio=False,
            complexidade_visual=1,
            recomendacao_pipeline="erro_recovery",
            elementos_detectados={"erro": erro},
            confianca_classificacao=0.0,
            
            processamento_sucesso=False,
            tempo_processamento=tempo,
            modelo_usado=None,
            analise_visual={},
            texto_extraido=None
        )
    
    def _atualizar_estatisticas_tempo(self, tempo: float):
        """Atualiza estatísticas de tempo de processamento"""
        if self.stats["tempo_medio_processamento"] == 0:
            self.stats["tempo_medio_processamento"] = tempo
        else:
            # Média móvel simples
            self.stats["tempo_medio_processamento"] = (
                self.stats["tempo_medio_processamento"] * 0.8 + tempo * 0.2
            )
    
    def processar_imagem(self, imagem: Union[Image.Image, str, bytes], 
                        tipo_analise: str = "geral") -> Dict[str, Any]:
        """
        Processa imagem usando Phi-3-Vision
        
        Args:
            imagem: Imagem para processamento
            tipo_analise: Tipo de análise ("geral", "texto", "classificacao")
            
        Returns:
            Dict com resultado do processamento
        """
        if not self.modelo_carregado:
            return {
                "sucesso": False,
                "erro": "Modelo não carregado",
                "resultado": None
            }
        
        try:
            resultado = self.phi3_loader.analisar_imagem(imagem, tipo_analise)
            return {
                "sucesso": resultado["sucesso"],
                "erro": resultado.get("erro"),
                "resultado": resultado.get("resposta"),
                "metadata": resultado.get("metadata", {})
            }
            
        except Exception as e:
            self.logger.error(f"Erro no processamento de imagem: {e}")
            return {
                "sucesso": False,
                "erro": str(e),
                "resultado": None
            }
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do classificador"""
        total = self.stats["total_classificacoes"]
        
        return {
            "modelo_carregado": self.modelo_carregado,
            "nome_modelo": self.nome_modelo,
            "total_classificacoes": total,
            "sucessos_modelo_real": self.stats["sucessos_modelo_real"],
            "fallbacks_basicos": self.stats["fallbacks_basicos"],
            "classificacoes_com_imagem": self.stats["classificacoes_com_imagem"],
            "tempo_medio_processamento": self.stats["tempo_medio_processamento"],
            "taxa_sucesso_modelo": (
                (self.stats["sucessos_modelo_real"] / total * 100) 
                if total > 0 else 0
            ),
            "cache_size": len(self._cache_classificacoes),
            "status_loader": self.phi3_loader.verificar_status() if self.phi3_loader else None
        }
    
    def limpar_cache(self):
        """Limpa cache de classificações"""
        self._cache_classificacoes.clear()
        self.logger.info("Cache de classificações limpo")
    
    def recarregar_modelo(self) -> bool:
        """Força recarregamento do modelo"""
        try:
            resultado = self.phi3_loader.carregar_modelo(
                nome_modelo=self.nome_modelo,
                force_reload=True
            )
            
            self.modelo_carregado = resultado.sucesso
            
            if resultado.sucesso:
                self.logger.info("Modelo recarregado com sucesso")
            else:
                self.logger.error(f"Falha no recarregamento: {resultado.erro}")
            
            return resultado.sucesso
            
        except Exception as e:
            self.logger.error(f"Erro no recarregamento: {e}")
            self.modelo_carregado = False
            return False
    
    def descarregar_modelo(self) -> bool:
        """Descarrega modelo para liberar memória"""
        try:
            sucesso = self.phi3_loader.descarregar_modelo(self.nome_modelo)
            self.modelo_carregado = False
            
            if sucesso:
                self.logger.info("Modelo descarregado com sucesso")
            else:
                self.logger.warning("Falha no descarregamento do modelo")
            
            return sucesso
            
        except Exception as e:
            self.logger.error(f"Erro no descarregamento: {e}")
            return False
    
    def benchmark_classificacao(self, incluir_imagens: bool = True) -> Dict[str, Any]:
        """Executa benchmark do classificador"""
        if not self.modelo_carregado:
            return {"erro": "Modelo não carregado para benchmark"}
        
        entradas_teste = [
            ("Este é um texto de notícia sobre economia.", None),
            ("Olha que meme engraçado kkkk", None),
            ("Eu vi o presidente ontem na rua.", None),
            ("Segundo fontes, houve um aumento nas vendas.", None),
            ("Este documento contém informações importantes.", None)
        ]
        
        resultados = []
        inicio_total = time.time()
        
        for i, (texto, imagem) in enumerate(entradas_teste):
            inicio = time.time()
            resultado = self.classificar_conteudo(texto, imagem, analise_detalhada=False)
            fim = time.time()
            
            resultados.append({
                "sucesso": resultado.processamento_sucesso,
                "tempo": fim - inicio,
                "tipo_detectado": resultado.tipo_principal,
                "confianca": resultado.confianca_classificacao,
                "modelo_usado": resultado.modelo_usado,
                "teve_imagem": imagem is not None
            })
        
        fim_total = time.time()
        
        # Calcular estatísticas
        sucessos = [r for r in resultados if r["sucesso"]]
        tempos = [r["tempo"] for r in resultados]
        
        return {
            "testes_executados": len(entradas_teste),
            "testes_bem_sucedidos": len(sucessos),
            "taxa_sucesso": len(sucessos) / len(entradas_teste) * 100,
            "tempo_total": fim_total - inicio_total,
            "tempo_medio_por_teste": sum(tempos) / len(tempos),
            "tempo_minimo": min(tempos),
            "tempo_maximo": max(tempos),
            "tipos_detectados": list(set(r["tipo_detectado"] for r in sucessos)),
            "confianca_media": sum(r["confianca"] for r in sucessos) / len(sucessos) if sucessos else 0,
            "modelo_usado": self.nome_modelo,
            "memoria_gpu_mb": self.phi3_loader._calcular_memoria_modelo() if self.phi3_loader else 0
        }
