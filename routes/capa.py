# routes/capa.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.capa import CAPA, SeguimientoCAPA
from models.orden_trabajo import OrdenTrabajo
from models.calibracion import Calibracion
from models.cambio import Cambio
from datetime import datetime, date
from utils.decorators import admin_required, tecnico_required
from utils.notificador_bd import notificador_bd
import json

capa_bp = Blueprint('capa', __name__)

@capa_bp.route('/')
@tecnico_required
def gestion_capa():
    """Listado de CAPAs"""
    capas = CAPA.query.order_by(CAPA.fecha_deteccion.desc()).all()
    
    abiertas = CAPA.query.filter_by(estado='Abierto').count()
    en_analisis = CAPA.query.filter_by(estado='En Análisis').count()
    en_implementacion = CAPA.query.filter_by(estado='En Implementación').count()
    en_verificacion = CAPA.query.filter_by(estado='En Verificación').count()
    cerradas = CAPA.query.filter_by(estado='Cerrado').count()
    
    return render_template('capa/gestion_capa.html',
                         capas=capas,
                         abiertas=abiertas,
                         en_analisis=en_analisis,
                         en_implementacion=en_implementacion,
                         en_verificacion=en_verificacion,
                         cerradas=cerradas)

@capa_bp.route('/nueva', methods=['GET', 'POST'])
@tecnico_required
def nueva_capa():
    """Crear nueva CAPA"""
    if request.method == 'POST':
        try:
            # Generar número de CAPA
            import random
            import string
            año = datetime.now().year
            mes = datetime.now().strftime('%m')
            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            numero_capa = f"CAPA-{año}{mes}-{random_chars}"
            
            nueva = CAPA(
                numero_capa=numero_capa,
                origen=request.form.get('origen'),
                origen_id=request.form.get('origen_id') or None,
                origen_descripcion=request.form.get('origen_descripcion'),
                titulo=request.form.get('titulo'),
                descripcion_problema=request.form.get('descripcion_problema'),
                fecha_deteccion=datetime.strptime(request.form.get('fecha_deteccion'), '%Y-%m-%d').date(),
                detectado_por=request.form.get('detectado_por'),
                tipo=request.form.get('tipo'),
                severidad=request.form.get('severidad'),
                prioridad=request.form.get('prioridad'),
                clasificacion=request.form.get('clasificacion'),
                estado='Abierto',
                created_by=session.get('username')
            )
            
            db.session.add(nueva)
            db.session.commit()
            
            flash(f'CAPA {numero_capa} creada exitosamente', 'success')
            return redirect(url_for('capa.detalle_capa', capa_id=nueva.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear CAPA: {str(e)}', 'error')
    
    # Obtener posibles orígenes
    ordenes = OrdenTrabajo.query.filter(OrdenTrabajo.requiere_capa == True).all()
    calibraciones = Calibracion.query.filter_by(resultado='No Conforme').all()
    cambios = Cambio.query.filter_by(estado='Implementado').all()
    
    return render_template('capa/nueva_capa.html',
                         ordenes=ordenes,
                         calibraciones=calibraciones,
                         cambios=cambios,
                         now=datetime.now())

@capa_bp.route('/<int:capa_id>')
@tecnico_required
def detalle_capa(capa_id):
    """Ver detalle de CAPA"""
    capa = CAPA.query.get_or_404(capa_id)
    return render_template('capa/detalle_capa.html', capa=capa)

@capa_bp.route('/<int:capa_id>/editar', methods=['GET', 'POST'])
@tecnico_required
def editar_capa(capa_id):
    """Editar CAPA (solo si está abierta)"""
    capa = CAPA.query.get_or_404(capa_id)
    
    if capa.estado not in ['Abierto', 'En Análisis']:
        flash('No se puede editar una CAPA en este estado', 'error')
        return redirect(url_for('capa.detalle_capa', capa_id=capa.id))
    
    if request.method == 'POST':
        try:
            # Actualizar campos
            capa.titulo = request.form.get('titulo')
            capa.descripcion_problema = request.form.get('descripcion_problema')
            capa.severidad = request.form.get('severidad')
            capa.prioridad = request.form.get('prioridad')
            capa.clasificacion = request.form.get('clasificacion')
            capa.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('CAPA actualizada correctamente', 'success')
            return redirect(url_for('capa.detalle_capa', capa_id=capa.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    return render_template('capa/editar_capa.html', capa=capa)

@capa_bp.route('/<int:capa_id>/analisis', methods=['POST'])
@tecnico_required
def registrar_analisis(capa_id):
    """Registrar análisis de causa raíz"""
    capa = CAPA.query.get_or_404(capa_id)
    
    try:
        capa.metodologia_analisis = request.form.get('metodologia_analisis')
        capa.analisis_causa = request.form.get('analisis_causa')
        capa.causa_raiz = request.form.get('causa_raiz')
        capa.estado = 'En Análisis'
        
        db.session.commit()
        flash('Análisis registrado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar análisis: {str(e)}', 'error')
    
    return redirect(url_for('capa.detalle_capa', capa_id=capa.id))

@capa_bp.route('/<int:capa_id>/acciones', methods=['POST'])
@tecnico_required
def registrar_acciones(capa_id):
    """Registrar acciones correctivas y preventivas"""
    capa = CAPA.query.get_or_404(capa_id)
    
    try:
        capa.acciones_correctivas = request.form.get('acciones_correctivas')
        capa.acciones_preventivas = request.form.get('acciones_preventivas')
        capa.plan_implementacion = request.form.get('plan_implementacion')
        capa.responsable = request.form.get('responsable')
        capa.equipo_trabajo = request.form.get('equipo_trabajo')
        capa.fecha_estimada_cierre = datetime.strptime(request.form.get('fecha_estimada_cierre'), '%Y-%m-%d').date()
        capa.costo_estimado = float(request.form.get('costo_estimado')) if request.form.get('costo_estimado') else None
        capa.estado = 'En Implementación'
        
        db.session.commit()
        flash('Acciones registradas correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar acciones: {str(e)}', 'error')
    
    return redirect(url_for('capa.detalle_capa', capa_id=capa.id))

@capa_bp.route('/<int:capa_id>/verificacion', methods=['POST'])
@admin_required
def registrar_verificacion(capa_id):
    """Registrar verificación de eficacia"""
    capa = CAPA.query.get_or_404(capa_id)
    
    try:
        capa.verificacion_eficacia = request.form.get('verificacion_eficacia')
        capa.fecha_verificacion = datetime.strptime(request.form.get('fecha_verificacion'), '%Y-%m-%d').date()
        capa.verificador = request.form.get('verificador')
        capa.resultado_verificacion = request.form.get('resultado_verificacion')
        capa.lecciones_aprendidas = request.form.get('lecciones_aprendidas')
        capa.requiere_capacitacion = bool(request.form.get('requiere_capacitacion'))
        capa.plan_capacitacion = request.form.get('plan_capacitacion')
        
        if request.form.get('resultado_verificacion') == 'Eficaz':
            capa.estado = 'Cerrado'
            capa.fecha_cierre = datetime.utcnow().date()
            capa.aprobado_por = session.get('username')
            capa.fecha_aprobacion = datetime.utcnow().date()
        else:
            capa.estado = 'En Implementación'  # Volver a implementación si no es eficaz
        
        db.session.commit()
        flash('Verificación registrada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar verificación: {str(e)}', 'error')
    
    return redirect(url_for('capa.detalle_capa', capa_id=capa.id))

@capa_bp.route('/<int:capa_id>/seguimiento', methods=['POST'])
@tecnico_required
def agregar_seguimiento(capa_id):
    """Agregar seguimiento a CAPA"""
    capa = CAPA.query.get_or_404(capa_id)
    
    try:
        seguimiento = SeguimientoCAPA(
            capa_id=capa_id,
            usuario=session.get('username'),
            tipo=request.form.get('tipo'),
            descripcion=request.form.get('descripcion'),
            porcentaje_avance=int(request.form.get('porcentaje_avance')) if request.form.get('porcentaje_avance') else None,
            proximos_pasos=request.form.get('proximos_pasos')
        )
        
        db.session.add(seguimiento)
        db.session.commit()
        
        flash('Seguimiento agregado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al agregar seguimiento: {str(e)}', 'error')
    
    return redirect(url_for('capa.detalle_capa', capa_id=capa.id))

@capa_bp.route('/<int:capa_id>/cerrar', methods=['POST'])
@admin_required
def cerrar_capa(capa_id):
    """Cerrar CAPA manualmente"""
    capa = CAPA.query.get_or_404(capa_id)
    
    try:
        capa.estado = 'Cerrado'
        capa.fecha_cierre = datetime.utcnow().date()
        capa.comentarios_cierre = request.form.get('comentarios_cierre')
        capa.aprobado_por = session.get('username')
        capa.fecha_aprobacion = datetime.utcnow().date()
        
        db.session.commit()
        flash('CAPA cerrada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cerrar CAPA: {str(e)}', 'error')
    
    return redirect(url_for('capa.detalle_capa', capa_id=capa.id))

@capa_bp.route('/api/resumen')
@tecnico_required
def api_resumen():
    """API para obtener resumen de CAPAs"""
    total = CAPA.query.count()
    abiertas = CAPA.query.filter(CAPA.estado.in_(['Abierto', 'En Análisis', 'En Implementación', 'En Verificación'])).count()
    vencidas = CAPA.query.filter(
        CAPA.estado.in_(['Abierto', 'En Análisis', 'En Implementación', 'En Verificación']),
        CAPA.fecha_estimada_cierre < date.today()
    ).count()
    
    por_prioridad = {
        'Alta': CAPA.query.filter(CAPA.prioridad == 'Alta', CAPA.estado != 'Cerrado').count(),
        'Media': CAPA.query.filter(CAPA.prioridad == 'Media', CAPA.estado != 'Cerrado').count(),
        'Baja': CAPA.query.filter(CAPA.prioridad == 'Baja', CAPA.estado != 'Cerrado').count()
    }
    
    return jsonify({
        'total': total,
        'abiertas': abiertas,
        'vencidas': vencidas,
        'por_prioridad': por_prioridad
    })