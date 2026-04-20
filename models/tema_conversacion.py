# models/tema_conversacion.py
from models import db
from datetime import datetime
import json
import random
import string

class TemaConversacion(db.Model):
    __tablename__ = 'temas_conversacion'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificación
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    
    # Clasificación
    sector = db.Column(db.String(50))
    tipo = db.Column(db.String(50))
    prioridad = db.Column(db.String(20), default='Media')
    
    # Contenido
    descripcion = db.Column(db.Text, nullable=False)
    
    # Responsables
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    creado_por_nombre = db.Column(db.String(100))
    asignado_a_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    asignado_a_nombre = db.Column(db.String(100))
    
    # Estados: Abierto, En Proceso, Resuelto, Cerrado, Archivado
    estado = db.Column(db.String(20), default='Abierto')
    
    # Fechas
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_limite = db.Column(db.Date)
    fecha_cierre = db.Column(db.DateTime)
    fecha_archivo = db.Column(db.DateTime)
    
    # Resolución
    solucion = db.Column(db.Text)
    resuelto_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    resuelto_por_nombre = db.Column(db.String(100))
    
    # Adjuntos del tema principal
    adjuntos = db.Column(db.Text, default='[]')
    
    # Relación con entidades (opcional: orden, capa, etc.)
    entidad_tipo = db.Column(db.String(50))
    entidad_id = db.Column(db.Integer)
    
    # Historial de asignaciones (JSON)
    _historial_asignaciones = db.Column(db.Text, default='[]')
    
    # Relaciones
    creado_por = db.relationship('Usuario', foreign_keys=[creado_por_id])
    asignado_a = db.relationship('Usuario', foreign_keys=[asignado_a_id])
    resuelto_por = db.relationship('Usuario', foreign_keys=[resuelto_por_id])
    mensajes = db.relationship('MensajeTema', backref='tema', lazy=True, cascade='all, delete-orphan')
    
    def generar_codigo(self):
        """Genera código único para el tema"""
        año = datetime.now().year
        mes = datetime.now().strftime('%m')
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"TEMA-{año}{mes}-{random_chars}"
    
    def get_estado_color(self):
        colores = {
            'Abierto': 'danger',
            'En Proceso': 'warning',
            'Resuelto': 'success',
            'Cerrado': 'secondary',
            'Archivado': 'dark'
        }
        return colores.get(self.estado, 'secondary')
    
    def get_estado_icon(self):
        iconos = {
            'Abierto': 'fa-circle',
            'En Proceso': 'fa-spinner',
            'Resuelto': 'fa-check-circle',
            'Cerrado': 'fa-lock',
            'Archivado': 'fa-archive'
        }
        return iconos.get(self.estado, 'fa-circle')
    
    def get_prioridad_color(self):
        colores = {
            'Alta': 'danger',
            'Media': 'warning',
            'Baja': 'success'
        }
        return colores.get(self.prioridad, 'secondary')
    
    def get_sector_icon(self):
        iconos = {
            'mantenimiento': 'fa-tools',
            'produccion': 'fa-industry',
            'calidad': 'fa-clipboard-check',
            'administracion': 'fa-building',
            'rrhh': 'fa-users',
            'contabilidad': 'fa-calculator',
            'compras': 'fa-shopping-cart',
            'sistemas': 'fa-server'
        }
        return iconos.get(self.sector, 'fa-comment')
    
    @property
    def historial_asignaciones(self):
        return json.loads(self._historial_asignaciones) if self._historial_asignaciones else []
    
    @historial_asignaciones.setter
    def historial_asignaciones(self, valor):
        self._historial_asignaciones = json.dumps(valor)
    
    def registrar_asignacion(self, usuario_id, usuario_nombre, comentario=None):
        """Registra un cambio de asignación en el historial"""
        historial = self.historial_asignaciones
        historial.append({
            'fecha': datetime.now().isoformat(),
            'usuario_id': usuario_id,
            'usuario_nombre': usuario_nombre,
            'comentario': comentario,
            'asignado_anterior': self.asignado_a_nombre,
            'asignado_nuevo': self.asignado_a_nombre
        })
        self.historial_asignaciones = historial
        db.session.commit()
    
    def __repr__(self):
        return f'<Tema {self.codigo}: {self.titulo[:30]}>'


class MensajeTema(db.Model):
    __tablename__ = 'mensajes_tema'
    
    id = db.Column(db.Integer, primary_key=True)
    tema_id = db.Column(db.Integer, db.ForeignKey('temas_conversacion.id'), nullable=False)
    
    contenido = db.Column(db.Text, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    usuario_nombre = db.Column(db.String(100))
    
    # Menciones (JSON con IDs de usuarios)
    _menciones = db.Column(db.Text, default='[]')
    
    # Adjuntos
    _adjuntos = db.Column(db.Text, default='[]')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    
    @property
    def menciones(self):
        return json.loads(self._menciones) if self._menciones else []
    
    @menciones.setter
    def menciones(self, valor):
        self._menciones = json.dumps(valor)
    
    @property
    def adjuntos(self):
        return json.loads(self._adjuntos) if self._adjuntos else []
    
    @adjuntos.setter
    def adjuntos(self, valor):
        self._adjuntos = json.dumps(valor)
    
    def agregar_adjunto(self, nombre, url, tamano=None):
        adjuntos = self.adjuntos
        adjuntos.append({
            'nombre': nombre,
            'url': url,
            'tamano': tamano,
            'fecha': datetime.now().isoformat()
        })
        self.adjuntos = adjuntos
        db.session.commit()
    
    def __repr__(self):
        return f'<Mensaje {self.id}: {self.contenido[:50]}>'