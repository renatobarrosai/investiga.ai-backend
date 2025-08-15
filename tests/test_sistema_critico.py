# test_sistema_critico.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from main import app
from src.agentes.coordenador_agentes import CoordenadorAgentes

# =============================================================================
# 1. TESTE CRÍTICO: PIPELINE COMPLETO END-TO-END
# =============================================================================

@pytest.mark.asyncio
async def test_pipeline_completo_funcionando():
    """Testa se o pipeline principal processa do início ao fim sem erros"""
    coordenador = CoordenadorAgentes()
    
    # Teste com conteúdo simples
    resultado = await coordenador.processar_completo_com_sintese(
        "O governo anunciou novas medidas econômicas"
    )
    
    # Verificações mínimas essenciais
    assert resultado is not None
    assert 'status_final' in resultado
    assert 'frontend_data' in resultado
    assert resultado['status_final'] in ['fact_check_completo', 'erro_sintese', 'sem_investigacao_para_sintese']

# =============================================================================
# 2. TESTE CRÍTICO: API ENDPOINTS FUNCIONANDO
# =============================================================================

def test_api_verificar_informacao():
    """Testa se o endpoint principal da API responde corretamente"""
    client = TestClient(app)
    
    response = client.post("/api/verify", json={
        "conteudo": "Teste de verificação de fatos"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "conclusion" in data or "error" in data

def test_api_status_sistema():
    """Testa se o endpoint de status funciona"""
    client = TestClient(app)
    
    response = client.get("/api/status")
    assert response.status_code == 200
    
    data = response.json()
    assert "agentes_carregados" in data
    assert "versao_sistema" in data

# =============================================================================
# 3. TESTE CRÍTICO: COMPONENTES INDIVIDUAIS BÁSICOS
# =============================================================================

def test_recepcionista_processa_entrada():
    """Testa se o recepcionista estrutura a entrada"""
    from src.agentes.recepcionista import ProcessadorRecepcionista
    
    recepcionista = ProcessadorRecepcionista()
    resultado = recepcionista.processar_entrada("Texto de teste com https://exemplo.com")
    
    assert resultado.conteudo_original == "Texto de teste com https://exemplo.com"
    assert len(resultado.urls_encontradas) == 1
    assert resultado.urls_encontradas[0] == "https://exemplo.com"

def test_filtro_seguranca_detecta_urls_suspeitas():
    """Testa se o filtro de segurança detecta URLs maliciosas"""
    from src.agentes.filtro_seguranca import FiltroSeguranca
    
    filtro = FiltroSeguranca()
    
    # URL segura
    resultado_seguro = filtro.avaliar_seguranca("Texto normal", ["https://google.com"])
    assert resultado_seguro.seguro == True
    
    # URL suspeita
    resultado_suspeito = filtro.avaliar_seguranca("Texto suspeito", ["https://golpe.com/premio"])
    assert resultado_suspeito.seguro == False
    assert resultado_suspeito.bloqueio_necessario == True

# =============================================================================
# 4. TESTE CRÍTICO: INVESTIGAÇÃO WEB (MOCK)
# =============================================================================

@pytest.mark.asyncio
async def test_investigacao_retorna_resultados():
    """Testa se a investigação web retorna estrutura correta"""
    from src.investigacao.coordenador_investigacao import CoordenadorInvestigacao
    
    investigador = CoordenadorInvestigacao()
    resultado = await investigador.investigar_alegacao("Teste de investigação")
    
    assert "alegacao_investigada" in resultado
    assert "status" in resultado
    assert resultado["status"] == "investigacao_concluida_com_sucesso"
    assert "avaliacoes_credibilidade" in resultado

# =============================================================================
# 5. TESTE CRÍTICO: SÍNTESE FINAL
# =============================================================================

@pytest.mark.asyncio
async def test_sintese_gera_veredicto():
    """Testa se a síntese gera um veredito válido"""
    from src.sintese.coordenador_sintese import CoordenadorSintese
    
    coordenador_sintese = CoordenadorSintese()
    
    # Mock de alegações e investigações
    alegacoes_mock = [{"texto": "teste"}]
    investigacoes_mock = [{
        "avaliacoes_credibilidade": [
            {"score_final": 0.8, "fonte": "gov.br"},
            {"score_final": 0.9, "fonte": "folha.uol.com.br"}
        ]
    }]
    
    resultado = await coordenador_sintese.processar_sintese_completa(
        alegacoes_mock, investigacoes_mock, "Contexto teste"
    )
    
    assert "conclusao_sintese" in resultado
    assert "veredicto" in resultado["conclusao_sintese"]
    assert resultado["conclusao_sintese"]["veredicto"] in [
        "VERDADEIRO", "FALSO", "PARCIALMENTE_VERDADEIRO", "INSUFICIENTE"
    ]

# =============================================================================
# 6. TESTE CRÍTICO: FORMATAÇÃO PARA FRONTEND
# =============================================================================

def test_formatacao_frontend():
    """Testa se a formatação para frontend está correta"""
    coordenador = CoordenadorAgentes()
    
    resultado_mock = {
        'sintese': {
            'conclusao_sintese': {
                'veredicto': 'VERDADEIRO',
                'confianca': 0.85,
                'reasoning': 'Teste'
            }
        },
        'investigacoes_web': [],
        'timestamp': 1234567890
    }
    
    frontend_data = coordenador._formatar_para_frontend(resultado_mock)
    
    assert "conclusion" in frontend_data
    assert "confidence" in frontend_data
    assert "reasoning" in frontend_data
    assert "sources" in frontend_data
    assert "metadata" in frontend_data
    assert frontend_data["conclusion"] == "VERDADEIRO"
    assert frontend_data["confidence"] == 0.85

# =============================================================================
# 7. TESTE CRÍTICO: CIRCUIT BREAKERS FUNCIONANDO
# =============================================================================

def test_circuit_breaker_protege_operacoes():
    """Testa se os circuit breakers protegem contra falhas"""
    from src.agentes.circuit_breakers import GerenciadorCircuitBreakers
    
    manager = GerenciadorCircuitBreakers()
    
    # Operação que funciona
    def operacao_sucesso():
        return "sucesso"
    
    resultado = manager.executar_com_protecao("teste", operacao_sucesso)
    assert resultado == "sucesso"
    
    # Operação que falha
    def operacao_falha():
        raise Exception("Erro simulado")
    
    with pytest.raises(Exception):
        manager.executar_com_protecao("teste", operacao_falha)

# =============================================================================
# 8. TESTE DE INTEGRAÇÃO: FLUXO SIMPLIFICADO
# =============================================================================

def test_fluxo_simplificado_funciona():
    """Testa se o processamento rápido funciona"""
    coordenador = CoordenadorAgentes()
    
    resultado = coordenador.processar_rapido("Teste de processamento rápido")
    
    assert "veredicto_rapido" in resultado
    assert "processamento_tipo" in resultado
    assert resultado["processamento_tipo"] == "rapido"
    assert resultado["veredicto_rapido"] in [
        "INFORMACAO_CONHECIDA", "REQUER_INVESTIGACAO", "POTENCIALMENTE_FALSO"
    ]

# =============================================================================
# FIXTURES E CONFIGURAÇÃO
# =============================================================================

@pytest.fixture
def coordenador_limpo():
    """Fixture que retorna um coordenador limpo para testes"""
    return CoordenadorAgentes()

# =============================================================================
# COMANDO PARA RODAR OS TESTES
# =============================================================================

if __name__ == "__main__":
    # Para rodar: python -m pytest test_sistema_critico.py -v
    # Para rodar async: python -m pytest test_sistema_critico.py -v --asyncio-mode=auto
    pass
