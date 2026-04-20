# utils/notificador_bd.py
from models import db
from models.notificacion import Notificacion
from models.usuario import Usuario
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


class NotificadorBD:
    def __init__(self):
        pass
    
    def _enviar_notificaciones_email_sms(self, notificacion, datos_adicionales=None):
        """Envía notificaciones por email y SMS según el tipo"""
        try:
            from utils.notificador_email import notificador_email
            from utils.notificador import notificador
            
            # Determinar destinatarios según el tipo
            destinatarios = []
            
            if notificacion.tipo == 'orden':
                # Técnicos de mantenimiento
                tecnicos = Usuario.query.filter(
                    Usuario.area_principal == 'mantenimiento',
                    Usuario.activo == True,
                    Usuario.email.isnot(None)
                ).all()
                destinatarios.extend(tecnicos)
                
                # Supervisores
                supervisores = Usuario.query.filter(
                    Usuario.nivel_jerarquico.in_(['jefe', 'supervisor']),
                    Usuario.activo == True
                ).all()
                destinatarios.extend(supervisores)
                
                # Técnico específico asignado
                if datos_adicionales and datos_adicionales.get('orden') and datos_adicionales['orden'].asignado_a:
                    tecnico = Usuario.query.filter_by(username=datos_adicionales['orden'].asignado_a).first()
                    if tecnico and tecnico not in destinatarios:
                        destinatarios.append(tecnico)
            
            elif notificacion.tipo == 'calibracion':
                # Responsables de calidad
                responsables = Usuario.query.filter(
                    Usuario.area_principal == 'calidad',
                    Usuario.activo == True,
                    Usuario.email.isnot(None)
                ).all()
                destinatarios.extend(responsables)
            
            elif notificacion.tipo == 'capa':
                # Calidad y administración
                responsables = Usuario.query.filter(
                    Usuario.area_principal.in_(['calidad', 'administracion']),
                    Usuario.activo == True
                ).all()
                destinatarios.extend(responsables)
            
            # Enviar emails y SMS
            for destinatario in destinatarios:
                if destinatario.email and notificacion.prioridad == 'Alta':
                    if notificacion.tipo == 'orden' and datos_adicionales and datos_adicionales.get('orden'):
                        notificador_email.enviar_notificacion_orden(
                            datos_adicionales['orden'], 
                            destinatario, 
                            'nueva'
                        )
                    elif notificacion.tipo == 'calibracion' and datos_adicionales and datos_adicionales.get('calibracion'):
                        notificador_email.enviar_notificacion_calibracion(
                            datos_adicionales['calibracion'],
                            destinatario,
                            datos_adicionales.get('dias', 0)
                        )
                
                if destinatario.telefono and notificacion.prioridad == 'Alta':
                    if notificacion.tipo == 'orden' and datos_adicionales and datos_adicionales.get('orden'):
                        notificador.notificar_orden_por_sms(
                            datos_adicionales['orden'],
                            destinatario
                        )
                    elif notificacion.tipo == 'calibracion' and datos_adicionales and datos_adicionales.get('calibracion'):
                        notificador.notificar_calibracion_por_sms(
                            datos_adicionales['calibracion'],
                            destinatario,
                            datos_adicionales.get('dias', 0)
                        )
        except Exception as e:
            logger.error(f"❌ Error enviando notificaciones email/sms: {e}")
    
    def crear_notificacion(self, tipo, titulo, mensaje, prioridad, elemento_id=None, 
                           elemento_tipo=None, area=None, usuario_id=None, url=None, 
                           fecha_vencimiento=None, enviar_email_sms=True):
        """Crea una notificación en la base de datos y opcionalmente envía email/SMS"""
        try:
            notif = Notificacion(
                tipo=tipo,
                titulo=titulo,
                mensaje=mensaje,
                prioridad=prioridad,
                elemento_id=elemento_id,
                elemento_tipo=elemento_tipo,
                area=area,
                usuario_id=usuario_id,
                url=url,
                fecha_vencimiento=fecha_vencimiento,
                leida=False
            )
            db.session.add(notif)
            db.session.commit()
            
            # Enviar email y SMS para prioridad Alta
            if enviar_email_sms and prioridad == 'Alta':
                datos_adicionales = {}
                if elemento_tipo == 'orden' and elemento_id:
                    from models.orden_trabajo import OrdenTrabajo
                    datos_adicionales['orden'] = OrdenTrabajo.query.get(elemento_id)
                elif elemento_tipo == 'calibracion' and elemento_id:
                    from models.calibracion import Calibracion
                    datos_adicionales['calibracion'] = Calibracion.query.get(elemento_id)
                    if fecha_vencimiento:
                        dias = (fecha_vencimiento - date.today()).days
                        datos_adicionales['dias'] = dias
                
                self._enviar_notificaciones_email_sms(notif, datos_adicionales)
            
            logger.info(f"✅ Notificación creada: {titulo}")
            return notif
        except Exception as e:
            logger.error(f"❌ Error creando notificación: {e}")
            db.session.rollback()
            return None
    
    def notificar_calibracion(self, calibracion, dias):
        """Crea notificación de calibración"""
        equipo = calibracion.equipo
        titulo = f"🔔 Calibración: {calibracion.instrumento}"
        mensaje = f"""
Instrumento: {calibracion.instrumento}
Código: {calibracion.codigo_instrumento or 'N/A'}
Equipo: {equipo.code if equipo else 'N/A'} - {equipo.name if equipo else 'N/A'}
Vence en: {dias} días
Fecha: {calibracion.fecha_proxima.strftime('%d/%m/%Y')}
        """
        
        prioridad = 'Alta' if dias <= 7 else 'Media'
        url = f"/calibraciones/ver/{calibracion.id}" if calibracion.id else None
        
        return self.crear_notificacion(
            tipo='calibracion',
            titulo=titulo,
            mensaje=mensaje,
            prioridad=prioridad,
            elemento_id=calibracion.id,
            elemento_tipo='calibracion',
            area='mantenimiento',
            url=url,
            fecha_vencimiento=calibracion.fecha_proxima
        )
    
    def notificar_mantenimiento(self, plan, dias_atraso):
        """Crea notificación de mantenimiento vencido"""
        equipo = plan.sistema.equipo if plan.sistema else None
        titulo = f"🔧 Mantenimiento vencido"
        mensaje = f"""
Equipo: {equipo.code if equipo else 'N/A'} - {equipo.name if equipo else 'N/A'}
Sistema: {plan.sistema.nombre if plan.sistema else 'N/A'}
Tarea: {plan.tarea_descripcion}
Vencido hace: {dias_atraso} días
Frecuencia: cada {plan.frecuencia_dias} días
        """
        
        prioridad = 'Alta' if dias_atraso > 15 else 'Media'
        url = f"/calendario/ver/{plan.id}" if plan.id else None
        
        return self.crear_notificacion(
            tipo='mantenimiento',
            titulo=titulo,
            mensaje=mensaje,
            prioridad=prioridad,
            elemento_id=plan.id,
            elemento_tipo='plan_mantenimiento',
            area='mantenimiento',
            url=url
        )
    
    def notificar_capa(self, capa, dias):
        """Crea notificación de CAPA"""
        titulo = f"⚠️ CAPA: {capa.numero_capa}"
        mensaje = f"""
Número: {capa.numero_capa}
Título: {capa.titulo}
Responsable: {capa.responsable or 'No asignado'}
Días abierta: {dias}
Fecha detección: {capa.fecha_deteccion.strftime('%d/%m/%Y')}
        """
        
        prioridad = 'Alta' if dias > 60 else 'Media'
        url = f"/capa/ver/{capa.id}" if capa.id else None
        
        return self.crear_notificacion(
            tipo='capa',
            titulo=titulo,
            mensaje=mensaje,
            prioridad=prioridad,
            elemento_id=capa.id,
            elemento_tipo='capa',
            area='calidad',
            url=url
        )
    
    def notificar_orden(self, orden):
        """Crea notificación de orden de trabajo"""
        equipo = orden.equipo
        titulo = f"📋 OT: {orden.numero_ot}"
        mensaje = f"""
N° OT: {orden.numero_ot}
Tipo: {orden.tipo}
Equipo: {equipo.code if equipo else 'N/A'}
Prioridad: {orden.prioridad}
Asignado a: {orden.asignado_a or 'Sin asignar'}
        """
        
        url = f"/ordenes/{orden.id}" if orden.id else None
        
        # Notificar al técnico asignado específicamente
        if orden.asignado_a:
            usuario = Usuario.query.filter_by(username=orden.asignado_a).first()
            if usuario:
                self.crear_notificacion(
                    tipo='orden',
                    titulo=titulo,
                    mensaje=mensaje,
                    prioridad=orden.prioridad,
                    elemento_id=orden.id,
                    elemento_tipo='orden',
                    usuario_id=usuario.id,
                    url=url
                )
        
        # También notificar al área de mantenimiento
        return self.crear_notificacion(
            tipo='orden',
            titulo=titulo,
            mensaje=mensaje,
            prioridad=orden.prioridad,
            elemento_id=orden.id,
            elemento_tipo='orden',
            area='mantenimiento',
            url=url
        )
    
    def notificar_documento(self, documento):
        """Crea notificación de documento generado"""
        titulo = f"📄 Documento generado: {documento.codigo}"
        mensaje = f"""
Documento: {documento.titulo}
Código: {documento.codigo}
Tipo: {documento.tipo.upper()}
Estado: {documento.estado}
        """
        
        url = f"/documentacion/ver/{documento.id}" if documento.id else None
        
        return self.crear_notificacion(
            tipo='documento',
            titulo=titulo,
            mensaje=mensaje,
            prioridad='Media',
            elemento_id=documento.id,
            elemento_tipo='documento',
            area='mantenimiento',
            url=url
        )

# Instancia global
notificador_bd = NotificadorBD()