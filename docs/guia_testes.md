# Guia Prático - Testes Críticos

## Setup Rápido

```bash
# 1. Instalar dependências de teste
pip install pytest pytest-asyncio httpx

# 2. Criar os arquivos de teste na raiz do projeto
# (usar os códigos dos artifacts anteriores)
```

## Execução por Prioridade

### 🚀 Teste Instantâneo (30s)
```bash
python -m pytest test_smoke.py -v
```
**O que testa**: Importações e instanciações básicas

### ⚡ Testes Críticos Essenciais (2-3 min)
```bash
python run_tests.py
```
**O que testa**: Pipeline principal, API, componentes críticos

### 🔍 Teste Completo (5-10 min)
```bash
python -m pytest test_sistema_critico.py -v
```
**O que testa**: Todos os componentes em detalhe

## Checklist de Validação

### ✅ Sistema Básico Funcionando
- [ ] Importações não falham
- [ ] Coordenador instancia
- [ ] API responde `/api/status`

### ✅ Pipeline Principal
- [ ] Recepcionista processa entrada
- [ ] Filtro segurança detecta ameaças  
- [ ] Fluxo simplificado funciona
- [ ] Formatação frontend correta

### ✅ Componentes Avançados
- [ ] Investigação web retorna dados
- [ ] Síntese gera veredito
- [ ] Pipeline completo end-to-end
- [ ] API principal `/api/verify`

## Solução de Problemas

### ❌ Falha em Importações
```bash
# Verificar estrutura de pastas
ls -la src/agentes/
ls -la src/investigacao/
ls -la src/sintese/

# Adicionar __init__.py se necessário
touch src/__init__.py
```

### ❌ Falha em Async
```bash
# Instalar versão correta
pip install pytest-asyncio==0.21.1

# Rodar com flag específica
python -m pytest --asyncio-mode=auto
```

### ❌ Falha na API
```bash
# Testar isoladamente
python -c "from main import app; print('API OK')"

# Verificar dependências FastAPI
pip install fastapi uvicorn
```

## Automatização CI/CD

### GitHub Actions (.github/workflows/tests.yml)
```yaml
name: Testes Críticos
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install -r requirements_test.txt
    - run: python run_tests.py
```

### Docker (para ambiente isolado)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install pytest pytest-asyncio httpx
CMD ["python", "run_tests.py"]
```

## Interpretação dos Resultados

### 🎉 **100% Sucessos**
Sistema pronto para produção

### 📊 **80-99% Sucessos** 
Sistema funcional, investigar falhas

### ⚠️ **50-79% Sucessos**
Problemas sérios, revisar código

### 🚨 **<50% Sucessos**
Sistema quebrado, debug necessário

## Testes Manuais Rápidos

### Teste API Manual
```bash
# Terminal 1: Subir API
uvicorn main:app --reload

# Terminal 2: Testar endpoint
curl -X POST "http://localhost:8000/api/verify" \
  -H "Content-Type: application/json" \
  -d '{"conteudo": "Teste manual"}'
```

### Teste Pipeline Manual
```python
from src.agentes.coordenador_agentes import CoordenadorAgentes
import asyncio

async def teste_manual():
    coord = CoordenadorAgentes()
    resultado = await coord.processar_completo_com_sintese("Teste")
    print(f"Status: {resultado.get('status_final')}")
    print(f"Veredito: {resultado.get('veredicto_final')}")

asyncio.run(teste_manual())
```
