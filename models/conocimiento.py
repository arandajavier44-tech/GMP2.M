# models/conocimiento.py
from models import db
from datetime import datetime

class Normativa(db.Model):
    __tablename__ = 'normativas'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    contenido = db.Column(db.Text, nullable=False)
    
    # Clasificación
    tipo = db.Column(db.String(50))  # 'GMP', 'ANMAT', 'FDA', 'ISO'
    categoria = db.Column(db.String(100))  # 'Validación', 'Limpieza', 'Calibración', etc.
    subcategoria = db.Column(db.String(100))
    
    # Alcance
    aplica_a = db.Column(db.String(200))  # 'Equipos críticos', 'Todos los equipos', etc.
    palabras_clave = db.Column(db.Text)  # Lista separada por comas
    
    # Fechas
    fecha_publicacion = db.Column(db.Date)
    fecha_vigencia = db.Column(db.Date)
    fecha_actualizacion = db.Column(db.Date)
    
    # Versión
    version = db.Column(db.String(20))
    documento_referencia = db.Column(db.String(200))
    
    # Embeddings para búsqueda semántica
    embedding = db.Column(db.Text)  # Almacenado como JSON
    
    # Estadísticas
    veces_consultada = db.Column(db.Integer, default=0)
    ultima_consulta = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Normativa {self.codigo}: {self.titulo}>'

class ConsultaIA(db.Model):
    __tablename__ = 'consultas_ia'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100))
    pregunta = db.Column(db.Text, nullable=False)
    respuesta = db.Column(db.Text)
    normativas_referenciadas = db.Column(db.Text)  # IDs de normativas usadas
    feedback = db.Column(db.Integer)  # 1-5 estrellas
    comentario_feedback = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Consulta {self.id}: {self.pregunta[:50]}>'

class RecomendacionIA(db.Model):
    __tablename__ = 'recomendaciones_ia'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))  # 'mantenimiento', 'calibracion', 'capa', 'cambio'
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'))
    
    titulo = db.Column(db.String(200))
    descripcion = db.Column(db.Text)
    prioridad = db.Column(db.String(20))  # 'Alta', 'Media', 'Baja'
    
    # Basado en normativas
    normativas_relacionadas = db.Column(db.Text)
    
    # Estado
    leida = db.Column(db.Boolean, default=False)
    aplicada = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    equipo = db.relationship('Equipo', foreign_keys=[equipo_id])
    orden = db.relationship('OrdenTrabajo', foreign_keys=[orden_id])