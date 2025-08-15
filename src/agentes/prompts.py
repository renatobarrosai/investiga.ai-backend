# src/agentes/prompts.py
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import re

class TipoPrompt(Enum):
    """Tipos de prompt no sistema"""
    ESTRUTURACAO = "estruturacao"              # Recepcionista - estruturar entrada
    VALIDACAO = "validacao"                    # Recepcionista - validar parsing
    EXTRACAO_URLS = "extracao_urls"            # Recepcionista - extrair URLs
    CLASSIFICACAO_CONTEUDO = "classificacao_conteudo"  # Classificador multimodal
    ANALISE_VISUAL = "analise_visual"          # Classificador - análise de imagem
    DETECCAO_AMEACAS = "deteccao_ameacas"      # Filtro segurança
    RESPOSTA_SUCESSO = "resposta_sucesso"      # Apresentador - resultado positivo
    RESPOSTA_INCERTA = "resposta_incerta"      # Apresentador - resultado incerto
    RESPOSTA_FALSO = "resposta_falso"          # Apresentador - resultado negativo
    EXPLICACAO_TECNICA = "explicacao_tecnica"  # Apresentador - detalhes técnicos

class ContextoUsuario(Enum):
    """Contextos de interação com usuário"""
    CASUAL = "casual"                    # Linguagem informal, cotidiana
    JORNALISTICO = "jornalistico"        # Contexto de mídia, profissional
    ACADEMICO = "academico"              # Contexto educacional, formal
    INVESTIGATIVO = "investigativo"      # Apuração detalhada, crítica

@dataclass
class PromptTemplate:
    """Template de prompt com metadados"""
    nome: str
    tipo: TipoPrompt
    contexto: ContextoUsuario
    template: str
    variaveis: List[str]
    instrucoes_especiais: Optional[str] = None
    exemplos: Optional[List[Dict]] = None
    configuracao: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Configurações padrão se não fornecidas
        if not self.configuracao:
            self.configuracao = {
                "max_tokens": 512,
                "temperature": 0.1,
                "top_p": 0.9,
                "repetition_penalty": 1.1
            }

class GerenciadorPrompts:
    """
    Gerenciador central de prompts para todos os agentes do sistema.
    
    Responsável por:
    - Armazenar e organizar templates de prompts
    - Formatação dinâmica com variáveis
    - Adaptação por contexto de usuário
    - Validação de prompts e outputs
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates: Dict[str, PromptTemplate] = {}
        self._inicializar_templates()
    
    def _inicializar_templates(self):
        """Inicializa todos os templates de prompt do sistema"""
        
        # ================== PROMPTS DO RECEPCIONISTA ==================
        
        # Estruturação de entrada
        self.registrar_template(PromptTemplate(
            nome="estruturar_entrada_casual",
            tipo=TipoPrompt.ESTRUTURACAO,
            contexto=ContextoUsuario.CASUAL,
            template="""Você é um assistente especializado em organizar informações.

Analise o seguinte conteúdo e estruture-o de forma clara:

CONTEÚDO RECEBIDO:
{conteudo}

Sua tarefa é extrair e organizar:
1. TIPO DE CONTEÚDO: (notícia, depoimento, afirmação, etc.)
2. FONTE: (se mencionada ou identificável)
3. ALEGAÇÕES PRINCIPAIS: (máximo 3 pontos principais)
4. URLS ENCONTRADAS: (se houver)
5. CONTEXTO: (onde/quando foi dito, se disponível)

Responda APENAS no formato JSON:
{
    "tipo_conteudo": "string",
    "fonte": "string ou null",
    "alegacoes_principais": ["string1", "string2", "string3"],
    "urls_encontradas": ["url1", "url2"],
    "contexto": "string ou null",
    "prioridade_verificacao": 1-10
}""",
            variaveis=["conteudo"],
            instrucoes_especiais="Mantenha linguagem objetiva e extraia apenas fatos verificáveis.",
            configuracao={"max_tokens": 512, "temperature": 0.1}
        ))
        
        # Validação de parsing
        self.registrar_template(PromptTemplate(
            nome="validar_estruturacao",
            tipo=TipoPrompt.VALIDACAO,
            contexto=ContextoUsuario.CASUAL,
            template="""Valide se a estruturação está correta e completa.

ENTRADA ORIGINAL:
{entrada_original}

ESTRUTURAÇÃO GERADA:
{estruturacao_gerada}

Verifique:
1. Todas as alegações importantes foram capturadas?
2. O tipo de conteúdo está correto?
3. As URLs foram extraídas corretamente?
4. A prioridade está adequada?

Responda apenas: "VÁLIDO" ou "INVÁLIDO: [razão]" """,
            variaveis=["entrada_original", "estruturacao_gerada"],
            configuracao={"max_tokens": 128, "temperature": 0.05}
        ))
        
        # Extração específica de URLs
        self.registrar_template(PromptTemplate(
            nome="extrair_urls",
            tipo=TipoPrompt.EXTRACAO_URLS,
            contexto=ContextoUsuario.CASUAL,
            template="""Extraia TODAS as URLs válidas do texto fornecido.

TEXTO:
{texto}

Identifique:
- URLs completas (http/https)
- Links encurtados (bit.ly, tinyurl, etc.)
- Menções de sites (facebook.com, twitter.com)

Responda em JSON:
{
    "urls_completas": ["url1", "url2"],
    "links_encurtados": ["url1", "url2"],
    "sites_mencionados": ["site1", "site2"]
}""",
            variaveis=["texto"],
            configuracao={"max_tokens": 256, "temperature": 0.0}
        ))
        
        # ================== PROMPTS DO FILTRO SEGURANÇA ==================
        
        self.registrar_template(PromptTemplate(
            nome="detectar_ameacas",
            tipo=TipoPrompt.DETECCAO_AMEACAS,
            contexto=ContextoUsuario.CASUAL,
            template="""Analise o conteúdo em busca de ameaças de segurança.

CONTEÚDO:
{conteudo}

URLS (se houver):
{urls}

Detecte:
1. LINKS SUSPEITOS: Sites de phishing, malware, golpes
2. TENTATIVAS DE INJECTION: Código malicioso, scripts
3. CONTEÚDO PREJUDICIAL: Spam, desinformação maliciosa
4. TENTATIVAS DE ENGENHARIA SOCIAL: Urgência falsa, ofertas suspeitas

Responda em JSON:
{
    "seguro": true/false,
    "ameacas_detectadas": ["tipo1", "tipo2"],
    "urls_maliciosas": ["url1", "url2"],
    "nivel_risco": "baixo/medio/alto/critico",
    "recomendacao": "permitir/revisar/bloquear",
    "detalhes": "explicação da decisão"
}""",
            variaveis=["conteudo", "urls"],
            configuracao={"max_tokens": 256, "temperature": 0.05}
        ))
        
        # ================== PROMPTS DO APRESENTADOR ==================
        
        # Resposta para resultado verdadeiro
        self.registrar_template(PromptTemplate(
            nome="resposta_verdadeiro_casual",
            tipo=TipoPrompt.RESPOSTA_SUCESSO,
            contexto=ContextoUsuario.CASUAL,
            template="""Prepare uma resposta clara e amigável para um resultado VERDADEIRO.

INFORMAÇÃO VERIFICADA:
{informacao_original}

EVIDÊNCIAS ENCONTRADAS:
{evidencias}

CONFIANÇA: {nivel_confianca}%

FONTES PRINCIPAIS:
{fontes_principais}

Crie uma resposta que:
1. Confirme que a informação é verdadeira
2. Resuma as evidências de forma simples
3. Cite as fontes principais
4. Use linguagem acessível e confiável

Formato:
✅ INFORMAÇÃO CONFIRMADA

[Explicação clara do resultado]

📚 FONTES VERIFICADAS:
[Lista das principais fontes]

💡 CONCLUSÃO:
[Resumo final em 1-2 frases]""",
            variaveis=["informacao_original", "evidencias", "nivel_confianca", "fontes_principais"],
            configuracao={"max_tokens": 1024, "temperature": 0.3}
        ))
        
        # Resposta para resultado falso
        self.registrar_template(PromptTemplate(
            nome="resposta_falso_casual",
            tipo=TipoPrompt.RESPOSTA_FALSO,
            contexto=ContextoUsuario.CASUAL,
            template="""Prepare uma resposta cuidadosa para um resultado FALSO.

INFORMAÇÃO ANALISADA:
{informacao_original}

EVIDÊNCIAS CONTRÁRIAS:
{evidencias_contrarias}

CONFIANÇA: {nivel_confianca}%

FONTES QUE DESMENTEM:
{fontes_contrarias}

Crie uma resposta que:
1. Indique claramente que a informação é falsa
2. Explique o que realmente aconteceu/é verdade
3. Cite fontes confiáveis
4. Seja respeitosa mas firme

Formato:
❌ INFORMAÇÃO INCORRETA

[Explicação do que está errado]

✅ O QUE REALMENTE ACONTECEU:
[Versão correta dos fatos]

📚 FONTES CONFIÁVEIS:
[Lista das fontes que comprovam]

⚠️ ALERTA:
[Recomendação sobre não compartilhar]""",
            variaveis=["informacao_original", "evidencias_contrarias", "nivel_confianca", "fontes_contrarias"],
            configuracao={"max_tokens": 1024, "temperature": 0.2}
        ))
        
        # Resposta para resultado incerto
        self.registrar_template(PromptTemplate(
            nome="resposta_incerta_casual",
            tipo=TipoPrompt.RESPOSTA_INCERTA,
            contexto=ContextoUsuario.CASUAL,
            template="""Prepare uma resposta honesta para um resultado INCERTO.

INFORMAÇÃO ANALISADA:
{informacao_original}

EVIDÊNCIAS ENCONTRADAS:
{evidencias_parciais}

LIMITAÇÕES DA ANÁLISE:
{limitacoes}

CONFIANÇA: {nivel_confianca}%

Crie uma resposta que:
1. Explique que não foi possível confirmar totalmente
2. Apresente o que foi encontrado
3. Seja transparente sobre as limitações
4. Oriente sobre como proceder

Formato:
❓ RESULTADO INCONCLUSIVO

[Explicação do que foi encontrado]

📊 EVIDÊNCIAS PARCIAIS:
[Resumo das evidências disponíveis]

🔍 LIMITAÇÕES:
[Por que não foi possível confirmar]

💭 RECOMENDAÇÃO:
[Como o usuário deve proceder]""",
            variaveis=["informacao_original", "evidencias_parciais", "limitacoes", "nivel_confianca"],
            configuracao={"max_tokens": 1024, "temperature": 0.3}
        ))
        
        # ================== PROMPTS DE CONTEXTO JORNALÍSTICO ==================
        
        self.registrar_template(PromptTemplate(
            nome="estruturar_entrada_jornalistico",
            tipo=TipoPrompt.ESTRUTURACAO,
            contexto=ContextoUsuario.JORNALISTICO,
            template="""Como fact-checker profissional, estruture esta informação para verificação.

CONTEÚDO A VERIFICAR:
{conteudo}

Extraia com precisão jornalística:

1. CLAIM PRINCIPAL: A alegação central que requer verificação
2. FONTE PRIMÁRIA: Quem fez a afirmação (pessoa, organização)
3. CONTEXTO TEMPORAL: Quando foi dita/publicada
4. CLAIMS SECUNDÁRIOS: Alegações de apoio ou relacionadas
5. ELEMENTOS VERIFICÁVEIS: Números, datas, eventos específicos
6. PALAVRAS-CHAVE: Para busca de evidências

JSON estruturado:
{
    "claim_principal": "string",
    "fonte_primaria": "string",
    "contexto_temporal": "string",
    "claims_secundarios": ["string1", "string2"],
    "elementos_verificaveis": ["elemento1", "elemento2"],
    "palavras_chave": ["palavra1", "palavra2"],
    "urgencia_verificacao": "baixa/media/alta",
    "tipo_verificacao": "factual/contextual/numerico"
}""",
            variaveis=["conteudo"],
            configuracao={"max_tokens": 768, "temperature": 0.1}
        ))
        
        self.logger.info(f"Sistema de prompts inicializado com {len(self.templates)} templates")
    
    def registrar_template(self, template: PromptTemplate):
        """Registra um novo template no sistema"""
        self.templates[template.nome] = template
        self.logger.debug(f"Template '{template.nome}' registrado")
    
    def obter_template(self, nome: str) -> Optional[PromptTemplate]:
        """Obtém um template específico"""
        return self.templates.get(nome)
    
    def listar_templates(self, tipo: Optional[TipoPrompt] = None, 
                        contexto: Optional[ContextoUsuario] = None) -> List[PromptTemplate]:
        """Lista templates filtrados por tipo e/ou contexto"""
        templates = list(self.templates.values())
        
        if tipo:
            templates = [t for t in templates if t.tipo == tipo]
        
        if contexto:
            templates = [t for t in templates if t.contexto == contexto]
        
        return templates
    
    def formatar_prompt(self, nome_template: str, variaveis: Dict[str, Any]) -> Optional[str]:
        """
        Formata um prompt substituindo variáveis
        
        Args:
            nome_template: Nome do template a usar
            variaveis: Dicionário com valores para substituição
            
        Returns:
            String do prompt formatado ou None se erro
        """
        template = self.obter_template(nome_template)
        if not template:
            self.logger.error(f"Template '{nome_template}' não encontrado")
            return None
        
        try:
            # Validar se todas as variáveis necessárias foram fornecidas
            variaveis_necessarias = set(template.variaveis)
            variaveis_fornecidas = set(variaveis.keys())
            
            if not variaveis_necessarias.issubset(variaveis_fornecidas):
                faltando = variaveis_necessarias - variaveis_fornecidas
                self.logger.error(f"Variáveis faltando para template '{nome_template}': {faltando}")
                return None
            
            # Formatação segura do prompt
            prompt_formatado = template.template.format(**variaveis)
            
            self.logger.debug(f"Prompt '{nome_template}' formatado com sucesso")
            return prompt_formatado
            
        except Exception as e:
            self.logger.error(f"Erro ao formatar prompt '{nome_template}': {e}")
            return None
    
    def obter_configuracao_geracao(self, nome_template: str) -> Dict[str, Any]:
        """Obtém configuração de geração para um template"""
        template = self.obter_template(nome_template)
        if template:
            return template.configuracao.copy()
        return {}
    
    def validar_output_json(self, output: str, template_nome: str) -> Dict[str, Any]:
        """
        Valida se o output está no formato JSON esperado
        
        Args:
            output: String de output do modelo
            template_nome: Nome do template usado
            
        Returns:
            Dict com resultado da validação
        """
        try:
            # Tentar extrair JSON do output
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if not json_match:
                return {
                    "valido": False,
                    "erro": "Nenhum JSON encontrado no output",
                    "dados": None
                }
            
            json_str = json_match.group()
            dados = json.loads(json_str)
            
            return {
                "valido": True,
                "erro": None,
                "dados": dados
            }
            
        except json.JSONDecodeError as e:
            return {
                "valido": False,
                "erro": f"JSON inválido: {str(e)}",
                "dados": None
            }
        except Exception as e:
            return {
                "valido": False,
                "erro": f"Erro na validação: {str(e)}",
                "dados": None
            }
    
    def adaptar_contexto(self, template_base: str, novo_contexto: ContextoUsuario) -> Optional[str]:
        """
        Adapta um template para um novo contexto de usuário
        
        Args:
            template_base: Nome do template base
            novo_contexto: Novo contexto desejado
            
        Returns:
            Nome do template adaptado ou None
        """
        template = self.obter_template(template_base)
        if not template:
            return None
        
        # Buscar template equivalente no novo contexto
        templates_mesmo_tipo = self.listar_templates(tipo=template.tipo, contexto=novo_contexto)
        
        if templates_mesmo_tipo:
            return templates_mesmo_tipo[0].nome
        
        return None
    
    def estatisticas_templates(self) -> Dict[str, Any]:
        """Retorna estatísticas dos templates registrados"""
        stats = {
            "total_templates": len(self.templates),
            "por_tipo": {},
            "por_contexto": {},
            "templates_por_agente": {}
        }
        
        # Contar por tipo
        for template in self.templates.values():
            tipo = template.tipo.value
            stats["por_tipo"][tipo] = stats["por_tipo"].get(tipo, 0) + 1
            
            contexto = template.contexto.value
            stats["por_contexto"][contexto] = stats["por_contexto"].get(contexto, 0) + 1
        
        # Classificar por agente baseado no nome
        for nome, template in self.templates.items():
            if "estrutur" in nome or "validar" in nome or "extrair" in nome:
                agente = "recepcionista"
            elif "ameaca" in nome or "detectar" in nome:
                agente = "filtro_seguranca"
            elif "resposta" in nome or "explicacao" in nome:
                agente = "apresentador"
            elif "classific" in nome or "visual" in nome:
                agente = "classificador"
            else:
                agente = "geral"
            
            stats["templates_por_agente"][agente] = stats["templates_por_agente"].get(agente, 0) + 1
        
        return stats


# ================ INSTÂNCIA GLOBAL ================

# Instância global do gerenciador de prompts para uso em todo o sistema
gerenciador_prompts = GerenciadorPrompts()

# ================ FUNÇÕES DE CONVENIÊNCIA ================

def obter_prompt(nome_template: str, **variaveis) -> Optional[str]:
    """Função de conveniência para obter prompt formatado"""
    return gerenciador_prompts.formatar_prompt(nome_template, variaveis)

def obter_config_geracao(nome_template: str) -> Dict[str, Any]:
    """Função de conveniência para obter configuração de geração"""
    return gerenciador_prompts.obter_configuracao_geracao(nome_template)

def validar_json_output(output: str, template_nome: str) -> Dict[str, Any]:
    """Função de conveniência para validar output JSON"""
    return gerenciador_prompts.validar_output_json(output, template_nome)

def listar_prompts_agente(agente: str) -> List[str]:
    """Lista nomes de prompts disponíveis para um agente específico"""
    todos_templates = gerenciador_prompts.templates
    
    filtros_agente = {
        "recepcionista": ["estrutur", "validar", "extrair"],
        "classificador": ["classific", "visual", "analise"],
        "filtro_seguranca": ["ameaca", "detectar", "segur"],
        "apresentador": ["resposta", "explicacao", "format"]
    }
    
    filtros = filtros_agente.get(agente, [])
    
    return [
        nome for nome in todos_templates.keys()
        if any(filtro in nome for filtro in filtros)
    ]
