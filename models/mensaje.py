# models/mensaje.py
from models import db
from datetime import datetime

class Mensaje(db.Model):
    __tablename__ = 'mensajes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Tipo de entidad asociada
    entidad_tipo = db.Column(db.String(50), nullable=False)  # 'orden', 'capa', 'calibracion', 'documento', 'inspeccion'
    entidad_id = db.Column(db.Integer, nullable=False)
    
    # Contenido
    mensaje = db.Column(db.Text, nullable=False)
    
    # Usuarios
    remitente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # NULL = público/área
    
    # Menciones (JSON con IDs de usuarios mencionados)
    menciones = db.Column(db.JSON, default=[])
    
    # Archivos adjuntos (JSON con rutas)
    adjuntos = db.Column(db.JSON, default=[])
    
    # Estado
    leido = db.Column(db.Boolean, default=False)
    fecha_lectura = db.Column(db.DateTime)
    
    # Respuesta a
    respuesta_a_id = db.Column(db.Integer, db.ForeignKey('mensajes.id'), nullable=True)
    
    # Fechas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    remitente = db.relationship('Usuario', foreign_keys=[remitente_id])
    destinatario = db.relationship('Usuario', foreign_keys=[destinatario_id])
    respuestas = db.relationship('Mensaje', backref=db.backref('respuesta_a', remote_side=[id]), lazy=True)
    
    def __repr__(self):
        return f'<Mensaje {self.id}: {self.mensaje[:50]}>'


class HistorialMensaje(db.Model):
    """Historial de cambios en mensajes (para GMP)"""
    __tablename__ = 'historial_mensajes'
    
    id = db.Column(db.Integer, primary_key=True)
    mensaje_id = db.Column(db.Integer, db.ForeignKey('mensajes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    accion = db.Column(db.String(50))  # 'CREADO', 'LEIDO', 'RESPONDIDO'
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    ip = db.Column(db.String(50))
    
    mensaje = db.relationship('Mensaje', backref='historial')
    usuario = db.relationship('Usuario')