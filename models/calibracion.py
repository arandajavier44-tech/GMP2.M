# models/calibracion.py
from models import db
from datetime import datetime, date

class Calibracion(db.Model):
    __tablename__ = 'calibraciones'
    
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'), nullable=False)
    
    # Identificación del instrumento
    instrumento = db.Column(db.String(100), nullable=False)
    codigo_instrumento = db.Column(db.String(50))
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    serie = db.Column(db.String(100))
    
    # Especificaciones técnicas
    rango = db.Column(db.String(50))
    unidad = db.Column(db.String(20))
    tolerancia = db.Column(db.String(50))
    precision = db.Column(db.String(50))
    
    # Clasificación GMP para calibración
    clasificacion_gmp = db.Column(db.String(50))  # Crítico, Importante, Auxiliar
    frecuencia_dias = db.Column(db.Integer, default=365)  # Frecuencia de calibración
    
    # Fechas de calibración
    fecha_calibracion = db.Column(db.Date, nullable=False)
    fecha_proxima = db.Column(db.Date, nullable=False)
    fecha_aviso = db.Column(db.Date)  # Fecha para enviar alerta (30 días antes)
    
    # Proveedor/Laboratorio
    laboratorio = db.Column(db.String(100))
    certificado_numero = db.Column(db.String(50), unique=True)
    certificado_archivo = db.Column(db.String(200))  # Ruta al PDF
    
    # Resultados
    resultado = db.Column(db.String(20))  # 'Conforme', 'No Conforme', 'Parcial'
    observaciones = db.Column(db.Text)
    acciones_correctivas = db.Column(db.Text)  # Si fue No Conforme
    
    # Patrón utilizado
    patron_utilizado = db.Column(db.String(100))
    patron_certificado = db.Column(db.String(50))
    trazabilidad = db.Column(db.String(200))  # Trazabilidad a patrones nacionales
    
    # Condiciones ambientales
    temperatura = db.Column(db.String(20))
    humedad = db.Column(db.String(20))
    
    # Responsables
    realizado_por = db.Column(db.String(100))
    revisado_por = db.Column(db.String(100))
    aprobado_por = db.Column(db.String(100))
    
    # Firmas
    firma_realizado = db.Column(db.String(100))
    firma_revisado = db.Column(db.String(100))
    firma_aprobado = db.Column(db.String(100))
    
    # Estado del instrumento
    estado = db.Column(db.String(20), default='Activo')  # Activo, Baja, En Reparación, Fuera de Servicio
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    
    # Relaciones
    equipo = db.relationship('Equipo', back_populates='calibraciones')
    
    def __repr__(self):
        return f'<Calibración {self.instrumento} - {self.fecha_calibracion}>'
    
    def get_estado_color(self):
        """Retorna el color del semáforo según la fecha de vencimiento"""
        hoy = date.today()
        if self.fecha_proxima < hoy:
            return 'red'  # Vencida
        elif (self.fecha_proxima - hoy).days <= 30:
            return 'yellow'  # Próxima a vencer
        else:
            return 'green'  # Vigente
    
    def get_estado_badge(self):
        """Retorna el badge de Bootstrap según el estado"""
        colores = {
            'red': 'danger',
            'yellow': 'warning',
            'green': 'success'
        }
        return colores.get(self.get_estado_color(), 'secondary')
    
    def get_estado_texto(self):
        """Retorna el texto del estado"""
        if self.fecha_proxima < date.today():
            return 'Vencida'
        elif (self.fecha_proxima - date.today()).days <= 30:
            return 'Por Vencer'
        else:
            return 'Vigente'
    
    def dias_para_vencer(self):
        """Retorna días hasta el vencimiento"""
        return (self.fecha_proxima - date.today()).days

class HistorialCalibracion(db.Model):
    """Historial de cambios en calibraciones"""
    __tablename__ = 'historial_calibraciones'
    
    id = db.Column(db.Integer, primary_key=True)
    calibracion_id = db.Column(db.Integer, db.ForeignKey('calibraciones.id'), nullable=False)
    fecha_cambio = db.Column(db.DateTime, default=datetime.utcnow)
    campo_modificado = db.Column(db.String(100))
    valor_anterior = db.Column(db.Text)
    valor_nuevo = db.Column(db.Text)
    modificado_por = db.Column(db.String(100))
    
    calibracion = db.relationship('Calibracion', backref='historial')