# models/tarea_mantenimiento.py
from models import db
from datetime import datetime

class TareaMantenimiento(db.Model):
    __tablename__ = 'tareas_mantenimiento'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    duracion_estimada = db.Column(db.Integer, default=60)
    especialidad = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True)
    
    # Comentar si existe relación con repuestos
    # repuestos = db.relationship('RepuestoPorTarea', back_populates='tarea', lazy=True)
    
    def __repr__(self):
        return f'<Tarea {self.nombre}>'