# src/utils/model_utils.py
import logging
import time
import hashlib
import psutil
import threading
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import json

class StatusValidacao(Enum):
    """Status de validação de um modelo"""
    VALIDO = "valido"
    ARQUIVO_NAO_ENCONTRADO = "arquivo_nao_encontrado"
    CORROMPIDO = "corrompido"
    INCOMPATIVEL = "incompativel"
    MEMORIA_INSUFICIENTE = "memoria_insuficiente"

@dataclass
class ResultadoValidacao:
    """Resultado de validação de um modelo"""
    status: StatusValidacao
    caminho: str
    tamanho_mb: float = 0.0
    hash_arquivo: str = ""
    detalhes: str = ""
    tempo_validacao: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class InfoMemoria:
    """Informações de memória do sistema"""
    total_ram_gb: float
    ram_disponivel_gb: float
    total_vram_gb: float
    vram_disponivel_gb: float
    memoria_processo_mb: float

class ModelUtils:
    """Utilitários essenciais para gerenciamento de modelos"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cache_validacoes = {}
        self._lock = threading.RLock()
        
    # ========================================================================
    # VALIDAÇÃO DE MODELOS
    # ========================================================================
    
    def validar_modelo(self, caminho: str, verificar_hash: bool = False, 
                      cache_resultado: bool = True) -> ResultadoValidacao:
        """
        Valida se um modelo está íntegro e pode ser carregado
        
        Args:
            caminho: Caminho para o modelo
            verificar_hash: Se deve verificar integridade por hash
            cache_resultado: Se deve cachear o resultado
            
        Returns:
            ResultadoValidacao com status da validação
        """
        inicio = time.time()
        
        # Verificar cache
        if cache_resultado and caminho in self._cache_validacoes:
            cached = self._cache_validacoes[caminho]
            if time.time() - cached['timestamp'] < 3600:  # Cache por 1 hora
                return cached['resultado']
        
        try:
            caminho_path = Path(caminho)
            
            # Verificar se arquivo/diretório existe
            if not caminho_path.exists():
                resultado = ResultadoValidacao(
                    status=StatusValidacao.ARQUIVO_NAO_ENCONTRADO,
                    caminho=caminho,
                    detalhes=f"Caminho não encontrado: {caminho}",
                    tempo_validacao=time.time() - inicio
                )
            else:
                # Validação completa
                resultado = self._validar_arquivo_completo(caminho_path, verificar_hash, inicio)
                
        except Exception as e:
            resultado = ResultadoValidacao(
                status=StatusValidacao.CORROMPIDO,
                caminho=caminho,
                detalhes=f"Erro na validação: {str(e)}",
                tempo_validacao=time.time() - inicio
            )
            
        # Cachear resultado
        if cache_resultado:
            with self._lock:
                self._cache_validacoes[caminho] = {
                    'timestamp': time.time(),
                    'resultado': resultado
                }
                
        return resultado
    
    def _validar_arquivo_completo(self, caminho_path: Path, verificar_hash: bool, inicio: float) -> ResultadoValidacao:
        """Executa validação completa do arquivo"""
        try:
            # Calcular tamanho
            tamanho_bytes = self._calcular_tamanho_recursivo(caminho_path)
            tamanho_mb = tamanho_bytes / (1024 * 1024)
            
            # Verificar se é diretório de modelo HuggingFace
            metadata = self._extrair_metadata_modelo(caminho_path)
            
            # Verificar hash se solicitado
            hash_arquivo = ""
            if verificar_hash:
                hash_arquivo = self._calcular_hash_modelo(caminho_path)
                
            # Verificar compatibilidade básica
            status = StatusValidacao.VALIDO
            detalhes = "Modelo validado com sucesso"
            
            # Verificações específicas
            if not self._verificar_arquivos_essenciais(caminho_path):
                status = StatusValidacao.INCOMPATIVEL
                detalhes = "Arquivos essenciais do modelo não encontrados"
            elif tamanho_mb < 1:  # Modelo muito pequeno
                status = StatusValidacao.CORROMPIDO
                detalhes = "Modelo muito pequeno, possivelmente corrompido"
                
            return ResultadoValidacao(
                status=status,
                caminho=str(caminho_path),
                tamanho_mb=tamanho_mb,
                hash_arquivo=hash_arquivo,
                detalhes=detalhes,
                tempo_validacao=time.time() - inicio,
                metadata=metadata
            )
            
        except Exception as e:
            return ResultadoValidacao(
                status=StatusValidacao.CORROMPIDO,
                caminho=str(caminho_path),
                detalhes=f"Erro na validação: {str(e)}",
                tempo_validacao=time.time() - inicio
            )
    
    def _calcular_tamanho_recursivo(self, caminho: Path) -> int:
        """Calcula tamanho total de um arquivo ou diretório"""
        if caminho.is_file():
            return caminho.stat().st_size
        elif caminho.is_dir():
            return sum(f.stat().st_size for f in caminho.rglob('*') if f.is_file())
        return 0
    
    def _extrair_metadata_modelo(self, caminho: Path) -> Dict[str, Any]:
        """Extrai metadados de um modelo (config.json, tokenizer_config.json, etc.)"""
        metadata = {}
        
        # Tentar ler config.json
        config_path = caminho / "config.json" if caminho.is_dir() else caminho.parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    metadata['model_config'] = {
                        'architecture': config.get('architectures', []),
                        'model_type': config.get('model_type', ''),
                        'vocab_size': config.get('vocab_size', 0),
                        'hidden_size': config.get('hidden_size', 0),
                        'num_layers': config.get('num_hidden_layers', 0)
                    }
            except Exception as e:
                self.logger.warning(f"Erro ao ler config.json: {e}")
        
        # Tentar ler tokenizer_config.json
        tokenizer_path = caminho / "tokenizer_config.json" if caminho.is_dir() else caminho.parent / "tokenizer_config.json"
        if tokenizer_path.exists():
            try:
                with open(tokenizer_path, 'r', encoding='utf-8') as f:
                    tokenizer_config = json.load(f)
                    metadata['tokenizer_config'] = {
                        'tokenizer_class': tokenizer_config.get('tokenizer_class', ''),
                        'vocab_size': tokenizer_config.get('vocab_size', 0),
                        'model_max_length': tokenizer_config.get('model_max_length', 0)
                    }
            except Exception as e:
                self.logger.warning(f"Erro ao ler tokenizer_config.json: {e}")
        
        return metadata
    
    def _verificar_arquivos_essenciais(self, caminho: Path) -> bool:
        """Verifica se arquivos essenciais do modelo estão presentes"""
        if caminho.is_file():
            # Arquivo único - assumir que é o modelo
            return True
            
        # Diretório - verificar arquivos essenciais HuggingFace
        arquivos_essenciais = []
        
        # Verificar se tem pelo menos um arquivo de peso
        arquivos_peso = list(caminho.glob("*.bin")) + list(caminho.glob("*.safetensors")) + list(caminho.glob("*.pth"))
        if arquivos_peso:
            arquivos_essenciais.append("weights")
        
        # Verificar config
        if (caminho / "config.json").exists():
            arquivos_essenciais.append("config")
            
        # Verificar tokenizer
        tokenizer_files = list(caminho.glob("tokenizer*"))
        if tokenizer_files:
            arquivos_essenciais.append("tokenizer")
        
        # Pelo menos weights e config devem existir
        return len(arquivos_essenciais) >= 2
    
    def _calcular_hash_modelo(self, caminho: Path) -> str:
        """Calcula hash MD5 simplificado do modelo"""
        try:
            hasher = hashlib.md5()
            
            if caminho.is_file():
                # Arquivo único
                with open(caminho, 'rb') as f:
                    # Ler apenas primeiros e últimos MB para performance
                    hasher.update(f.read(1024*1024))
                    f.seek(-1024*1024, 2)  # Últimos 1MB
                    hasher.update(f.read())
            else:
                # Diretório - hash dos arquivos principais
                for arquivo in sorted(caminho.glob("*.bin")):
                    hasher.update(arquivo.name.encode())
                    hasher.update(str(arquivo.stat().st_size).encode())
                    
            return hasher.hexdigest()[:16]  # Hash truncado para performance
            
        except Exception as e:
            self.logger.warning(f"Erro ao calcular hash: {e}")
            return ""
    
    # ========================================================================
    # ANÁLISE DE MEMÓRIA
    # ========================================================================
    
    def analisar_memoria_sistema(self) -> InfoMemoria:
        """Analisa memória disponível no sistema"""
        try:
            # Memória RAM
            memoria_virtual = psutil.virtual_memory()
            total_ram_gb = memoria_virtual.total / (1024**3)
            ram_disponivel_gb = memoria_virtual.available / (1024**3)
            
            # Memória do processo atual
            processo = psutil.Process()
            memoria_processo_mb = processo.memory_info().rss / (1024**2)
            
            # VRAM (simplificado - seria expandido com pynvml)
            total_vram_gb = 0.0
            vram_disponivel_gb = 0.0
            
            try:
                # Tentar importar GPUtil para info da GPU
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Primeira GPU
                    total_vram_gb = gpu.memoryTotal / 1024
                    vram_disponivel_gb = gpu.memoryFree / 1024
            except ImportError:
                self.logger.warning("GPUtil não disponível - informações de VRAM não coletadas")
            
            return InfoMemoria(
                total_ram_gb=total_ram_gb,
                ram_disponivel_gb=ram_disponivel_gb,
                total_vram_gb=total_vram_gb,
                vram_disponivel_gb=vram_disponivel_gb,
                memoria_processo_mb=memoria_processo_mb
            )
            
        except Exception as e:
            self.logger.error(f"Erro ao analisar memória: {e}")
            return InfoMemoria(0, 0, 0, 0, 0)
    
    def calcular_memoria_necessaria(self, config_modelo: Dict) -> float:
        """
        Calcula memória necessária estimada para um modelo
        
        Args:
            config_modelo: Configuração do modelo
            
        Returns:
            Memória necessária em MB
        """
        # Cálculo baseado em heurísticas conhecidas
        memoria_base = config_modelo.get('memoria_mb', 0)
        
        # Fatores de correção
        quantizacao = config_modelo.get('quantizacao', 'nenhuma')
        if quantizacao in ['gptq', 'awq']:
            memoria_base *= 0.6  # Quantização reduz ~40% da memória
        elif quantizacao == 'gguf':
            memoria_base *= 0.5  # GGUF reduz ~50%
        
        # Overhead do sistema (15-25%)
        overhead = memoria_base * 0.2
        
        # Overhead de inferência (varia por tipo)
        tipo_modelo = config_modelo.get('tipo_modelo', 'llm')
        if tipo_modelo == 'vision':
            overhead += 1024  # 1GB extra para processamento de imagem
        elif tipo_modelo == 'audio':
            overhead += 512   # 512MB extra para áudio
        
        return memoria_base + overhead
    
    def verificar_memoria_suficiente(self, memoria_necessaria_mb: float, 
                                   incluir_swap: bool = False) -> bool:
        """Verifica se há memória suficiente para carregar modelo"""
        info_memoria = self.analisar_memoria_sistema()
        
        # Verificar VRAM primeiro (preferencial para modelos)
        if info_memoria.vram_disponivel_gb * 1024 >= memoria_necessaria_mb:
            return True
        
        # Verificar RAM principal
        memoria_disponivel_mb = info_memoria.ram_disponivel_gb * 1024
        
        # Deixar margem de segurança (1GB)
        margem_seguranca_mb = 1024
        memoria_utilizavel = memoria_disponivel_mb - margem_seguranca_mb
        
        return memoria_utilizavel >= memoria_necessaria_mb
    
    # ========================================================================
    # OPERAÇÕES DE ARQUIVO
    # ========================================================================
    
    def verificar_espaco_disco(self, caminho: str, espaco_necessario_gb: float) -> bool:
        """Verifica se há espaço suficiente em disco"""
        try:
            statvfs = psutil.disk_usage(caminho)
            espaco_livre_gb = statvfs.free / (1024**3)
            return espaco_livre_gb >= espaco_necessario_gb
        except Exception as e:
            self.logger.error(f"Erro ao verificar espaço em disco: {e}")
            return False
    
    def limpar_cache_modelos(self, diretorio_cache: str = "cache/modelos") -> Dict[str, Any]:
        """Remove arquivos de cache antigos de modelos"""
        try:
            cache_path = Path(diretorio_cache)
            if not cache_path.exists():
                return {"arquivos_removidos": 0, "espaco_liberado_mb": 0}
            
            arquivos_removidos = 0
            espaco_liberado = 0
            
            # Remover arquivos mais antigos que 7 dias
            limite_tempo = time.time() - (7 * 24 * 3600)
            
            for arquivo in cache_path.rglob("*"):
                if arquivo.is_file() and arquivo.stat().st_mtime < limite_tempo:
                    try:
                        tamanho = arquivo.stat().st_size
                        arquivo.unlink()
                        arquivos_removidos += 1
                        espaco_liberado += tamanho
                    except Exception as e:
                        self.logger.warning(f"Erro ao remover {arquivo}: {e}")
            
            espaco_liberado_mb = espaco_liberado / (1024**2)
            
            self.logger.info(f"Cache limpo: {arquivos_removidos} arquivos, {espaco_liberado_mb:.1f}MB liberados")
            
            return {
                "arquivos_removidos": arquivos_removidos,
                "espaco_liberado_mb": espaco_liberado_mb
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao limpar cache: {e}")
            return {"erro": str(e)}
    
    def criar_diretorio_seguro(self, caminho: str) -> bool:
        """Cria diretório com permissões seguras"""
        try:
            Path(caminho).mkdir(parents=True, exist_ok=True, mode=0o755)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao criar diretório {caminho}: {e}")
            return False
    
    # ========================================================================
    # UTILITÁRIOS DE CONVERSÃO
    # ========================================================================
    
    def converter_tamanho_humano(self, bytes_size: int) -> str:
        """Converte bytes para formato legível (KB, MB, GB)"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def converter_tempo_humano(self, segundos: float) -> str:
        """Converte segundos para formato legível"""
        if segundos < 60:
            return f"{segundos:.1f}s"
        elif segundos < 3600:
            return f"{segundos/60:.1f}m"
        else:
            return f"{segundos/3600:.1f}h"
    
    def parsear_dispositivo(self, device_string: str) -> Dict[str, Any]:
        """Parseia string de dispositivo (ex: 'cuda:0', 'cpu', 'auto')"""
        device_string = device_string.lower().strip()
        
        if device_string == "auto":
            return {"tipo": "auto", "indice": None}
        elif device_string == "cpu":
            return {"tipo": "cpu", "indice": None}
        elif device_string.startswith("cuda"):
            if ":" in device_string:
                indice = int(device_string.split(":")[1])
                return {"tipo": "cuda", "indice": indice}
            else:
                return {"tipo": "cuda", "indice": 0}
        else:
            return {"tipo": "desconhecido", "indice": None}
    
    # ========================================================================
    # DIAGNÓSTICO E DEBUG
    # ========================================================================
    
    def diagnostico_sistema(self) -> Dict[str, Any]:
        """Executa diagnóstico completo do sistema para modelos"""
        diagnostico = {
            "timestamp": time.time(),
            "status_geral": "OK"
        }
        
        try:
            # Informações de memória
            info_memoria = self.analisar_memoria_sistema()
            diagnostico["memoria"] = {
                "ram_total_gb": info_memoria.total_ram_gb,
                "ram_disponivel_gb": info_memoria.ram_disponivel_gb,
                "vram_total_gb": info_memoria.total_vram_gb,
                "vram_disponivel_gb": info_memoria.vram_disponivel_gb,
                "processo_atual_mb": info_memoria.memoria_processo_mb
            }
            
            # Informações de GPU
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                diagnostico["gpus"] = []
                for gpu in gpus:
                    diagnostico["gpus"].append({
                        "id": gpu.id,
                        "nome": gpu.name,
                        "memoria_total_mb": gpu.memoryTotal,
                        "memoria_livre_mb": gpu.memoryFree,
                        "utilizacao_percentual": gpu.load * 100,
                        "temperatura_celsius": gpu.temperature
                    })
            except ImportError:
                diagnostico["gpus"] = "GPUtil não disponível"
            
            # Informações de CPU
            diagnostico["cpu"] = {
                "cores_fisicos": psutil.cpu_count(logical=False),
                "cores_logicos": psutil.cpu_count(logical=True),
                "utilizacao_percentual": psutil.cpu_percent(interval=1),
                "arquitetura": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else "N/A"
            }
            
            # Informações de disco
            diagnostico["disco"] = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    diagnostico["disco"].append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total_gb": usage.total / (1024**3),
                        "livre_gb": usage.free / (1024**3),
                        "usado_percentual": (usage.used / usage.total) * 100
                    })
                except PermissionError:
                    pass
            
            # Verificações de compatibilidade
            diagnostico["compatibilidade"] = {
                "python_version": ".".join(map(str, __import__('sys').version_info[:3])),
                "torch_disponivel": self._verificar_torch(),
                "transformers_disponivel": self._verificar_transformers(),
                "cuda_disponivel": self._verificar_cuda()
            }
            
        except Exception as e:
            diagnostico["status_geral"] = "ERRO"
            diagnostico["erro"] = str(e)
            
        return diagnostico
    
    def _verificar_torch(self) -> bool:
        """Verifica se PyTorch está disponível"""
        try:
            import torch
            return True
        except ImportError:
            return False
    
    def _verificar_transformers(self) -> bool:
        """Verifica se Transformers está disponível"""
        try:
            import transformers
            return True
        except ImportError:
            return False
    
    def _verificar_cuda(self) -> bool:
        """Verifica se CUDA está disponível"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    # ========================================================================
    # GESTÃO DE CACHE
    # ========================================================================
    
    def limpar_cache_validacoes(self, idade_maxima_horas: float = 24.0):
        """Remove validações antigas do cache"""
        with self._lock:
            agora = time.time()
            limite = idade_maxima_horas * 3600
            
            chaves_antigas = [
                chave for chave, dados in self._cache_validacoes.items()
                if agora - dados['timestamp'] > limite
            ]
            
            for chave in chaves_antigas:
                del self._cache_validacoes[chave]
                
            if chaves_antigas:
                self.logger.info(f"Removidas {len(chaves_antigas)} validações antigas do cache")
    
    def obter_estatisticas_cache(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache de validações"""
        with self._lock:
            agora = time.time()
            
            idades = [agora - dados['timestamp'] for dados in self._cache_validacoes.values()]
            
            return {
                "total_entradas": len(self._cache_validacoes),
                "idade_media_horas": (sum(idades) / len(idades) / 3600) if idades else 0,
                "entrada_mais_antiga_horas": (max(idades) / 3600) if idades else 0,
                "memoria_estimada_kb": len(str(self._cache_validacoes)) / 1024
            }

# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

# Instância global para uso conveniente
model_utils = ModelUtils()
