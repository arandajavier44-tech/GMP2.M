# models/orden_servicio_general.py
from models import db
from datetime import datetime
import json

class OrdenServicioGeneral(db.Model):
    __tablename__ = 'ordenes_servicio_general'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_ot = db.Column(db.String(30), unique=True, nullable=False)
    numero_correlativo = db.Column(db.Integer)
    
    # Referencia a la instalación
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'), nullable=True)
    
    # Tipo y origen
    tipo = db.Column(db.String(20), nullable=False)  # 'Preventivo', 'Correctivo', 'Solicitud', 'Mejora', 'Refacción'
    origen = db.Column(db.String(20))  # 'Interno' (Mantenimiento), 'Externo' (Otros deptos)
    subtipo = db.Column(db.String(30))  # 'Eléctrico', 'Edilicio', 'Climatización', 'Sanitario', etc.
    
    # Datos del solicitante (si es externo)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    solicitante_nombre = db.Column(db.String(100))
    solicitante_sector = db.Column(db.String(100))
    solicitante_contacto = db.Column(db.String(50))
    
    # Datos de la orden
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    ubicacion_detallada = db.Column(db.String(200))
    
    # Para preventivo: referencia al plan
    plan_mantenimiento_id = db.Column(db.Integer, db.ForeignKey('planes_mantenimiento_instalacion.id'))
    tareas_plan = db.Column(db.Text)  # JSON con tareas del plan
    
    # Estado y prioridad
    estado = db.Column(db.String(20), default='Pendiente')
    prioridad = db.Column(db.String(20), default='Media')
    
    # Fechas
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_estimada = db.Column(db.Date)
    fecha_estimada_fin = db.Column(db.Date)
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    fecha_cierre = db.Column(db.DateTime)
    
    # Tiempos (en horas)
    tiempo_estimado = db.Column(db.Float)
    tiempo_real = db.Column(db.Float)
    tiempo_respuesta = db.Column(db.Float)  # horas desde creación hasta inicio
    
    # Asignación
    asignado_a = db.Column(db.String(100))
    asignado_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    equipo_trabajo = db.Column(db.Text)  # JSON con lista de técnicos
    
    creado_por = db.Column(db.String(100))
    
    # Diagnóstico y trabajo realizado
    diagnostico = db.Column(db.Text)
    trabajo_realizado = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    recomendaciones = db.Column(db.Text)
    
    # Materiales y costos
    materiales_utilizados = db.Column(db.Text)  # JSON
    servicios_terceros = db.Column(db.Text)     # JSON
    costo_total_materiales = db.Column(db.Float)
    costo_total_servicios = db.Column(db.Float)
    costo_total_mano_obra = db.Column(db.Float)
    
    # Aprobación
    requiere_aprobacion = db.Column(db.Boolean, default=True)
    aprobado_por = db.Column(db.String(100))
    fecha_aprobacion = db.Column(db.DateTime)
    motivo_rechazo = db.Column(db.Text)
    
    # Verificación y cierre
    verificado_por = db.Column(db.String(100))
    fecha_verificacion = db.Column(db.DateTime)
    firma_tecnico = db.Column(db.String(100))
    firma_supervisor = db.Column(db.String(100))
    firma_solicitante = db.Column(db.String(100))
    
    # Adjuntos
    fotos_antes = db.Column(db.Text)   # JSON array
    fotos_despues = db.Column(db.Text) # JSON array
    documentos_adjuntos = db.Column(db.Text)  # JSON array
    
    # QR para trazabilidad
    qr_code = db.Column(db.String(200))
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    instalacion = db.relationship('Instalacion', back_populates='ordenes_servicio')
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    asignado = db.relationship('Usuario', foreign_keys=[asignado_id])
    plan_mantenimiento = db.relationship('PlanMantenimientoInstalacion')
    seguimientos = db.relationship('SeguimientoOrdenSG', back_populates='orden', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<OSG {self.numero_ot}: {self.titulo}>'
    
    def get_estado_color(self):
        colores = {
            'Pendiente': 'warning',
            'Aprobada': 'info',
            'Rechazada': 'danger',
            'En Progreso': 'primary',
            'Pausada': 'secondary',
            'Completada': 'success',
            'Verificada': 'success',
            'Cancelada': 'danger'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_estado_icon(self):
        iconos = {
            'Pendiente': 'fa-clock',
            'Aprobada': 'fa-check-circle',
            'Rechazada': 'fa-times-circle',
            'En Progreso': 'fa-play-circle',
            'Pausada': 'fa-pause-circle',
            'Completada': 'fa-check-double',
            'Verificada': 'fa-stamp',
            'Cancelada': 'fa-ban'
        }
        return iconos.get(self.estado, 'fa-question-circle')
    
    def get_prioridad_color(self):
        colores = {
            'Baja': 'success',
            'Media': 'info',
            'Alta': 'warning',
            'Urgente': 'danger',
            'Emergencia': 'dark'
        }
        return colores.get(self.prioridad, 'secondary')
    
    def get_tipo_icon(self):
        iconos = {
            'Preventivo': 'fa-calendar-check',
            'Correctivo': 'fa-exclamation-triangle',
            'Solicitud': 'fa-ticket-alt',
            'Mejora': 'fa-arrow-up',
            'Refacción': 'fa-hammer'
        }
        return iconos.get(self.tipo, 'fa-clipboard-list')
    
    def calcular_tiempo_respuesta(self):
        """Calcula tiempo desde creación hasta inicio en horas"""
        if self.fecha_creacion and self.fecha_inicio:
            delta = self.fecha_inicio - self.fecha_creacion
            self.tiempo_respuesta = round(delta.total_seconds() / 3600, 2)
        return self.tiempo_respuesta
    
    def get_materiales_utilizados_list(self):
        """Retorna lista de materiales utilizados"""
        if self.materiales_utilizados:
            return json.loads(self.materiales_utilizados)
        return []
    
    def agregar_material(self, codigo, nombre, cantidad, unidad, costo_unitario=0):
        """Agrega un material utilizado"""
        materiales = self.get_materiales_utilizados_list()
        materiales.append({
            'codigo': codigo,
            'nombre': nombre,
            'cantidad': cantidad,
            'unidad': unidad,
            'costo_unitario': costo_unitario,
            'costo_total': cantidad * costo_unitario,
            'fecha': datetime.utcnow().isoformat()
        })
        self.materiales_utilizados = json.dumps(materiales)
        self.costo_total_materiales = sum(m.get('costo_total', 0) for m in materiales)
    
    def agregar_seguimiento(self, usuario, comentario, estado_anterior=None, estado_nuevo=None):
        """Agrega un seguimiento a la orden"""
        seguimiento = SeguimientoOrdenSG(
            orden_id=self.id,
            usuario=usuario,
            comentario=comentario,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo
        )
        db.session.add(seguimiento)
        return seguimiento


class SeguimientoOrdenSG(db.Model):
    __tablename__ = 'seguimiento_orden_sg'
    
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_servicio_general.id'), nullable=False)
    
    usuario = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    comentario = db.Column(db.Text)
    
    estado_anterior = db.Column(db.String(20))
    estado_nuevo = db.Column(db.String(20))
    
    # Relaciones
    orden = db.relationship('OrdenServicioGeneral', back_populates='seguimientos')