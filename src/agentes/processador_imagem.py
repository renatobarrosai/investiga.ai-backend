# src/agentes/processador_imagem.py
import logging
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
import base64
import numpy as np
from pathlib import Path
import re

try:
    import cv2
    CV2_DISPONIVEL = True
except ImportError:
    CV2_DISPONIVEL = False
    logging.warning("OpenCV não disponível - algumas funcionalidades de processamento de imagem podem estar limitadas")

@dataclass
class ResultadoProcessamentoImagem:
    """Resultado do processamento de uma imagem"""
    sucesso: bool
    imagem_processada: Optional[Image.Image] = None
    texto_extraido: str = ""
    elementos_detectados: List[str] = field(default_factory=list)
    metadados: Dict[str, Any] = field(default_factory=dict)
    tempo_processamento: float = 0.0
    erro: Optional[str] = None
    confianca_ocr: float = 0.0
    analise_visual: Dict[str, Any] = field(default_factory=dict)

class ProcessadorImagem:
    """
    Processador especializado para análise avançada de imagens.
    
    Funcionalidades:
    - OCR (Optical Character Recognition) usando Phi-3-Vision
    - Preprocessamento de imagens para melhor qualidade
    - Detecção de elementos visuais específicos
    - Normalização e otimização de imagens
    - Análise de qualidade e características
    - Extração de metadados visuais
    """
    
    def __init__(self, phi3_loader=None):
        self.logger = logging.getLogger(__name__)
        self.phi3_loader = phi3_loader
        
        # Configurações de processamento
        self.config = {
            "max_image_size": 1024,
            "min_image_size": 224,
            "qualidade_jpeg": 95,
            "formato_padrao": "RGB",
            "dpi_padrao": 300,
            "contrast_enhancement": True,
            "noise_reduction": True,
            "auto_rotate": True,
            "preserve_aspect_ratio": True
        }
        
        # Padrões para detecção de elementos
        self.padroes_texto = {
            "urls": re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
            "emails": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "telefones": re.compile(r'(?:\+55\s?)?(?:\(?[1-9]{2}\)?\s?)?(?:[2-9][0-9]{3,4}[-\s]?[0-9]{4})'),
            "datas": re.compile(r'\b(?:[0-3]?[0-9])/(?:[01]?[0-9])/(?:[0-9]{2,4})\b'),
            "hashtags": re.compile(r'#\w+'),
            "mentions": re.compile(r'@\w+')
        }
        
        # Estatísticas
        self.stats = {
            "total_processamentos": 0,
            "sucessos_ocr": 0,
            "imagens_preprocessadas": 0,
            "tempo_medio_processamento": 0.0
        }
    
    def processar_imagem_completa(self, imagem: Union[str, bytes, Image.Image], 
                                 incluir_ocr: bool = True,
                                 preprocessar: bool = True,
                                 analisar_elementos: bool = True) -> ResultadoProcessamentoImagem:
        """
        Processamento completo de uma imagem
        
        Args:
            imagem: Imagem em diversos formatos
            incluir_ocr: Se deve extrair texto da imagem
            preprocessar: Se deve aplicar preprocessamento
            analisar_elementos: Se deve analisar elementos visuais
            
        Returns:
            ResultadoProcessamentoImagem com todos os dados
        """
        inicio = time.time()
        self.stats["total_processamentos"] += 1
        
        try:
            # 1. Converter para PIL Image
            pil_image = self._converter_para_pil(imagem)
            if pil_image is None:
                return ResultadoProcessamentoImagem(
                    sucesso=False,
                    erro="Não foi possível converter a imagem",
                    tempo_processamento=time.time() - inicio
                )
            
            # 2. Obter metadados básicos
            metadados = self._extrair_metadados_imagem(pil_image)
            
            # 3. Preprocessar imagem se solicitado
            imagem_processada = pil_image
            if preprocessar:
                imagem_processada = self._preprocessar_imagem(pil_image)
                self.stats["imagens_preprocessadas"] += 1
            
            # 4. Extrair texto (OCR) se solicitado e modelo disponível
            texto_extraido = ""
            confianca_ocr = 0.0
            if incluir_ocr and self.phi3_loader and self.phi3_loader.modelo_carregado:
                resultado_ocr = self._extrair_texto_phi3(imagem_processada)
                texto_extraido = resultado_ocr["texto"]
                confianca_ocr = resultado_ocr["confianca"]
                if resultado_ocr["sucesso"]:
                    self.stats["sucessos_ocr"] += 1
            
            # 5. Analisar elementos visuais se solicitado
            elementos_detectados = []
            analise_visual = {}
            if analisar_elementos:
                elementos_detectados = self._detectar_elementos_visuais(imagem_processada, texto_extraido)
                analise_visual = self._analisar_caracteristicas_visuais(imagem_processada)
            
            # 6. Atualizar metadados com informações de processamento
            metadados.update({
                "preprocessamento_aplicado": preprocessar,
                "ocr_realizado": incluir_ocr,
                "elementos_analisados": analisar_elementos,
                "texto_encontrado": len(texto_extraido) > 0,
                "qualidade_estimada": self._estimar_qualidade_imagem(imagem_processada)
            })
            
            tempo_total = time.time() - inicio
            self._atualizar_estatisticas_tempo(tempo_total)
            
            return ResultadoProcessamentoImagem(
                sucesso=True,
                imagem_processada=imagem_processada,
                texto_extraido=texto_extraido,
                elementos_detectados=elementos_detectados,
                metadados=metadados,
                tempo_processamento=tempo_total,
                confianca_ocr=confianca_ocr,
                analise_visual=analise_visual
            )
            
        except Exception as e:
            self.logger.error(f"Erro no processamento de imagem: {e}", exc_info=True)
            return ResultadoProcessamentoImagem(
                sucesso=False,
                erro=str(e),
                tempo_processamento=time.time() - inicio
            )
    
    def _converter_para_pil(self, imagem: Union[str, bytes, Image.Image]) -> Optional[Image.Image]:
        """Converte diferentes formatos de imagem para PIL Image"""
        try:
            if isinstance(imagem, Image.Image):
                return imagem
            
            elif isinstance(imagem, str):
                # Pode ser path, base64 ou data URL
                if imagem.startswith('data:image'):
                    # Base64 data URL
                    header, data = imagem.split(',', 1)
                    image_data = base64.b64decode(data)
                    return Image.open(io.BytesIO(image_data))
                elif Path(imagem).exists():
                    # Path para arquivo
                    return Image.open(imagem)
                else:
                    # Tentar como base64 puro
                    try:
                        image_data = base64.b64decode(imagem)
                        return Image.open(io.BytesIO(image_data))
                    except:
                        return None
            
            elif isinstance(imagem, bytes):
                return Image.open(io.BytesIO(imagem))
            
            elif isinstance(imagem, np.ndarray):
                return Image.fromarray(imagem)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro na conversão de imagem: {e}")
            return None
    
    def _extrair_metadados_imagem(self, imagem: Image.Image) -> Dict[str, Any]:
        """Extrai metadados básicos da imagem"""
        metadados = {
            "largura": imagem.width,
            "altura": imagem.height,
            "modo": imagem.mode,
            "formato": getattr(imagem, 'format', 'Desconhecido'),
            "tamanho_pixels": imagem.width * imagem.height,
            "aspecto_ratio": round(imagem.width / imagem.height, 2),
            "orientacao": "paisagem" if imagem.width > imagem.height else "retrato"
        }
        
        # Informações adicionais se disponíveis
        if hasattr(imagem, 'info'):
            metadados["dpi"] = imagem.info.get("dpi", (72, 72))
            metadados["exif"] = bool(imagem.info.get("exif"))
        
        return metadados
    
    def _preprocessar_imagem(self, imagem: Image.Image) -> Image.Image:
        """Aplica preprocessamento para melhorar qualidade"""
        try:
            imagem_processada = imagem.copy()
            
            # 1. Converter para RGB se necessário
            if imagem_processada.mode not in ['RGB', 'L']:
                imagem_processada = imagem_processada.convert('RGB')
            
            # 2. Redimensionar se muito grande
            max_size = self.config["max_image_size"]
            if max(imagem_processada.size) > max_size:
                # Manter aspect ratio
                ratio = max_size / max(imagem_processada.size)
                new_size = tuple(int(dim * ratio) for dim in imagem_processada.size)
                imagem_processada = imagem_processada.resize(new_size, Image.Resampling.LANCZOS)
            
            # 3. Melhorar contraste se configurado
            if self.config["contrast_enhancement"]:
                enhancer = ImageEnhance.Contrast(imagem_processada)
                imagem_processada = enhancer.enhance(1.1)  # Leve aumento
            
            # 4. Melhorar nitidez para OCR
            enhancer = ImageEnhance.Sharpness(imagem_processada)
            imagem_processada = enhancer.enhance(1.2)
            
            # 5. Ajustar brilho se necessário
            brightness_enhancer = ImageEnhance.Brightness(imagem_processada)
            imagem_processada = brightness_enhancer.enhance(1.05)
            
            return imagem_processada
            
        except Exception as e:
            self.logger.error(f"Erro no preprocessamento: {e}")
            return imagem  # Retornar original em caso de erro
    
    def _extrair_texto_phi3(self, imagem: Image.Image) -> Dict[str, Any]:
        """Extrai texto usando Phi-3-Vision"""
        try:
            if not self.phi3_loader:
                return {"sucesso": False, "texto": "", "confianca": 0.0}
            
            # Usar prompt especializado para OCR
            prompt_ocr = """Extraia TODO o texto visível nesta imagem.

Instruções:
1. Transcreva exatamente como está escrito
2. Mantenha quebras de linha quando apropriado
3. Se não houver texto, responda "NENHUM_TEXTO_DETECTADO"
4. Inclua números, símbolos e pontuação
5. Preserve a formatação quando possível

Texto extraído:"""
            
            resultado = self.phi3_loader.gerar_resposta_multimodal(
                prompt=prompt_ocr,
                imagem=imagem,
                max_tokens=512,
                temperature=0.0  # Determinístico para OCR
            )
            
            if resultado["sucesso"]:
                texto = resultado["resposta"].strip()
                
                # Verificar se realmente encontrou texto
                if texto and texto != "NENHUM_TEXTO_DETECTADO":
                    # Estimar confiança baseada em características do texto
                    confianca = self._estimar_confianca_ocr(texto)
                    return {
                        "sucesso": True,
                        "texto": texto,
                        "confianca": confianca,
                        "metadata": resultado["metadata"]
                    }
            
            return {"sucesso": False, "texto": "", "confianca": 0.0}
            
        except Exception as e:
            self.logger.error(f"Erro na extração de texto: {e}")
            return {"sucesso": False, "texto": "", "confianca": 0.0}
    
    def _estimar_confianca_ocr(self, texto: str) -> float:
        """Estima confiança do OCR baseado nas características do texto"""
        if not texto:
            return 0.0
        
        confianca = 0.5  # Base
        
        # Fatores que aumentam confiança
        if len(texto) > 10:
            confianca += 0.1
        
        if any(char.isalpha() for char in texto):
            confianca += 0.2
        
        if any(char.isdigit() for char in texto):
            confianca += 0.1
        
        # Verificar se tem estrutura de texto normal
        palavras = texto.split()
        if len(palavras) >= 3:
            confianca += 0.1
        
        # Verificar presença de caracteres especiais suspeitos
        caracteres_suspeitos = len([c for c in texto if ord(c) > 127])
        if caracteres_suspeitos > len(texto) * 0.3:
            confianca -= 0.2
        
        return max(0.0, min(1.0, confianca))
    
    def _detectar_elementos_visuais(self, imagem: Image.Image, texto_extraido: str) -> List[str]:
        """Detecta tipos de elementos visuais na imagem"""
        elementos = []
        
        # Análise baseada no texto extraído
        if texto_extraido:
            elementos.append("texto")
            
            # Detectar tipos específicos de texto
            for tipo, padrao in self.padroes_texto.items():
                if padrao.search(texto_extraido):
                    elementos.append(f"texto_{tipo}")
        
        # Análise baseada nas dimensões e características
        width, height = imagem.size
        aspecto = width / height
        
        if aspecto > 2.0:
            elementos.append("formato_banner")
        elif 0.8 <= aspecto <= 1.2:
            elementos.append("formato_quadrado")
        
        # Análise de cores dominantes
        cores_dominantes = self._analisar_cores_dominantes(imagem)
        if cores_dominantes:
            elementos.extend(cores_dominantes)
        
        # Detectar possível screenshot
        if width >= 300 and height >= 400:
            elementos.append("possivel_screenshot")
        
        return list(set(elementos))  # Remover duplicatas
    
    def _analisar_cores_dominantes(self, imagem: Image.Image) -> List[str]:
        """Analisa cores dominantes na imagem"""
        try:
            # Converter para RGB se necessário
            if imagem.mode != 'RGB':
                imagem = imagem.convert('RGB')
            
            # Reduzir para análise mais rápida
            imagem_pequena = imagem.resize((100, 100))
            
            # Obter cores mais comuns
            cores = imagem_pequena.getcolors(maxcolors=256*256*256)
            if not cores:
                return []
            
            # Ordenar por frequência
            cores_ordenadas = sorted(cores, reverse=True, key=lambda x: x[0])
            
            elementos_cor = []
            
            # Analisar as 3 cores mais comuns
            for count, (r, g, b) in cores_ordenadas[:3]:
                if count > 1000:  # Cor muito dominante
                    if r > 200 and g > 200 and b > 200:
                        elementos_cor.append("predominante_claro")
                    elif r < 50 and g < 50 and b < 50:
                        elementos_cor.append("predominante_escuro")
                    elif r > 200 and g < 100 and b < 100:
                        elementos_cor.append("predominante_vermelho")
                    elif r < 100 and g > 200 and b < 100:
                        elementos_cor.append("predominante_verde")
                    elif r < 100 and g < 100 and b > 200:
                        elementos_cor.append("predominante_azul")
            
            return elementos_cor
            
        except Exception as e:
            self.logger.error(f"Erro na análise de cores: {e}")
            return []
    
    def _analisar_caracteristicas_visuais(self, imagem: Image.Image) -> Dict[str, Any]:
        """Análise detalhada das características visuais"""
        analise = {
            "dimensoes": {"largura": imagem.width, "altura": imagem.height},
            "aspecto_ratio": round(imagem.width / imagem.height, 2),
            "tamanho_categoria": self._categorizar_tamanho(imagem.size),
            "qualidade_estimada": self._estimar_qualidade_imagem(imagem),
            "complexidade_visual": self._estimar_complexidade_visual(imagem)
        }
        
        # Análise de brilho médio
        if imagem.mode == 'RGB':
            # Converter para escala de cinza para análise de brilho
            cinza = imagem.convert('L')
            pixels = list(cinza.getdata())
            brilho_medio = sum(pixels) / len(pixels)
            analise["brilho_medio"] = round(brilho_medio, 2)
            
            if brilho_medio > 200:
                analise["categoria_brilho"] = "muito_claro"
            elif brilho_medio > 150:
                analise["categoria_brilho"] = "claro"
            elif brilho_medio > 100:
                analise["categoria_brilho"] = "medio"
            elif brilho_medio > 50:
                analise["categoria_brilho"] = "escuro"
            else:
                analise["categoria_brilho"] = "muito_escuro"
        
        return analise
    
    def _categorizar_tamanho(self, size: Tuple[int, int]) -> str:
        """Categoriza o tamanho da imagem"""
        width, height = size
        pixels = width * height
        
        if pixels < 100000:  # < 0.1MP
            return "pequena"
        elif pixels < 500000:  # < 0.5MP
            return "media"
        elif pixels < 2000000:  # < 2MP
            return "grande"
        else:
            return "muito_grande"
    
    def _estimar_qualidade_imagem(self, imagem: Image.Image) -> float:
        """Estima qualidade da imagem (0.0 a 1.0)"""
        try:
            qualidade = 0.5  # Base
            
            # Fator tamanho
            pixels = imagem.width * imagem.height
            if pixels > 500000:
                qualidade += 0.2
            elif pixels < 100000:
                qualidade -= 0.2
            
            # Fator aspecto ratio (quadradas ou 16:9 são melhores)
            aspect = imagem.width / imagem.height
            if 0.8 <= aspect <= 1.2 or 1.7 <= aspect <= 1.8:
                qualidade += 0.1
            
            # Análise de variação de pixels (mais variação = mais detalhes)
            if imagem.mode == 'RGB':
                cinza = imagem.convert('L')
                # Reduzir para análise mais rápida
                pequena = cinza.resize((50, 50))
                pixels = list(pequena.getdata())
                
                # Calcular desvio padrão como medida de variação
                media = sum(pixels) / len(pixels)
                variancia = sum((p - media) ** 2 for p in pixels) / len(pixels)
                desvio = variancia ** 0.5
                
                # Normalizar (desvio típico entre 0-70)
                if desvio > 30:
                    qualidade += 0.2
                elif desvio < 10:
                    qualidade -= 0.1
            
            return max(0.0, min(1.0, qualidade))
            
        except Exception:
            return 0.5  # Valor neutro em caso de erro
    
    def _estimar_complexidade_visual(self, imagem: Image.Image) -> int:
        """Estima complexidade visual da imagem (1-10)"""
        try:
            complexidade = 5  # Base
            
            # Fator tamanho
            if max(imagem.size) > 1000:
                complexidade += 1
            
            # Análise de variação de cores
            if imagem.mode == 'RGB':
                pequena = imagem.resize((20, 20))
                cores = pequena.getcolors(maxcolors=400)
                
                if cores:
                    num_cores = len(cores)
                    if num_cores > 100:
                        complexidade += 2
                    elif num_cores > 50:
                        complexidade += 1
                    elif num_cores < 10:
                        complexidade -= 1
            
            return max(1, min(10, complexidade))
            
        except Exception:
            return 5
    
    def otimizar_para_ocr(self, imagem: Union[str, bytes, Image.Image]) -> Optional[Image.Image]:
        """Otimiza imagem especificamente para OCR"""
        try:
            pil_image = self._converter_para_pil(imagem)
            if not pil_image:
                return None
            
            # Converter para escala de cinza para melhor OCR
            if pil_image.mode != 'L':
                otimizada = pil_image.convert('L')
            else:
                otimizada = pil_image.copy()
            
            # Aumentar contraste
            enhancer = ImageEnhance.Contrast(otimizada)
            otimizada = enhancer.enhance(2.0)
            
            # Aumentar nitidez
            enhancer = ImageEnhance.Sharpness(otimizada)
            otimizada = enhancer.enhance(1.5)
            
            # Redimensionar se muito pequena
            if max(otimizada.size) < 300:
                scale = 300 / max(otimizada.size)
                new_size = tuple(int(dim * scale) for dim in otimizada.size)
                otimizada = otimizada.resize(new_size, Image.Resampling.LANCZOS)
            
            return otimizada
            
        except Exception as e:
            self.logger.error(f"Erro na otimização para OCR: {e}")
            return None
    
    def extrair_texto_otimizado(self, imagem: Union[str, bytes, Image.Image]) -> Dict[str, Any]:
        """Extrai texto com otimização específica para OCR"""
        try:
            # Otimizar imagem primeiro
            imagem_otimizada = self.otimizar_para_ocr(imagem)
            if not imagem_otimizada:
                return {"sucesso": False, "erro": "Falha na otimização da imagem"}
            
            # Extrair texto da imagem otimizada
            resultado = self._extrair_texto_phi3(imagem_otimizada)
            
            # Se falhou, tentar com imagem original
            if not resultado["sucesso"]:
                imagem_original = self._converter_para_pil(imagem)
                if imagem_original:
                    resultado = self._extrair_texto_phi3(imagem_original)
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na extração otimizada: {e}")
            return {"sucesso": False, "erro": str(e)}
    
    def _atualizar_estatisticas_tempo(self, tempo: float):
        """Atualiza estatísticas de tempo de processamento"""
        if self.stats["tempo_medio_processamento"] == 0:
            self.stats["tempo_medio_processamento"] = tempo
        else:
            # Média móvel simples
            self.stats["tempo_medio_processamento"] = (
                self.stats["tempo_medio_processamento"] * 0.8 + tempo * 0.2
            )
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do processador"""
        total = self.stats["total_processamentos"]
        
        return {
            "total_processamentos": total,
            "sucessos_ocr": self.stats["sucessos_ocr"],
            "imagens_preprocessadas": self.stats["imagens_preprocessadas"],
            "taxa_sucesso_ocr": (
                (self.stats["sucessos_ocr"] / total * 100) 
                if total > 0 else 0
            ),
            "tempo_medio_processamento": self.stats["tempo_medio_processamento"],
            "phi3_loader_disponivel": self.phi3_loader is not None,
            "cv2_disponivel": CV2_DISPONIVEL,
            "configuracoes": self.config
        }
    
    def configurar_processamento(self, **kwargs):
        """Atualiza configurações de processamento"""
        for chave, valor in kwargs.items():
            if chave in self.config:
                self.config[chave] = valor
                self.logger.info(f"Configuração atualizada: {chave} = {valor}")
    
    def benchmark_processamento(self, num_testes: int = 5) -> Dict[str, Any]:
        """Executa benchmark do processamento de imagem"""
        if not self.phi3_loader:
            return {"erro": "Phi3Loader não disponível para benchmark"}
        
        # Criar imagem de teste
        imagem_teste = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(imagem_teste)
        
        # Adicionar texto de teste
        texto_teste = "TEXTO DE TESTE 123\nSegunda linha de teste"
        try:
            # Tentar usar fonte padrão
            draw.text((10, 10), texto_teste, fill='black')
        except:
            # Fallback se não conseguir carregar fonte
            draw.text((10, 10), texto_teste, fill='black')
        
        resultados = []
        inicio_total = time.time()
        
        for i in range(num_testes):
            resultado = self.processar_imagem_completa(
                imagem=imagem_teste,
                incluir_ocr=True,
                preprocessar=True,
                analisar_elementos=True
            )
            
            resultados.append({
                "sucesso": resultado.sucesso,
                "tempo": resultado.tempo_processamento,
                "texto_detectado": len(resultado.texto_extraido) > 0,
                "confianca_ocr": resultado.confianca_ocr,
                "elementos_detectados": len(resultado.elementos_detectados)
            })
        
        fim_total = time.time()
        
        # Calcular estatísticas
        sucessos = [r for r in resultados if r["sucesso"]]
        tempos = [r["tempo"] for r in resultados]
        
        return {
            "testes_executados": num_testes,
            "testes_bem_sucedidos": len(sucessos),
            "taxa_sucesso": len(sucessos) / num_testes * 100,
            "tempo_total": fim_total - inicio_total,
            "tempo_medio_por_teste": sum(tempos) / len(tempos),
            "ocr_funcionando": any(r["texto_detectado"] for r in resultados),
            "confianca_media_ocr": sum(r["confianca_ocr"] for r in resultados) / len(resultados),
            "elementos_detectados_medio": sum(r["elementos_detectados"] for r in resultados) / len(resultados)
        }
