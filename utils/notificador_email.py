# -*- coding: utf-8 -*-
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

logger = logging.getLogger(__name__)


class NotificadorEmail:
    def __init__(self):
        # Leer desde variables de entorno
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', 587))
        self.email_remitente = os.environ.get('EMAIL_REMITENTE')
        self.password = os.environ.get('EMAIL_PASSWORD')
        
        if not self.email_remitente or not self.password:
            logger.warning("⚠️ Email no configurado. Las notificaciones se guardarán en logs.")
            logger.warning("   Configure las variables EMAIL_REMITENTE y EMAIL_PASSWORD")
            self.habilitado = False
        else:
            self.habilitado = True
            logger.info(f"✅ Notificador Email configurado: {self.email_remitente}")
    
    def enviar(self, destino, asunto, mensaje_html, mensaje_texto=None):
        """Envía un email en formato HTML"""
        if not self.habilitado:
            logger.info(f"📧 [EMAIL SIMULADO] Para: {destino}")
            logger.info(f"   Asunto: {asunto}")
            return True
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_remitente
            msg['To'] = destino
            msg['Subject'] = asunto
            
            if mensaje_texto:
                part_text = MIMEText(mensaje_texto, 'plain', 'utf-8')
                msg.attach(part_text)
            
            part_html = MIMEText(mensaje_html, 'html', 'utf-8')
            msg.attach(part_html)
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_remitente, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email enviado a {destino}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enviando email: {e}")
            return False
    
    def enviar_notificacion_orden(self, orden, destinatario, tipo_evento):
        """Envía email específico para orden de trabajo"""
        prioridad_colores = {
            'Alta': '#dc3545',
            'Media': '#ffc107',
            'Baja': '#28a745'
        }
        
        asunto = f"[GMP] Orden de Trabajo {orden.numero_ot} - {tipo_evento}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2c3e50; color: white; padding: 15px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .footer {{ font-size: 12px; color: #6c757d; text-align: center; padding: 15px; }}
                .priority-{orden.prioridad.lower()} {{ 
                    background-color: {prioridad_colores.get(orden.prioridad, '#6c757d')};
                    color: white;
                    padding: 5px 10px;
                    border-radius: 5px;
                    display: inline-block;
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 8px; border-bottom: 1px solid #dee2e6; }}
                .label {{ font-weight: bold; width: 40%; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🔧 GMP Maintenance</h2>
                    <h3>Notificación de Orden de Trabajo</h3>
                </div>
                <div class="content">
                    <p>Estimado/a <strong>{destinatario.nombre_completo or destinatario.username}</strong>,</p>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <span class="priority-{orden.prioridad.lower()}">Prioridad: {orden.prioridad}</span>
                    </div>
                    
                    <table>
                        <tr><td class="label">N° Orden:</td><td><strong>{orden.numero_ot}</strong></td></tr>
                        <tr><td class="label">Título:</td><td>{orden.titulo}</td></tr>
                        <tr><td class="label">Tipo:</td><td>{orden.tipo}</td></tr>
                        <tr><td class="label">Equipo:</td><td>{orden.equipo.code if orden.equipo else 'N/A'} - {orden.equipo.name if orden.equipo else 'N/A'}</td></tr>
                        <tr><td class="label">Fecha estimada:</td><td>{orden.fecha_estimada if orden.fecha_estimada else 'No definida'}</td></tr>
                        <tr><td class="label">Estado:</td><td>{orden.estado}</td></tr>
                    </table>
                    
                    <div style="margin-top: 20px; text-align: center;">
                        <a href="http://localhost:5000/ordenes/{orden.id}" 
                           style="background-color: #2c3e50; color: white; padding: 10px 20px; 
                                  text-decoration: none; border-radius: 5px;">
                            Ver Orden de Trabajo
                        </a>
                    </div>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático del sistema GMP Maintenance.</p>
                    <p>Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.enviar(destinatario.email, asunto, html)
    
    def enviar_notificacion_calibracion(self, calibracion, destinatario, dias):
        """Envía email para calibración próxima a vencer"""
        asunto = f"[GMP] Calibración próxima a vencer - {calibracion.instrumento}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #e74a3b; color: white; padding: 15px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 15px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 8px; border-bottom: 1px solid #dee2e6; }}
                .label {{ font-weight: bold; width: 40%; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚠️ Alerta de Calibración</h2>
                </div>
                <div class="content">
                    <p>Estimado/a <strong>{destinatario.nombre_completo or destinatario.username}</strong>,</p>
                    
                    <div class="warning">
                        <strong>¡Atención!</strong> El siguiente instrumento requiere calibración en <strong>{dias} días</strong>.
                    </div>
                    
                    <table>
                        <tr><td class="label">Instrumento:</td><td><strong>{calibracion.instrumento}</strong></td></tr>
                        <tr><td class="label">Código:</td><td>{calibracion.codigo_instrumento or 'N/A'}</td></tr>
                        <tr><td class="label">Equipo:</td><td>{calibracion.equipo.code if calibracion.equipo else 'N/A'}</td></tr>
                        <tr><td class="label">Fecha calibración:</td><td>{calibracion.fecha_calibracion}</td></tr>
                        <tr><td class="label">Próxima calibración:</td><td><strong style="color: #e74a3b;">{calibracion.fecha_proxima}</strong></td></tr>
                    </table>
                    
                    <div style="margin-top: 20px; text-align: center;">
                        <a href="http://localhost:5000/calibraciones/ver/{calibracion.id}" 
                           style="background-color: #e74a3b; color: white; padding: 10px 20px; 
                                  text-decoration: none; border-radius: 5px;">
                            Gestionar Calibración
                        </a>
                    </div>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático del sistema GMP Maintenance.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.enviar(destinatario.email, asunto, html)

# Instancia global
notificador_email = NotificadorEmail()