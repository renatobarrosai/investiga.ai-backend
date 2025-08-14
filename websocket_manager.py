# Criar websocket_manager.py na raiz do check_cl
from fastapi import WebSocket
from typing import Dict, List
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_station_update(self, client_id: str, station: str, description: str):
        if client_id in self.active_connections:
            message = {
                "type": "station_update",
                "station": station, 
                "description": description
            }
            await self.active_connections[client_id].send_text(json.dumps(message))
    
    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(json.dumps(message))
