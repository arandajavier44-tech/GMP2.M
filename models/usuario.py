# models/usuario.py
from models import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # Información personal
    nombre_completo = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    
    # Área principal del usuario
    area_principal = db.Column(db.String(50))  # 'mantenimiento', 'produccion', 'calidad', 'almacen', 'administracion'
    
    # Nivel jerárquico
    nivel_jerarquico = db.Column(db.String(20))  # 'jefe', 'supervisor', 'operador', 'asistente'
    
    # Múltiples roles (guardados como JSON)
    _roles = db.Column(db.Text, default='[]')
    
    # Permisos específicos (guardados como JSON)
    _permisos = db.Column(db.Text, default='{}')
    
    # Competencias técnicas (guardadas como JSON)
    _competencias = db.Column(db.Text, default='[]')
    
    # Firmas y autenticación
    firma_digital = db.Column(db.String(200))
    pin_firma = db.Column(db.String(10))
    
    # Estado
    activo = db.Column(db.Boolean, default=True)
    ultimo_acceso = db.Column(db.DateTime)
    
    # Preferencias de notificaciones
    preferencias_notificaciones = db.Column(db.Text, default='{}')
    
    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    # Relaciones
    actividades = db.relationship('ActividadUsuario', backref='usuario', lazy=True, cascade='all, delete-orphan')
    
    @property
    def roles(self):
        return json.loads(self._roles) if self._roles else []
    
    @roles.setter
    def roles(self, lista_roles):
        self._roles = json.dumps(lista_roles)
    
    def agregar_rol(self, rol):
        roles_actuales = self.roles
        if rol not in roles_actuales:
            roles_actuales.append(rol)
            self.roles = roles_actuales
    
    def quitar_rol(self, rol):
        roles_actuales = self.roles
        if rol in roles_actuales:
            roles_actuales.remove(rol)
            self.roles = roles_actuales
    
    def tiene_rol(self, rol):
        return rol in self.roles
    
    def tiene_cualquier_rol(self, lista_roles):
        return any(rol in self.roles for rol in lista_roles)
    
    @property
    def permisos(self):
        return json.loads(self._permisos) if self._permisos else {}
    
    @permisos.setter
    def permisos(self, dict_permisos):
        self._permisos = json.dumps(dict_permisos)
    
    def tiene_permiso(self, permiso):
        if self.nivel_jerarquico in ['jefe', 'supervisor']:
            return True
        permisos = self.permisos
        return permisos.get(permiso, False)
    
    @property
    def competencias(self):
        return json.loads(self._competencias) if self._competencias else []
    
    @competencias.setter
    def competencias(self, lista_competencias):
        self._competencias = json.dumps(lista_competencias)
    
    def tiene_competencia(self, competencia):
        return competencia in self.competencias
    
    def get_icon_rol(self):
        iconos = {
            'jefe': 'fa-crown',
            'supervisor': 'fa-user-tie',
            'operador': 'fa-user-cog',
            'asistente': 'fa-user',
        }
        iconos_area = {
            'mantenimiento': 'fa-tools',
            'produccion': 'fa-industry',
            'calidad': 'fa-clipboard-check',
            'almacen': 'fa-warehouse',
            'administracion': 'fa-building',
        }
        return iconos.get(self.nivel_jerarquico, iconos_area.get(self.area_principal, 'fa-user'))
    
    def get_color_rol(self):
        colores = {
            'jefe': 'danger',
            'supervisor': 'warning',
            'operador': 'primary',
            'asistente': 'secondary',
        }
        colores_area = {
            'mantenimiento': 'primary',
            'produccion': 'success',
            'calidad': 'info',
            'almacen': 'warning',
            'administracion': 'danger',
        }
        return colores.get(self.nivel_jerarquico, colores_area.get(self.area_principal, 'secondary'))
    
    def __repr__(self):
        return f'<Usuario {self.username}: {self.nombre_completo}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    def puede_generar_orden(self, tipo_orden):
        if self.nivel_jerarquico in ['jefe', 'supervisor']:
            return True
        if self.area_principal == 'mantenimiento':
            if tipo_orden in ['Preventivo', 'Correctivo']:
                return True
        elif self.area_principal == 'produccion':
            if tipo_orden == 'Servicio' and self.tiene_rol('operador_produccion'):
                return True
        elif self.area_principal == 'almacen':
            if tipo_orden == 'Servicio' and self.tiene_rol('operador_almacen'):
                return True
        return False
    
    def registrar_actividad(self, accion, modulo, detalle=None, ip=None):
        actividad = ActividadUsuario(
            usuario_id=self.id,
            accion=accion,
            modulo=modulo,
            detalle=detalle,
            ip=ip
        )
        db.session.add(actividad)
        db.session.commit()


class ActividadUsuario(db.Model):
    __tablename__ = 'actividades_usuario'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    accion = db.Column(db.String(50))
    modulo = db.Column(db.String(50))
    detalle = db.Column(db.Text)
    ip = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)