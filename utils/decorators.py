# utils/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for, request
from models.usuario import Usuario

# ============ DECORADOR BÁSICO ============

def login_required(f):
    """Verifica que el usuario haya iniciado sesión"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Solo administradores (jefe de administración)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('area') != 'administracion' or session.get('role') != 'jefe':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'error')
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def supervisor_required(f):
    """Supervisores y jefes de cualquier área"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('role') not in ['jefe', 'supervisor']:
            flash('Acceso denegado. Se requieren permisos de supervisor.', 'error')
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def tecnico_required(f):
    """Técnicos, supervisores y jefes (pueden ejecutar órdenes)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('role') not in ['jefe', 'supervisor', 'operador']:
            flash('Acceso denegado. No tiene permisos suficientes.', 'error')
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def area_required(area):
    """Requiere un área específica"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor inicie sesión para acceder', 'warning')
                return redirect(url_for('auth.login'))
            
            if session.get('area') != area:
                flash(f'Acceso denegado. Esta función es solo para el área de {area}.', 'error')
                return redirect(url_for('dashboard.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============ DECORADORES PARA ÓRDENES ============

def puede_crear_orden(f):
    """Permite crear órdenes según rol y área"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        # Jefes y supervisores siempre pueden
        if role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        # Mantenimiento puede crear preventivas y correctivas
        if area == 'mantenimiento' and role == 'operador':
            return f(*args, **kwargs)
        
        # Producción y Almacén solo pueden crear solicitudes de servicio
        if area in ['produccion', 'almacen'] and request.endpoint and 'servicio' in request.endpoint:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para crear órdenes de este tipo.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

def puede_editar_orden(f):
    """Permite editar órdenes (solo si está pendiente y es el asignado o supervisor)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        # Solo jefes, supervisores y admin pueden editar
        if role in ['jefe', 'supervisor'] or area == 'administracion':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para editar órdenes.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

def puede_eliminar_orden(f):
    """Solo administradores pueden eliminar órdenes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('area') == 'administracion' and session.get('role') == 'jefe':
            return f(*args, **kwargs)
        
        flash('Solo los administradores pueden eliminar órdenes.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

def puede_ejecutar_orden(f):
    """Permite ejecutar/completar órdenes (técnicos asignados o supervisores)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        # Jefes, supervisores y personal de mantenimiento pueden ejecutar
        if role in ['jefe', 'supervisor'] or area == 'mantenimiento':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para ejecutar órdenes de trabajo.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

def puede_aprobar_orden(f):
    """Solo supervisores y jefes pueden aprobar órdenes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('role') not in ['jefe', 'supervisor']:
            flash('Solo supervisores pueden aprobar órdenes.', 'error')
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# ============ DECORADORES PARA CALIBRACIONES ============

def puede_gestionar_calibraciones(f):
    """Calidad y Mantenimiento pueden gestionar calibraciones"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area in ['calidad', 'mantenimiento'] or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para gestionar calibraciones.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

# ============ DECORADORES PARA INVENTARIO ============

def puede_gestionar_inventario(f):
    """Almacén y Mantenimiento pueden gestionar inventario"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area in ['almacen', 'mantenimiento'] or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para gestionar inventario.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

def puede_consumir_repuestos(f):
    """Técnicos pueden consumir repuestos al completar órdenes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area == 'mantenimiento' or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para consumir repuestos.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

# ============ DECORADORES PARA EQUIPOS ============

def puede_gestionar_equipos(f):
    """Mantenimiento y Administración pueden gestionar equipos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area in ['mantenimiento', 'administracion'] or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para gestionar equipos.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

# ============ DECORADORES PARA REPORTES ============

def puede_ver_reportes(f):
    """Todos pueden ver reportes, pero con restricciones"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def puede_ver_reportes_completos(f):
    """Solo jefes y supervisores ven reportes completos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('role') in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para ver reportes completos.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return decorated_function

# ============ DECORADORES PARA SERVICIOS GENERALES ============

def puede_solicitar_servicio_general(f):
    """Cualquier usuario autenticado puede solicitar servicios generales"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def puede_ver_panel_sg(f):
    """Panel de servicios generales (mantenimiento, jefes, supervisores)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        # Mantenimiento, jefes y supervisores pueden ver el panel
        if area == 'mantenimiento' or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para acceder al panel de servicios generales.', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    return decorated_function


def puede_gestionar_ordenes_sg(f):
    """Gestionar órdenes de servicios generales (mantenimiento)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area == 'mantenimiento' or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para gestionar órdenes de servicios generales.', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    return decorated_function


def puede_aprobar_solicitud_sg(f):
    """Aprobar solicitudes de servicios generales (jefes y supervisores)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        # Solo jefes y supervisores (de cualquier área) pueden aprobar
        # También mantenimiento puede aprobar
        if role in ['jefe', 'supervisor'] or area == 'mantenimiento':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para aprobar solicitudes.', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=kwargs.get('orden_id')))
    return decorated_function


def puede_ejecutar_orden_sg(f):
    """Ejecutar/completar órdenes de servicios generales (técnicos de mantenimiento)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        # Mantenimiento y supervisores pueden ejecutar
        if area == 'mantenimiento' or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para ejecutar órdenes de servicios generales.', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=kwargs.get('orden_id')))
    return decorated_function


def puede_crear_preventiva_sg(f):
    """Crear órdenes preventivas de servicios generales (mantenimiento)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        if area == 'mantenimiento' or role in ['jefe', 'supervisor']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para crear órdenes preventivas.', 'error')
        return redirect(url_for('servicios_generales.panel_mantenimiento'))
    return decorated_function


def puede_gestionar_instalaciones_sg(f):
    """Gestionar instalaciones (crear, editar, eliminar) - solo mantenimiento"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        area = session.get('area', '')
        role = session.get('role', '')
        
        # Solo mantenimiento puede gestionar instalaciones
        if area == 'mantenimiento' or role == 'jefe':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para gestionar instalaciones.', 'error')
        return redirect(url_for('servicios_generales.gestion_instalaciones'))
    return decorated_function


def puede_cancelar_orden_sg(f):
    """Cancelar órdenes de servicios generales (jefes, supervisores)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        if role in ['jefe', 'supervisor'] or area == 'mantenimiento':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para cancelar órdenes.', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=kwargs.get('orden_id')))
    return decorated_function


def puede_ver_reportes_sg(f):
    """Ver reportes de servicios generales (jefes, supervisores)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        if role in ['jefe', 'supervisor'] or area in ['mantenimiento', 'administracion']:
            return f(*args, **kwargs)
        
        flash('No tiene permisos para ver reportes.', 'error')
        return redirect(url_for('servicios_generales.panel_mantenimiento'))
    return decorated_function


def puede_asignar_tecnico_sg(f):
    """Asignar técnicos a órdenes (supervisores, jefes de mantenimiento)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder', 'warning')
            return redirect(url_for('auth.login'))
        
        role = session.get('role', '')
        area = session.get('area', '')
        
        if role in ['jefe', 'supervisor'] or area == 'mantenimiento':
            return f(*args, **kwargs)
        
        flash('No tiene permisos para asignar técnicos.', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=kwargs.get('orden_id')))
    return decorated_function
