# services/notification_service.py
from models.notificacion import Notificacion
from models import db
from datetime import datetime
from utils.notificador_bd import notificador_bd
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Servicio unificado de notificaciones - Usa notificador_bd existente"""
    
    @staticmethod
    def crear_notificacion(tipo, titulo, mensaje, prioridad='Media', 
                           usuario_id=None, area=None, elemento_id=None, 
                           elemento_tipo=None, url=None, fecha_vencimiento=None):
        """Crea una nueva notificación usando notificador_bd"""
        return notificador_bd.crear_notificacion(
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            prioridad=prioridad,
            elemento_id=elemento_id,
            elemento_tipo=elemento_tipo,
            area=area,
            usuario_id=usuario_id,
            url=url,
            fecha_vencimiento=fecha_vencimiento
        )
    
    @staticmethod
    def notificar_orden_trabajo(orden, evento, usuario_destino=None):
        """Genera notificaciones para órdenes de trabajo"""
        from utils.notificador_bd import notificador_bd
        
        if evento == 'creacion':
            notificador_bd.notificar_orden(orden)
        elif evento == 'vencimiento':
            # Notificación personalizada para vencimiento
            equipo = orden.equipo
            titulo = f"⚠️ OT próxima a vencer: {orden.numero_ot}"
            mensaje = f"La orden {orden.numero_ot} del equipo {equipo.code if equipo else 'N/A'} vence pronto."
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
    
    @staticmethod
    def notificar_calibracion(calibracion, evento):
        """Genera notificaciones para calibraciones"""
        from utils.notificador_bd import notificador_bd
        
        if evento == 'vencimiento_proximo':
            dias = (calibracion.fecha_proxima - datetime.now().date()).days
            notificador_bd.notificar_calibracion(calibracion, dias)
        elif evento == 'vencida':
            notificador_bd.notificar_calibracion(calibracion, 0)
    
    @staticmethod
    def notificar_capa(capa, evento):
        """Genera notificaciones para CAPAs"""
        from utils.notificador_bd import notificador_bd
        
        if evento == 'vencimiento':
            notificador_bd.notificar_capa(capa, 30)
        elif evento == 'verificacion':
            titulo = f"✅ CAPA lista para verificar: {capa.numero_capa}"
            mensaje = f"La CAPA {capa.numero_capa} requiere verificación de eficacia."
            notificador_bd.crear_notificacion(
                tipo='capa',
                titulo=titulo,
                mensaje=mensaje,
                prioridad='Alta',
                elemento_id=capa.id,
                elemento_tipo='capa',
                area='calidad',
                url=f"/capa/ver/{capa.id}"
            )
    
    @staticmethod
    def notificar_mantenimiento(plan, dias_atraso):
        """Genera notificaciones para mantenimientos"""
        from utils.notificador_bd import notificador_bd
        notificador_bd.notificar_mantenimiento(plan, dias_atraso)
    
    @staticmethod
    def notificar_stock_bajo(repuesto):
        """Genera notificación para stock bajo"""
        from utils.notificador_bd import notificador_bd
        titulo = f"📦 Stock bajo: {repuesto.nombre}"
        mensaje = f"Stock actual: {repuesto.stock_actual} unidades. Mínimo: {repuesto.stock_minimo}"
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
    
    @staticmethod
    def notificar_documento(documento):
        """Genera notificaciones para documentos"""
        from utils.notificador_bd import notificador_bd
        notificador_bd.notificar_documento(documento)