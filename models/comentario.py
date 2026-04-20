# models/comentario.py
from models import db
from datetime import datetime
import json

class Comentario(db.Model):
    __tablename__ = 'comentarios'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Entidad relacionada
    entidad_tipo = db.Column(db.String(50), nullable=False)  # 'orden', 'capa', 'documento', 'calibracion', 'inspeccion', 'equipo'
    entidad_id = db.Column(db.Integer, nullable=False)
    
    # Contenido
    contenido = db.Column(db.Text, nullable=False)
    
    # Autor
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    usuario_nombre = db.Column(db.String(100))
    
    # Menciones (usuarios @mencionados)
    _menciones = db.Column(db.Text, default='[]')  # JSON almacenado como string
    
    # Adjuntos
    _adjuntos = db.Column(db.Text, default='[]')  # JSON almacenado como string
    
    # Respuesta a (hilos de conversación)
    respuesta_a_id = db.Column(db.Integer, db.ForeignKey('comentarios.id'), nullable=True)
    
    # Fechas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    respuestas = db.relationship('Comentario', backref=db.backref('parent', remote_side=[id]), lazy=True)
    
    @property
    def menciones(self):
        return json.loads(self._menciones) if self._menciones else []
    
    @menciones.setter
    def menciones(self, valor):
        self._menciones = json.dumps(valor)
    
    @property
    def adjuntos(self):
        return json.loads(self._adjuntos) if self._adjuntos else []
    
    @adjuntos.setter
    def adjuntos(self, valor):
        self._adjuntos = json.dumps(valor)
    
    def agregar_adjunto(self, nombre, url, tamano=None):
        """Agrega un archivo adjunto al comentario"""
        adjuntos = self.adjuntos
        adjuntos.append({
            'nombre': nombre,
            'url': url,
            'tamano': tamano,
            'fecha': datetime.now().isoformat()
        })
        self.adjuntos = adjuntos
        db.session.commit()
    
    def __repr__(self):
        return f'<Comentario {self.id}: {self.contenido[:50]}>'


class Mencion(db.Model):
    __tablename__ = 'menciones'
    
    id = db.Column(db.Integer, primary_key=True)
    comentario_id = db.Column(db.Integer, db.ForeignKey('comentarios.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    leida = db.Column(db.Boolean, default=False)
    notificacion_id = db.Column(db.Integer, db.ForeignKey('notificaciones.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    comentario = db.relationship('Comentario', backref='menciones_list')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    notificacion = db.relationship('Notificacion', foreign_keys=[notificacion_id])
    
    def __repr__(self):
        return f'<Mencion {self.id}: @{self.usuario.username} en comentario {self.comentario_id}>'


class Conversacion(db.Model):
    """Para mensajería directa entre usuarios"""
    __tablename__ = 'conversaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Participantes (JSON)
    _participantes = db.Column(db.Text, default='[]')
    
    @property
    def participantes(self):
        return json.loads(self._participantes) if self._participantes else []
    
    @participantes.setter
    def participantes(self, valor):
        self._participantes = json.dumps(valor)
    
    # Relaciones
    creador = db.relationship('Usuario', foreign_keys=[creador_id])
    mensajes = db.relationship('MensajeDirecto', backref='conversacion', lazy=True, cascade='all, delete-orphan')


class MensajeDirecto(db.Model):
    """Mensajes dentro de una conversación"""
    __tablename__ = 'mensajes_directos'
    
    id = db.Column(db.Integer, primary_key=True)
    conversacion_id = db.Column(db.Integer, db.ForeignKey('conversaciones.id'), nullable=False)
    remitente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    leido = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    remitente = db.relationship('Usuario', foreign_keys=[remitente_id])