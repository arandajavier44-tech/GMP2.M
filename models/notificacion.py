# models/notificacion.py
from models import db
from datetime import datetime

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))  # 'calibracion', 'mantenimiento', 'capa', 'orden', 'documento', 'recordatorio'
    titulo = db.Column(db.String(200))
    mensaje = db.Column(db.Text)
    prioridad = db.Column(db.String(20))  # 'Alta', 'Media', 'Baja'
    
    # URL para redirigir al elemento relacionado (NUEVO)
    url = db.Column(db.String(500))  # Ej: '/calibraciones/ver/123'
    
    # Fecha de vencimiento (para notificaciones de recordatorio)
    fecha_vencimiento = db.Column(db.Date)
    
    # Relación con elementos
    elemento_id = db.Column(db.Integer)  # ID del elemento relacionado
    elemento_tipo = db.Column(db.String(50))  # 'calibracion', 'plan', etc.
    
    # Para quién es
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    area = db.Column(db.String(50))  # 'mantenimiento', 'calidad', etc.
    
    # Estado
    leida = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_lectura = db.Column(db.DateTime)
    
    # Relación
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    
    def __repr__(self):
        return f'<Notificacion {self.id}: {self.titulo}>'
    
    def marcar_leida(self):
        self.leida = True
        self.fecha_lectura = datetime.utcnow()
        db.session.commit()