# run_tests.py - Script para executar apenas os testes críticos
"""
Script simples para executar os testes críticos do sistema.
Uso: python run_tests.py
"""
import subprocess
import sys

def executar_testes():
    """Executa apenas os testes críticos essenciais"""
    
    print("🧪 Executando testes críticos do sistema...")
    print("=" * 50)
    
    # Lista dos testes críticos na ordem de importância
    testes_criticos = [
        "tests/test_sistema_critico.py::test_api_status_sistema",
        "tests/test_sistema_critico.py::test_recepcionista_processa_entrada", 
        "tests/test_sistema_critico.py::test_filtro_seguranca_detecta_urls_suspeitas",
        "tests/test_sistema_critico.py::test_fluxo_simplificado_funciona",
        "tests/test_sistema_critico.py::test_formatacao_frontend",
        "tests/test_sistema_critico.py::test_investigacao_retorna_resultados",
        "tests/test_sistema_critico.py::test_sintese_gera_veredicto",
        "tests/test_sistema_critico.py::test_pipeline_completo_funcionando",
        "tests/test_sistema_critico.py::test_api_verificar_informacao"
    ]
    
    falhas = 0
    sucessos = 0
    
    for teste in testes_criticos:
        print(f"\n⚡ Executando: {teste.split('::')[1]}")
        try:
            resultado = subprocess.run([
                sys.executable, "-m", "pytest", teste, "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=30)
            
            if resultado.returncode == 0:
                print("✅ PASSOU")
                sucessos += 1
            else:
                print("❌ FALHOU")
                print(f"Erro: {resultado.stdout}")
                falhas += 1
                
        except subprocess.TimeoutExpired:
            print("⏰ TIMEOUT - Teste demorou mais de 30s")
            falhas += 1
        except Exception as e:
            print(f"💥 ERRO INESPERADO: {e}")
            falhas += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTADO FINAL:")
    print(f"✅ Sucessos: {sucessos}")
    print(f"❌ Falhas: {falhas}")
    print(f"📈 Taxa de sucesso: {(sucessos/(sucessos+falhas)*100):.1f}%")
    
    if falhas == 0:
        print("🎉 TODOS OS TESTES CRÍTICOS PASSARAM!")
        return True
    else:
        print("⚠️  ALGUNS TESTES CRÍTICOS FALHARAM!")
        return False

if __name__ == "__main__":
    sucesso = executar_testes()
    sys.exit(0 if sucesso else 1)

# test_smoke.py - Teste "smoke" ultra-simplificado
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

# Makefile alternativo (caso não queira usar o script Python)
# test-critical:
# 	python -m pytest tests/test_sistema_critico.py::test_api_status_sistema -v
# 	python -m pytest tests/test_sistema_critico.py::test_fluxo_simplificado_funciona -v
# 	python -m pytest tests/test_sistema_critico.py::test_formatacao_frontend -v
# 
# test-smoke:
# 	python -m pytest test_smoke.py -v
# 
# test-all:
# 	python -m pytest tests/test_sistema_critico.py -v
