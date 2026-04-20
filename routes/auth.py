# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from models.usuario import Usuario
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.activo:
                login_user(user, remember=True)
                
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.nivel_jerarquico
                session['area'] = user.area_principal
                session['nombre_completo'] = user.nombre_completo
                
                user.ultimo_acceso = datetime.utcnow()
                db.session.commit()
                
                flash(f'Bienvenido al sistema GMP, {user.nombre_completo or user.username}', 'success')
                
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard.dashboard'))
            else:
                flash('Usuario inactivo. Contacte al administrador.', 'error')
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil')
@login_required
def perfil():
    return render_template('auth/perfil.html', user=current_user)

@auth_bp.route('/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    
    if current_user.check_password(old_password):
        current_user.set_password(new_password)
        db.session.commit()
        flash('Contraseña actualizada correctamente', 'success')
    else:
        flash('Contraseña actual incorrecta', 'error')
    
    return redirect(url_for('auth.perfil'))

@auth_bp.route('/session-info')
@login_required
def session_info():
    """Devuelve información de la sesión actual"""
    return jsonify({
        'username': current_user.username,
        'nombre_completo': current_user.nombre_completo,
        'area_principal': current_user.area_principal,
        'nivel_jerarquico': current_user.nivel_jerarquico,
        'activo': current_user.activo
    })