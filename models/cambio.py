# models/cambio.py
from models import db
from datetime import datetime

class Cambio(db.Model):
    __tablename__ = 'cambios'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_cambio = db.Column(db.String(20), unique=True, nullable=False)
    
    # Relaciones
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    sistema_id = db.Column(db.Integer, db.ForeignKey('sistemas_equipo.id'))
    orden_trabajo_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'))
    
    # Información básica
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50))  # 'Equipo', 'Proceso', 'Documentación', 'Instalación', 'Proveedor'
    
    # Clasificación GMP
    clasificacion_gmp = db.Column(db.String(50))  # 'Crítico', 'Importante', 'Menor'
    impacto_calidad = db.Column(db.String(20))  # 'Alto', 'Medio', 'Bajo'
    impacto_validacion = db.Column(db.String(20))  # 'Requiere Revalidación', 'No Requiere'
    
    # Estado del cambio
    estado = db.Column(db.String(20), default='Borrador')  # Borrador, En Revisión, Aprobado, Rechazado, Implementado, Cerrado
    
    # Fechas
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_aprobacion = db.Column(db.DateTime)
    fecha_implementacion = db.Column(db.DateTime)
    fecha_cierre = db.Column(db.DateTime)
    
    # Solicitante
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    solicitante_nombre = db.Column(db.String(100))
    departamento = db.Column(db.String(100))
    
    # Justificación
    motivo = db.Column(db.Text, nullable=False)
    beneficio = db.Column(db.Text)
    riesgo = db.Column(db.Text)
    
    # Detalles del cambio
    cambio_propuesto = db.Column(db.Text)
    estado_actual = db.Column(db.Text)
    estado_nuevo = db.Column(db.Text)
    
    # Documentación afectada
    documentos_afectados = db.Column(db.Text)  # Lista de documentos que cambian
    nuevos_documentos = db.Column(db.Text)     # Nuevos documentos requeridos
    
    # Validación
    requiere_validacion = db.Column(db.Boolean, default=True)
    plan_validacion = db.Column(db.Text)
    resultados_validacion = db.Column(db.Text)
    
    # CAPA relacionado (si aplica)
    capa_id = db.Column(db.Integer, db.ForeignKey('capas.id'))
    requiere_capa = db.Column(db.Boolean, default=False)
    
    # Aprobaciones
    aprobador_1_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    aprobador_1_nombre = db.Column(db.String(100))
    aprobador_1_fecha = db.Column(db.DateTime)
    aprobador_1_comentarios = db.Column(db.Text)
    
    aprobador_2_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    aprobador_2_nombre = db.Column(db.String(100))
    aprobador_2_fecha = db.Column(db.DateTime)
    aprobador_2_comentarios = db.Column(db.Text)
    
    aprobador_calidad_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    aprobador_calidad_nombre = db.Column(db.String(100))
    aprobador_calidad_fecha = db.Column(db.DateTime)
    aprobador_calidad_comentarios = db.Column(db.Text)
    
    # Implementación
    implementado_por = db.Column(db.String(100))
    fecha_implementacion_real = db.Column(db.DateTime)
    comentarios_implementacion = db.Column(db.Text)
    
    # Verificación de eficacia
    verificacion_requerida = db.Column(db.Boolean, default=True)
    verificador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    verificador_nombre = db.Column(db.String(100))
    fecha_verificacion = db.Column(db.DateTime)
    resultado_verificacion = db.Column(db.String(20))  # 'Eficaz', 'No Eficaz', 'Parcial'
    comentarios_verificacion = db.Column(db.Text)
    
    # Notificaciones
    notificar_a = db.Column(db.Text)  # Lista de personas a notificar
    fecha_notificacion = db.Column(db.DateTime)
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    # Relaciones
    equipo = db.relationship('Equipo', foreign_keys=[equipo_id])
    sistema = db.relationship('SistemaEquipo', foreign_keys=[sistema_id])
    orden_trabajo = db.relationship('OrdenTrabajo', foreign_keys=[orden_trabajo_id])
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    aprobador_1 = db.relationship('Usuario', foreign_keys=[aprobador_1_id])
    aprobador_2 = db.relationship('Usuario', foreign_keys=[aprobador_2_id])
    aprobador_calidad = db.relationship('Usuario', foreign_keys=[aprobador_calidad_id])
    verificador = db.relationship('Usuario', foreign_keys=[verificador_id])
    
    # Historial de cambios
    historial = db.relationship('HistorialCambio', backref='cambio', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Cambio {self.numero_cambio}: {self.titulo}>'
    
    def generar_numero(self):
        """Genera número de cambio automático"""
        import random
        import string
        año = datetime.now().year
        mes = datetime.now().strftime('%m')
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"CC-{año}{mes}-{random_chars}"
    
    def get_estado_color(self):
        colores = {
            'Borrador': 'secondary',
            'En Revisión': 'info',
            'Aprobado': 'success',
            'Rechazado': 'danger',
            'Implementado': 'primary',
            'Cerrado': 'dark'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_clasificacion_color(self):
        colores = {
            'Crítico': 'danger',
            'Importante': 'warning',
            'Menor': 'info'
        }
        return colores.get(self.clasificacion_gmp, 'secondary')
    
    def get_impacto_color(self):
        colores = {
            'Alto': 'danger',
            'Medio': 'warning',
            'Bajo': 'success'
        }
        return colores.get(self.impacto_calidad, 'secondary')

class HistorialCambio(db.Model):
    __tablename__ = 'historial_cambios'
    
    id = db.Column(db.Integer, primary_key=True)
    cambio_id = db.Column(db.Integer, db.ForeignKey('cambios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(100))
    accion = db.Column(db.String(50))  # 'CREACIÓN', 'MODIFICACIÓN', 'APROBACIÓN', 'RECHAZO', 'IMPLEMENTACIÓN', 'CIERRE'
    campo = db.Column(db.String(100))
    valor_anterior = db.Column(db.Text)
    valor_nuevo = db.Column(db.Text)
    comentarios = db.Column(db.Text)