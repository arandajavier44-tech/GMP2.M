# models/orden_trabajo.py
from models import db
from datetime import datetime

class OrdenTrabajo(db.Model):
    __tablename__ = 'ordenes_trabajo'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_ot = db.Column(db.String(30), unique=True, nullable=False)
    
    # NUEVOS CAMPOS PARA TRAZABILIDAD
    numero_correlativo = db.Column(db.Integer)
    codigo_equipo = db.Column(db.String(20))
    tiempo_respuesta = db.Column(db.Integer)  # minutos desde creación a inicio
    tiempo_parada = db.Column(db.Integer)     # minutos equipo fuera servicio
    
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'), nullable=False)
    
    # Tipo: Preventivo, Correctivo, Servicio
    tipo = db.Column(db.String(20), nullable=False)
    
    # Subtipo para preventivo (opcional)
    sistema_id = db.Column(db.Integer, db.ForeignKey('sistemas_equipo.id'))
    
    # ⚠️ SOLO UNA RELACIÓN CON PlanMantenimiento - ELIMINA LA OTRA ⚠️
    # Usamos tarea_origen_id como la única referencia
    tarea_origen_id = db.Column(db.Integer, db.ForeignKey('planes_mantenimiento.id'))
    
    # Próxima fecha calculada después de ejecutar (para el calendario)
    fecha_proxima = db.Column(db.Date)
    
    # Título y descripción
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    
    # Para preventivo: tareas seleccionadas (JSON)
    tareas_seleccionadas = db.Column(db.JSON)
    
    # Para correctivo/servicio
    solicitante = db.Column(db.String(100))
    sector = db.Column(db.String(100))
    falla_reportada = db.Column(db.Text)
    sintomas = db.Column(db.String(200))
    causa_probable = db.Column(db.String(200))
    
    # Estado y prioridad
    estado = db.Column(db.String(20), default='Pendiente')
    prioridad = db.Column(db.String(20), default='Media')

    # Campos adicionales para cierre de órdenes
    diagnostico_final = db.Column(db.Text)
    solucion_aplicada = db.Column(db.Text)
    trabajo_futuro = db.Column(db.String(200))
    fecha_prox_mantenimiento = db.Column(db.Date)
    repuestos_utilizados = db.Column(db.Text)  # JSON como string
    tareas_ejecutadas = db.Column(db.Text)     # JSON como string
    matricula_tecnico = db.Column(db.String(50))
    accion_inmediata_capa = db.Column(db.Text)
    impacto_calidad_capa = db.Column(db.String(50))

    # Fechas GMP
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    fecha_cierre = db.Column(db.DateTime)
    fecha_estimada = db.Column(db.Date)
    fecha_aprobacion = db.Column(db.DateTime)
    
    # Tiempos
    tiempo_estimado = db.Column(db.Float)
    tiempo_ejecucion = db.Column(db.Float)
    tiempo_real = db.Column(db.Float)
    
    # Asignación
    asignado_a = db.Column(db.String(100))
    creado_por = db.Column(db.String(100))
    aprobado_por = db.Column(db.String(100))
    
    # Resultado
    resultado = db.Column(db.String(50))
    observaciones = db.Column(db.Text)
    recomendaciones = db.Column(db.Text)
    
    # Firmas GMP
    firma_tecnico = db.Column(db.String(100))
    firma_supervisor = db.Column(db.String(100))
    firma_calidad = db.Column(db.String(100))
    
    fecha_firma_tecnico = db.Column(db.DateTime)
    fecha_firma_supervisor = db.Column(db.DateTime)
    fecha_firma_calidad = db.Column(db.DateTime)
    
    # CAPA
    requiere_capa = db.Column(db.Boolean, default=False)
    capa_id = db.Column(db.Integer, db.ForeignKey('capas.id'))
    motivo_capa = db.Column(db.Text)
    
    # QR
    qr_code = db.Column(db.String(200))
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # ========== RELACIONES ==========
    equipo = db.relationship('Equipo', back_populates='ordenes_trabajo')
    sistema = db.relationship('SistemaEquipo')
    consumos = db.relationship('ConsumoRepuesto', back_populates='orden', lazy=True)
    
    # ⚠️ SOLO UNA RELACIÓN con PlanMantenimiento - especificando foreign_keys
    tarea_origen = db.relationship('PlanMantenimiento', foreign_keys=[tarea_origen_id])
    
    # ⚠️ ELIMINAR estas líneas si existen:
    # plan_mantenimiento_id = ...
    # plan_mantenimiento = db.relationship(...)
    
    def __repr__(self):
        return f'<OT {self.numero_ot}: {self.titulo}>'
    
    def get_estado_color(self):
        colores = {
            'Pendiente': 'warning',
            'Aprobada': 'info',
            'En Progreso': 'primary',
            'Completada': 'success',
            'Cancelada': 'danger'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_prioridad_color(self):
        colores = {
            'Baja': 'success',
            'Media': 'info',
            'Alta': 'warning',
            'Crítica': 'danger'
        }
        return colores.get(self.prioridad, 'secondary')
    
    def get_tipo_icon(self):
        iconos = {
            'Preventivo': 'calendar-check',
            'Correctivo': 'exclamation-triangle',
            'Servicio': 'tools'
        }
        return iconos.get(self.tipo, 'clipboard-list')

# Agregar en models/orden_trabajo.py - método save()
def save(self):
    """Sobrescribir save para generar notificaciones automáticas"""
    from services.notification_service import NotificationService
    
    es_nueva = self.id is None
    
    # Guardar primero
    db.session.add(self)
    db.session.commit()
    
    if es_nueva:
        # Notificar creación
        NotificationService.notificar_orden_trabajo(self, 'creacion')
        
        # Notificar al técnico asignado
        if self.asignado_id:
            from models.usuario import Usuario
            tecnico = Usuario.query.get(self.asignado_id)
            if tecnico:
                NotificationService.notificar_orden_trabajo(self, 'asignacion', tecnico)

# Agregar en models/calibracion.py
def save(self):
    from services.notification_service import NotificationService
    
    es_nueva = self.id is None
    db.session.add(self)
    db.session.commit()
    
    if es_nueva:
        NotificationService.notificar_calibracion(self, 'creacion')
