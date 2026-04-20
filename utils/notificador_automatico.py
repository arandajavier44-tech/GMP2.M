# utils/notificador_automatico.py
import schedule
import time
import logging
from datetime import datetime, date, timedelta
from models import db
from models.calibracion import Calibracion
from models.orden_trabajo import OrdenTrabajo
from models.capa import CAPA
from models.sistema import PlanMantenimiento
from utils.notificador_bd import notificador_bd
from utils.notificador_email import notificador

logger = logging.getLogger(__name__)

class notificador_automatico:
    def __init__(self):
        self.ejecutando = True
        
    def iniciar(self):
        """Inicia el programador de notificaciones"""
        schedule.every(6).hours.do(self.ejecutar_notificaciones)
        schedule.every(1).minutes.do(self.ejecutar_notificaciones).tag('inicio')
        
        logger.info("📱 Notificador automático programado:")
        logger.info("   - Notificaciones cada 6 horas")
        
        while self.ejecutando:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("🛑 Deteniendo notificador...")
                self.ejecutando = False
                break
            except Exception as e:
                logger.error(f"Error en bucle principal: {e}")
                time.sleep(60)
    
    def ejecutar_notificaciones(self):
        """Ejecuta el proceso de notificaciones"""
        logger.info(f"\n{'📱'*25}")
        logger.info(f"📱 Iniciando notificaciones automáticas: {datetime.now()}")
        logger.info(f"{'📱'*25}")
        
        try:
            inicio = time.time()
            
            self._verificar_calibraciones()
            self._verificar_ordenes()
            self._verificar_capas()
            self._verificar_mantenimientos()
            
            duracion = time.time() - inicio
            logger.info(f"✅ Notificaciones completadas en {duracion:.2f}s")
            
            schedule.clear('inicio')
            
        except Exception as e:
            logger.error(f"❌ Error en notificaciones: {e}")
    
    def _verificar_calibraciones(self):
        """Verifica calibraciones próximas a vencer"""
        hoy = date.today()
        limite_7 = hoy + timedelta(days=7)
        limite_15 = hoy + timedelta(days=15)
        
        criticas = Calibracion.query.filter(
            Calibracion.fecha_proxima <= limite_7,
            Calibracion.fecha_proxima > hoy,
            Calibracion.estado == 'Activo'
        ).all()
        
        for cal in criticas:
            dias = (cal.fecha_proxima - hoy).days
            notificador_bd.notificar_calibracion(cal, dias)
            logger.info(f"   📱 Calibración URGENTE: {cal.instrumento} vence en {dias} días")
        
        proximas = Calibracion.query.filter(
            Calibracion.fecha_proxima <= limite_15,
            Calibracion.fecha_proxima > limite_7,
            Calibracion.estado == 'Activo'
        ).all()
        
        for cal in proximas:
            dias = (cal.fecha_proxima - hoy).days
            notificador_bd.notificar_calibracion(cal, dias)
            logger.info(f"   📋 Calibración próxima: {cal.instrumento} vence en {dias} días")
    
    def _verificar_ordenes(self):
        """Verifica órdenes de alta prioridad pendientes"""
        ordenes = OrdenTrabajo.query.filter(
            OrdenTrabajo.prioridad.in_(['Alta', 'Crítica']),
            OrdenTrabajo.estado == 'Pendiente'
        ).all()
        
        for orden in ordenes:
            notificador_bd.notificar_orden(orden)
            logger.info(f"   📱 Orden {orden.prioridad}: {orden.numero_ot}")
    
    def _verificar_capas(self):
        """Verifica CAPAs abiertas por más de 30 días"""
        hoy = date.today()
        limite_30 = hoy - timedelta(days=30)
        limite_60 = hoy - timedelta(days=60)
        
        capas_30 = CAPA.query.filter(
            CAPA.estado.in_(['Abierto', 'En Análisis', 'En Implementación']),
            CAPA.fecha_deteccion <= limite_30,
            CAPA.fecha_deteccion > limite_60
        ).all()
        
        for capa in capas_30:
            dias = (hoy - capa.fecha_deteccion).days
            notificador_bd.notificar_capa(capa, dias)
            logger.info(f"   📋 CAPA pendiente: {capa.numero_capa} - {dias} días")
        
        capas_60 = CAPA.query.filter(
            CAPA.estado.in_(['Abierto', 'En Análisis', 'En Implementación']),
            CAPA.fecha_deteccion <= limite_60
        ).all()
        
        for capa in capas_60:
            dias = (hoy - capa.fecha_deteccion).days
            notificador_bd.notificar_capa(capa, dias)
            logger.info(f"   📱 CAPA URGENTE: {capa.numero_capa} - {dias} días")
    
    def _verificar_mantenimientos(self):
        """Verifica mantenimientos preventivos vencidos"""
        hoy = date.today()
        limite_7 = hoy - timedelta(days=7)
        limite_30 = hoy - timedelta(days=30)
        
        recientes = PlanMantenimiento.query.filter(
            PlanMantenimiento.proxima_ejecucion < hoy,
            PlanMantenimiento.proxima_ejecucion >= limite_7,
            PlanMantenimiento.activo == True
        ).all()
        
        for plan in recientes:
            dias = (hoy - plan.proxima_ejecucion).days
            notificador_bd.notificar_mantenimiento(plan, dias)
            logger.info(f"   📋 Mantenimiento vencido: {plan.tarea_descripcion[:30]} - {dias} días")
        
        vencidos = PlanMantenimiento.query.filter(
            PlanMantenimiento.proxima_ejecucion < limite_7,
            PlanMantenimiento.activo == True
        ).limit(10).all()
        
        for plan in vencidos:
            dias = (hoy - plan.proxima_ejecucion).days
            notificador_bd.notificar_mantenimiento(plan, dias)
            logger.info(f"   📱 Mantenimiento URGENTE: {plan.tarea_descripcion[:30]} - {dias} días")
    
    def detener(self):
        """Detiene el notificador"""
        self.ejecutando = False
        logger.info("📱 Notificador detenido")