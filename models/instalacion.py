# models/instalacion.py
from models import db
from datetime import datetime
import json

class Instalacion(db.Model):
    __tablename__ = 'instalaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    
    # Clasificación
    categoria = db.Column(db.String(50))
    subcategoria = db.Column(db.String(50))
    ubicacion = db.Column(db.String(200))
    sector = db.Column(db.String(50))
    edificio = db.Column(db.String(50))
    piso = db.Column(db.String(20))
    
    # Estado
    estado = db.Column(db.String(20), default='Operativo')
    
    # Especificaciones técnicas
    marca = db.Column(db.String(50))
    modelo = db.Column(db.String(50))
    anio_instalacion = db.Column(db.Integer)
    especificaciones = db.Column(db.Text)  # JSON
    
    # Mantenimiento programado
    requiere_mantenimiento_periodico = db.Column(db.Boolean, default=False)
    frecuencia_mantenimiento_dias = db.Column(db.Integer)
    frecuencia_mantenimiento_horas = db.Column(db.Integer)
    ultima_ejecucion = db.Column(db.Date)
    proxima_ejecucion = db.Column(db.Date)
    
    # Responsables
    responsable_area = db.Column(db.String(100))
    proveedor_servicio = db.Column(db.String(100))
    contrato_mantenimiento = db.Column(db.String(100))
    
    # Documentación
    manual_path = db.Column(db.String(200))
    plano_path = db.Column(db.String(200))
    fotos = db.Column(db.Text)  # JSON array de paths
    
    # QR para trazabilidad
    qr_code = db.Column(db.String(200))
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    # Relaciones
    ordenes_servicio = db.relationship('OrdenServicioGeneral', back_populates='instalacion', lazy=True, cascade='all, delete-orphan')
    planes_mantenimiento = db.relationship('PlanMantenimientoInstalacion', back_populates='instalacion', lazy=True, cascade='all, delete-orphan')
    historial_estados = db.relationship('HistorialEstadoInstalacion', back_populates='instalacion', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Instalacion {self.codigo}: {self.nombre}>'
    
    def get_estado_color(self):
        colores = {
            'Operativo': 'success',
            'En Mantenimiento': 'primary',
            'Fuera de Servicio': 'danger',
            'En Reparación': 'warning',
            'Pendiente': 'secondary'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_estado_icon(self):
        iconos = {
            'Operativo': 'fa-check-circle',
            'En Mantenimiento': 'fa-tools',
            'Fuera de Servicio': 'fa-times-circle',
            'En Reparación': 'fa-wrench',
            'Pendiente': 'fa-clock'
        }
        return iconos.get(self.estado, 'fa-question-circle')
    
    def cambiar_estado(self, nuevo_estado, usuario, motivo=None):
        """Cambia el estado y registra en el historial"""
        estado_anterior = self.estado
        
        historial = HistorialEstadoInstalacion(
            instalacion_id=self.id,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            motivo=motivo,
            cambiado_por=usuario
        )
        db.session.add(historial)
        
        self.estado = nuevo_estado
        db.session.commit()


class PlanMantenimientoInstalacion(db.Model):
    __tablename__ = 'planes_mantenimiento_instalacion'
    
    id = db.Column(db.Integer, primary_key=True)
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'), nullable=False)
    
    codigo_plan = db.Column(db.String(30))
    tarea_descripcion = db.Column(db.String(200), nullable=False)
    tipo_tarea = db.Column(db.String(30))  # 'Inspección', 'Limpieza', 'Reemplazo', 'Calibración', 'Prueba'
    
    # Frecuencia
    frecuencia_dias = db.Column(db.Integer)
    frecuencia_horas = db.Column(db.Integer)
    frecuencia_tipo = db.Column(db.String(20))  # 'diaria', 'semanal', 'mensual', 'trimestral', 'anual'
    
    # Fechas
    ultima_ejecucion = db.Column(db.Date)
    proxima_ejecucion = db.Column(db.Date)
    
    # Estado
    activo = db.Column(db.Boolean, default=True)
    
    # Procedimiento detallado
    procedimiento = db.Column(db.Text)
    instrucciones_seguridad = db.Column(db.Text)
    herramientas_requeridas = db.Column(db.Text)  # JSON
    materiales_requeridos = db.Column(db.Text)    # JSON
    epp_requerido = db.Column(db.Text)            # JSON (EPP: Equipo de Protección Personal)
    
    # Tiempos estimados
    tiempo_estimado = db.Column(db.Float)  # horas
    tiempo_preparacion = db.Column(db.Float)
    tiempo_ejecucion = db.Column(db.Float)
    tiempo_limpieza = db.Column(db.Float)
    
    # Personal requerido
    cantidad_personas = db.Column(db.Integer, default=1)
    especialidad_requerida = db.Column(db.String(50))
    
    # Costos estimados
    costo_estimado_materiales = db.Column(db.Float)
    costo_estimado_mano_obra = db.Column(db.Float)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    instalacion = db.relationship('Instalacion', back_populates='planes_mantenimiento')
    
    def calcular_proxima_ejecucion(self):
        if self.ultima_ejecucion and self.frecuencia_dias:
            from datetime import timedelta
            self.proxima_ejecucion = self.ultima_ejecucion + timedelta(days=self.frecuencia_dias)
        return self.proxima_ejecucion
    
    def get_frecuencia_texto(self):
        if self.frecuencia_tipo:
            return self.frecuencia_tipo.capitalize()
        elif self.frecuencia_dias:
            if self.frecuencia_dias == 1:
                return 'Diaria'
            elif self.frecuencia_dias == 7:
                return 'Semanal'
            elif self.frecuencia_dias == 30:
                return 'Mensual'
            elif self.frecuencia_dias == 90:
                return 'Trimestral'
            elif self.frecuencia_dias == 180:
                return 'Semestral'
            elif self.frecuencia_dias == 365:
                return 'Anual'
            else:
                return f'Cada {self.frecuencia_dias} días'
        return 'No definida'


class HistorialEstadoInstalacion(db.Model):
    __tablename__ = 'historial_estados_instalacion'
    
    id = db.Column(db.Integer, primary_key=True)
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'), nullable=False)
    
    estado_anterior = db.Column(db.String(20))
    estado_nuevo = db.Column(db.String(20))
    motivo = db.Column(db.Text)
    
    fecha_cambio = db.Column(db.DateTime, default=datetime.utcnow)
    cambiado_por = db.Column(db.String(100))
    
    # Relaciones
    instalacion = db.relationship('Instalacion', back_populates='historial_estados')