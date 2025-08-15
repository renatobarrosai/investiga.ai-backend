# src/utils/prompt_utils.py
import logging
import re
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import unicodedata

class FormatoSaida(Enum):
    """Formatos de saída suportados para prompts"""
    JSON = "json"
    TEXTO_SIMPLES = "texto_simples"
    LISTA = "lista"
    ESTRUTURADO = "estruturado"

@dataclass
class ContextoPrompt:
    """Contexto para adaptação dinâmica de prompts"""
    usuario_tipo: str = "geral"  # "casual", "jornalista", "pesquisador", etc.
    dominio: str = "geral"       # "politica", "saude", "tecnologia", etc.
    urgencia: str = "normal"     # "baixa", "normal", "alta", "critica"
    formalidade: str = "media"   # "informal", "media", "formal", "academica"
    complexidade: str = "media"  # "simples", "media", "complexa", "tecnica"

class PromptUtils:
    """
    Utilitários avançados para formatação, validação e adaptação de prompts.
    
    Fornece funções para:
    - Formatação dinâmica com variáveis
    - Adaptação de contexto automática
    - Validação de inputs e outputs
    - Limpeza e normalização de texto
    - Extração de informações estruturadas
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Padrões regex úteis
        self.padroes = {
            "json": re.compile(r'\{[\s\S]*\}'),
            "urls": re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
            "emails": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "telefones": re.compile(r'(?:\+55\s?)?(?:\(?[1-9]{2}\)?\s?)?(?:[2-9][0-9]{3,4}[-\s]?[0-9]{4})'),
            "datas": re.compile(r'\b(?:[0-3]?[0-9])/(?:[01]?[0-9])/(?:[0-9]{2,4})\b'),
            "numeros": re.compile(r'\b\d+(?:\.\d+)?\b')
        }
        
        # Mapeamentos para adaptação de contexto
        self.mapeamentos_contexto = {
            "formalidade": {
                "informal": {
                    "tratamento": "você",
                    "estilo": "conversacional",
                    "conectores": ["aí", "então", "tipo"],
                    "explicacoes": "simples e diretas"
                },
                "formal": {
                    "tratamento": "você/sr./sra.",
                    "estilo": "respeitoso",
                    "conectores": ["portanto", "assim sendo", "dessa forma"],
                    "explicacoes": "detalhadas e precisas"
                },
                "academica": {
                    "tratamento": "leitor",
                    "estilo": "técnico",
                    "conectores": ["outrossim", "não obstante", "por conseguinte"],
                    "explicacoes": "fundamentadas e referenciadas"
                }
            }
        }
        
    def formatar_prompt_dinamico(self, template: str, variaveis: Dict[str, Any], 
                                contexto: Optional[ContextoPrompt] = None) -> str:
        """
        Formata prompt com substituição de variáveis e adaptação de contexto
        
        Args:
            template: Template base do prompt
            variaveis: Dicionário com valores para substituição
            contexto: Contexto para adaptação do prompt
            
        Returns:
            Prompt formatado e adaptado
        """
        try:
            # Primeira passada: substituição básica de variáveis
            prompt_formatado = template.format(**variaveis)
            
            # Segunda passada: adaptação por contexto se fornecido
            if contexto:
                prompt_formatado = self._adaptar_por_contexto(prompt_formatado, contexto)
            
            # Terceira passada: limpeza e normalização
            prompt_formatado = self.normalizar_texto(prompt_formatado)
            
            return prompt_formatado
            
        except KeyError as e:
            self.logger.error(f"Variável não encontrada no template: {e}")
            raise ValueError(f"Variável obrigatória não fornecida: {e}")
        except Exception as e:
            self.logger.error(f"Erro na formatação do prompt: {e}")
            raise
    
    def _adaptar_por_contexto(self, prompt: str, contexto: ContextoPrompt) -> str:
        """Adapta prompt baseado no contexto fornecido"""
        prompt_adaptado = prompt
        
        # Adaptação por formalidade
        if contexto.formalidade in self.mapeamentos_contexto["formalidade"]:
            config_formalidade = self.mapeamentos_contexto["formalidade"][contexto.formalidade]
            
            # Substituir tratamentos
            if "você" in prompt_adaptado and config_formalidade["tratamento"] != "você":
                prompt_adaptado = prompt_adaptado.replace("você", config_formalidade["tratamento"])
        
        # Adaptação por urgência
        if contexto.urgencia == "critica":
            prompt_adaptado = "URGENTE: " + prompt_adaptado
        elif contexto.urgencia == "alta":
            prompt_adaptado = "IMPORTANTE: " + prompt_adaptado
        
        # Adaptação por complexidade
        if contexto.complexidade == "simples":
            prompt_adaptado += "\n\nIMPORTANTE: Use linguagem simples e clara."
        elif contexto.complexidade == "tecnica":
            prompt_adaptado += "\n\nOBS: Pode usar terminologia técnica apropriada."
        
        return prompt_adaptado
    
    def extrair_variaveis_template(self, template: str) -> List[str]:
        """
        Extrai lista de variáveis necessárias em um template
        
        Args:
            template: String do template
            
        Returns:
            Lista de nomes de variáveis encontradas
        """
        # Usar regex para encontrar {variavel}
        padrao_variaveis = re.compile(r'\{([^}]+)\}')
        variaveis = padrao_variaveis.findall(template)
        
        # Filtrar apenas nomes válidos (sem formatação)
        variaveis_limpas = []
        for var in variaveis:
            # Remover formatações como {var:format}
            nome_var = var.split(':')[0]
            if nome_var and nome_var.isidentifier():
                variaveis_limpas.append(nome_var)
        
        return list(set(variaveis_limpas))  # Remover duplicatas
    
    def validar_template(self, template: str, variaveis_obrigatorias: List[str]) -> Dict[str, Any]:
        """
        Valida se um template está bem formado
        
        Args:
            template: String do template a validar
            variaveis_obrigatorias: Lista de variáveis que devem estar presentes
            
        Returns:
            Dict com resultado da validação
        """
        resultado = {
            "valido": True,
            "erros": [],
            "avisos": [],
            "variaveis_encontradas": [],
            "variaveis_faltando": []
        }
        
        try:
            # Extrair variáveis do template
            variaveis_template = self.extrair_variaveis_template(template)
            resultado["variaveis_encontradas"] = variaveis_template
            
            # Verificar variáveis obrigatórias
            variaveis_faltando = set(variaveis_obrigatorias) - set(variaveis_template)
            if variaveis_faltando:
                resultado["valido"] = False
                resultado["variaveis_faltando"] = list(variaveis_faltando)
                resultado["erros"].append(f"Variáveis obrigatórias faltando: {variaveis_faltando}")
            
            # Verificar sintaxe básica do template
            try:
                # Testar formatação com valores dummy
                valores_teste = {var: "TESTE" for var in variaveis_template}
                template.format(**valores_teste)
            except Exception as e:
                resultado["valido"] = False
                resultado["erros"].append(f"Erro de sintaxe no template: {e}")
            
            # Verificações de qualidade
            if len(template) < 50:
                resultado["avisos"].append("Template muito curto - pode ser vago demais")
            
            if len(template) > 5000:
                resultado["avisos"].append("Template muito longo - pode exceder limites do modelo")
            
            if "{" in template and "}" in template:
                # Verificar chaves desbalanceadas
                abertas = template.count("{")
                fechadas = template.count("}")
                if abertas != fechadas:
                    resultado["valido"] = False
                    resultado["erros"].append("Chaves desbalanceadas no template")
            
        except Exception as e:
            resultado["valido"] = False
            resultado["erros"].append(f"Erro na validação: {e}")
        
        return resultado
    
    def extrair_json_do_texto(self, texto: str, formato_esperado: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extrai JSON válido de um texto que pode conter outros conteúdos
        
        Args:
            texto: Texto contendo JSON
            formato_esperado: Estrutura esperada para validação
            
        Returns:
            Dict com resultado da extração
        """
        resultado = {
            "sucesso": False,
            "dados": None,
            "erro": None,
            "json_bruto": None
        }
        
        try:
            # Tentar encontrar JSON no texto
            match = self.padroes["json"].search(texto)
            if not match:
                resultado["erro"] = "Nenhum JSON encontrado no texto"
                return resultado
            
            json_str = match.group()
            resultado["json_bruto"] = json_str
            
            # Tentar parsear JSON
            try:
                dados = json.loads(json_str)
                resultado["dados"] = dados
                resultado["sucesso"] = True
                
                # Validar estrutura se formato fornecido
                if formato_esperado:
                    validacao_estrutura = self._validar_estrutura_json(dados, formato_esperado)
                    if not validacao_estrutura["valido"]:
                        resultado["erro"] = f"Estrutura inválida: {validacao_estrutura['erro']}"
                        resultado["sucesso"] = False
                
            except json.JSONDecodeError as e:
                resultado["erro"] = f"JSON inválido: {e}"
                
                # Tentar correção automática de JSON
                json_corrigido = self._tentar_corrigir_json(json_str)
                if json_corrigido:
                    try:
                        dados = json.loads(json_corrigido)
                        resultado["dados"] = dados
                        resultado["sucesso"] = True
                        resultado["erro"] = "JSON corrigido automaticamente"
                    except:
                        pass
        
        except Exception as e:
            resultado["erro"] = f"Erro na extração: {e}"
        
        return resultado
    
    def _validar_estrutura_json(self, dados: Dict, formato_esperado: Dict) -> Dict[str, Any]:
        """Valida se dados JSON seguem estrutura esperada"""
        try:
            # Verificação simples de chaves obrigatórias
            chaves_esperadas = set(formato_esperado.keys())
            chaves_dados = set(dados.keys())
            
            chaves_faltando = chaves_esperadas - chaves_dados
            if chaves_faltando:
                return {
                    "valido": False,
                    "erro": f"Chaves faltando: {chaves_faltando}"
                }
            
            return {"valido": True, "erro": None}
            
        except Exception as e:
            return {"valido": False, "erro": str(e)}
    
    def _tentar_corrigir_json(self, json_str: str) -> Optional[str]:
        """Tenta corrigir JSON malformado"""
        try:
            # Correções comuns
            corrigido = json_str
            
            # Remover vírgulas extras antes de }
            corrigido = re.sub(r',\s*}', '}', corrigido)
            corrigido = re.sub(r',\s*]', ']', corrigido)
            
            # Adicionar aspas em chaves sem aspas
            corrigido = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', corrigido)
            
            # Testar se a correção funcionou
            json.loads(corrigido)
            return corrigido
            
        except:
            return None
    
    def normalizar_texto(self, texto: str) -> str:
        """
        Normaliza texto removendo caracteres desnecessários e formatando
        
        Args:
            texto: Texto a ser normalizado
            
        Returns:
            Texto normalizado
        """
        if not texto:
            return ""
        
        # Normalizar unicode
        texto = unicodedata.normalize('NFKC', texto)
        
        # Remover espaços extras
        texto = re.sub(r'\s+', ' ', texto)
        
        # Remover quebras de linha desnecessárias
        texto = re.sub(r'\n\s*\n', '\n\n', texto)
        
        # Trim espaços do início e fim
        texto = texto.strip()
        
        return texto
    
    def extrair_informacoes_estruturadas(self, texto: str) -> Dict[str, List[str]]:
        """
        Extrai informações estruturadas de um texto usando regex
        
        Args:
            texto: Texto para análise
            
        Returns:
            Dict com listas de informações encontradas
        """
        resultado = {
            "urls": [],
            "emails": [],
            "telefones": [],
            "datas": [],
            "numeros": []
        }
        
        for tipo, padrao in self.padroes.items():
            if tipo in resultado:
                matches = padrao.findall(texto)
                resultado[tipo] = list(set(matches))  # Remover duplicatas
        
        return resultado
    
    def gerar_resumo_prompt(self, prompt: str, max_chars: int = 100) -> str:
        """
        Gera resumo curto de um prompt para logging/debug
        
        Args:
            prompt: Prompt completo
            max_chars: Máximo de caracteres no resumo
            
        Returns:
            Resumo do prompt
        """
        if len(prompt) <= max_chars:
            return prompt
        
        # Pegar início e fim do prompt
        metade = max_chars // 2 - 5
        inicio = prompt[:metade]
        fim = prompt[-metade:]
        
        return f"{inicio}...{fim}"
    
    def substituir_variaveis_segura(self, template: str, variaveis: Dict[str, Any]) -> str:
        """
        Substitui variáveis de forma segura, tratando valores None/vazios
        
        Args:
            template: Template com variáveis
            variaveis: Dict com valores para substituição
            
        Returns:
            Template com variáveis substituídas
        """
        variaveis_seguras = {}
        
        for chave, valor in variaveis.items():
            if valor is None:
                variaveis_seguras[chave] = ""
            elif isinstance(valor, (list, dict)):
                variaveis_seguras[chave] = json.dumps(valor, ensure_ascii=False)
            else:
                variaveis_seguras[chave] = str(valor)
        
        try:
            return template.format(**variaveis_seguras)
        except KeyError as e:
            self.logger.warning(f"Variável não encontrada: {e}")
            # Substituir variáveis faltando por placeholder
            variaveis_seguras[str(e).strip("'")] = "[VALOR_NAO_DISPONIVEL]"
            return template.format(**variaveis_seguras)
    
    def criar_prompt_condicional(self, condicoes: List[Dict[str, Any]], 
                                template_base: str) -> str:
        """
        Cria prompt com seções condicionais baseadas em critérios
        
        Args:
            condicoes: Lista de condições com template e critério
            template_base: Template base a ser expandido
            
        Returns:
            Prompt com seções condicionais aplicadas
        """
        prompt_final = template_base
        
        for condicao in condicoes:
            criterio = condicao.get("criterio", True)
            template_condicional = condicao.get("template", "")
            posicao = condicao.get("posicao", "fim")  # "inicio", "fim", "antes_X"
            
            if criterio:  # Se condição é verdadeira
                if posicao == "inicio":
                    prompt_final = template_condicional + "\n\n" + prompt_final
                elif posicao == "fim":
                    prompt_final = prompt_final + "\n\n" + template_condicional
                # Outras posições podem ser implementadas conforme necessário
        
        return prompt_final
    
    def analisar_qualidade_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Analisa qualidade de um prompt e sugere melhorias
        
        Args:
            prompt: Prompt a ser analisado
            
        Returns:
            Dict com análise de qualidade
        """
        analise = {
            "score_qualidade": 0.0,
            "pontos_fortes": [],
            "melhorias_sugeridas": [],
            "estatisticas": {},
            "classificacao": "baixa"
        }
        
        # Estatísticas básicas
        palavras = len(prompt.split())
        frases = len(re.split(r'[.!?]+', prompt))
        chars = len(prompt)
        
        analise["estatisticas"] = {
            "palavras": palavras,
            "frases": frases,
            "caracteres": chars,
            "palavras_por_frase": palavras / max(frases, 1)
        }
        
        score = 0.0
        
        # Critérios de qualidade
        
        # 1. Comprimento adequado (20-40 pontos)
        if 50 <= palavras <= 500:
            score += 20
            analise["pontos_fortes"].append("Comprimento adequado")
        elif palavras < 50:
            score += 10
            analise["melhorias_sugeridas"].append("Prompt muito curto - adicionar mais contexto")
        else:
            score += 5
            analise["melhorias_sugeridas"].append("Prompt muito longo - considerar simplificar")
        
        # 2. Clareza e estrutura (20 pontos)
        if ":" in prompt or "1." in prompt or "-" in prompt:
            score += 15
            analise["pontos_fortes"].append("Bem estruturado com listas/seções")
        
        if any(palavra in prompt.lower() for palavra in ["responda", "formate", "estruture", "analise"]):
            score += 10
            analise["pontos_fortes"].append("Instruções claras de ação")
        
        # 3. Especificidade (20 pontos)
        if "JSON" in prompt or "formato" in prompt.lower():
            score += 10
            analise["pontos_fortes"].append("Especifica formato de saída")
        
        if any(palavra in prompt.lower() for palavra in ["exemplo", "template", "modelo"]):
            score += 10
            analise["pontos_fortes"].append("Inclui exemplos ou templates")
        
        # 4. Contexto e propósito (20 pontos)
        if any(palavra in prompt.lower() for palavra in ["contexto", "objetivo", "propósito", "tarefa"]):
            score += 15
            analise["pontos_fortes"].append("Fornece contexto claro")
        
        # 5. Tratamento de edge cases (20 pontos)
        if any(palavra in prompt.lower() for palavra in ["se", "caso", "quando", "exceto"]):
            score += 10
            analise["pontos_fortes"].append("Considera casos especiais")
        
        analise["score_qualidade"] = min(score, 100.0)
        
        # Classificação final
        if score >= 80:
            analise["classificacao"] = "excelente"
        elif score >= 60:
            analise["classificacao"] = "boa"
        elif score >= 40:
            analise["classificacao"] = "media"
        else:
            analise["classificacao"] = "baixa"
        
        return analise


# ================ INSTÂNCIA GLOBAL ================

# Instância global para uso conveniente
prompt_utils = PromptUtils()

# ================ FUNÇÕES DE CONVENIÊNCIA ================

def formatar_prompt(template: str, **variaveis) -> str:
    """Função de conveniência para formatação de prompt"""
    return prompt_utils.formatar_prompt_dinamico(template, variaveis)

def extrair_json_seguro(texto: str) -> Optional[Dict]:
    """Função de conveniência para extração de JSON"""
    resultado = prompt_utils.extrair_json_do_texto(texto)
    return resultado["dados"] if resultado["sucesso"] else None

def normalizar_prompt(texto: str) -> str:
    """Função de conveniência para normalização"""
    return prompt_utils.normalizar_texto(texto)

def validar_prompt(template: str, variaveis_obrigatorias: List[str]) -> bool:
    """Função de conveniência para validação rápida"""
    resultado = prompt_utils.validar_template(template, variaveis_obrigatorias)
    return resultado["valido"]

def extrair_urls_texto(texto: str) -> List[str]:
    """Função de conveniência para extrair URLs"""
    info = prompt_utils.extrair_informacoes_estruturadas(texto)
    return info["urls"]

def criar_contexto_prompt(usuario_tipo: str = "geral", 
                         dominio: str = "geral", 
                         urgencia: str = "normal",
                         formalidade: str = "media", 
                         complexidade: str = "media") -> ContextoPrompt:
    """Função de conveniência para criar contexto"""
    return ContextoPrompt(
        usuario_tipo=usuario_tipo,
        dominio=dominio,
        urgencia=urgencia,
        formalidade=formalidade,
        complexidade=complexidade
    )
