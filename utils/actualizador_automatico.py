# utils/actualizador_automatico.py
import schedule
import time
import logging
from datetime import datetime
from .procesador_normativas import ProcesadorNormativas
#from utils.ia_engine import ia_engine

logger = logging.getLogger(__name__)

class ActualizadorAutomatico:  # Cambiado a CamelCase (PEP 8)
    def __init__(self):
        self.procesador = ProcesadorNormativas(ia_engine)
        self.ejecutando = True
        
    def iniciar(self):
        """Inicia el programador de actualizaciones"""
        schedule.every().day.at("03:00").do(self.ejecutar_actualizacion)
        schedule.every(6).hours.do(self.ejecutar_actualizacion)
        
        logger.info("🕒 Actualizador automático programado:")
        logger.info("   - Actualización diaria a las 03:00")
        logger.info("   - Actualización cada 6 horas (modo prueba)")
        
        while self.ejecutando:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("🛑 Deteniendo actualizador...")
                self.ejecutando = False
                break
            except Exception as e:
                logger.error(f"Error en bucle principal: {e}")
                time.sleep(60)
    
    def ejecutar_actualizacion(self):
        """Ejecuta el proceso de actualización"""
        logger.info(f"\n{'='*50}")
        logger.info(f"🔄 Iniciando actualización de normativas: {datetime.now()}")
        logger.info(f"{'='*50}")
        
        try:
            inicio = time.time()
            nuevas = self.procesador.actualizar_base_conocimiento()
            duracion = time.time() - inicio
            
            if nuevas and len(nuevas) > 0:
                logger.info(f"✅ Actualización completada en {duracion:.2f}s")
                logger.info(f"📚 Se agregaron {len(nuevas)} nuevas normativas")
            else:
                logger.info(f"📭 No se encontraron nuevas normativas (duración: {duracion:.2f}s)")
            
            logger.info(f"{'='*50}\n")
            return nuevas
            
        except Exception as e:
            logger.error(f"❌ Error en actualización: {e}")
            return []
    
    def detener(self):
        """Detiene el actualizador"""
        self.ejecutando = False
        logger.info("🛑 Actualizador detenido")