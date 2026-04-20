# models/equipo.py
from models import db
from datetime import datetime

class Equipo(db.Model):
    __tablename__ = 'equipos'
    
    id = db.Column(db.Integer, primary_key=True)

    # Código QR
    qr_code = db.Column(db.String(200)) 
    
    # Sección 1: Identificación GMP
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    gmp_id = db.Column(db.String(50))
    
    # Sección 2: Clasificación GMP
    gmp_classification = db.Column(db.String(50), nullable=False)
    risk_level = db.Column(db.String(20), default='Medio')
    product_contact = db.Column(db.String(20), nullable=False)
    cleaning_level = db.Column(db.String(50))
    
    # Sección 3: Información Técnica
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100), unique=True)
    capacity = db.Column(db.String(50))
    operating_range = db.Column(db.String(100))
    power_requirements = db.Column(db.String(100))
    description = db.Column(db.Text)
    
    # Sección 4: Validación GMP
    validation_status = db.Column(db.String(20))
    validation_date = db.Column(db.Date)
    next_validation = db.Column(db.Date)
    validation_doc = db.Column(db.String(100))
    requires_requalification = db.Column(db.Boolean, default=False)
    
    # Sección 5: Localización
    location = db.Column(db.String(100))
    production_area = db.Column(db.String(50))
    room_number = db.Column(db.String(50))
    installation_date = db.Column(db.Date)
    
    # Sección 6: Documentación GMP
    sop_number = db.Column(db.String(50))
    maintenance_sop = db.Column(db.String(50))
    cleaning_sop = db.Column(db.String(50))
    calibration_sop = db.Column(db.String(50))
    gmp_notes = db.Column(db.Text)
    
    # Sección 7: Firmas y Responsables
    created_by = db.Column(db.String(100), nullable=False)
    quality_approver = db.Column(db.String(100))
    maintenance_responsible = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Estado actual
    current_status = db.Column(db.String(20), default='Operativo')
    
    # Relaciones
    sistemas = db.relationship('SistemaEquipo', back_populates='equipo', lazy=True, cascade='all, delete-orphan')
    ordenes_trabajo = db.relationship('OrdenTrabajo', back_populates='equipo', lazy=True)
    calibraciones = db.relationship('Calibracion', back_populates='equipo', lazy=True)
    repuestos_asignados = db.relationship('RepuestoPorEquipo', back_populates='equipo', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Equipo {self.code}: {self.name}>'
    
    def get_status_color(self):
        status_colors = {
            'Operativo': 'green',
            'En Mantenimiento': 'yellow',
            'Fuera de Servicio': 'red',
            'Calibración Vencida': 'red'
        }
        return status_colors.get(self.current_status, 'gray')
    
    def get_repuestos_criticos(self):
        return [rp for rp in self.repuestos_asignados if rp.es_critico]
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'gmp_classification': self.gmp_classification,
            'location': self.location,
            'current_status': self.current_status,
            'status_color': self.get_status_color()
        }