# src/agentes/coordenador_agentes.py
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from fastapi import UploadFile

try:
    from PIL import Image
except ImportError:
    Image = None

# Importação de componentes das fases de análise inicial (2-3)
from .recepcionista import ProcessadorRecepcionista
from .classificador_multimodal import ClassificadorMultimodal  
from .filtro_seguranca import FiltroSeguranca
from .deconstrutor import DeconstructorComplexo
from .cache_semantico import CacheSemantico
from .circuit_breakers import GerenciadorCircuitBreakers

# Importação de componentes das fases de investigação e síntese (4-5)
import sys
sys.path.append('src')
from investigacao.coordenador_investigacao import CoordenadorInvestigacao
from sintese.coordenador_sintese import CoordenadorSintese

class CoordenadorAgentes:
    """
    Orquestrador central do sistema de checagem de fatos.
    Este coordenador integra e gerencia o fluxo de trabalho completo,
    passando por todas as etapas: da análise inicial e classificação até a
    investigação aprofundada e a síntese final do veredito.
    
    MODIFICAÇÕES PARA FRONTEND:
    - Suporte a callbacks para WebSocket updates em tempo real
    - Processamento de uploads de arquivos (imagem, áudio, vídeo)
    - Integração com sistema de notificações para frontend
    """
    
    def __init__(self):
        """
        Inicializa o coordenador, instanciando todos os componentes
        necessários para o funcionamento do pipeline de checagem.
        """
        self.logger = logging.getLogger(__name__)
        
        # Componentes fundamentais de gerenciamento
        self.agentes = {}
        self.cache = CacheSemantico()
        self.circuit_manager = GerenciadorCircuitBreakers()
        
        # Coordenadores para as fases especializadas
        self.investigador = CoordenadorInvestigacao()
        self.sintetizador_coordenador = CoordenadorSintese()
        
        # Inicializa os agentes individuais
        self._inicializar_agentes()
        
    def _inicializar_agentes(self):
        """
        Instancia e carrega todos os agentes especializados que compõem
        a primeira fase de análise do conteúdo.
        """
        try:
            self.agentes['recepcionista'] = ProcessadorRecepcionista()
            self.agentes['classificador'] = ClassificadorMultimodal()
            self.agentes['filtro_seguranca'] = FiltroSeguranca()
            self.agentes['deconstrutor'] = DeconstructorComplexo()
            
            self.logger.info("Todos os agentes foram inicializados com sucesso.")
        except Exception as e:
            self.logger.error(f"Falha durante a inicialização dos agentes: {e}", exc_info=True)

    # =============================================================================
    # NOVOS MÉTODOS PARA INTEGRAÇÃO FRONTEND
    # =============================================================================

    async def processar_arquivo(self, arquivo: UploadFile, tipo: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Processa arquivos de diferentes tipos (imagem, áudio, vídeo)
        
        Args:
            arquivo: Arquivo enviado pelo frontend
            tipo: MIME type do arquivo
            callback: Função para enviar updates via WebSocket
            
        Returns:
            Dict com resultado do processamento
        """
        if callback:
            await callback("upload", f"Processando arquivo: {arquivo.filename}")
        
        try:
            if tipo.startswith('image/'):
                # Usa Phi-3-vision via classificador
                if callback:
                    await callback("classificador", "Extraindo texto da imagem...")
                
                # Lê o arquivo de imagem
                conteudo_arquivo = await arquivo.read()
                
                # Processa a imagem para extrair texto
                resultado_classificacao = await self.agentes['classificador'].processar_imagem(conteudo_arquivo)
                conteudo_extraido = resultado_classificacao.get('conteudo_extraido', '')
                
                if callback:
                    await callback("recepcionista", "Processando conteúdo extraído da imagem...")
                
                # Processa o conteúdo extraído
                return await self.processar_completo_com_sintese(
                    conteudo_extraido, 
                    imagem=conteudo_arquivo,
                    callback=callback
                )
            
            elif tipo.startswith('audio/'):
                # Para quando implementar distil-whisper
                if callback:
                    await callback("transcricao", "Transcrevendo áudio...")
                
                texto_transcrito = await self.processar_audio(arquivo)
                
                if callback:
                    await callback("recepcionista", "Processando transcrição do áudio...")
                
                return await self.processar_completo_com_sintese(
                    texto_transcrito,
                    callback=callback
                )
            
            elif tipo.startswith('video/'):
                # Para processamento futuro de vídeo
                if callback:
                    await callback("video", "Extraindo áudio e frames do vídeo...")
                
                resultado_video = await self.processar_video(arquivo)
                
                return await self.processar_completo_com_sintese(
                    resultado_video.get('transcricao', ''),
                    imagem=resultado_video.get('frame_chave'),
                    callback=callback
                )
            
            else:
                raise ValueError(f"Tipo de arquivo não suportado: {tipo}")
                
        except Exception as e:
            if callback:
                await callback("erro", f"Erro ao processar arquivo: {str(e)}")
            raise

    async def processar_audio(self, arquivo: UploadFile) -> str:
        """
        Placeholder para transcrição de áudio usando distil-whisper
        
        TODO: Implementar integração com distil-whisper
        """
        self.logger.warning("Transcrição de áudio ainda não implementada")
        return f"[TRANSCRIÇÃO PENDENTE] Arquivo de áudio: {arquivo.filename}"

    async def processar_video(self, arquivo: UploadFile) -> Dict[str, Any]:
        """
        Placeholder para processamento de vídeo
        
        TODO: Implementar extração de frames + transcrição de áudio
        """
        self.logger.warning("Processamento de vídeo ainda não implementado")
        return {
            'transcricao': f"[TRANSCRIÇÃO PENDENTE] Arquivo de vídeo: {arquivo.filename}",
            'frame_chave': None
        }

    # =============================================================================
    # PIPELINE DE ANÁLISE INICIAL (FASES 2-3) - MODIFICADO PARA CALLBACKS
    # =============================================================================
    
    def processar_entrada_completa(self, conteudo: str, imagem=None, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Executa o pipeline de análise inicial: estruturação, classificação,
        verificação de segurança e extração de alegações.

        Args:
            conteudo (str): O texto a ser analisado.
            imagem (optional): Uma imagem associada ao conteúdo.
            callback (optional): Função para enviar updates via WebSocket.

        Returns:
            Dict[str, Any]: Um dicionário com os resultados de cada etapa.
        """
        
        resultado = {
            'timestamp': time.time(),
            'entrada_original': conteudo,
            'tem_imagem': imagem is not None,
            'fase_atual': 'processamento_basico'
        }
        
        try:
            # Etapa 1: Estruturação da entrada pelo Recepcionista
            if callback:
                asyncio.create_task(callback("recepcionista", "Organizando informações..."))
            
            entrada_estruturada = self.circuit_manager.executar_com_protecao(
                'recepcionista', 
                self.agentes['recepcionista'].processar_entrada, 
                conteudo
            )
            resultado['entrada_estruturada'] = entrada_estruturada
            
            # Etapa 2: Classificação do tipo de conteúdo
            if callback:
                asyncio.create_task(callback("classificador", "Analisando tipo de conteúdo..."))
            
            classificacao = self.circuit_manager.executar_com_protecao(
                'classificador', 
                self.agentes['classificador'].classificar_conteudo, 
                conteudo, imagem
            )
            resultado['classificacao'] = classificacao
            
            # Etapa 3: Análise de segurança
            if callback:
                asyncio.create_task(callback("seguranca", "Verificando segurança..."))
            
            avaliacao_seguranca = self.circuit_manager.executar_com_protecao(
                'filtro_seguranca', 
                self.agentes['filtro_seguranca'].avaliar_seguranca,
                conteudo, entrada_estruturada.urls_encontradas
            )
            resultado['seguranca'] = avaliacao_seguranca
            
            # Etapa 4: Decisão de bloqueio com base na segurança
            if avaliacao_seguranca.bloqueio_necessario:
                if callback:
                    asyncio.create_task(callback("bloqueado", f"Conteúdo bloqueado: {avaliacao_seguranca.recomendacao}"))
                
                resultado['status'] = 'bloqueado'
                resultado['motivo_bloqueio'] = avaliacao_seguranca.recomendacao
                resultado['pode_prosseguir'] = False
                return resultado
                
            # Etapa 5: Verificação no cache semântico
            if callback:
                asyncio.create_task(callback("cache", "Verificando cache semântico..."))
            
            alegacoes_cache = self.cache.buscar_similar(conteudo)
            if alegacoes_cache:
                resultado['alegacoes'] = alegacoes_cache
                resultado['fonte_alegacoes'] = 'cache_semantico'
                resultado['cache_hit'] = True
                self.logger.info("Cache hit: alegações recuperadas do cache semântico.")
            else:
                # Etapa 6: Extração de alegações
                if callback:
                    asyncio.create_task(callback("deconstrutor", "Extraindo alegações..."))
                
                alegacoes = self.circuit_manager.executar_com_protecao(
                    'deconstrutor', 
                    self.agentes['deconstrutor'].extrair_alegacoes, 
                    conteudo
                )
                resultado['alegacoes'] = alegacoes
                resultado['fonte_alegacoes'] = 'deconstrutor_reasoning'
                resultado['cache_hit'] = False
                
                # Armazena as novas alegações no cache
                self.cache.armazenar(conteudo, alegacoes)
                self.logger.info(f"Extraídas {len(alegacoes)} novas alegações.")
                
            # Etapa 7: Determinação dos próximos passos
            resultado['proximos_passos'] = self._determinar_pipeline_completo(
                classificacao, alegacoes_cache is not None
            )
            resultado['status'] = 'alegacoes_extraidas'
            resultado['pode_prosseguir'] = True
            
            self.logger.info(f"Pipeline de análise inicial concluído com status: {resultado['status']}")
                
        except Exception as e:
            if callback:
                asyncio.create_task(callback("erro", f"Erro no processamento: {str(e)}"))
            
            resultado['status'] = 'erro_pipeline_basico'
            resultado['erro'] = str(e)
            resultado['pode_prosseguir'] = False
            self.logger.error(f"Erro durante a execução do pipeline básico: {e}", exc_info=True)
            
        # Inclui o status dos circuit breakers no resultado
        resultado['circuit_breakers'] = self.circuit_manager.obter_status_global()
        
        return resultado
        
    # =============================================================================
    # PIPELINE DE INVESTIGAÇÃO WEB (FASE 4) - MODIFICADO PARA CALLBACKS
    # =============================================================================
    
    async def processar_entrada_completa_com_web(self, conteudo: str, imagem=None, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Executa o pipeline completo, incluindo a fase de investigação web.

        Args:
            conteudo (str): O texto a ser analisado.
            imagem (optional): Uma imagem associada ao conteúdo.
            callback (optional): Função para enviar updates via WebSocket.

        Returns:
            Dict[str, Any]: O resultado consolidado, incluindo as evidências da web.
        """
        
        # Executa as fases anteriores
        resultado = self.processar_entrada_completa(conteudo, imagem, callback)
        resultado['fase_atual'] = 'investigacao_web'
        
        if resultado.get('pode_prosseguir'):
            try:
                # Inicia a investigação para cada alegação extraída
                if callback:
                    await callback("investigacao", "Iniciando investigação web...")
                
                alegacoes = resultado.get('alegacoes', [])
                investigacoes = []
                
                self.logger.info(f"Iniciando investigação web para {len(alegacoes)} alegações.")
                
                for i, alegacao in enumerate(alegacoes[:3]):  # Limita a 3 para eficiência
                    try:
                        if callback:
                            await callback("investigacao", f"Investigando alegação {i+1}/{min(len(alegacoes), 3)}...")
                        
                        texto_alegacao = getattr(alegacao, 'texto_original', str(alegacao))
                            
                        inv_resultado = await self.investigador.investigar_alegacao(texto_alegacao)
                        investigacoes.append(inv_resultado)
                        
                        self.logger.info(f"Investigação {i+1}/{len(alegacoes)} concluída.")
                        
                    except Exception as e:
                        self.logger.error(f"Erro ao investigar a alegação {i+1}: {e}", exc_info=True)
                        
                resultado['investigacoes_web'] = investigacoes
                resultado['total_investigacoes'] = len(investigacoes)
                resultado['status'] = 'investigacao_web_completa'
                
                if callback:
                    await callback("investigacao", f"Investigação concluída. {len(investigacoes)} fontes analisadas.")
                
            except Exception as e:
                if callback:
                    await callback("erro", f"Erro na investigação web: {str(e)}")
                
                resultado['status'] = 'erro_investigacao_web'
                resultado['erro_investigacao'] = str(e)
                self.logger.error(f"Erro na fase de investigação web: {e}", exc_info=True)
                
        return resultado
        
    # =============================================================================
    # PIPELINE COMPLETO COM SÍNTESE (FASE 5) - MODIFICADO PARA CALLBACKS
    # =============================================================================
    
    async def processar_completo_com_sintese(
        self, 
        conteudo: str, 
        imagem=None, 
        callback: Optional[Callable] = None,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orquestra o pipeline completo: desde a análise inicial até a síntese final.

        Args:
            conteudo (str): O texto a ser analisado.
            imagem (optional): Uma imagem associada ao conteúdo.
            callback (optional): Função para enviar updates via WebSocket.
            client_id (optional): ID do cliente para WebSocket.

        Returns:
            Dict[str, Any]: O resultado final da checagem de fatos.
        """
        
        # Executa as fases anteriores, incluindo a investigação
        resultado = await self.processar_entrada_completa_com_web(conteudo, imagem, callback)
        resultado['fase_atual'] = 'sintese_final'
        resultado['client_id'] = client_id
        
        if resultado.get('investigacoes_web'):
            try:
                # Executa a síntese das evidências coletadas
                if callback:
                    await callback("sintese", "Analisando evidências coletadas...")
                
                alegacoes = resultado.get('alegacoes', [])
                investigacoes = resultado.get('investigacoes_web', [])
                
                self.logger.info("Iniciando a síntese das evidências coletadas.")
                
                sintese_resultado = await self.sintetizador_coordenador.processar_sintese_completa(
                    alegacoes, investigacoes, conteudo
                )
                
                resultado['sintese'] = sintese_resultado
                resultado['status_final'] = 'fact_check_completo'
                
                # Extrai o veredito principal para fácil acesso
                if 'conclusao_sintese' in sintese_resultado:
                    resultado['veredicto_final'] = sintese_resultado['conclusao_sintese']['veredicto']
                    resultado['confianca_final'] = sintese_resultado['conclusao_sintese']['confianca']
                    
                if callback:
                    await callback("apresentacao", "Preparando relatório final...")
                
                # Formata resultado para o frontend
                resultado['frontend_data'] = self._formatar_para_frontend(resultado)
                
                if callback:
                    await callback("concluido", f"Verificação concluída: {resultado.get('veredicto_final', 'N/A')}")
                    
                self.logger.info(f"Checagem de fatos completa. Veredicto: {resultado.get('veredicto_final', 'N/A')}")
                
            except Exception as e:
                if callback:
                    await callback("erro", f"Erro na síntese: {str(e)}")
                
                resultado['status_final'] = 'erro_sintese'
                resultado['erro_sintese'] = str(e)
                self.logger.error(f"Erro na fase de síntese: {e}", exc_info=True)
        else:
            resultado['status_final'] = 'sem_investigacao_para_sintese'
            if callback:
                await callback("aviso", "Síntese não realizada - sem investigações suficientes")
            
        return resultado

    def _formatar_para_frontend(self, resultado: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado para consumo do frontend
        
        Args:
            resultado: Resultado completo do processamento
            
        Returns:
            Dict formatado para o frontend
        """
        try:
            sintese = resultado.get('sintese', {})
            conclusao = sintese.get('conclusao_sintese', {})
            investigacoes = resultado.get('investigacoes_web', [])
            
            return {
                "conclusion": conclusao.get('veredicto', 'INCONCLUSIVO'),
                "confidence": conclusao.get('confianca', 0.0),
                "reasoning": conclusao.get('reasoning', 'Análise não disponível'),
                "summary": conclusao.get('resumo', ''),
                "verdict_color": self._get_verdict_color(conclusao.get('veredicto', '')),
                "sources": [
                    {
                        "name": fonte.get('nome', 'Fonte desconhecida'),
                        "url": fonte.get('url', '#'),
                        "authority": fonte.get('authority', 0.5),
                        "excerpt": fonte.get('excerpt', ''),
                        "credibility_score": fonte.get('credibility_score', 0.5)
                    } for fonte in investigacoes[:5]  # Limita a 5 fontes principais
                ],
                "metadata": {
                    "processing_time": time.time() - resultado.get('timestamp', time.time()),
                    "total_sources": len(investigacoes),
                    "timestamp": time.time(),
                    "pipeline_used": "completo_com_sintese"
                },
                "stages_completed": [
                    "recepcionista", "classificador", "seguranca", 
                    "deconstrutor", "investigacao", "sintese", "apresentacao"
                ]
            }
        except Exception as e:
            self.logger.error(f"Erro ao formatar para frontend: {e}")
            return {
                "conclusion": "ERRO",
                "confidence": 0.0,
                "reasoning": f"Erro ao processar resultado: {str(e)}",
                "sources": [],
                "metadata": {"error": str(e)}
            }

    def _get_verdict_color(self, veredicto: str) -> str:
        """
        Retorna cor para o frontend baseada no veredicto
        """
        colors = {
            "VERDADEIRO": "green",
            "FALSO": "red", 
            "PARCIALMENTE_VERDADEIRO": "orange",
            "INCONCLUSIVO": "gray",
            "INSUFICIENTE": "gray",
            "ERRO": "red"
        }
        return colors.get(veredicto.upper(), "gray")
        
    # =============================================================================
    # PIPELINE SIMPLIFICADO (PARA TESTES E ANÁLISES RÁPIDAS)
    # =============================================================================
    
    def processar_rapido(self, conteudo: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Executa um processamento rápido, sem investigação web ou síntese complexa,
        ideal para uma primeira avaliação.

        Args:
            conteudo (str): O texto a ser analisado.
            callback (optional): Função para enviar updates via WebSocket.

        Returns:
            Dict[str, Any]: Um resultado preliminar com um veredito rápido.
        """
        
        if callback:
            asyncio.create_task(callback("rapido", "Iniciando análise rápida..."))
        
        resultado_basico = self.processar_entrada_completa(conteudo, callback=callback)
        
        # Gera uma conclusão simples baseada nos resultados iniciais
        if resultado_basico.get('seguranca', {}).get('seguro', True):
            if resultado_basico.get('cache_hit'):
                veredicto = "INFORMACAO_CONHECIDA"
            else:
                veredicto = "REQUER_INVESTIGACAO"
        else:
            veredicto = "POTENCIALMENTE_FALSO"
            
        resultado_basico.update({
            'veredicto_rapido': veredicto,
            'processamento_tipo': 'rapido',
            'recomendacao': self._gerar_recomendacao_rapida(veredicto)
        })
        
        if callback:
            asyncio.create_task(callback("concluido", f"Análise rápida: {veredicto}"))
        
        return resultado_basico
        
    # =============================================================================
    # MÉTODOS AUXILIARES (INALTERADOS)
    # =============================================================================
        
    def _determinar_pipeline_completo(self, classificacao, cache_hit: bool) -> Dict[str, bool]:
        """
        Define quais etapas adicionais são necessárias com base na
        classificação inicial e no resultado do cache.

        Args:
            classificacao: O resultado do agente classificador.
            cache_hit (bool): Se houve um acerto no cache semântico.

        Returns:
            Dict[str, bool]: Um dicionário de flags para controlar o fluxo.
        """
        return {
            "usar_investigacao_web": True,
            "usar_processamento_visual": classificacao.necessita_processamento_visual,
            "usar_processamento_audio": getattr(classificacao, 'necessita_processamento_audio', False),
            "prioridade_alta": classificacao.confianca_classificacao < 0.7,
            "pipeline_recomendado": classificacao.recomendacao_pipeline,
            "pular_validacao_adicional": cache_hit,
            "reasoning_complexo_necessario": getattr(classificacao, 'complexidade_visual', 1) >= 5
        }
        
    def _gerar_recomendacao_rapida(self, veredicto: str) -> str:
        """
        Gera uma recomendação textual para o resultado do processamento rápido.
        """
        recomendacoes = {
            "INFORMACAO_CONHECIDA": "Informação já verificada anteriormente.",
            "REQUER_INVESTIGACAO": "Recomenda-se uma investigação completa para um veredito final.",
            "POTENCIALMENTE_FALSO": "Conteúdo contém elementos suspeitos. Não compartilhe."
        }
        return recomendacoes.get(veredicto, "Análise inconclusiva.")
        
    # =============================================================================
    # MÉTODOS DE STATUS E CONTROLE (INALTERADOS)
    # =============================================================================
        
    def obter_status_completo(self) -> Dict[str, Any]:
        """
        Retorna um status consolidado de todos os componentes do sistema.
        """
        return {
            "agentes_carregados": list(self.agentes.keys()),
            "circuit_breakers": self.circuit_manager.obter_status_global(),
            "cache_stats": {
                "entradas_cache": len(self.cache.cache),
                "threshold_similaridade": self.cache.threshold_similaridade
            },
            "agentes_disponiveis": {
                nome: getattr(agente, 'carregado', True)
                for nome, agente in self.agentes.items()
            },
            "componentes_especializados": {
                "investigador_web": self.investigador is not None,
                "sintetizador": self.sintetizador_coordenador is not None
            },
            "timestamp": time.time(),
            "versao_sistema": "1.0.0",
            "suporte_frontend": {
                "websocket_callbacks": True,
                "upload_arquivos": True,
                "processamento_multimodal": True
            }
        }
        
    def resetar_circuit_breaker(self, nome_agente: str) -> bool:
        """
        Reseta manualmente o circuit breaker de um agente específico.
        """
        return self.circuit_manager.resetar_breaker(nome_agente)
        
    def limpar_cache(self) -> bool:
        """
        Limpa o cache semântico de alegações.
        """
        try:
            self.cache.limpar_cache()
            self.logger.info("Cache semântico foi limpo com sucesso.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao tentar limpar o cache: {e}", exc_info=True)
            return False
            
    def estatisticas_processamento(self) -> Dict[str, Any]:
        """
        Fornece estatísticas detalhadas sobre o uso e o desempenho do sistema.
        """
        total_cache = len(self.cache.cache)
        # Esta é uma forma segura de calcular o uso, mesmo que a estrutura mude.
        uso_total = sum(getattr(entrada, 'uso_count', 0) for entrada in self.cache.cache.values())
        
        return {
            "total_processamentos_cache": total_cache,
            "uso_medio_cache": (uso_total / total_cache) if total_cache > 0 else 0,
            "agentes_ativos": len(self.agentes),
            "circuit_breakers_status": self.circuit_manager.obter_status_global(),
            "componentes_integrados": [
                "recepcionista", "classificador", "filtro_seguranca", 
                "deconstrutor", "investigador_web", "sintetizador"
            ],
            "pipelines_disponiveis": [
                "processar_rapido", "processar_entrada_completa",
                "processar_entrada_completa_com_web", "processar_completo_com_sintese",
                "processar_arquivo"  # Novo pipeline para uploads
            ],
            "tipos_arquivo_suportados": ["image/*", "audio/*", "video/*"]
        }
        
    # =============================================================================
    # MÉTODOS DE DIAGNÓSTICO (INALTERADOS)
    # =============================================================================
    
    async def diagnostico_sistema(self) -> Dict[str, Any]:
        """
        Executa uma série de verificações para diagnosticar a saúde do sistema.
        """
        
        diagnostico = {
            "timestamp": time.time(),
            "status_geral": "OK"
        }
        
        try:
            # Testa o pipeline básico de forma síncrona
            teste_basico = self.processar_rapido("Teste de diagnóstico do sistema.")
            diagnostico["pipeline_basico"] = "OK" if 'erro' not in teste_basico else "ERRO"
            
            # Verifica a disponibilidade dos coordenadores
            diagnostico["investigador_web"] = "OK" if self.investigador else "INDISPONIVEL"
            diagnostico["sintetizador"] = "OK" if self.sintetizador_coordenador else "INDISPONIVEL"
            
            # Verifica o status de cada agente individual
            diagnostico["agentes_status"] = {}
            for nome, agente in self.agentes.items():
                try:
                    # Simula uma chamada simples para verificar se o agente responde
                    if nome == 'recepcionista':
                        agente.processar_entrada("teste")
                    elif nome == 'classificador':
                        agente.classificar_conteudo("teste")
                    # Adicionar mais testes específicos se necessário
                    diagnostico["agentes_status"][nome] = "OK"
                except Exception:
                    diagnostico["agentes_status"][nome] = "ERRO"
                    
            # Consolida o status geral
            if "ERRO" in diagnostico.values() or "ERRO" in diagnostico["agentes_status"].values():
                diagnostico["status_geral"] = "ERRO"
            elif "INDISPONIVEL" in diagnostico.values():
                diagnostico["status_geral"] = "PARCIAL"
                
        except Exception as e:
            diagnostico["status_geral"] = "ERRO_CRITICO"
            diagnostico["erro"] = str(e)
            self.logger.critical(f"Erro crítico durante o diagnóstico do sistema: {e}", exc_info=True)
            
        return diagnostico