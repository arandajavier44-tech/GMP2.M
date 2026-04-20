# routes/usuarios.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from models import db
from models.usuario import Usuario, ActividadUsuario
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from utils.decorators import admin_required
import re

# Intentar importar desde config_data (nuestra carpeta de roles)
try:
    from config_data.roles import AREAS, NIVELES_JERARQUICOS, ROLES_POR_AREA, PERMISOS_POR_NIVEL
except ImportError:
    # Valores por defecto si no existe el archivo
    AREAS = [
        {'id': 'mantenimiento', 'nombre': 'Mantenimiento', 'icono': 'fa-tools'},
        {'id': 'produccion', 'nombre': 'Producción', 'icono': 'fa-industry'},
        {'id': 'calidad', 'nombre': 'Calidad', 'icono': 'fa-clipboard-check'},
        {'id': 'almacen', 'nombre': 'Almacén', 'icono': 'fa-warehouse'},
        {'id': 'administracion', 'nombre': 'Administración', 'icono': 'fa-building'},
    ]
    
    NIVELES_JERARQUICOS = [
        {'id': 'jefe', 'nombre': 'Jefe de Área', 'nivel': 100},
        {'id': 'supervisor', 'nombre': 'Supervisor', 'nivel': 80},
        {'id': 'operador', 'nombre': 'Operador', 'nivel': 50},
        {'id': 'asistente', 'nombre': 'Asistente', 'nivel': 30},
    ]
    
    ROLES_POR_AREA = {
        'mantenimiento': [
            {'id': 'mecanico', 'nombre': 'Mecánico', 'competencias': ['reparacion_mecanica', 'diagnostico_fallas']},
            {'id': 'electrico', 'nombre': 'Eléctrico', 'competencias': ['reparacion_electrica', 'instalaciones']},
        ],
        'produccion': [
            {'id': 'operador_linea', 'nombre': 'Operador de Línea', 'competencias': ['operacion_maquina', 'control_calidad']},
        ],
        'administracion': [
            {'id': 'admin_global', 'nombre': 'Administrador Global', 'competencias': ['gestion_usuarios']},
        ],
    }
    
    PERMISOS_POR_NIVEL = {
        'jefe': {'gestionar_usuarios': True},
        'supervisor': {},
        'operador': {},
        'asistente': {},
    }

# DEFINIR EL BLUEPRINT
usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/')
@admin_required
def gestion_usuarios():
    """Listado de usuarios"""
    usuarios = Usuario.query.order_by(Usuario.created_at.desc()).all()
    
    # Serializar usuarios para JSON
    usuarios_serializados = []
    for u in usuarios:
        usuarios_serializados.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'nombre_completo': u.nombre_completo,
            'area_principal': u.area_principal,
            'nivel_jerarquico': u.nivel_jerarquico,
            'roles': u.roles,
            'activo': u.activo,
            'ultimo_acceso': u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            'created_at': u.created_at.isoformat() if u.created_at else None
        })
    
    # Estadísticas
    total_activos = Usuario.query.filter_by(activo=True).count()
    total_admin = Usuario.query.filter_by(area_principal='administracion', nivel_jerarquico='jefe').count()
    total_supervisor = Usuario.query.filter_by(nivel_jerarquico='supervisor').count()
    total_tecnico = Usuario.query.filter_by(area_principal='mantenimiento', nivel_jerarquico='operador').count()
    
    return render_template('usuarios/gestion_usuarios.html',
                         usuarios=usuarios_serializados,
                         total_activos=total_activos,
                         total_admin=total_admin,
                         total_supervisor=total_supervisor,
                         total_tecnico=total_tecnico)

@usuarios_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_required
def nuevo_usuario():
    """Crear nuevo usuario con roles múltiples"""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Validar username único
            if Usuario.query.filter_by(username=username).first():
                flash('El nombre de usuario ya existe', 'error')
                return redirect(url_for('usuarios.nuevo_usuario'))
            
            # Validar email único
            if Usuario.query.filter_by(email=email).first():
                flash('El email ya está registrado', 'error')
                return redirect(url_for('usuarios.nuevo_usuario'))
            
            # Obtener roles seleccionados (múltiples)
            roles_seleccionados = request.form.getlist('roles[]')
            
            # Crear usuario
            nuevo_usuario = Usuario(
                username=username,
                email=email,
                nombre_completo=request.form.get('nombre_completo'),
                telefono=request.form.get('telefono'),
                area_principal=request.form.get('area_principal'),
                nivel_jerarquico=request.form.get('nivel_jerarquico'),
                activo=bool(request.form.get('activo', True))
            )
            
            # Asignar roles (lista JSON)
            nuevo_usuario.roles = roles_seleccionados
            
            # Asignar permisos según nivel jerárquico
            nivel = request.form.get('nivel_jerarquico')
            if nivel and nivel in PERMISOS_POR_NIVEL:
                nuevo_usuario.permisos = PERMISOS_POR_NIVEL[nivel]
            
            nuevo_usuario.set_password(password)
            
            db.session.add(nuevo_usuario)
            db.session.commit()
            
            flash(f'Usuario {username} creado exitosamente', 'success')
            return redirect(url_for('usuarios.gestion_usuarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear usuario: {str(e)}', 'error')
    
    return render_template('usuarios/nuevo_usuario.html',
                         areas=AREAS,
                         niveles=NIVELES_JERARQUICOS,
                         roles_por_area=ROLES_POR_AREA)

@usuarios_bp.route('/<int:usuario_id>')
@admin_required
def detalle_usuario(usuario_id):
    """Ver detalle de usuario"""
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Obtener actividades recientes
    actividades = ActividadUsuario.query.filter_by(usuario_id=usuario.id)\
        .order_by(ActividadUsuario.created_at.desc()).limit(20).all()
    
    return render_template('usuarios/detalle_usuario.html', 
                         usuario=usuario, 
                         actividades=actividades)

@usuarios_bp.route('/<int:usuario_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_usuario(usuario_id):
    """Editar usuario"""
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if request.method == 'POST':
        try:
            # Actualizar campos
            usuario.nombre_completo = request.form.get('nombre_completo')
            usuario.telefono = request.form.get('telefono')
            usuario.area_principal = request.form.get('area_principal')
            usuario.nivel_jerarquico = request.form.get('nivel_jerarquico')
            usuario.activo = bool(request.form.get('activo', True))
            
            # Actualizar roles
            roles_seleccionados = request.form.getlist('roles[]')
            usuario.roles = roles_seleccionados
            
            # Actualizar permisos según nivel jerárquico
            nivel = request.form.get('nivel_jerarquico')
            if nivel and nivel in PERMISOS_POR_NIVEL:
                usuario.permisos = PERMISOS_POR_NIVEL[nivel]
            
            db.session.commit()
            
            flash('Usuario actualizado correctamente', 'success')
            return redirect(url_for('usuarios.detalle_usuario', usuario_id=usuario.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    return render_template('usuarios/editar_usuario.html', 
                         usuario=usuario,
                         areas=AREAS,
                         niveles=NIVELES_JERARQUICOS,
                         roles_por_area=ROLES_POR_AREA)

@usuarios_bp.route('/<int:usuario_id>/cambiar-password', methods=['POST'])
@admin_required
def cambiar_password(usuario_id):
    """Cambiar contraseña de usuario (solo admin)"""
    usuario = Usuario.query.get_or_404(usuario_id)
    
    try:
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        if not nueva_password or len(nueva_password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return redirect(url_for('usuarios.detalle_usuario', usuario_id=usuario.id))
        
        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('usuarios.detalle_usuario', usuario_id=usuario.id))
        
        usuario.set_password(nueva_password)
        db.session.commit()
        
        flash('Contraseña actualizada correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar contraseña: {str(e)}', 'error')
    
    return redirect(url_for('usuarios.detalle_usuario', usuario_id=usuario.id))

@usuarios_bp.route('/<int:usuario_id>/toggle-estado', methods=['POST'])
@login_required
def toggle_estado(usuario_id):
    """Activa/Desactiva un usuario"""
    from models.usuario import Usuario
    
    # Solo administradores pueden hacer esto
    if current_user.nivel_jerarquico != 'jefe':
        return jsonify({'error': 'No autorizado'}), 403
    
    usuario = Usuario.query.get_or_404(usuario_id)
    usuario.activo = not usuario.activo
    db.session.commit()
    
    return jsonify({'success': True})

@usuarios_bp.route('/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
def eliminar_usuario(usuario_id):
    """Elimina un usuario"""
    from models.usuario import Usuario
    
    # Solo administradores pueden hacer esto
    if current_user.nivel_jerarquico != 'jefe':
        return jsonify({'error': 'No autorizado'}), 403
    
    # No permitir eliminar el propio usuario
    if usuario_id == current_user.id:
        return jsonify({'error': 'No puedes eliminar tu propio usuario'}), 400
    
    usuario = Usuario.query.get_or_404(usuario_id)
    db.session.delete(usuario)
    db.session.commit()
    
    return jsonify({'success': True})

@usuarios_bp.route('/api/verificar-username')
@admin_required
def verificar_username():
    """Verifica si un username está disponible"""
    username = request.args.get('username')
    usuario_id = request.args.get('usuario_id')
    
    query = Usuario.query.filter_by(username=username)
    if usuario_id:
        query = query.filter(Usuario.id != int(usuario_id))
    
    existe = query.first() is not None
    
    return jsonify({'disponible': not existe})

@usuarios_bp.route('/api/verificar-email')
@admin_required
def verificar_email():
    """Verifica si un email está disponible"""
    email = request.args.get('email')
    usuario_id = request.args.get('usuario_id')
    
    query = Usuario.query.filter_by(email=email)
    if usuario_id:
        query = query.filter(Usuario.id != int(usuario_id))
    
    existe = query.first() is not None
    
    return jsonify({'disponible': not existe})

@usuarios_bp.route('/<int:usuario_id>/test-email', methods=['POST'])
@login_required
def test_email(usuario_id):
    """Envía email de prueba al usuario"""
    from models.usuario import Usuario
    from utils.notificador_email import notificador_email
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if not usuario.email:
        return jsonify({'error': 'El usuario no tiene email configurado'}), 400
    
    resultado = notificador_email.enviar(
        usuario.email,
        "🧪 Prueba GMP Maintenance",
        f"<h1>Hola {usuario.nombre_completo or usuario.username}!</h1>"
        f"<p>Este es un email de prueba desde el sistema GMP Maintenance.</p>"
        f"<p>Si recibes este mensaje, la configuración de email funciona correctamente.</p>"
        f"<hr><small>Enviado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</small>"
    )
    
    if resultado:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'No se pudo enviar el email'}), 500

@usuarios_bp.route('/api/lista')
@login_required
def api_lista_usuarios():
    """Lista de usuarios para menciones"""
    usuarios = Usuario.query.filter_by(activo=True).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'nombre': u.nombre_completo or u.username,
        'area': u.area_principal
    } for u in usuarios])