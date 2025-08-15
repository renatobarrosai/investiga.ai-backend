# src/agentes/recepcionista.py
import logging
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .model_loaders.gemma_loader import GemmaLoader
from .prompts import gerenciador_prompts, obter_prompt, obter_config_geracao, validar_json_output

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
    
    # Novos campos para integração com modelo real
    processamento_sucesso: bool = True
    tempo_processamento: float = 0.0
    modelo_usado: Optional[str] = None
    confianca_estruturacao: float = 1.0

class ProcessadorRecepcionista:
    """
    Atua como a porta de entrada do sistema, recebendo as requisições
    brutas, limpando-as e estruturando-as em um formato padronizado
    para o restante do pipeline de análise.
    
    EVOLUÍDO PARA USAR MODELO REAL:
    - Integração com GemmaLoader para processamento com IA
    - Sistema de prompts adaptativos por contexto
    - Validação automática de outputs
    - Fallback para processamento básico em caso de falha
    """
    
    def __init__(self, registry=None, monitor_gpu=None, contexto_padrao="casual"):
        """
        Inicializa o processador recepcionista com modelo real.
        
        Args:
            registry: Registry de modelos para integração
            monitor_gpu: Monitor de GPU para otimização
            contexto_padrao: Contexto padrão para prompts ("casual", "jornalistico", etc.)
        """
        self.logger = logging.getLogger(__name__)
        self.contexto_padrao = contexto_padrao
        
        # Integração com modelo real
        self.gemma_loader = GemmaLoader(registry=registry, monitor_gpu=monitor_gpu)
        self.modelo_carregado = False
        self.nome_modelo = "gemma-2b-recepcionista"
        
        # Controle de fallback
        self.usar_modelo_real = True
        self.tentativas_carregamento = 0
        self.max_tentativas = 3
        
        # Estatísticas
        self.stats = {
            "total_processamentos": 0,
            "sucessos_modelo_real": 0,
            "fallbacks_basicos": 0,
            "tempo_medio_processamento": 0.0
        }
        
        # Inicialização
        self._inicializar_modelo()
        
    def _inicializar_modelo(self):
        """Inicializa o modelo Gemma-2B para recepção"""
        try:
            self.logger.info("Inicializando modelo Gemma-2B para recepcionista...")
            
            resultado = self.gemma_loader.carregar_modelo(
                nome_modelo=self.nome_modelo,
                force_reload=False
            )
            
            if resultado.sucesso:
                self.modelo_carregado = True
                self.logger.info(f"Modelo {self.nome_modelo} carregado com sucesso")
                self.logger.info(f"Memória alocada: {resultado.memoria_alocada_mb:.1f}MB")
                self.logger.info(f"Tempo de carregamento: {resultado.tempo_carregamento:.2f}s")
            else:
                self.logger.warning(f"Falha ao carregar modelo: {resultado.erro}")
                self.logger.info("Modo fallback ativado - processamento básico disponível")
                self.modelo_carregado = False
                
        except Exception as e:
            self.logger.error(f"Erro na inicialização do modelo: {e}")
            self.modelo_carregado = False
            
    def processar_entrada(self, conteudo: str, contexto: Optional[str] = None, 
                         force_fallback: bool = False) -> EntradaEstruturada:
        """
        Analisa o conteúdo bruto, extrai informações essenciais como URLs
        e formata os dados na estrutura `EntradaEstruturada`.

        Args:
            conteudo (str): O dado de entrada a ser processado.
            contexto (str, optional): Contexto específico para este processamento
            force_fallback (bool): Força uso do processamento básico

        Returns:
            EntradaEstruturada: Um objeto com os dados devidamente organizados.
        """
        inicio = time.time()
        self.stats["total_processamentos"] += 1
        
        contexto_usado = contexto or self.contexto_padrao
        
        try:
            # Tentar processamento com modelo real
            if (self.modelo_carregado and self.usar_modelo_real and not force_fallback):
                resultado = self._processar_com_modelo(conteudo, contexto_usado)
                if resultado:
                    self.stats["sucessos_modelo_real"] += 1
                    resultado.tempo_processamento = time.time() - inicio
                    self._atualizar_estatisticas_tempo(resultado.tempo_processamento)
                    return resultado
            
            # Fallback para processamento básico
            self.logger.info("Usando processamento básico (fallback)")
            resultado = self._processar_basico(conteudo)
            self.stats["fallbacks_basicos"] += 1
            resultado.tempo_processamento = time.time() - inicio
            self._atualizar_estatisticas_tempo(resultado.tempo_processamento)
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro no processamento: {e}", exc_info=True)
            # Em caso de erro total, retornar estrutura mínima
            return self._criar_estrutura_erro(conteudo, str(e), time.time() - inicio)
            
    def _processar_com_modelo(self, conteudo: str, contexto: str) -> Optional[EntradaEstruturada]:
        """Processa entrada usando modelo Gemma-2B com prompts"""
        try:
            # Determinar template de prompt baseado no contexto
            if contexto.lower() in ["jornalistico", "jornalístico", "profissional"]:
                nome_template = "estruturar_entrada_jornalistico"
            else:
                nome_template = "estruturar_entrada_casual"
            
            # Obter prompt formatado
            prompt = obter_prompt(nome_template, conteudo=conteudo)
            if not prompt:
                self.logger.error(f"Falha ao obter prompt '{nome_template}'")
                return None
            
            # Obter configurações de geração
            config_geracao = obter_config_geracao(nome_template)
            
            # Gerar resposta com modelo
            resposta = self.gemma_loader.gerar_resposta(
                prompt=prompt,
                **config_geracao
            )
            
            if not resposta["sucesso"]:
                self.logger.error(f"Falha na geração: {resposta.get('erro', 'Erro desconhecido')}")
                return None
            
            # Validar e extrair JSON da resposta
            validacao = validar_json_output(resposta["resposta"], nome_template)
            
            if not validacao["valido"]:
                self.logger.warning(f"Output inválido: {validacao['erro']}")
                # Tentar fallback com processamento básico
                return None
            
            dados_estruturados = validacao["dados"]
            
            # Converter para EntradaEstruturada
            return self._converter_para_entrada_estruturada(
                conteudo, dados_estruturados, resposta["metadata"]
            )
            
        except Exception as e:
            self.logger.error(f"Erro no processamento com modelo: {e}")
            return None
    
    def _converter_para_entrada_estruturada(self, conteudo_original: str, 
                                          dados: Dict, metadata_geracao: Dict) -> EntradaEstruturada:
        """Converte dados JSON do modelo para EntradaEstruturada"""
        
        # Extrair URLs usando regex como backup
        urls_regex = self._extrair_urls_regex(conteudo_original)
        urls_modelo = dados.get("urls_encontradas", [])
        urls_combinadas = list(set(urls_regex + urls_modelo))
        
        return EntradaEstruturada(
            conteudo_original=conteudo_original,
            tipo_conteudo=dados.get("tipo_conteudo", "texto"),
            alegacoes_detectadas=dados.get("alegacoes_principais", []),
            urls_encontradas=urls_combinadas,
            contexto_detalhado=dados.get("contexto", "Processado pelo recepcionista com IA"),
            prioridade_verificacao=dados.get("prioridade_verificacao", 5),
            metadata={
                "fonte_dados": dados.get("fonte"),
                "modelo_usado": self.nome_modelo,
                "tempo_geracao": metadata_geracao.get("tempo_geracao", 0),
                "tokens_processados": metadata_geracao.get("tokens_entrada", 0) + metadata_geracao.get("tokens_gerados", 0),
                "metodo_processamento": "modelo_real"
            },
            processamento_sucesso=True,
            modelo_usado=self.nome_modelo,
            confianca_estruturacao=0.85  # Confiança baseada em modelo real
        )
    
    def _processar_basico(self, conteudo: str) -> EntradaEstruturada:
        """
        Processamento básico (fallback) sem modelo de IA.
        Mantém funcionalidade mínima do sistema.
        """
        # Utiliza uma expressão regular para encontrar todas as URLs no texto.
        urls = self._extrair_urls_regex(conteudo)
        
        # Análise básica de tipo de conteúdo
        tipo_conteudo = self._detectar_tipo_basico(conteudo)
        
        # Extração simples de possíveis alegações (primeiras frases)
        alegacoes = self._extrair_alegacoes_basicas(conteudo)
        
        # Cria e retorna o objeto estruturado.
        return EntradaEstruturada(
            conteudo_original=conteudo,
            tipo_conteudo=tipo_conteudo,
            alegacoes_detectadas=alegacoes,
            urls_encontradas=urls,
            contexto_detalhado="Processado pelo Recepcionista (modo básico).",
            prioridade_verificacao=5,  # Prioridade padrão.
            metadata={
                "metodo_processamento": "basico_fallback"
            },
            processamento_sucesso=True,
            modelo_usado=None,
            confianca_estruturacao=0.6  # Confiança menor no processamento básico
        )
    
    def _extrair_urls_regex(self, conteudo: str) -> List[str]:
        """Extrai URLs usando expressões regulares"""
        padrao_urls = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(padrao_urls, conteudo)
        
        # Detectar possíveis URLs sem protocolo
        padrao_sites = r'(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(?:\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})*\.(?:[a-zA-Z]{2,})'
        sites = re.findall(padrao_sites, conteudo)
        
        # Adicionar protocolo aos sites sem protocolo
        for site in sites:
            if site not in conteudo.replace(f"http://{site}", "").replace(f"https://{site}", ""):
                urls.append(f"https://{site}")
        
        return list(set(urls))  # Remover duplicatas
    
    def _detectar_tipo_basico(self, conteudo: str) -> str:
        """Detecta tipo de conteúdo usando heurísticas simples"""
        conteudo_lower = conteudo.lower()
        
        # Palavras-chave para diferentes tipos
        if any(palavra in conteudo_lower for palavra in ["breaking", "notícia", "jornal", "reportagem"]):
            return "noticia"
        elif any(palavra in conteudo_lower for palavra in ["eu vi", "eu estava", "presenciei", "testemunhei"]):
            return "depoimento"
        elif any(palavra in conteudo_lower for palavra in ["segundo", "de acordo com", "conforme", "fonte"]):
            return "citacao"
        elif "?" in conteudo:
            return "pergunta"
        elif len(conteudo) > 500:
            return "artigo"
        else:
            return "afirmacao"
    
    def _extrair_alegacoes_basicas(self, conteudo: str) -> List[str]:
        """Extrai alegações usando análise básica de texto"""
        # Dividir em frases
        frases = re.split(r'[.!?]+', conteudo)
        
        alegacoes = []
        for frase in frases[:3]:  # Máximo 3 alegações
            frase = frase.strip()
            if len(frase) > 20 and len(frase) < 200:  # Filtrar frases muito curtas ou longas
                alegacoes.append(frase)
        
        return alegacoes
    
    def _criar_estrutura_erro(self, conteudo: str, erro: str, tempo: float) -> EntradaEstruturada:
        """Cria estrutura mínima em caso de erro total"""
        return EntradaEstruturada(
            conteudo_original=conteudo,
            tipo_conteudo="erro",
            alegacoes_detectadas=[],
            urls_encontradas=[],
            contexto_detalhado=f"Erro no processamento: {erro}",
            prioridade_verificacao=1,
            metadata={"erro": erro, "metodo_processamento": "erro_recovery"},
            processamento_sucesso=False,
            tempo_processamento=tempo,
            modelo_usado=None,
            confianca_estruturacao=0.0
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
    
    def validar_estruturacao(self, entrada_estruturada: EntradaEstruturada) -> Dict[str, Any]:
        """
        Valida uma estruturação usando o modelo, se disponível
        
        Args:
            entrada_estruturada: Resultado da estruturação
            
        Returns:
            Dict com resultado da validação
        """
        if not self.modelo_carregado:
            return {
                "valido": True,
                "observacoes": ["Validação não disponível - modelo não carregado"],
                "confianca": 0.5
            }
        
        try:
            # Usar prompt de validação
            prompt = obter_prompt(
                "validar_estruturacao",
                entrada_original=entrada_estruturada.conteudo_original,
                estruturacao_gerada=str({
                    "tipo": entrada_estruturada.tipo_conteudo,
                    "alegacoes": entrada_estruturada.alegacoes_detectadas,
                    "urls": entrada_estruturada.urls_encontradas,
                    "prioridade": entrada_estruturada.prioridade_verificacao
                })
            )
            
            config = obter_config_geracao("validar_estruturacao")
            resposta = self.gemma_loader.gerar_resposta(prompt=prompt, **config)
            
            if resposta["sucesso"]:
                resultado_validacao = resposta["resposta"].strip()
                
                if "VÁLIDO" in resultado_validacao:
                    return {
                        "valido": True,
                        "observacoes": [resultado_validacao],
                        "confianca": 0.9
                    }
                else:
                    return {
                        "valido": False,
                        "observacoes": [resultado_validacao],
                        "confianca": 0.8
                    }
            else:
                return {
                    "valido": True,
                    "observacoes": ["Falha na validação - assumindo válido"],
                    "confianca": 0.5
                }
                
        except Exception as e:
            self.logger.error(f"Erro na validação: {e}")
            return {
                "valido": True,
                "observacoes": [f"Erro na validação: {e}"],
                "confianca": 0.5
            }
    
    def extrair_urls_detalhado(self, conteudo: str) -> Dict[str, List[str]]:
        """
        Extração detalhada de URLs usando modelo, se disponível
        
        Returns:
            Dict com URLs categorizadas
        """
        if not self.modelo_carregado:
            # Fallback para regex
            urls_simples = self._extrair_urls_regex(conteudo)
            return {
                "urls_completas": urls_simples,
                "links_encurtados": [],
                "sites_mencionados": []
            }
        
        try:
            prompt = obter_prompt("extrair_urls", texto=conteudo)
            config = obter_config_geracao("extrair_urls")
            
            resposta = self.gemma_loader.gerar_resposta(prompt=prompt, **config)
            
            if resposta["sucesso"]:
                validacao = validar_json_output(resposta["resposta"], "extrair_urls")
                if validacao["valido"]:
                    return validacao["dados"]
            
            # Fallback em caso de falha
            urls_simples = self._extrair_urls_regex(conteudo)
            return {
                "urls_completas": urls_simples,
                "links_encurtados": [],
                "sites_mencionados": []
            }
            
        except Exception as e:
            self.logger.error(f"Erro na extração detalhada de URLs: {e}")
            urls_simples = self._extrair_urls_regex(conteudo)
            return {
                "urls_completas": urls_simples,
                "links_encurtados": [],
                "sites_mencionados": []
            }
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do processador"""
        total = self.stats["total_processamentos"]
        
        estatisticas = {
            "modelo_carregado": self.modelo_carregado,
            "nome_modelo": self.nome_modelo,
            "total_processamentos": total,
            "sucessos_modelo_real": self.stats["sucessos_modelo_real"],
            "fallbacks_basicos": self.stats["fallbacks_basicos"],
            "tempo_medio_processamento": self.stats["tempo_medio_processamento"],
            "taxa_sucesso_modelo": (
                (self.stats["sucessos_modelo_real"] / total * 100) 
                if total > 0 else 0
            ),
            "status_loader": self.gemma_loader.verificar_status() if self.gemma_loader else None
        }
        
        return estatisticas
    
    def recarregar_modelo(self) -> bool:
        """Força recarregamento do modelo"""
        try:
            resultado = self.gemma_loader.carregar_modelo(
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
            sucesso = self.gemma_loader.descarregar_modelo(self.nome_modelo)
            self.modelo_carregado = False
            
            if sucesso:
                self.logger.info("Modelo descarregado com sucesso")
            else:
                self.logger.warning("Falha no descarregamento do modelo")
            
            return sucesso
            
        except Exception as e:
            self.logger.error(f"Erro no descarregamento: {e}")
            return False
    
    def benchmark_processamento(self, num_testes: int = 10) -> Dict[str, Any]:
        """Executa benchmark do processamento"""
        entradas_teste = [
            "O governo anunciou novas medidas econômicas para combater a inflação.",
            "Estudo mostra que 70% dos brasileiros preferem trabalhar remotamente.",
            "Empresa de tecnologia lança produto revolucionário no mercado nacional.",
            "Pesquisa indica aumento de 15% no consumo de energia renovável.",
            "Especialistas alertam sobre mudanças climáticas na região sul.",
            "Nova lei será votada no congresso na próxima semana.",
            "Aplicativo brasileiro ganha prêmio internacional de inovação.",
            "Dados mostram crescimento de 8% no setor de turismo este ano.",
            "Universidade divulga pesquisa sobre hábitos alimentares dos jovens.",
            "Cidade implementa sistema inteligente de monitoramento urbano."
        ]
        
        resultados = []
        inicio_total = time.time()
        
        for i in range(num_testes):
            entrada = entradas_teste[i % len(entradas_teste)]
            
            inicio = time.time()
            resultado = self.processar_entrada(entrada)
            fim = time.time()
            
            resultados.append({
                "sucesso": resultado.processamento_sucesso,
                "tempo": fim - inicio,
                "modelo_usado": resultado.modelo_usado,
                "confianca": resultado.confianca_estruturacao,
                "alegacoes_extraidas": len(resultado.alegacoes_detectadas),
                "urls_encontradas": len(resultado.urls_encontradas)
            })
        
        fim_total = time.time()
        
        # Calcular estatísticas
        sucessos = [r for r in resultados if r["sucesso"]]
        tempos = [r["tempo"] for r in resultados]
        
        return {
            "testes_executados": num_testes,
            "testes_bem_sucedidos": len(sucessos),
            "taxa_sucesso": len(sucessos) / num_testes * 100,
            "tempo_total": fim_total - inicio_total,
            "tempo_medio_por_teste": sum(tempos) / len(tempos),
            "tempo_minimo": min(tempos),
            "tempo_maximo": max(tempos),
            "modelo_usado_frequencia": {
                resultado["modelo_usado"]: sum(1 for r in resultados if r["modelo_usado"] == resultado["modelo_usado"])
                for resultado in resultados
            },
            "confianca_media": sum(r["confianca"] for r in sucessos) / len(sucessos) if sucessos else 0
        }
