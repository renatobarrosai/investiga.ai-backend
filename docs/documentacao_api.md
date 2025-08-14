# 🌐 API Reference - Investiga.AI

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-blue.svg)](#swagger-ui)
[![WebSocket](https://img.shields.io/badge/WebSocket-Suportado-orange.svg)](#websocket)
[![REST](https://img.shields.io/badge/REST-API-purple.svg)](#endpoints)

**API REST completa para verificação automatizada de fatos**

[📖 Endpoints](#endpoints) • [🔌 WebSocket](#websocket) • [📊 Exemplos](#exemplos) • [🛠️ SDKs](#sdks)

</div>

---

## 📋 Índice

- [🚀 Início Rápido](#início-rápido)
- [🔗 Endpoints](#endpoints)
- [🔌 WebSocket](#websocket)
- [📊 Modelos de Dados](#modelos-de-dados)
- [💡 Exemplos de Uso](#exemplos-de-uso)
- [🛠️ SDKs](#sdks)
- [❌ Códigos de Erro](#códigos-de-erro)
- [🔐 Autenticação](#autenticação)

---

## 🚀 Início Rápido

### 🌐 URL Base
```
http://localhost:8000
```

### 📋 Swagger UI
```
http://localhost:8000/docs
```

### 🧪 Health Check
```bash
curl http://localhost:8000/api/health
```

### ⚡ Verificação Simples
```bash
curl -X POST "http://localhost:8000/api/verify" \
     -H "Content-Type: application/json" \
     -d '{"conteudo": "O governo anunciou novos investimentos"}'
```

---

## 🔗 Endpoints

### 🏥 Health & Status

#### `GET /api/health`
**Descrição**: Verifica se a API está funcionando

**Resposta**:
```json
{
  "status": "healthy",
  "service": "check-cl-api"
}
```

**Códigos de Status**:
- `200`: Serviço funcionando
- `503`: Serviço indisponível

---

#### `GET /api/status`
**Descrição**: Status detalhado do sistema

**Resposta**:
```json
{
  "agentes_carregados": ["recepcionista", "classificador", "filtro_seguranca", "deconstrutor"],
  "circuit_breakers": {},
  "cache_stats": {
    "entradas_cache": 42,
    "threshold_similaridade": 0.8
  },
  "agentes_disponiveis": {
    "recepcionista": true,
    "classificador": true,
    "filtro_seguranca": true,
    "deconstrutor": true
  },
  "componentes_especializados": {
    "investigador_web": true,
    "sintetizador": true
  },
  "timestamp": 1703024400.123,
  "versao_sistema": "1.0.0",
  "suporte_frontend": {
    "websocket_callbacks": true,
    "upload_arquivos": true,
    "processamento_multimodal": true
  }
}
```

---

### 🔍 Verificação de Fatos

#### `POST /api/verify`
**Descrição**: Verificação completa de conteúdo textual

**Parâmetros**:
```json
{
  "conteudo": "string",      // Obrigatório: texto a ser verificado
  "imagem": "string|null"    // Opcional: imagem em base64
}
```

**Exemplo de Requisição**:
```bash
curl -X POST "http://localhost:8000/api/verify" \
     -H "Content-Type: application/json" \
     -d '{
       "conteudo": "O governo gastou R$ 100 bilhões em infraestrutura em 2024",
       "imagem": null
     }'
```

**Exemplo de Resposta**:
```json
{
  "conclusion": "VERDADEIRO",
  "confidence": 0.85,
  "reasoning": "A informação foi confirmada por fontes governamentais oficiais...",
  "summary": "Investimentos confirmados em múltiplas fontes autoritativas",
  "verdict_color": "green",
  "sources": [
    {
      "name": "gov.br",
      "url": "https://www.gov.br/exemplo",
      "authority": 0.95,
      "excerpt": "Confirmação oficial dos investimentos...",
      "credibility_score": 0.9
    }
  ],
  "metadata": {
    "processing_time": 28.5,
    "total_sources": 3,
    "timestamp": 1703024400.123,
    "pipeline_used": "completo_com_sintese"
  },
  "stages_completed": [
    "recepcionista",
    "classificador", 
    "seguranca",
    "deconstrutor",
    "investigacao",
    "sintese",
    "apresentacao"
  ]
}
```

**Códigos de Status**:
- `200`: Verificação concluída
- `400`: Dados inválidos
- `500`: Erro interno

---

#### `POST /api/verify-file`
**Descrição**: Verificação de arquivos (imagem, áudio, vídeo)

**Parâmetros**:
```
file: File (multipart/form-data)
```

**Tipos Suportados**:
- **🖼️ Imagens**: PNG, JPG, JPEG, GIF, WEBP
- **🎵 Áudio**: MP3, WAV, M4A, FLAC
- **🎬 Vídeo**: MP4, AVI, MOV, MKV

**Exemplo de Requisição**:
```bash
curl -X POST "http://localhost:8000/api/verify-file" \
     -F "file=@documento.jpg"
```

**Resposta**: Igual ao `/api/verify`

---

### ⚡ Verificação em Tempo Real

#### `POST /api/verify-realtime/{client_id}`
**Descrição**: Verificação com updates em tempo real via WebSocket

**Parâmetros de URL**:
- `client_id`: ID único do cliente conectado via WebSocket

**Parâmetros do Body**:
```json
{
  "conteudo": "string",
  "imagem": "string|null"
}
```

**Fluxo**:
1. Conecte-se ao WebSocket em `/ws/{client_id}`
2. Faça POST para `/api/verify-realtime/{client_id}`
3. Receba updates em tempo real via WebSocket
4. Receba resultado final via WebSocket

**Resposta**:
```json
{
  "status": "completed",
  "client_id": "abc123"
}
```

---

## 🔌 WebSocket

### 🌐 Conexão
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/meu-client-id');
```

### 📨 Tipos de Mensagem

#### Progress Update
```json
{
  "type": "progress",
  "station": "recepcionista",
  "description": "Organizando informações..."
}
```

#### Resultado Final  
```json
{
  "type": "result",
  "data": {
    "conclusion": "VERDADEIRO",
    "confidence": 0.85,
    // ... resto dos dados
  }
}
```

#### Erro
```json
{
  "type": "error", 
  "message": "Erro ao processar arquivo"
}
```

### 🎯 Estações de Progresso

| Estação | Descrição |
|---------|-----------|
| `upload` | Processando upload de arquivo |
| `recepcionista` | Organizando informações |
| `classificador` | Analisando tipo de conteúdo |
| `seguranca` | Verificando segurança |
| `deconstrutor` | Extraindo alegações |
| `investigacao` | Investigando na web |
| `sintese` | Analisando evidências |
| `apresentacao` | Preparando resultado |
| `concluido` | Verificação finalizada |

---

## 📊 Modelos de Dados

### 🔍 VerifyRequest
```typescript
interface VerifyRequest {
  conteudo: string;        // Texto a ser verificado
  imagem?: string;         // Imagem em base64 (opcional)
}
```

### ✅ VerifyResponse
```typescript
interface VerifyResponse {
  conclusion: "VERDADEIRO" | "FALSO" | "PARCIALMENTE_VERDADEIRO" | "INCONCLUSIVO";
  confidence: number;      // 0.0 a 1.0
  reasoning: string;       // Explicação do resultado
  summary: string;         // Resumo executivo
  verdict_color: "green" | "red" | "orange" | "gray";
  sources: Source[];       // Fontes consultadas
  metadata: Metadata;      // Metadados do processamento
  stages_completed: string[]; // Etapas concluídas
}
```

### 📚 Source
```typescript
interface Source {
  name: string;           // Nome da fonte
  url: string;            // URL da fonte
  authority: number;      // Autoridade da fonte (0.0 a 1.0)
  excerpt: string;        // Trecho relevante
  credibility_score: number; // Score de credibilidade
}
```

### 📈 Metadata
```typescript
interface Metadata {
  processing_time: number;  // Tempo de processamento (segundos)
  total_sources: number;    // Total de fontes consultadas
  timestamp: number;        // Timestamp Unix
  pipeline_used: string;    // Pipeline utilizado
}
```

### 🏥 HealthResponse
```typescript
interface HealthResponse {
  status: "healthy" | "unhealthy";
  service: string;
}
```

### 📊 StatusResponse
```typescript
interface StatusResponse {
  agentes_carregados: string[];
  circuit_breakers: Record<string, any>;
  cache_stats: {
    entradas_cache: number;
    threshold_similaridade: number;
  };
  agentes_disponiveis: Record<string, boolean>;
  componentes_especializados: Record<string, boolean>;
  timestamp: number;
  versao_sistema: string;
  suporte_frontend: {
    websocket_callbacks: boolean;
    upload_arquivos: boolean;
    processamento_multimodal: boolean;
  };
}
```

---

## 💡 Exemplos de Uso

### 🐍 Python
```python
import requests
import json

# Configuração
BASE_URL = "http://localhost:8000"

def verificar_alegacao(conteudo, imagem=None):
    """Verifica uma alegação textual"""
    payload = {
        "conteudo": conteudo,
        "imagem": imagem
    }
    
    response = requests.post(
        f"{BASE_URL}/api/verify",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

# Exemplo de uso
resultado = verificar_alegacao(
    "O Brasil é o maior país da América do Sul"
)

print(f"Veredicto: {resultado['conclusion']}")
print(f"Confiança: {resultado['confidence']:.2f}")
print(f"Fontes: {len(resultado['sources'])}")
```

### 🟨 JavaScript/Node.js
```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';

async function verificarAlegacao(conteudo, imagem = null) {
    try {
        const response = await axios.post(`${BASE_URL}/api/verify`, {
            conteudo: conteudo,
            imagem: imagem
        });
        
        return response.data;
    } catch (error) {
        console.error('Erro na verificação:', error.response?.data || error.message);
        throw error;
    }
}

// Exemplo de uso
(async () => {
    const resultado = await verificarAlegacao(
        'O governo anunciou novos investimentos em educação'
    );
    
    console.log(`Veredicto: ${resultado.conclusion}`);
    console.log(`Confiança: ${resultado.confidence}`);
    console.log(`Fontes consultadas: ${resultado.metadata.total_sources}`);
})();
```

### 🌐 JavaScript/Browser com WebSocket
```javascript
class InvestigaAI {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.ws = null;
        this.clientId = Math.random().toString(36).substr(2, 9);
    }
    
    // Conectar WebSocket
    connect() {
        const wsUrl = this.baseUrl.replace('http', 'ws') + `/ws/${this.clientId}`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        return new Promise((resolve) => {
            this.ws.onopen = () => resolve();
        });
    }
    
    // Verificar com updates em tempo real
    async verificarTempoReal(conteudo, onProgress) {
        this.onProgress = onProgress;
        
        const response = await fetch(`${this.baseUrl}/api/verify-realtime/${this.clientId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conteudo })
        });
        
        return response.json();
    }
    
    // Manipular mensagens do WebSocket
    handleMessage(data) {
        switch (data.type) {
            case 'progress':
                if (this.onProgress) {
                    this.onProgress(data.station, data.description);
                }
                break;
                
            case 'result':
                if (this.onResult) {
                    this.onResult(data.data);
                }
                break;
                
            case 'error':
                if (this.onError) {
                    this.onError(data.message);
                }
                break;
        }
    }
}

// Uso
const api = new InvestigaAI();

api.connect().then(async () => {
    await api.verificarTempoReal(
        'Informação a ser verificada',
        (station, description) => {
            console.log(`📍 ${station}: ${description}`);
        }
    );
    
    api.onResult = (resultado) => {
        console.log('🎯 Resultado final:', resultado);
    };
});
```

### 🦀 Rust
```rust
use reqwest;
use serde_json::{json, Value};
use std::error::Error;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let client = reqwest::Client::new();
    
    let payload = json!({
        "conteudo": "O Brasil tem mais de 200 milhões de habitantes"
    });
    
    let response = client
        .post("http://localhost:8000/api/verify")
        .json(&payload)
        .send()
        .await?;
    
    let resultado: Value = response.json().await?;
    
    println!("Veredicto: {}", resultado["conclusion"]);
    println!("Confiança: {}", resultado["confidence"]);
    
    Ok(())
}
```

### 🐹 Go
```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type VerifyRequest struct {
    Conteudo string  `json:"conteudo"`
    Imagem   *string `json:"imagem,omitempty"`
}

type VerifyResponse struct {
    Conclusion string  `json:"conclusion"`
    Confidence float64 `json:"confidence"`
    Reasoning  string  `json:"reasoning"`
}

func verificarAlegacao(conteudo string) (*VerifyResponse, error) {
    payload := VerifyRequest{Conteudo: conteudo}
    jsonData, _ := json.Marshal(payload)
    
    resp, err := http.Post(
        "http://localhost:8000/api/verify",
        "application/json",
        bytes.NewBuffer(jsonData),
    )
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var resultado VerifyResponse
    err = json.NewDecoder(resp.Body).Decode(&resultado)
    return &resultado, err
}

func main() {
    resultado, err := verificarAlegacao("O Sol é uma estrela")
    if err != nil {
        panic(err)
    }
    
    fmt.Printf("Veredicto: %s\n", resultado.Conclusion)
    fmt.Printf("Confiança: %.2f\n", resultado.Confidence)
}
```

---

## 🛠️ SDKs

### 📦 SDK Python Oficial

```bash
pip install investiga-ai-sdk
```

```python
from investiga_ai import InvestigaAI

# Inicializar cliente
client = InvestigaAI(base_url="http://localhost:8000")

# Verificação simples
resultado = client.verificar("Alegação a ser verificada")

# Verificação com callback de progresso
async def on_progress(station, description):
    print(f"{station}: {description}")

resultado = await client.verificar_async(
    "Alegação complexa",
    on_progress=on_progress
)

# Upload de arquivo
with open("documento.pdf", "rb") as f:
    resultado = client.verificar_arquivo(f)
```

### 📦 SDK JavaScript/TypeScript

```bash
npm install @investiga-ai/sdk
```

```typescript
import { InvestigaAI } from '@investiga-ai/sdk';

const client = new InvestigaAI({
    baseUrl: 'http://localhost:8000'
});

// Verificação simples
const resultado = await client.verificar('Alegação para verificar');

// Com WebSocket
await client.conectar();
const resultado = await client.verificarTempoReal(
    'Alegação complexa',
    (station, description) => {
        console.log(`${station}: ${description}`);
    }
);
```

---

## ❌ Códigos de Erro

### 🔢 Códigos HTTP

| Código | Significado | Descrição |
|--------|-------------|-----------|
| `200` | ✅ Sucesso | Requisição processada com sucesso |
| `400` | ❌ Bad Request | Dados de entrada inválidos |
| `422` | ❌ Validation Error | Erro de validação dos dados |
| `429` | ⏱️ Rate Limit | Muitas requisições |
| `500` | 🔥 Internal Error | Erro interno do servidor |
| `503` | 🚫 Service Unavailable | Serviço temporariamente indisponível |

### 📋 Estrutura de Erro

```json
{
  "detail": "Descrição do erro",
  "type": "validation_error",
  "errors": [
    {
      "loc": ["conteudo"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

### 🔧 Tratamento de Erros

```python
import requests
from requests.exceptions import RequestException

try:
    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()
    
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        print("Dados inválidos:", e.response.json())
    elif e.response.status_code == 429:
        print("Rate limit atingido, aguarde")
    elif e.response.status_code == 500:
        print("Erro interno do servidor")
        
except requests.exceptions.ConnectionError:
    print("Erro de conexão com a API")
    
except requests.exceptions.Timeout:
    print("Timeout na requisição")
```

---

## 🔐 Autenticação

### 🔑 API Key (Futuro)
```bash
curl -X POST "http://localhost:8000/api/verify" \
     -H "Authorization: Bearer sua-api-key" \
     -H "Content-Type: application/json" \
     -d '{"conteudo": "Texto a verificar"}'
```

### 🛡️ Rate Limiting (Futuro)
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1703024400
```

---

## 📊 Monitoramento

### 📈 Métricas Disponíveis

- **⚡ Latência**: Tempo de resposta por endpoint
- **📊 Throughput**: Requisições por minuto
- **❌ Taxa de Erro**: Percentual de falhas
- **🎯 Cache Hit**: Taxa de acerto do cache
- **🖥️ Recursos**: CPU, memória, GPU

### 📋 Health Check Detalhado

```bash
curl http://localhost:8000/api/status | jq
```

### 🔍 Logs de Auditoria

Todas as verificações são logadas com:
- Timestamp da requisição
- Conteúdo verificado (hash)
- Resultado obtido
- Fontes consultadas
- Tempo de processamento

---

## 🚀 Performance

### ⚡ Benchmarks Típicos

| Operação | Latência | Throughput |
|----------|----------|------------|
| **Health Check** | ~10ms | 10,000/min |
| **Verificação Rápida** | ~1s | 60/min |
| **Verificação Completa** | ~30s | 100/hora |
| **Upload Arquivo** | ~45s | 80/hora |

### 🎯 Otimizações

- **💾 Cache inteligente** com hit rate ~60%
- **🔄 Pool de conexões** reutilizáveis
- **🧵 Processamento paralelo** para múltiplas requisições
- **🎮 Aceleração GPU** quando disponível

---

## 🔧 Configuração da API

### ⚙️ Variáveis de Ambiente

```bash
# Servidor
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# CORS
CORS_ORIGINS=["http://localhost:3000"]
CORS_CREDENTIALS=true

# Rate Limiting (futuro)
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# Timeouts
REQUEST_TIMEOUT=300
WEBSOCKET_TIMEOUT=600
```

### 📋 Configuração Avançada

```python
# main.py customizado
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Investiga.AI API",
    version="1.0.0",
    description="API para verificação automatizada de fatos"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)
```

---

## 📚 Recursos Adicionais

### 📖 Documentação

- **🌐 Swagger UI**: `/docs`
- **📋 ReDoc**: `/redoc`
- **📄 OpenAPI Schema**: `/openapi.json`

### 🧪 Ambiente de Teste

```bash
# Inicia servidor de desenvolvimento
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Testa todos os endpoints
python tests/test_api_completa.py
```

### 🔧 Ferramentas de Desenvolvimento

- **📊 Postman Collection**: [Download](api/investiga-ai.postman_collection.json)
- **🧪 Insomnia Workspace**: [Download](api/investiga-ai.insomnia.json)
- **📜 OpenAPI Generator**: Gere SDKs para qualquer linguagem

---

<div align="center">

**🌐 API robusta para integração com qualquer sistema**

[![Voltar ao README](https://img.shields.io/badge/←_Voltar-README-blue.svg)](../README.md)
[![Swagger UI](https://img.shields.io/badge/🌐_Swagger-UI-green.svg)](http://localhost:8000/docs)

</div>