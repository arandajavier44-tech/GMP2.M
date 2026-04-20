# models/riesgo.py
from models import db
from datetime import datetime, date

class MatrizRiesgo(db.Model):
    __tablename__ = 'matrices_riesgo'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    version = db.Column(db.String(10), default='1.0')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_revision = db.Column(db.Date)
    
    # Alcance
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    area = db.Column(db.String(50))
    proceso = db.Column(db.String(100))
    
    # Metodología
    metodologia = db.Column(db.String(50))  # 'FMEA', 'HAZOP', 'What-If'
    
    # Responsables
    elaborado_por = db.Column(db.String(100))
    revisado_por = db.Column(db.String(100))
    aprobado_por = db.Column(db.String(100))
    
    # Datos de la matriz (JSON)
    riesgos = db.Column(db.JSON)  # Lista de riesgos identificados
    acciones = db.Column(db.JSON)  # Plan de acción
    
    # Relaciones
    equipo = db.relationship('Equipo')
    
    def __repr__(self):
        return f'<MatrizRiesgo {self.nombre} v{self.version}>'

class RiesgoIdentificado(db.Model):
    __tablename__ = 'riesgos_identificados'
    
    id = db.Column(db.Integer, primary_key=True)
    matriz_id = db.Column(db.Integer, db.ForeignKey('matrices_riesgo.id'), nullable=False)
    
    # Identificación
    codigo = db.Column(db.String(20))
    descripcion = db.Column(db.Text, nullable=False)
    causa = db.Column(db.Text)
    efecto = db.Column(db.Text)
    
    # Clasificación
    categoria = db.Column(db.String(50))  # 'calidad', 'seguridad', 'ambiental', 'operacional'
    
    # Evaluación inicial
    severidad = db.Column(db.Integer)  # 1-5
    ocurrencia = db.Column(db.Integer)  # 1-5
    detectabilidad = db.Column(db.Integer)  # 1-5
    npr = db.Column(db.Integer)  # Número Prioritario de Riesgo (Severidad * Ocurrencia * Detectabilidad)
    
    # Evaluación después de controles
    severidad_residual = db.Column(db.Integer)
    ocurrencia_residual = db.Column(db.Integer)
    detectabilidad_residual = db.Column(db.Integer)
    npr_residual = db.Column(db.Integer)
    
    # Controles
    controles_actuales = db.Column(db.Text)
    controles_propuestos = db.Column(db.Text)
    responsable = db.Column(db.String(100))
    fecha_limite = db.Column(db.Date)
    
    # Estado
    estado = db.Column(db.String(20), default='Identificado')  # 'Identificado', 'En Tratamiento', 'Controlado', 'Aceptado'
    
    matriz = db.relationship('MatrizRiesgo', backref='riesgos_list')