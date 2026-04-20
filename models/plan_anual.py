# models/plan_anual.py
from models import db
from datetime import datetime, date

class PlanAnual(db.Model):
    __tablename__ = 'planes_anuales'
    
    id = db.Column(db.Integer, primary_key=True)
    año = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(200))
    descripcion = db.Column(db.Text)
    
    # Datos del plan en JSON
    meses = db.Column(db.JSON)  # Estructura con actividades por mes
    
    # Estado
    estado = db.Column(db.String(20), default='Borrador')  # Borrador, Aprobado, Ejecución, Cerrado
    
    # Fechas
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_aprobacion = db.Column(db.Date)
    
    # Responsables
    creado_por = db.Column(db.String(100))
    aprobado_por = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<PlanAnual {self.año}: {self.nombre}>'
    
    def generar_estructura_base(self):
        """Genera estructura base del plan anual"""
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        estructura = []
        for i, mes in enumerate(meses, 1):
            estructura.append({
                'mes_numero': i,
                'mes_nombre': mes,
                'semanas': [1, 2, 3, 4],
                'actividades': []
            })
        return estructura

class ActividadPlanAnual(db.Model):
    __tablename__ = 'actividades_plan_anual'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('planes_anuales.id'), nullable=False)
    
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    sistema_id = db.Column(db.Integer, db.ForeignKey('sistemas_equipo.id'))
    tarea_id = db.Column(db.Integer, db.ForeignKey('planes_mantenimiento.id'))
    
    mes = db.Column(db.Integer)  # 1-12
    semana = db.Column(db.Integer)  # 1-4
    
    descripcion = db.Column(db.String(200))
    tipo = db.Column(db.String(50))  # 'preventivo', 'calibracion', 'inspeccion', 'validacion'
    
    duracion_estimada = db.Column(db.Float)  # horas
    responsable = db.Column(db.String(100))
    
    # Programación
    fecha_programada = db.Column(db.Date)
    fecha_ejecucion = db.Column(db.Date)
    estado = db.Column(db.String(20), default='Programado')  # Programado, Completado, Atrasado, Cancelado
    
    # Relaciones
    plan = db.relationship('PlanAnual', backref='actividades')
    equipo = db.relationship('Equipo')
    sistema = db.relationship('SistemaEquipo')
    tarea = db.relationship('PlanMantenimiento')
    
    def __repr__(self):
        return f'<Actividad {self.descripcion} - Mes {self.mes}>'