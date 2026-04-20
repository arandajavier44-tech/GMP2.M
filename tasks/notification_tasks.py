# tasks/notification_tasks.py
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)

def verificar_calibraciones_vencidas():
    """Verifica calibraciones próximas a vencer o vencidas"""
    try:
        from models.calibracion import Calibracion
        from services.notification_service import NotificationService
        
        hoy = date.today()
        
        # Calibraciones activas
        calibraciones = Calibracion.query.filter(
            Calibracion.estado == 'Activo'
        ).all()
        
        contador = 0
        for cal in calibraciones:
            if cal.fecha_proxima < hoy:
                # Vencida
                NotificationService.notificar_calibracion(cal, 'vencida')
                contador += 1
            elif (cal.fecha_proxima - hoy).days <= 7:
                # Próxima a vencer (7 días o menos)
                NotificationService.notificar_calibracion(cal, 'vencimiento_proximo')
                contador += 1
        
        if contador > 0:
            logger.info(f"✅ Verificadas calibraciones: {contador} notificaciones enviadas")
        
    except Exception as e:
        logger.error(f"❌ Error en verificar_calibraciones_vencidas: {e}")

def verificar_ordenes_vencimiento():
    """Verifica órdenes de trabajo próximas a vencer"""
    try:
        from models.orden_trabajo import OrdenTrabajo
        from services.notification_service import NotificationService
        
        hoy = date.today()
        
        ordenes = OrdenTrabajo.query.filter(
            OrdenTrabajo.fecha_estimada <= hoy + timedelta(days=3),
            OrdenTrabajo.fecha_estimada >= hoy,
            OrdenTrabajo.estado.in_(['Pendiente', 'En Progreso', 'Aprobada'])
        ).all()
        
        for orden in ordenes:
            NotificationService.notificar_orden_trabajo(orden, 'vencimiento')
        
        if len(ordenes) > 0:
            logger.info(f"✅ Verificadas órdenes: {len(ordenes)} notificaciones enviadas")
        
    except Exception as e:
        logger.error(f"❌ Error en verificar_ordenes_vencimiento: {e}")

def verificar_stock_bajo():
    """Verifica repuestos con stock bajo"""
    try:
        from models.inventario import Repuesto
        from services.notification_service import NotificationService
        from models.notificacion import Notificacion
        
        repuestos = Repuesto.query.filter(
            Repuesto.stock_actual <= Repuesto.stock_minimo
        ).all()
        
        for repuesto in repuestos:
            # Verificar si ya se notificó en los últimos 3 días
            notificacion_reciente = Notificacion.query.filter(
                Notificacion.elemento_id == repuesto.id,
                Notificacion.elemento_tipo == 'repuesto',
                Notificacion.fecha_creacion >= datetime.now() - timedelta(days=3)
            ).first()
            
            if not notificacion_reciente:
                NotificationService.notificar_stock_bajo(repuesto)
                logger.info(f"📦 Notificación de stock bajo para {repuesto.nombre}")
        
    except Exception as e:
        logger.error(f"❌ Error en verificar_stock_bajo: {e}")

def ejecutar_todas_verificaciones():
    """Ejecuta todas las verificaciones de notificaciones"""
    logger.info("🔄 Iniciando verificación de notificaciones...")
    verificar_calibraciones_vencidas()
    verificar_ordenes_vencimiento()
    verificar_stock_bajo()
    logger.info("✅ Verificación de notificaciones completada")

# Para pruebas manuales
if __name__ == '__main__':
    ejecutar_todas_verificaciones()