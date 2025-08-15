"""
Teste de fumaça - verifica se o sistema básico está funcionando
"""
def test_smoke_importacoes():
    """Testa se as importações básicas funcionam"""
    try:
        from src.agentes.coordenador_agentes import CoordenadorAgentes
        from main import app
        assert True
    except ImportError as e:
        assert False, f"Erro de importação: {e}"

def test_smoke_coordenador_instancia():
    """Testa se o coordenador instancia sem erros"""
    from src.agentes.coordenador_agentes import CoordenadorAgentes
    
    coordenador = CoordenadorAgentes()
    assert coordenador is not None
    assert len(coordenador.agentes) > 0

def test_smoke_api_criada():
    """Testa se a API FastAPI é criada"""
    from main import app
    assert app is not None
