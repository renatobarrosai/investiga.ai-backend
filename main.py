# main.py
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

# Importa o coordenador já modificado
from src.agentes.coordenador_agentes import CoordenadorAgentes

app = FastAPI(title="Check CL API", version="1.0.0")

# Configurar CORS para o frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # URL do frontend Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dicionário para gerenciar conexões WebSocket
conexoes_ativas = {}

class VerifyRequest(BaseModel):
    conteudo: str
    imagem: Optional[str] = None  # base64 se tiver

@app.post("/api/verify")
async def verificar_informacao(request: VerifyRequest):
    """Endpoint principal para verificação de fatos"""
    try:
        coordenador = CoordenadorAgentes()
        
        resultado = await coordenador.processar_completo_com_sintese(
            request.conteudo, 
            request.imagem
        )
        
        return resultado.get('frontend_data', resultado)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify-file")
async def verificar_arquivo(file: UploadFile = File(...)):
    """Endpoint para upload e verificação de arquivos"""
    try:
        coordenador = CoordenadorAgentes()
        
        resultado = await coordenador.processar_arquivo(
            file, 
            file.content_type
        )
        
        return resultado.get('frontend_data', resultado)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket para updates em tempo real"""
    await websocket.accept()
    conexoes_ativas[client_id] = websocket
    
    try:
        while True:
            # Mantém conexão ativa
            data = await websocket.receive_text()
            
            if data == "verify":
                # Aqui poderia processar verificação via WebSocket
                pass
                
    except WebSocketDisconnect:
        if client_id in conexoes_ativas:
            del conexoes_ativas[client_id]

@app.post("/api/verify-realtime/{client_id}")
async def verificar_tempo_real(client_id: str, request: VerifyRequest):
    """Verificação com updates em tempo real via WebSocket"""
    try:
        coordenador = CoordenadorAgentes()
        
        # Função callback para enviar updates via WebSocket
        async def progress_callback(station: str, description: str):
            if client_id in conexoes_ativas:
                await conexoes_ativas[client_id].send_text(json.dumps({
                    "type": "progress",
                    "station": station,
                    "description": description
                }))
        
        resultado = await coordenador.processar_completo_com_sintese(
            request.conteudo, 
            request.imagem,
            callback=progress_callback,
            client_id=client_id
        )
        
        # Envia resultado final
        if client_id in conexoes_ativas:
            await conexoes_ativas[client_id].send_text(json.dumps({
                "type": "result",
                "data": resultado.get('frontend_data', resultado)
            }))
        
        return {"status": "completed", "client_id": client_id}
        
    except Exception as e:
        # Envia erro via WebSocket
        if client_id in conexoes_ativas:
            await conexoes_ativas[client_id].send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def status_sistema():
    """Status geral do sistema"""
    coordenador = CoordenadorAgentes()
    return coordenador.obter_status_completo()

@app.get("/api/health")
async def health_check():
    """Health check para monitoramento"""
    return {"status": "healthy", "service": "check-cl-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
