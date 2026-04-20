# utils/notificador.py
import logging
from datetime import datetime, date, timedelta
from models import db
from models.usuario import Usuario
from models.calibracion import Calibracion
from models.orden_trabajo import OrdenTrabajo
from models.capa import CAPA
from models.sistema import PlanMantenimiento
import os
import requests

# Configurar logging
logger = logging.getLogger(__name__)


class NotificadorSMS:
    def __init__(self):
        self.habilitado = False
        self.proveedor = None
        
        # Intentar importar twilio (opcional)
        try:
            from twilio.rest import Client
            self.twilio_client = None
            
            # Leer credenciales de variables de entorno
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            self.remitente = os.environ.get('TWILIO_PHONE_NUMBER')
            
            if account_sid and auth_token and self.remitente:
                self.twilio_client = Client(account_sid, auth_token)
                self.habilitado = True
                self.proveedor = 'twilio'
                logger.info("✅ Notificador SMS inicializado con Twilio")
            else:
                logger.warning("⚠️ Credenciales de Twilio no configuradas. SMS deshabilitados.")
                
        except ImportError:
            # Soporte para gateway alternativo
            self.sms_gateway_url = os.environ.get('SMS_GATEWAY_URL')
            self.sms_api_key = os.environ.get('SMS_API_KEY')
            
            if self.sms_gateway_url and self.sms_api_key:
                self.habilitado = True
                self.proveedor = 'gateway'
                logger.info("✅ Notificador SMS inicializado con Gateway")
            else:
                logger.warning("⚠️ Twilio no instalado. SMS deshabilitados.")
    
    def enviar_sms(self, destino, mensaje):
        """Envía un SMS a un número de teléfono"""
        if not self.habilitado:
            logger.info(f"📱 [SMS SIMULADO] Para: {destino}")
            logger.info(f"   Mensaje: {mensaje[:100]}...")
            return True
        
        try:
            # Limitar longitud del mensaje (SMS estándar)
            if len(mensaje) > 160:
                mensaje = mensaje[:157] + "..."
            
            if self.proveedor == 'twilio':
                self.twilio_client.messages.create(
                    body=mensaje,
                    from_=self.remitente,
                    to=destino
                )
            elif self.proveedor == 'gateway':
                response = requests.post(
                    self.sms_gateway_url,
                    json={
                        'api_key': self.sms_api_key,
                        'to': destino,
                        'message': mensaje,
                        'from': self.remitente
                    },
                    timeout=10
                )
                if response.status_code != 200:
                    raise Exception(f"Gateway respondió: {response.status_code}")
            
            logger.info(f"✅ SMS enviado a {destino}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enviando SMS: {e}")
            return False
    
    def enviar_sms_multiple(self, destinos, mensaje):
        """Envía SMS a múltiples destinatarios"""
        enviados = 0
        for destino in destinos:
            if self.enviar_sms(destino, mensaje):
                enviados += 1
        return enviados


class GestorNotificaciones:
    def __init__(self):
        self.sms = NotificadorSMS()
    
    def notificar_calibracion_proxima(self, calibracion, dias):
        """Notifica sobre una calibración próxima a vencer"""
        if not calibracion.equipo:
            return
        
        mensaje = f"🔔 ALERTA CALIBRACIÓN: {calibracion.instrumento} del equipo {calibracion.equipo.code} vence en {dias} días. Programar calibración."
        
        # Buscar responsables
        telefonos = self._obtener_telefonos_responsables(['mantenimiento', 'calidad'])
        
        if telefonos:
            self.sms.enviar_sms_multiple(telefonos, mensaje)
    
    def notificar_orden_pendiente(self, orden):
        """Notifica sobre una orden de trabajo pendiente"""
        if not orden.equipo:
            return
        
        prioridad_icon = {
            'Alta': '🔴',
            'Media': '🟡',
            'Baja': '🟢'
        }.get(orden.prioridad, '⚪')
        
        mensaje = f"{prioridad_icon} ORDEN {orden.tipo}: {orden.numero_ot} - {orden.equipo.code}. Prioridad: {orden.prioridad}"
        
        # Buscar responsables
        telefonos = self._obtener_telefonos_responsables(['mantenimiento'])
        
        if orden.asignado_a:
            usuario = Usuario.query.filter_by(username=orden.asignado_a).first()
            if usuario and usuario.telefono:
                telefonos.append(usuario.telefono)
        
        if telefonos:
            self.sms.enviar_sms_multiple(telefonos, mensaje)
    
    def notificar_capa_vencida(self, capa):
        """Notifica sobre una CAPA abierta por mucho tiempo"""
        dias = (date.today() - capa.fecha_deteccion).days
        
        mensaje = f"⚠️ CAPA URGENTE: {capa.numero_capa} lleva {dias} días abierta. Responsable: {capa.responsable or 'No asignado'}"
        
        telefonos = self._obtener_telefonos_responsables(['calidad', 'administracion'])
        
        if telefonos:
            self.sms.enviar_sms_multiple(telefonos, mensaje)
    
    def notificar_mantenimiento_vencido(self, plan):
        """Notifica sobre un mantenimiento preventivo vencido"""
        if not plan.sistema or not plan.sistema.equipo:
            return
        
        dias_atraso = (date.today() - plan.proxima_ejecucion).days
        
        mensaje = f"🔧 MANTENIMIENTO VENCIDO: {plan.sistema.equipo.code} - {plan.tarea_descripcion[:30]}. Vencido hace {dias_atraso} días"
        
        telefonos = self._obtener_telefonos_responsables(['mantenimiento'])
        
        if telefonos:
            self.sms.enviar_sms_multiple(telefonos, mensaje)
    
    def notificar_orden_por_sms(self, orden, destinatario):
        """Envía SMS específico para una orden a un destinatario"""
        prioridad_icon = {
            'Alta': '🔴',
            'Media': '🟡',
            'Baja': '🟢'
        }.get(orden.prioridad, '⚪')
        
        mensaje = f"{prioridad_icon} GMP: OT {orden.numero_ot} - {orden.titulo[:30]}. Equipo: {orden.equipo.code if orden.equipo else 'N/A'}. Prioridad: {orden.prioridad}"
        
        return self.sms.enviar_sms(destinatario.telefono, mensaje)
    
    def notificar_calibracion_por_sms(self, calibracion, destinatario, dias):
        """Envía SMS para calibración a un destinatario"""
        mensaje = f"⚠️ GMP: Calibración de {calibracion.instrumento} vence en {dias} días. Equipo: {calibracion.equipo.code if calibracion.equipo else 'N/A'}"
        
        return self.sms.enviar_sms(destinatario.telefono, mensaje)
    
    def _obtener_telefonos_responsables(self, areas):
        """Obtiene números de teléfono de usuarios en áreas específicas"""
        telefonos = []
        for area in areas:
            usuarios = Usuario.query.filter_by(area_principal=area, activo=True).all()
            for u in usuarios:
                if u.telefono:
                    telefono = u.telefono.strip()
                    if telefono and len(telefono) >= 8:
                        telefonos.append(telefono)
        return list(set(telefonos))

# Instancia global
notificador = GestorNotificaciones()