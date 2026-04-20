# utils/generador_notificaciones_auto.py
import logging
from datetime import datetime, date, timedelta
from models import db
from models.notificacion import Notificacion
from models.calibracion import Calibracion
from models.orden_trabajo import OrdenTrabajo
from models.capa import CAPA
from models.sistema import PlanMantenimiento
from models.documento import DocumentoGMP

logger = logging.getLogger(__name__)

class GeneradorNotificacionesAuto:
    def __init__(self):
        self.notificaciones_creadas = 0
    
    def generar_todas(self):
        """Genera todas las notificaciones automáticas"""
        self.generar_calibraciones_vencidas()
        self.generar_mantenimientos_vencidos()
        self.generar_ordenes_pendientes()
        self.generar_capas_vencidas()
        self.generar_documentos_pendientes_revision()
        
        db.session.commit()
        logger.info(f"✅ Generadas {self.notificaciones_creadas} notificaciones automáticas")
        return self.notificaciones_creadas
    
    def generar_calibraciones_vencidas(self):
        """Genera notificaciones para calibraciones próximas a vencer"""
        hoy = date.today()
        
        # Buscar calibraciones que vencen en los próximos 30 días
        calibraciones = Calibracion.query.filter(
            Calibracion.fecha_proxima >= hoy,
            Calibracion.fecha_proxima <= hoy + timedelta(days=30)
        ).all()
        
        for cal in calibraciones:
            dias = (cal.fecha_proxima - hoy).days
            
            # Verificar si ya existe notificación para esta calibración
            existe = Notificacion.query.filter_by(
                elemento_tipo='calibracion',
                elemento_id=cal.id,
                leida=False
            ).first()
            
            if not existe:
                equipo = cal.equipo
                titulo = f"🔔 Calibración próxima: {cal.instrumento}"
                mensaje = f"""El instrumento {cal.instrumento} del equipo {equipo.code if equipo else 'N/A'} vence en {dias} días.
Fecha: {cal.fecha_proxima.strftime('%d/%m/%Y')}"""
                
                prioridad = 'Alta' if dias <= 7 else 'Media'
                url = f"/calibraciones/ver/{cal.id}" if cal.id else None
                
                notif = Notificacion(
                    tipo='calibracion',
                    titulo=titulo,
                    mensaje=mensaje,
                    prioridad=prioridad,
                    elemento_id=cal.id,
                    elemento_tipo='calibracion',
                    area='mantenimiento',
                    url=url,
                    fecha_vencimiento=cal.fecha_proxima
                )
                db.session.add(notif)
                self.notificaciones_creadas += 1
                logger.info(f"📌 Notificación calibración: {cal.instrumento}")
    
    def generar_mantenimientos_vencidos(self):
        """Genera notificaciones para mantenimientos vencidos"""
        hoy = date.today()
        
        # Buscar planes de mantenimiento vencidos
        planes = PlanMantenimiento.query.filter(
            PlanMantenimiento.proxima_ejecucion <= hoy,
            PlanMantenimiento.activo == True
        ).all()
        
        for plan in planes:
            dias_atraso = (hoy - plan.proxima_ejecucion).days
            
            # Verificar si ya existe notificación
            existe = Notificacion.query.filter_by(
                elemento_tipo='plan_mantenimiento',
                elemento_id=plan.id,
                leida=False
            ).first()
            
            if not existe and plan.sistema and plan.sistema.equipo:
                equipo = plan.sistema.equipo
                titulo = f"🔧 Mantenimiento vencido: {equipo.code}"
                mensaje = f"""El mantenimiento preventivo del equipo {equipo.code} está vencido hace {dias_atraso} días.
Tarea: {plan.tarea_descripcion}"""
                
                prioridad = 'Alta' if dias_atraso > 15 else 'Media'
                url = f"/calendario/ver/{plan.id}" if plan.id else None
                
                notif = Notificacion(
                    tipo='mantenimiento',
                    titulo=titulo,
                    mensaje=mensaje,
                    prioridad=prioridad,
                    elemento_id=plan.id,
                    elemento_tipo='plan_mantenimiento',
                    area='mantenimiento',
                    url=url
                )
                db.session.add(notif)
                self.notificaciones_creadas += 1
                logger.info(f"📌 Notificación mantenimiento: {equipo.code}")
    
    def generar_ordenes_pendientes(self):
        """Genera notificaciones para órdenes de trabajo pendientes"""
        ordenes = OrdenTrabajo.query.filter_by(estado='Pendiente').all()
        
        for orden in ordenes:
            # Verificar si ya existe notificación
            existe = Notificacion.query.filter_by(
                elemento_tipo='orden',
                elemento_id=orden.id,
                leida=False
            ).first()
            
            if not existe and orden.equipo:
                equipo = orden.equipo
                titulo = f"📋 Orden pendiente: {orden.numero_ot}"
                mensaje = f"""La orden de trabajo {orden.numero_ot} está pendiente.
Equipo: {equipo.code}
Tipo: {orden.tipo}
Prioridad: {orden.prioridad}"""
                
                url = f"/ordenes/{orden.id}" if orden.id else None
                
                notif = Notificacion(
                    tipo='orden',
                    titulo=titulo,
                    mensaje=mensaje,
                    prioridad=orden.prioridad,
                    elemento_id=orden.id,
                    elemento_tipo='orden',
                    area='mantenimiento',
                    url=url
                )
                db.session.add(notif)
                self.notificaciones_creadas += 1
                logger.info(f"📌 Notificación orden: {orden.numero_ot}")
    
    def generar_capas_vencidas(self):
        """Genera notificaciones para CAPAs abiertas por mucho tiempo"""
        hoy = date.today()
        
        capas = CAPA.query.filter_by(estado='Abierta').all()
        
        for capa in capas:
            dias = (hoy - capa.fecha_deteccion).days
            
            # Notificar solo si lleva más de 30 días
            if dias > 30:
                existe = Notificacion.query.filter_by(
                    elemento_tipo='capa',
                    elemento_id=capa.id,
                    leida=False
                ).first()
                
                if not existe:
                    titulo = f"⚠️ CAPA crítica: {capa.numero_capa}"
                    mensaje = f"""La CAPA {capa.numero_capa} lleva {dias} días abierta.
Título: {capa.titulo}
Responsable: {capa.responsable or 'No asignado'}"""
                    
                    prioridad = 'Alta' if dias > 60 else 'Media'
                    url = f"/capa/ver/{capa.id}" if capa.id else None
                    
                    notif = Notificacion(
                        tipo='capa',
                        titulo=titulo,
                        mensaje=mensaje,
                        prioridad=prioridad,
                        elemento_id=capa.id,
                        elemento_tipo='capa',
                        area='calidad',
                        url=url
                    )
                    db.session.add(notif)
                    self.notificaciones_creadas += 1
                    logger.info(f"📌 Notificación CAPA: {capa.numero_capa}")
    
    def generar_documentos_pendientes_revision(self):
        """Genera notificaciones para documentos que requieren revisión"""
        hoy = date.today()
        
        documentos = DocumentoGMP.query.filter(
            DocumentoGMP.fecha_proxima_revision <= hoy,
            DocumentoGMP.estado == 'Vigente'
        ).all()
        
        for doc in documentos:
            dias_atraso = (hoy - doc.fecha_proxima_revision).days
            
            existe = Notificacion.query.filter_by(
                elemento_tipo='documento',
                elemento_id=doc.id,
                leida=False
            ).first()
            
            if not existe:
                titulo = f"📄 Revisión pendiente: {doc.codigo}"
                mensaje = f"""El documento {doc.codigo} requiere revisión.
Título: {doc.titulo}
Vencido hace: {dias_atraso} días"""
                
                url = f"/documentacion/ver/{doc.id}" if doc.id else None
                
                notif = Notificacion(
                    tipo='documento',
                    titulo=titulo,
                    mensaje=mensaje,
                    prioridad='Media',
                    elemento_id=doc.id,
                    elemento_tipo='documento',
                    area='calidad',
                    url=url
                )
                db.session.add(notif)
                self.notificaciones_creadas += 1
                logger.info(f"📌 Notificación documento: {doc.codigo}")

# Instancia global
generador_auto = GeneradorNotificacionesAuto()