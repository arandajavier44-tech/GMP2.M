# utils/actualizador_inteligente.py
import logging
from datetime import datetime
from models import db
from models.conocimiento import Normativa
from utils.scraper_anmat_completo import ScraperANMATCompleto
from utils.scraper_inteligente import ScraperInteligente
from utils.procesador_normativas import ProcesadorNormativas

logger = logging.getLogger(__name__)

class ActualizadorInteligente:
    def __init__(self, ia_engine):
        self.ia_engine = ia_engine
        self.scraper_anmat = ScraperANMATCompleto()
        self.scraper_inteligente = ScraperInteligente()
        self.procesador = ProcesadorNormativas(ia_engine)
    
    def actualizar_completo(self):
        """Actualización completa: fuentes fijas + descubrimiento inteligente"""
        nuevas_normativas = []
        
        try:
            # PASO 1: Scraping completo de fuentes ANMAT oficiales
            logger.info("📚 PASO 1: Scrapeando fuentes ANMAT oficiales...")
            normativas_anmat = self.scraper_anmat.scrapear_todo()
            
            for norm in normativas_anmat:
                if self.procesador._guardar_normativa(norm):
                    nuevas_normativas.append(norm)
            
            logger.info(f"✅ {len(nuevas_normativas)} normativas de fuentes oficiales")
            
            # PASO 2: Buscar nuevas fuentes en Google
            logger.info("🔍 PASO 2: Buscando nuevas fuentes de normativas...")
            nuevas_fuentes = self.scraper_inteligente.buscar_nuevas_fuentes()
            
            # PASO 3: Explorar las nuevas fuentes descubiertas
            for fuente in nuevas_fuentes:
                logger.info(f"📡 Explorando fuente descubierta: {fuente['url']}")
                normativas_descubiertas = self.scraper_inteligente.explorar_fuente(fuente)
                
                for norm in normativas_descubiertas:
                    # Aquí necesitarías obtener el contenido completo
                    if self.procesador._es_normativa_valida(norm.get('titulo', '')):
                        # Crear estructura básica
                        estructura = self.procesador._crear_estructura_normativa(
                            {'titulo': norm['titulo'], 'url': norm['url'], 'fuente': norm['fuente']},
                            norm.get('descripcion', '')
                        )
                        if self.procesador._guardar_normativa(estructura):
                            nuevas_normativas.append(estructura)
            
            # PASO 4: Actualizar timestamp
            self._actualizar_ultima_consulta()
            
            logger.info(f"🎉 Actualización completa: {len(nuevas_normativas)} nuevas normativas")
            
        except Exception as e:
            logger.error(f"❌ Error en actualización completa: {e}")
        
        return nuevas_normativas
    
    def _actualizar_ultima_consulta(self):
        """Actualiza timestamp de última consulta"""
        try:
            import os
            os.makedirs('data', exist_ok=True)
            with open('data/ultima_consulta_completa.txt', 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Error guardando última consulta: {e}")