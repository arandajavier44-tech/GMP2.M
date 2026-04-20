# models/capa.py
from models import db
from datetime import datetime

class CAPA(db.Model):
    __tablename__ = 'capas'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_capa = db.Column(db.String(20), unique=True, nullable=False)
    
    # Origen de la CAPA
    origen = db.Column(db.String(50))  # 'Auditoría', 'Desviación', 'Reclamo', 'No Conformidad', 'OT', 'Calibración', 'Cambio'
    origen_id = db.Column(db.Integer)  # ID del registro origen
    origen_descripcion = db.Column(db.String(200))
    
    # Información básica
    titulo = db.Column(db.String(200), nullable=False)
    descripcion_problema = db.Column(db.Text, nullable=False)
    fecha_deteccion = db.Column(db.Date, nullable=False)
    detectado_por = db.Column(db.String(100))
    
    # Clasificación
    tipo = db.Column(db.String(20))  # 'Correctiva', 'Preventiva'
    severidad = db.Column(db.String(20))  # 'Alta', 'Media', 'Baja'
    prioridad = db.Column(db.String(20))  # 'Alta', 'Media', 'Baja'
    clasificacion = db.Column(db.String(50))  # 'Calidad', 'Seguridad', 'Proceso', 'Documentación'
    
    # Análisis de causa raíz
    metodologia_analisis = db.Column(db.String(50))  # '5 Porqués', 'Ishikawa', 'FMEA', 'Árbol de fallas'
    analisis_causa = db.Column(db.Text)
    causa_raiz = db.Column(db.Text)
    
    # Acciones
    acciones_correctivas = db.Column(db.Text)
    acciones_preventivas = db.Column(db.Text)
    plan_implementacion = db.Column(db.Text)
    
    # Responsables
    responsable = db.Column(db.String(100))
    equipo_trabajo = db.Column(db.String(200))  # Lista de nombres
    
    # Fechas
    fecha_inicio = db.Column(db.Date, default=datetime.utcnow().date)
    fecha_estimada_cierre = db.Column(db.Date)
    fecha_cierre = db.Column(db.Date)
    
    # Estado
    estado = db.Column(db.String(20), default='Abierto')  # Abierto, En Análisis, En Implementación, En Verificación, Cerrado
    
    # Verificación de eficacia
    verificacion_eficacia = db.Column(db.Text)
    fecha_verificacion = db.Column(db.Date)
    verificador = db.Column(db.String(100))
    resultado_verificacion = db.Column(db.String(20))  # 'Eficaz', 'No Eficaz', 'Parcial'
    
    # Documentación
    documentos_asociados = db.Column(db.Text)  # Lista de documentos
    evidencia_objetiva = db.Column(db.Text)  # Descripción de evidencias
    
    # Costos
    costo_estimado = db.Column(db.Float)
    costo_real = db.Column(db.Float)
    
    # Lecciones aprendidas
    lecciones_aprendidas = db.Column(db.Text)
    requiere_capacitacion = db.Column(db.Boolean, default=False)
    plan_capacitacion = db.Column(db.Text)
    
    # Cierre
    comentarios_cierre = db.Column(db.Text)
    aprobado_por = db.Column(db.String(100))
    fecha_aprobacion = db.Column(db.Date)
    
    # Seguimiento
    seguimiento = db.relationship('SeguimientoCAPA', backref='capa', lazy=True, cascade='all, delete-orphan')
    
    # Auditoría
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    ordenes_trabajo = db.relationship('OrdenTrabajo', backref='capa_rel', lazy=True)
    cambios = db.relationship('Cambio', backref='capa_rel', lazy=True)
    
    def __repr__(self):
        return f'<CAPA {self.numero_capa}: {self.titulo}>'
    
    def generar_numero_capa(self):
        """Genera número de CAPA automático"""
        import random
        import string
        año = datetime.now().year
        mes = datetime.now().strftime('%m')
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"CAPA-{año}{mes}-{random_chars}"
    
    def get_estado_color(self):
        colores = {
            'Abierto': 'danger',
            'En Análisis': 'warning',
            'En Implementación': 'info',
            'En Verificación': 'primary',
            'Cerrado': 'success'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_prioridad_color(self):
        colores = {
            'Alta': 'danger',
            'Media': 'warning',
            'Baja': 'success'
        }
        return colores.get(self.prioridad, 'secondary')
    
    def get_severidad_color(self):
        colores = {
            'Alta': 'danger',
            'Media': 'warning',
            'Baja': 'success'
        }
        return colores.get(self.severidad, 'secondary')
    
    def dias_abierto(self):
        """Días que lleva abierta la CAPA"""
        if self.fecha_cierre:
            return (self.fecha_cierre - self.fecha_deteccion).days
        else:
            return (datetime.now().date() - self.fecha_deteccion).days

class SeguimientoCAPA(db.Model):
    __tablename__ = 'seguimiento_capa'
    
    id = db.Column(db.Integer, primary_key=True)
    capa_id = db.Column(db.Integer, db.ForeignKey('capas.id'), nullable=False)
    
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(100))
    tipo = db.Column(db.String(50))  # 'Avance', 'Problema', 'Hito', 'Cambio'
    descripcion = db.Column(db.Text)
    porcentaje_avance = db.Column(db.Integer)  # 0-100
    proximos_pasos = db.Column(db.Text)
    
    # Archivos adjuntos (opcional)
    archivo = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Seguimiento {self.id} - CAPA {self.capa_id}>'