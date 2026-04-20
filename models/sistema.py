# models/sistema.py
from models import db
from datetime import date, timedelta

class SistemaEquipo(db.Model):
    __tablename__ = 'sistemas_equipo'
    
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'), nullable=False)
    
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    categoria = db.Column(db.String(50))
    icono = db.Column(db.String(50), default='cogs')
    color = db.Column(db.String(7), default='#007bff')
    tareas = db.Column(db.JSON)
    documentacion = db.Column(db.Text)
    fecha_creacion = db.Column(db.Date, default=date.today)
    
    equipo = db.relationship('Equipo', back_populates='sistemas')
    planes_pm = db.relationship('PlanMantenimiento', back_populates='sistema', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Sistema {self.nombre}>'
    
    def get_tareas_count(self):
        return len(self.planes_pm) if self.planes_pm else 0
    
    def get_icon_class(self):
        iconos = {
            'cogs': 'fas fa-cogs',
            'bolt': 'fas fa-bolt',
            'tint': 'fas fa-tint',
            'wind': 'fas fa-wind',
            'microchip': 'fas fa-microchip',
            'shield-alt': 'fas fa-shield-alt',
            'thermometer-half': 'fas fa-thermometer-half',
            'compress-arrows-alt': 'fas fa-compress-arrows-alt'
        }
        return iconos.get(self.icono, 'fas fa-cogs')


class PlanMantenimiento(db.Model):
    __tablename__ = 'planes_mantenimiento'
    
    id = db.Column(db.Integer, primary_key=True)
    sistema_id = db.Column(db.Integer, db.ForeignKey('sistemas_equipo.id'), nullable=False)
    
    tarea_descripcion = db.Column(db.String(200), nullable=False)
    frecuencia_dias = db.Column(db.Integer, nullable=False)
    tiempo_estimado = db.Column(db.Float, default=1.0)
    
    ultima_ejecucion = db.Column(db.Date)
    proxima_ejecucion = db.Column(db.Date)
    
    activo = db.Column(db.Boolean, default=True)
    requiere_notificacion = db.Column(db.Boolean, default=True)
    dias_notificacion = db.Column(db.Integer, default=7)
    orden_generada = db.Column(db.Boolean, default=False)
    
    sistema = db.relationship('SistemaEquipo', back_populates='planes_pm')
    repuestos_necesarios = db.relationship('RepuestoPorTarea', back_populates='tarea', lazy=True, cascade='all, delete-orphan')
    
    def calcular_proxima_ejecucion(self):
        """Calcula la próxima fecha de ejecución basada en la última ejecución"""
        hoy = date.today()
        
        if self.ultima_ejecucion:
            self.proxima_ejecucion = self.ultima_ejecucion + timedelta(days=self.frecuencia_dias)
        else:
            self.proxima_ejecucion = hoy
        
        return self.proxima_ejecucion
    
    def registrar_ejecucion(self, fecha_ejecucion=None):
        """Registra que se ejecutó la tarea y recalcula próxima fecha"""
        if fecha_ejecucion is None:
            fecha_ejecucion = date.today()
        
        self.ultima_ejecucion = fecha_ejecucion
        self.calcular_proxima_ejecucion()
    
    def __repr__(self):
        return f'<Plan PM: {self.tarea_descripcion[:30]}...>'