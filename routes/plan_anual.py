# routes/plan_anual.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models.plan_anual import PlanAnual, ActividadPlanAnual
from models.equipo import Equipo
from models.sistema import SistemaEquipo, PlanMantenimiento
from models.orden_trabajo import OrdenTrabajo
from datetime import datetime, date, timedelta
from utils.decorators import tecnico_required, admin_required
import calendar

plan_anual_bp = Blueprint('plan_anual', __name__, url_prefix='/plan-anual')

@plan_anual_bp.route('/')
@tecnico_required
def index():
    """Listado de planes anuales"""
    planes = PlanAnual.query.order_by(PlanAnual.año.desc()).all()
    return render_template('plan_anual/index.html', planes=planes)

@plan_anual_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_required
def nuevo():
    """Crear nuevo plan anual"""
    if request.method == 'POST':
        try:
            año = int(request.form.get('año'))
            nombre = request.form.get('nombre') or f"Plan de Mantenimiento {año}"
            
            # Verificar si ya existe un plan para ese año
            existente = PlanAnual.query.filter_by(año=año).first()
            if existente:
                flash(f'Ya existe un plan para el año {año}', 'error')
                return redirect(url_for('plan_anual.nuevo'))
            
            plan = PlanAnual(
                año=año,
                nombre=nombre,
                descripcion=request.form.get('descripcion'),
                meses=PlanAnual().generar_estructura_base(),
                creado_por=current_user.username,
                estado='Borrador'
            )
            
            db.session.add(plan)
            db.session.commit()
            
            flash(f'Plan anual {año} creado correctamente', 'success')
            return redirect(url_for('plan_anual.editar', plan_id=plan.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear plan: {str(e)}', 'error')
    
    return render_template('plan_anual/nuevo.html')

@plan_anual_bp.route('/<int:plan_id>')
@tecnico_required
def ver(plan_id):
    """Ver plan anual"""
    plan = PlanAnual.query.get_or_404(plan_id)
    actividades = ActividadPlanAnual.query.filter_by(plan_id=plan.id).order_by(
        ActividadPlanAnual.mes, ActividadPlanAnual.semana
    ).all()
    
    return render_template('plan_anual/ver.html', plan=plan, actividades=actividades)

@plan_anual_bp.route('/<int:plan_id>/editar')
@tecnico_required
def editar(plan_id):
    """Editar plan anual"""
    plan = PlanAnual.query.get_or_404(plan_id)
    actividades = ActividadPlanAnual.query.filter_by(plan_id=plan.id).order_by(
        ActividadPlanAnual.mes, ActividadPlanAnual.semana
    ).all()
    equipos = Equipo.query.all()
    
    return render_template('plan_anual/editar.html', plan=plan, actividades=actividades, equipos=equipos)

@plan_anual_bp.route('/<int:plan_id>/api/actividades')
@tecnico_required
def api_actividades(plan_id):
    """API para obtener actividades del plan"""
    actividades = ActividadPlanAnual.query.filter_by(plan_id=plan_id).all()
    
    return jsonify([{
        'id': a.id,
        'mes': a.mes,
        'semana': a.semana,
        'equipo_id': a.equipo_id,
        'equipo': a.equipo.code if a.equipo else None,
        'sistema': a.sistema.nombre if a.sistema else None,
        'tarea': a.tarea.tarea_descripcion if a.tarea else a.descripcion,
        'tipo': a.tipo,
        'duracion': a.duracion_estimada,
        'responsable': a.responsable,
        'estado': a.estado
    } for a in actividades])

@plan_anual_bp.route('/api/agregar-actividad', methods=['POST'])
@admin_required
def api_agregar_actividad():
    """API para agregar actividad al plan"""
    data = request.json
    
    try:
        actividad = ActividadPlanAnual(
            plan_id=data['plan_id'],
            equipo_id=data.get('equipo_id'),
            sistema_id=data.get('sistema_id'),
            tarea_id=data.get('tarea_id'),
            mes=data['mes'],
            semana=data.get('semana', 1),
            descripcion=data['descripcion'],
            tipo=data.get('tipo', 'preventivo'),
            duracion_estimada=data.get('duracion', 1),
            responsable=data.get('responsable'),
            fecha_programada=datetime.strptime(data['fecha'], '%Y-%m-%d').date() if data.get('fecha') else None
        )
        
        db.session.add(actividad)
        db.session.commit()
        
        return jsonify({'success': True, 'id': actividad.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@plan_anual_bp.route('/api/eliminar-actividad/<int:actividad_id>', methods=['POST'])
@admin_required
def api_eliminar_actividad(actividad_id):
    """API para eliminar actividad"""
    try:
        actividad = ActividadPlanAnual.query.get_or_404(actividad_id)
        db.session.delete(actividad)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@plan_anual_bp.route('/api/actualizar-estado/<int:actividad_id>', methods=['POST'])
@tecnico_required
def api_actualizar_estado(actividad_id):
    """API para actualizar estado de actividad"""
    data = request.json
    try:
        actividad = ActividadPlanAnual.query.get_or_404(actividad_id)
        actividad.estado = data['estado']
        if data['estado'] == 'Completado':
            actividad.fecha_ejecucion = date.today()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@plan_anual_bp.route('/api/cambiar-estado/<int:plan_id>', methods=['POST'])
@admin_required
def api_cambiar_estado(plan_id):
    """API para cambiar estado del plan"""
    data = request.json
    try:
        plan = PlanAnual.query.get_or_404(plan_id)
        plan.estado = data['estado']
        if data['estado'] == 'Aprobado':
            plan.fecha_aprobacion = date.today()
            plan.aprobado_por = current_user.username
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@plan_anual_bp.route('/api/generar-desde-pm/<int:plan_id>', methods=['POST'])
@admin_required
def api_generar_desde_pm(plan_id):
    """Genera actividades automáticamente desde los planes de mantenimiento"""
    plan = PlanAnual.query.get_or_404(plan_id)
    
    try:
        # Obtener todas las tareas de mantenimiento activas
        tareas = PlanMantenimiento.query.filter_by(activo=True).all()
        contador = 0
        
        for tarea in tareas:
            if not tarea.sistema or not tarea.sistema.equipo:
                continue
            
            # Calcular mes aproximado (simplificado)
            mes_estimado = 1  # Enero por defecto
            if tarea.ultima_ejecucion:
                # Si tiene última ejecución, programar según frecuencia
                meses_desde_ultima = (date.today() - tarea.ultima_ejecucion).days / 30
                mes_estimado = (meses_desde_ultima % 12) + 1
            else:
                # Si nunca se ejecutó, programar para el mes actual
                mes_estimado = date.today().month
            
            actividad = ActividadPlanAnual(
                plan_id=plan.id,
                equipo_id=tarea.sistema.equipo_id,
                sistema_id=tarea.sistema_id,
                tarea_id=tarea.id,
                mes=mes_estimado,
                semana=1,
                descripcion=tarea.tarea_descripcion,
                tipo='preventivo',
                duracion_estimada=tarea.tiempo_estimado or 1,
                estado='Programado'
            )
            db.session.add(actividad)
            contador += 1
        
        db.session.commit()
        return jsonify({'success': True, 'cantidad': contador})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@plan_anual_bp.route('/api/exportar/<int:plan_id>')
@tecnico_required
def api_exportar(plan_id):
    """Exportar plan a formato calendario"""
    plan = PlanAnual.query.get_or_404(plan_id)
    actividades = ActividadPlanAnual.query.filter_by(plan_id=plan.id).all()
    
    # Crear estructura para calendario
    eventos = []
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    for act in actividades:
        # Fecha aproximada (primer día del mes + semana*7)
        año = plan.año
        mes = act.mes
        dia = act.semana * 7
        if dia > calendar.monthrange(año, mes)[1]:
            dia = calendar.monthrange(año, mes)[1]
        
        eventos.append({
            'titulo': act.descripcion,
            'equipo': act.equipo.code if act.equipo else 'N/A',
            'mes': meses[mes-1],
            'semana': act.semana,
            'tipo': act.tipo,
            'responsable': act.responsable,
            'estado': act.estado
        })
    
    return jsonify({
        'plan': {
            'año': plan.año,
            'nombre': plan.nombre,
            'estado': plan.estado
        },
        'actividades': eventos
    })