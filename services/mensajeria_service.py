# services/mensajeria_service.py
from models import db
from models.mensaje import Mensaje, HistorialMensaje
from models.usuario import Usuario
from utils.notificador_bd import notificador_bd
from utils.notificador_email import notificador_email
import re
import logging

logger = logging.getLogger(__name__)

class MensajeriaService:
    
    @staticmethod
    def enviar_mensaje(entidad_tipo, entidad_id, remitente_id, mensaje, 
                       destinatario_id=None, mencionar_a=None, adjuntos=None):
        """Envía un mensaje asociado a una entidad"""
        
        # Procesar menciones en el texto
        menciones = MensajeriaService._extraer_menciones(mensaje)
        if mencionar_a:
            menciones.extend(mencionar_a)
        menciones = list(set(menciones))
        
        nuevo_mensaje = Mensaje(
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            remitente_id=remitente_id,
            destinatario_id=destinatario_id,
            mensaje=mensaje,
            menciones=menciones,
            adjuntos=adjuntos or [],
            leido=False
        )
        
        db.session.add(nuevo_mensaje)
        db.session.commit()
        
        # Registrar historial
        historial = HistorialMensaje(
            mensaje_id=nuevo_mensaje.id,
            usuario_id=remitente_id,
            accion='CREADO'
        )
        db.session.add(historial)
        db.session.commit()
        
        # Notificar a destinatarios
        MensajeriaService._notificar_destinatarios(nuevo_mensaje, entidad_tipo, entidad_id)
        
        return nuevo_mensaje
    
    @staticmethod
    def _extraer_menciones(texto):
        """Extrae @menciones del texto"""
        patron = r'@(\w+)'
        return re.findall(patron, texto)
    
    @staticmethod
    def _notificar_destinatarios(mensaje, entidad_tipo, entidad_id):
        """Envía notificaciones a los destinatarios y mencionados"""
        
        # Notificar al destinatario directo
        if mensaje.destinatario_id:
            destinatario = Usuario.query.get(mensaje.destinatario_id)
            if destinatario:
                MensajeriaService._crear_notificacion(
                    destinatario,
                    mensaje,
                    entidad_tipo,
                    entidad_id
                )
        
        # Notificar a usuarios mencionados
        for username in mensaje.menciones:
            usuario = Usuario.query.filter_by(username=username).first()
            if usuario and usuario.id != mensaje.destinatario_id:
                MensajeriaService._crear_notificacion(
                    usuario,
                    mensaje,
                    entidad_tipo,
                    entidad_id
                )
    
    @staticmethod
    def _crear_notificacion(usuario, mensaje, entidad_tipo, entidad_id):
        """Crea notificación en BD y envía email"""
        
        # URLs según tipo de entidad
        urls = {
            'orden': f'/ordenes/{entidad_id}',
            'capa': f'/capa/ver/{entidad_id}',
            'calibracion': f'/calibraciones/ver/{entidad_id}',
            'documento': f'/documentacion/ver/{entidad_id}',
            'inspeccion': f'/inspecciones/ver/{entidad_id}'
        }
        
        titulo = f"💬 Nuevo mensaje en {entidad_tipo.upper()}"
        cuerpo = f"{mensaje.remitente.nombre_completo or mensaje.remitente.username} te ha mencionado: {mensaje.mensaje[:100]}"
        
        # Notificación en BD
        notificador_bd.crear_notificacion(
            tipo='mensaje',
            titulo=titulo,
            mensaje=cuerpo,
            prioridad='Media',
            usuario_id=usuario.id,
            elemento_id=entidad_id,
            elemento_tipo=entidad_tipo,
            url=urls.get(entidad_tipo, '/dashboard')
        )
        
        # Email si tiene correo
        if usuario.email:
            notificador_email.enviar(
                usuario.email,
                f"[GMP] {titulo}",
                f"""
                <h3>{titulo}</h3>
                <p><strong>De:</strong> {mensaje.remitente.nombre_completo or mensaje.remitente.username}</p>
                <p><strong>Mensaje:</strong></p>
                <div style="background:#f4f4f4; padding:10px; border-radius:5px;">
                    {mensaje.mensaje}
                </div>
                <p><a href="http://localhost:5000{urls.get(entidad_tipo, '/dashboard')}">Ver conversación</a></p>
                """
            )
    
    @staticmethod
    def obtener_conversacion(entidad_tipo, entidad_id):
        """Obtiene todos los mensajes de una entidad"""
        mensajes = Mensaje.query.filter_by(
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id
        ).order_by(Mensaje.created_at.asc()).all()
        
        return [{
            'id': m.id,
            'remitente': m.remitente.nombre_completo or m.remitente.username,
            'remitente_id': m.remitente_id,
            'mensaje': m.mensaje,
            'fecha': m.created_at.strftime('%d/%m/%Y %H:%M'),
            'menciones': m.menciones,
            'adjuntos': m.adjuntos,
            'respuestas': len(m.respuestas)
        } for m in mensajes]
    
    @staticmethod
    def marcar_leido(mensaje_id, usuario_id):
        """Marca un mensaje como leído"""
        mensaje = Mensaje.query.get(mensaje_id)
        if mensaje and not mensaje.leido:
            mensaje.leido = True
            mensaje.fecha_lectura = datetime.utcnow()
            
            historial = HistorialMensaje(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id,
                accion='LEIDO'
            )
            db.session.add(historial)
            db.session.commit()
            return True
        return False

# Instancia global
mensajeria = MensajeriaService()