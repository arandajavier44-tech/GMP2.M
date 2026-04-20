# tasks/generar_notificaciones_reales.py
import logging
from datetime import datetime, date, timedelta
from models import db
from models.calibracion import Calibracion
from models.orden_trabajo import OrdenTrabajo
from models.capa import CAPA
from models.sistema import PlanMantenimiento
from models.documento import DocumentoGMP
from models.inventario import Repuesto
from utils.notificador_bd import notificador_bd
from utils.generador_notificaciones_auto import generador_auto

logger = logging.getLogger(__name__)

def generar_todas_notificaciones_reales():
    """Genera todas las notificaciones a partir de datos REALES usando el generador existente"""
    logger.info("=" * 50)
    logger.info("🔄 Generando notificaciones desde datos REALES...")
    logger.info("=" * 50)
    
    total = 0
    
    # Usar el generador automático existente
    total = generador_auto.generar_todas()
    
    # También generar notificaciones adicionales específicas
    total += generar_notificaciones_ordenes_vencimiento()
    total += generar_notificaciones_stock_bajo()
    
    logger.info("=" * 50)
    logger.info(f"✅ TOTAL: {total} notificaciones generadas desde datos REALES")
    logger.info("=" * 50)
    
    return total

def generar_notificaciones_ordenes_vencimiento():
    """Genera notificaciones para órdenes próximas a vencer"""
    hoy = date.today()
    notificaciones_creadas = 0
    
    ordenes = OrdenTrabajo.query.filter(
        OrdenTrabajo.fecha_estimada <= hoy + timedelta(days=3),
        OrdenTrabajo.fecha_estimada >= hoy,
        OrdenTrabajo.estado.in_(['Pendiente', 'En Progreso'])
    ).all()
    
    for orden in ordenes:
        dias = (orden.fecha_estimada - hoy).days
        titulo = f"⚠️ OT próxima a vencer: {orden.numero_ot}"
        mensaje = f"La orden {orden.numero_ot} vence en {dias} días. Prioridad: {orden.prioridad}"
        
        notificador_bd.crear_notificacion(
            tipo='orden',
            titulo=titulo,
            mensaje=mensaje,
            prioridad='Alta',
            elemento_id=orden.id,
            elemento_tipo='orden',
            area='mantenimiento',
            url=f"/ordenes/{orden.id}"
        )
        notificaciones_creadas += 1
        logger.info(f"📋 Notificación vencimiento OT: {orden.numero_ot}")
    
    return notificaciones_creadas

def generar_notificaciones_stock_bajo():
    """Genera notificaciones para repuestos con stock bajo"""
    notificaciones_creadas = 0
    
    repuestos = Repuesto.query.filter(
        Repuesto.stock_actual <= Repuesto.stock_minimo
    ).all()
    
    for repuesto in repuestos:
        titulo = f"📦 Stock bajo: {repuesto.nombre}"
        mensaje = f"Stock actual: {repuesto.stock_actual} (mínimo: {repuesto.stock_minimo})"
        
        notificador_bd.crear_notificacion(
            tipo='recordatorio',
            titulo=titulo,
            mensaje=mensaje,
            prioridad='Media',
            elemento_id=repuesto.id,
            elemento_tipo='repuesto',
            area='almacen',
            url=f"/inventario/repuestos/ver/{repuesto.id}"
        )
        notificaciones_creadas += 1
        logger.info(f"📦 Notificación stock bajo: {repuesto.nombre}")
    
    return notificaciones_creadas