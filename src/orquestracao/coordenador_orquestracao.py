import asyncio
import logging
from typing import Dict, Any
from .langgraph_orchestrator import WorkflowAdaptativo
from .load_balancer import LoadBalancerInteligente
from .cache_multilayer import CacheMultiLayer, TipoConteudo
from .monitoring_avancado import MonitoringAvancado, Metrica, TipoMetrica

class CoordenadorOrquestracao:
    """
    Orquestrador de alto nível que gerencia o fluxo de processamento
    de ponta a ponta, utilizando componentes avançados como balanceamento
    de carga, cache de múltiplos níveis e monitoramento detalhado.
    """
    
    def __init__(self, coordenador_agentes):
        """
        Inicializa o coordenador de orquestração.

        Args:
            coordenador_agentes: A instância do coordenador de agentes,
                                 que contém a lógica de negócio principal.
        """
        self.logger = logging.getLogger(__name__)
        self.coordenador_agentes = coordenador_agentes
        
        # Instanciação dos componentes de orquestração avançada
        self.workflow = WorkflowAdaptativo(coordenador_agentes)
        self.load_balancer = LoadBalancerInteligente()
        self.cache = CacheMultiLayer()
        self.monitoring = MonitoringAvancado()
        
    async def inicializar(self):
        """
        Inicializa de forma assíncrona todos os componentes da camada de orquestração.
        """
        await self.load_balancer.inicializar()
        await self.monitoring.inicializar()
        self.logger.info("Camada de orquestração avançada foi inicializada com sucesso.")
        
    async def processar_com_orquestracao(self, conteudo: str, imagem=None, config=None) -> Dict[str, Any]:
        """
        Executa o pipeline de processamento completo, aplicando as lógicas
        de cache, balanceamento de carga e execução de workflow.

        Args:
            conteudo (str): O conteúdo textual a ser processado.
            imagem (optional): Uma imagem associada ao conteúdo.
            config (optional): Configurações específicas para esta requisição.

        Returns:
            Dict[str, Any]: Um dicionário detalhado com o resultado e metadados da orquestração.
        """
        
        inicio = asyncio.get_event_loop().time()
        
        # Registra o início do processamento no sistema de monitoramento
        await self.monitoring.registrar_metrica(Metrica(
            nome="processamento_iniciado",
            tipo=TipoMetrica.CONTADOR,
            valor=1,
            timestamp=inicio,
            tags={"tipo": "orquestracao"}
        ))
        
        resultado = {
            'timestamp_inicio': inicio,
            'orquestracao_usada': True
        }
        
        try:
            # Etapa 1: Verificação no cache de múltiplos níveis
            chave_cache = f"processamento_{hash(conteudo)}"
            resultado_cache = await self.cache.get(chave_cache, TipoConteudo.SINTESE_COMPLETA)
            
            if resultado_cache:
                resultado.update({
                    'status': 'cache_hit',
                    'resultado': resultado_cache,
                    'fonte': 'cache_multilayer'
                })
                self.logger.info(f"Cache hit para a chave: {chave_cache}")
                return resultado
                
            # Etapa 2: Seleção do recurso de processamento via balanceador de carga
            componente = await self.load_balancer.selecionar_componente_otimo(
                "processamento_completo", prioridade=7
            )
            self.logger.info(f"Componente '{componente}' selecionado pelo balanceador de carga.")
            
            # Etapa 3: Execução do workflow adaptativo
            resultado_workflow = await self.workflow.executar_workflow(conteudo, imagem, config)
            
            # Etapa 4: Armazenamento do resultado no cache
            if resultado_workflow.get('status') == 'sucesso':
                await self.cache.set(
                    chave_cache, 
                    resultado_workflow['resultado'], 
                    TipoConteudo.SINTESE_COMPLETA
                )
                self.logger.info(f"Resultado armazenado no cache com a chave: {chave_cache}")
                
            # Etapa 5: Registro do uso do componente no balanceador de carga
            fim = asyncio.get_event_loop().time()
            await self.load_balancer.registrar_uso_componente(
                componente, inicio, fim, 
                resultado_workflow.get('status') == 'sucesso'
            )
            
            resultado.update({
                'status': 'processamento_completo',
                'componente_usado': componente,
                'workflow_resultado': resultado_workflow,
                'tempo_total': fim - inicio
            })
            
            # Registra métrica de sucesso
            await self.monitoring.registrar_metrica(Metrica(
                nome="processamento_sucesso",
                tipo=TipoMetrica.CONTADOR,
                valor=1,
                timestamp=fim,
                tags={"componente": componente}
            ))
            
        except Exception as e:
            self.logger.error(f"Erro durante a orquestração do processamento: {e}", exc_info=True)
            # Registra métrica de erro
            await self.monitoring.registrar_metrica(Metrica(
                nome="processamento_erro",
                tipo=TipoMetrica.CONTADOR,
                valor=1,
                timestamp=asyncio.get_event_loop().time(),
                tags={"erro": str(e)[:50]} # Limita o tamanho da tag de erro
            ))
            
            resultado.update({
                'status': 'erro_orquestracao',
                'erro': str(e)
            })
            
        return resultado
        
    def obter_status_orquestracao(self) -> Dict[str, Any]:
        """
        Coleta e retorna um status consolidado de todos os componentes da orquestração.

        Returns:
            Dict[str, Any]: Um dicionário com estatísticas do balanceador de carga,
                            cache, monitoramento e alertas ativos.
        """
        return {
            'load_balancer': self.load_balancer.obter_estatisticas(),
            'cache': self.cache.obter_estatisticas_detalhadas(),
            'monitoring': self.monitoring.obter_dashboard_dados(),
            'alertas_ativos': len(self.monitoring.obter_alertas_ativos())
        }