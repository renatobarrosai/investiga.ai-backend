# ⚙️ Guia de Instalação - Investiga.AI

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Sistemas](https://img.shields.io/badge/Sistemas-Linux%20|%20Windows%20|%20macOS-green.svg)](#requisitos-do-sistema)
[![GPU](https://img.shields.io/badge/GPU-Opcional-orange.svg)](#configuração-gpu)

**Guia completo para configurar o sistema Investiga.AI**

</div>

---

## 📋 Índice

- [🔧 Requisitos do Sistema](#requisitos-do-sistema)
- [🚀 Instalação Rápida](#instalação-rápida)
- [🛠️ Instalação Detalhada](#instalação-detalhada)
- [🖥️ Configuração GPU](#configuração-gpu)
- [🧪 Verificação da Instalação](#verificação-da-instalação)
- [🐳 Instalação com Docker](#instalação-com-docker)
- [❌ Solução de Problemas](#solução-de-problemas)

---

## 🔧 Requisitos do Sistema

### 💻 Requisitos Mínimos

| Componente | Especificação |
|------------|---------------|
| **🐍 Python** | 3.11.0 ou superior |
| **💾 RAM** | 8GB (16GB recomendado) |
| **💿 Armazenamento** | 20GB livres |
| **🌐 Internet** | Conexão estável para investigação web |
| **🖥️ OS** | Linux, Windows 10+, macOS 10.15+ |

### 🚀 Requisitos Recomendados

| Componente | Especificação |
|------------|---------------|
| **🖥️ CPU** | 8+ cores, 3.0GHz+ |
| **💾 RAM** | 32GB+ |
| **🎮 GPU** | NVIDIA GTX 1080+ / AMD equivalente |
| **💿 SSD** | 50GB+ espaço livre |
| **🌐 Banda** | 100Mbps+ |

### 📚 Dependências do Sistema

#### 🐧 Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y build-essential git curl
sudo apt install -y libjpeg-dev zlib1g-dev  # Para Pillow
```

#### 🪟 Windows
```powershell
# Instale Python 3.11+ do site oficial
# Instale Git e Visual Studio Build Tools
winget install Python.Python.3.11
winget install Git.Git
winget install Microsoft.VisualStudio.2022.BuildTools
```

#### 🍎 macOS
```bash
# Instale Homebrew se não tiver
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instale Python e dependências
brew install python@3.11 git
```

---

## 🚀 Instalação Rápida

### 📥 Clone e Configure

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/investiga-ai.git
cd investiga-ai

# 2. Crie ambiente virtual
python3.11 -m venv venv

# 3. Ative o ambiente
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 4. Instale dependências
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verifique a instalação
./tests/executar_teste_fase1.sh
```

### ✅ Verificação Rápida

```bash
# Teste básico
python -c "
from src.agentes.coordenador_agentes import CoordenadorAgentes
coordenador = CoordenadorAgentes()
resultado = coordenador.processar_rapido('Teste de instalação')
print('✅ Instalação bem-sucedida!' if 'veredicto_rapido' in resultado else '❌ Erro na instalação')
"
```

---

## 🛠️ Instalação Detalhada

### 1️⃣ Preparação do Ambiente

#### 📁 Estrutura de Diretórios
```bash
# Crie a estrutura necessária
mkdir -p investiga-ai/{models,cache,logs,config,data}
cd investiga-ai

# Estrutura esperada:
# investiga-ai/
# ├── src/           # Código fonte
# ├── tests/         # Testes
# ├── models/        # Modelos de IA
# ├── cache/         # Cache do sistema
# ├── logs/          # Logs de execução
# ├── config/        # Configurações
# └── data/          # Dados temporários
```

#### 🐍 Ambiente Virtual Detalhado
```bash
# Verifique a versão do Python
python3.11 --version  # Deve ser 3.11.0+

# Crie ambiente virtual com nome específico
python3.11 -m venv venv-investiga-ai

# Ative o ambiente
source venv-investiga-ai/bin/activate  # Linux/macOS
# venv-investiga-ai\Scripts\activate  # Windows

# Confirme a ativação
which python  # Deve apontar para o venv
python --version  # Deve ser 3.11+
```

### 2️⃣ Instalação de Dependências

#### 📦 Dependências Base
```bash
# Atualize pip e setuptools
pip install --upgrade pip setuptools wheel

# Instale dependências em ordem
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers[torch]
pip install fastapi uvicorn[standard]
pip install pillow beautifulsoup4 requests
pip install psutil GPUtil
pip install pytest pytest-asyncio
pip install numpy scikit-learn
```

#### 🎮 Dependências GPU (Opcional)
```bash
# Para NVIDIA GPU (CUDA)
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verifique instalação GPU
python -c "
import torch
print(f'CUDA disponível: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPUs detectadas: {torch.cuda.device_count()}')
    print(f'GPU atual: {torch.cuda.get_device_name()}')
"
```

### 3️⃣ Configuração de Modelos

#### 📚 Modelos Pré-treinados
```bash
# Crie configuração de modelos
cat > config/modelos.json << 'EOF'
{
  "gemma-2b-recepcionista": {
    "nome": "gemma-2b-recepcionista",
    "caminho": "models/gemma-2b-it-quantized",
    "tipo_modelo": "llm",
    "memoria_necessaria_mb": 2048.0,
    "quantizacao": "awq",
    "especialidade": "recepcionista",
    "versao": "1.0",
    "prioridade": 8,
    "dependencias": [],
    "configuracoes": {
      "max_tokens": 512,
      "temperature": 0.1
    }
  },
  "llama-3-8b-deconstrutor": {
    "nome": "llama-3-8b-deconstrutor", 
    "caminho": "models/llama-3-8b-quantized",
    "tipo_modelo": "llm",
    "memoria_necessaria_mb": 6144.0,
    "quantizacao": "gptq",
    "especialidade": "deconstrutor",
    "versao": "1.0",
    "prioridade": 9,
    "dependencias": [],
    "configuracoes": {
      "max_tokens": 1024,
      "temperature": 0.2
    }
  },
  "phi-3-vision-classificador": {
    "nome": "phi-3-vision-classificador",
    "caminho": "models/phi-3-vision-128k",
    "tipo_modelo": "vision",
    "memoria_necessaria_mb": 4096.0,
    "quantizacao": "nenhuma",
    "especialidade": "classificador",
    "versao": "1.0",
    "prioridade": 7,
    "dependencias": [],
    "configuracoes": {
      "max_tokens": 256
    }
  }
}
EOF
```

### 4️⃣ Configuração do Sistema

#### ⚙️ Arquivo de Configuração Principal
```bash
# Crie configuração principal
cat > config/sistema.yaml << 'EOF'
sistema:
  nome: "Investiga.AI"
  versao: "1.0.0"
  
gpu:
  intervalo_atualizacao: 1.0
  threshold_memoria_critico: 90.0
  threshold_memoria_alto: 75.0
  threshold_utilizacao_alto: 85.0
  margem_seguranca_memoria: 512.0

scheduler:
  tempo_inatividade_descarregar: 300.0
  max_modelos_simultaneos: 3

filas:
  max_concurrent: 3
  timeout_padrao: 300.0

logging:
  nivel: "INFO"
  arquivo: "logs/sistema.log"
  formato: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
EOF
```

#### 🔐 Variáveis de Ambiente
```bash
# Crie arquivo .env
cat > .env << 'EOF'
# Configurações do Sistema
PYTHONPATH=./src
LOG_LEVEL=INFO
CACHE_DIR=./cache
MODELS_DIR=./models

# Configurações GPU
GPU_THRESHOLD_CRITICO=90.0
GPU_THRESHOLD_ALTO=75.0
SCHEDULER_TEMPO_INATIVIDADE=300.0
FILAS_MAX_CONCURRENT=3

# Configurações da API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]

# Configurações de Debug (opcional)
DEBUG=false
VERBOSE=false
EOF
```

---

## 🖥️ Configuração GPU

### 🎮 NVIDIA GPU Setup

#### 🔧 Instalação CUDA
```bash
# Ubuntu/Debian
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda-repo-ubuntu2204-12-1-local_12.1.0-530.30.02-1_amd64.deb
sudo dpkg -i cuda-repo-ubuntu2204-12-1-local_12.1.0-530.30.02-1_amd64.deb
sudo cp /var/cuda-repo-ubuntu2204-12-1-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda
```

#### 🧪 Verificação GPU
```bash
# Teste detalhado da GPU
python << 'EOF'
import torch
import GPUtil

print("=== Informações da GPU ===")

# PyTorch
print(f"PyTorch versão: {torch.__version__}")
print(f"CUDA disponível: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Versão CUDA: {torch.version.cuda}")
    print(f"Número de GPUs: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        gpu = torch.cuda.get_device_properties(i)
        print(f"GPU {i}: {gpu.name}")
        print(f"  Memória total: {gpu.total_memory / 1024**3:.1f} GB")
        print(f"  Multiprocessadores: {gpu.multi_processor_count}")

# GPUtil
print("\n=== Status atual das GPUs ===")
gpus = GPUtil.getGPUs()
for gpu in gpus:
    print(f"GPU {gpu.id}: {gpu.name}")
    print(f"  Carga: {gpu.load*100:.1f}%")
    print(f"  Memória: {gpu.memoryUsed}/{gpu.memoryTotal} MB ({gpu.memoryUtil*100:.1f}%)")
    print(f"  Temperatura: {gpu.temperature}°C")

EOF
```

---

## 🧪 Verificação da Instalação

### 🔬 Testes Automatizados

#### 📋 Suite de Testes Completa
```bash
# Execute todos os testes em sequência
echo "🧪 Executando testes completos..."

# Fase 1: Infraestrutura
echo "📊 Fase 1: Infraestrutura..."
./tests/executar_teste_fase1.sh

# Fase 2: Agentes IA  
echo "🤖 Fase 2: Agentes IA..."
./tests/executar_teste_fase2.sh

# Fase 3: Cache e Reasoning
echo "🧠 Fase 3: Cache e Reasoning..."
./tests/executar_teste_fase3.sh

# Fase 4: Investigação Web
echo "🌐 Fase 4: Investigação Web..."
./tests/executar_teste_fase4.sh

# Fase 5: Síntese Final
echo "🎯 Fase 5: Síntese Final..."
./tests/executar_teste_fase5.sh

# Fase 6: Orquestração
echo "🎛️ Fase 6: Orquestração..."
./tests/executar_teste_fase6.sh

echo "✅ Todos os testes concluídos!"
```

#### 🎯 Teste de Funcionalidade Principal
```bash
# Teste funcional completo
python << 'EOF'
import asyncio
from src.agentes.coordenador_agentes import CoordenadorAgentes

async def teste_completo():
    print("🔬 Teste Funcional do Investiga.AI")
    print("=" * 50)
    
    coordenador = CoordenadorAgentes()
    
    # Teste 1: Processamento rápido
    print("🚀 Teste 1: Processamento Rápido")
    resultado_rapido = coordenador.processar_rapido(
        "O governo anunciou investimentos em infraestrutura"
    )
    print(f"✅ Resultado: {resultado_rapido['veredicto_rapido']}")
    
    # Teste 2: Processamento completo
    print("\n🌐 Teste 2: Processamento Completo")
    resultado_completo = await coordenador.processar_completo_com_sintese(
        "Ministério da Saúde anuncia nova campanha de vacinação"
    )
    
    if resultado_completo.get('sintese'):
        conclusao = resultado_completo['sintese']['conclusao_sintese']
        print(f"✅ Veredicto: {conclusao['veredicto']}")
        print(f"✅ Confiança: {conclusao['confianca']:.2f}")
    else:
        print("✅ Processamento concluído (síntese simplificada)")
    
    # Teste 3: Status do sistema
    print("\n📊 Teste 3: Status do Sistema")
    status = coordenador.obter_status_completo()
    print(f"✅ Agentes carregados: {len(status['agentes_carregados'])}")
    print(f"✅ Cache entries: {status['cache_stats']['entradas_cache']}")
    
    print("\n🎉 Todos os testes funcionais passaram!")

# Execute o teste
asyncio.run(teste_completo())
EOF
```

### 🌐 Teste da API

#### 🚀 Iniciar Servidor
```bash
# Terminal 1: Inicie o servidor
python main.py

# Aguarde a mensagem:
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### 🧪 Teste Endpoints
```bash
# Terminal 2: Teste a API

# Health check
curl http://localhost:8000/api/health

# Status do sistema
curl http://localhost:8000/api/status

# Verificação simples
curl -X POST "http://localhost:8000/api/verify" \
     -H "Content-Type: application/json" \
     -d '{
       "conteudo": "Teste de verificação via API"
     }'

# Upload de arquivo (se tiver imagem)
curl -X POST "http://localhost:8000/api/verify-file" \
     -F "file=@tests/data/imagem_teste.jpg"
```

---

## 🐳 Instalação com Docker

### 📋 Dockerfile
```dockerfile
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY . .

# Criar diretórios necessários
RUN mkdir -p models cache logs config data

# Expor porta da API
EXPOSE 8000

# Comando padrão
CMD ["python", "main.py"]
```

### 🐳 Docker Compose
```yaml
version: '3.8'

services:
  investiga-ai:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./cache:/app/cache
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - PYTHONPATH=/app/src
      - LOG_LEVEL=INFO
    restart: unless-stopped
    
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

networks:
  default:
    name: investiga-ai-network
```

### 🚀 Comandos Docker
```bash
# Build e execução
docker-compose up --build -d

# Verificar logs
docker-compose logs -f investiga-ai

# Teste
curl http://localhost:8000/api/health

# Parar serviços
docker-compose down
```

---

## ❌ Solução de Problemas

### 🔧 Problemas Comuns

#### 🐍 Erro de Versão Python
```bash
# Erro: "python3.11: command not found"

# Solução Ubuntu/Debian:
sudo apt install python3.11 python3.11-venv

# Solução macOS:
brew install python@3.11

# Solução Windows:
# Baixe Python 3.11+ do site oficial
```

#### 📦 Erro de Dependências
```bash
# Erro: "Failed building wheel for X"

# Solução Linux:
sudo apt install build-essential python3.11-dev

# Solução macOS:
xcode-select --install

# Solução Windows:
# Instale Visual Studio Build Tools
```

#### 🎮 Erro de GPU
```bash
# Erro: "CUDA not available"

# Verificar instalação:
nvidia-smi  # Deve mostrar driver NVIDIA

# Reinstalar PyTorch com CUDA:
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

#### 💾 Erro de Memória
```bash
# Erro: "OutOfMemoryError"

# Soluções:
# 1. Reduza max_concurrent em config/sistema.yaml
# 2. Use modelos quantizados menores
# 3. Aumente swap do sistema
# 4. Use GPU com mais memória
```

### 📋 Checklist de Diagnóstico

```bash
# Execute este script para diagnóstico completo
python << 'EOF'
import sys
import torch
import importlib.util

def check_component(name, module_name):
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            print(f"✅ {name}: OK")
            return True
        else:
            print(f"❌ {name}: Não encontrado")
            return False
    except ImportError:
        print(f"❌ {name}: Erro de importação")
        return False

print("🔬 Diagnóstico do Sistema")
print("=" * 40)

# Verificações básicas
print(f"🐍 Python: {sys.version}")
print(f"📍 Executável: {sys.executable}")

# Verificações de módulos
checks = [
    ("PyTorch", "torch"),
    ("Transformers", "transformers"),
    ("FastAPI", "fastapi"),
    ("Pillow", "PIL"),
    ("BeautifulSoup", "bs4"),
    ("Requests", "requests"),
    ("psutil", "psutil"),
    ("GPUtil", "GPUtil"),
    ("pytest", "pytest"),
    ("numpy", "numpy"),
    ("sklearn", "sklearn")
]

all_ok = True
for name, module in checks:
    if not check_component(name, module):
        all_ok = False

# Verificação GPU
print(f"\n🎮 GPU CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   Dispositivos: {torch.cuda.device_count()}")

# Verificação dos módulos do projeto
project_modules = [
    ("Coordenador Agentes", "src.agentes.coordenador_agentes"),
    ("Investigação", "src.investigacao.coordenador_investigacao"),
    ("Síntese", "src.sintese.coordenador_sintese")
]

print("\n🤖 Módulos do Projeto:")
for name, module in project_modules:
    check_component(name, module)

print(f"\n{'🎉 Sistema OK!' if all_ok else '❌ Problemas encontrados'}")
EOF
```

### 🆘 Suporte

Se os problemas persistirem:

1. **📧 Issues**: [Abrir issue no GitHub](../../issues/new)
2. **💬 Discussões**: [Fórum de discussões](../../discussions)  
3. **📖 Documentação**: [FAQ](faq.md)
4. **🔧 Reset completo**:
   ```bash
   # Remove ambiente e recria
   rm -rf venv-investiga-ai
   python3.11 -m venv venv-investiga-ai
   source venv-investiga-ai/bin/activate
   pip install -r requirements.txt
   ```

---

## ✅ Próximos Passos

Após a instalação bem-sucedida:

1. **📖 [Configuração Avançada](configuracao.md)** - Personalize o sistema
2. **🌐 [Referência da API](api.md)** - Integre com sua aplicação
3. **🏗️ [Arquitetura](arquitetura.md)** - Entenda o funcionamento interno
4. **🤝 [Contribuição](contribuicao.md)** - Ajude a melhorar o projeto

---

<div align="center">

**⚙️ Sistema configurado e pronto para combater a desinformação!**

[![Voltar ao README](https://img.shields.io/badge/←_Voltar-README-blue.svg)](../README.md)
[![Próximo: Configuração](https://img.shields.io/badge/Próximo→-Configuração-green.svg)](configuracao.md)

</div>