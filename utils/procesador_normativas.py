# utils/procesador_normativas.py
import json
import hashlib
import logging
from datetime import datetime, timedelta
from models import db
from models.conocimiento import Normativa
from utils.scraper_normativas import ScraperNormativas
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

#class ProcesadorNormativas:
    #def __init__(self, ia_engine):
        #self.ia_engine = ia_engine
        self.scraper = ScraperNormativas()
    
    def actualizar_base_conocimiento(self):
        """Actualiza la base de conocimiento con nuevas normativas"""
        nuevas_normativas = []
        
        try:
            # Última consulta (guardar en un archivo)
            ultima_consulta = self._obtener_ultima_consulta()
            logger.info(f"📅 Última consulta: {ultima_consulta}")
            
            # Obtener novedades
            novedades = self.scraper.obtener_novedades(ultima_consulta)
            
            logger.info(f"🔍 Se encontraron {len(novedades)} posibles normativas nuevas")
            
            # Procesar cada una
            for item in novedades:
                try:
                    # Extraer contenido completo de la página
                    contenido_completo = self._extraer_contenido_completo(item['url'])
                    
                    if not contenido_completo:
                        continue
                    
                    # Verificar si realmente es una normativa
                    if self._es_normativa_valida(contenido_completo):
                        # Crear estructura de normativa
                        normativa = self._crear_estructura_normativa(item, contenido_completo)
                        
                        # Guardar en base de datos
                        if self._guardar_normativa(normativa):
                            nuevas_normativas.append(normativa)
                            logger.info(f"✅ Normativa agregada: {normativa['codigo']} - {normativa['titulo'][:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error procesando item {item.get('titulo', '')}: {e}")
                    continue
            
            # Actualizar timestamp de última consulta
            self._actualizar_ultima_consulta(datetime.now())
            
            logger.info(f"📚 Proceso completado. {len(nuevas_normativas)} nuevas normativas agregadas.")
            
        except Exception as e:
            logger.error(f"❌ Error en actualización: {e}")
        
        return nuevas_normativas
    
    def _extraer_contenido_completo(self, url):
        """Extrae el contenido completo de una página"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Intentar diferentes selectores según el sitio
            selectores = [
                '.node__content',
                '.field--name-body',
                '.content',
                'article',
                'main',
                '.ecl',
                '#content'
            ]
            
            for selector in selectores:
                contenido = soup.select_one(selector)
                if contenido:
                    # Limpiar el texto
                    texto = contenido.get_text(strip=True)
                    return texto[:5000]  # Limitar a 5000 caracteres
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extrayendo contenido de {url}: {e}")
            return ""
    
    def _es_normativa_valida(self, contenido):
        """Determina si el contenido corresponde a una normativa"""
        indicadores = [
            'disposición', 'resolución', 'normativa', 'anexo', 'artículo',
            'buenas prácticas', 'requisitos', 'debe cumplir', 'establece',
            'queda prohibido', 'autorízase', 'apruébase', 'reglamento',
            'gmp', 'good manufacturing', 'pharmaceutical', 'drug',
            'fda', 'ema', 'anmat', 'ministerio de salud'
        ]
        
        contenido_lower = contenido.lower()
        
        # Debe tener al menos 2 indicadores
        contador = sum(1 for ind in indicadores if ind in contenido_lower)
        
        return contador >= 2
    
    def _crear_estructura_normativa(self, item, contenido):
        """Crea la estructura JSON de la normativa"""
        # Generar código basado en fuente y fecha
        fecha_str = item['fecha'].strftime('%Y%m')
        hash_corto = hashlib.md5(item['url'].encode()).hexdigest()[:4]
        
        if item['fuente'] == 'ANMAT':
            codigo = f"ANMAT-{fecha_str}-{hash_corto}"
        elif item['fuente'] == 'FDA':
            codigo = f"FDA-{fecha_str}-{hash_corto}"
        elif item['fuente'] == 'EMA':
            codigo = f"EMA-{fecha_str}-{hash_corto}"
        else:
            codigo = f"GMP-{fecha_str}-{hash_corto}"
        
        # Clasificar por IA
        categoria = self._clasificar_normativa(contenido)
        
        return {
            'codigo': codigo,
            'titulo': item['titulo'],
            'descripcion': contenido[:200] + '...',
            'contenido': contenido,
            'tipo': item['fuente'],
            'categoria': categoria,
            'subcategoria': '',
            'aplica_a': '',
            'palabras_clave': self._extraer_palabras_clave(contenido),
            'fecha_publicacion': item['fecha'].strftime('%Y-%m-%d'),
            'version': '1.0',
            'url_fuente': item['url']
        }
    
    def _clasificar_normativa(self, contenido):
        """Clasifica la normativa por categoría"""
        contenido_lower = contenido.lower()
        
        categorias = {
            'Calibración': ['calibra', 'calibration', 'patrón', 'standard'],
            'Validación': ['validación', 'validation', 'cualificación', 'qualification'],
            'Limpieza': ['limpieza', 'cleaning', 'residuo', 'residue'],
            'CAPA': ['capa', 'correctiva', 'preventive', 'corrective'],
            'Control de Cambios': ['cambio', 'change', 'modificación'],
            'Documentación': ['documentación', 'sop', 'procedimiento', 'procedure']
        }
        
        for categoria, palabras in categorias.items():
            for palabra in palabras:
                if palabra in contenido_lower:
                    return categoria
        
        return 'BPM'  # Default
    
    def _extraer_palabras_clave(self, contenido):
        """Extrae palabras clave del contenido"""
        palabras_comunes = [
            'gmp', 'anmat', 'fda', 'buenas prácticas', 'manufactura',
            'calidad', 'farmacéutico', 'medicamento', 'validación',
            'calibración', 'limpieza', 'capa', 'control de cambios',
            'documentación', 'procedimiento', 'requisito', 'normativa'
        ]
        
        encontradas = []
        contenido_lower = contenido.lower()
        
        for palabra in palabras_comunes:
            if palabra in contenido_lower:
                encontradas.append(palabra)
        
        return ', '.join(encontradas[:10])
    
    def _guardar_normativa(self, normativa_data):
        """Guarda la normativa en la base de datos"""
        try:
            # Verificar si ya existe
            existente = Normativa.query.filter_by(codigo=normativa_data['codigo']).first()
            if existente:
                logger.info(f"⏩ Normativa ya existe: {normativa_data['codigo']}")
                return False
            
            nueva_normativa = Normativa(
                codigo=normativa_data['codigo'],
                titulo=normativa_data['titulo'],
                descripcion=normativa_data['descripcion'],
                contenido=normativa_data['contenido'],
                tipo=normativa_data['tipo'],
                categoria=normativa_data['categoria'],
                subcategoria=normativa_data['subcategoria'],
                aplica_a=normativa_data['aplica_a'],
                palabras_clave=normativa_data['palabras_clave'],
                fecha_publicacion=datetime.strptime(normativa_data['fecha_publicacion'], '%Y-%m-%d').date(),
                version=normativa_data['version']
            )
            
            db.session.add(nueva_normativa)
            db.session.flush()
            
            # También agregar a ChromaDB para búsqueda semántica
            if self.ia_engine and self.ia_engine.inicializado:
                texto_embedding = f"{nueva_normativa.codigo} {nueva_normativa.titulo} {nueva_normativa.contenido}"
                embedding = self.ia_engine.model.encode(texto_embedding).tolist()
                
                self.ia_engine.collection.add(
                    embeddings=[embedding],
                    documents=[texto_embedding],
                    metadatas=[{
                        'id': nueva_normativa.id,
                        'codigo': nueva_normativa.codigo,
                        'titulo': nueva_normativa.titulo,
                        'tipo': nueva_normativa.tipo,
                        'categoria': nueva_normativa.categoria
                    }],
                    ids=[f"norm_{nueva_normativa.id}"]
                )
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error guardando normativa: {e}")
            db.session.rollback()
            return False
    
    def _obtener_ultima_consulta(self):
        """Obtiene timestamp de última consulta desde archivo"""
        try:
            import os
            if os.path.exists('data/ultima_consulta.txt'):
                with open('data/ultima_consulta.txt', 'r') as f:
                    return datetime.fromisoformat(f.read().strip())
        except:
            pass
        
        # Si no existe, usar fecha de hace 7 días
        return datetime.now() - timedelta(days=7)
    
    def _actualizar_ultima_consulta(self, fecha):
        """Actualiza timestamp de última consulta"""
        try:
            import os
            os.makedirs('data', exist_ok=True)
            with open('data/ultima_consulta.txt', 'w') as f:
                f.write(fecha.isoformat())
        except Exception as e:
            logger.error(f"Error guardando última consulta: {e}")