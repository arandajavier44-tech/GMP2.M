# routes/equipos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.equipo import Equipo
from models.sistema import SistemaEquipo, PlanMantenimiento
from models.inventario import Repuesto, RepuestoPorEquipo
from datetime import datetime
import re
from utils.decorators import admin_required, tecnico_required
from models.inventario import RepuestoPorEquipo


equipos_bp = Blueprint('equipos', __name__)

@equipos_bp.route('/')
@tecnico_required
def gestion_equipos():
    equipos = Equipo.query.order_by(Equipo.created_at.desc()).all()
    for equipo in equipos:
        equipo.semaforo_color = equipo.get_status_color()
    return render_template('equipos/gestion_equipos.html', equipos=equipos)

@equipos_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_required
def nuevo_equipo():
    if request.method == 'POST':
        try:
            print("=== PROCESANDO NUEVO EQUIPO ===")
            
            nuevo_equipo = Equipo(
                code=request.form.get('code'),
                name=request.form.get('name'),
                gmp_id=request.form.get('gmp_id'),
                gmp_classification=request.form.get('gmp_classification'),
                risk_level=request.form.get('risk_level', 'Medio'),
                product_contact=request.form.get('product_contact'),
                cleaning_level=request.form.get('cleaning_level'),
                manufacturer=request.form.get('manufacturer'),
                model=request.form.get('model'),
                serial_number=request.form.get('serial_number'),
                capacity=request.form.get('capacity'),
                operating_range=request.form.get('operating_range'),
                power_requirements=request.form.get('power_requirements'),
                description=request.form.get('description'),
                validation_status=request.form.get('validation_status'),
                validation_date=datetime.strptime(request.form.get('validation_date'), '%Y-%m-%d') if request.form.get('validation_date') else None,
                next_validation=datetime.strptime(request.form.get('next_validation'), '%Y-%m-%d') if request.form.get('next_validation') else None,
                validation_doc=request.form.get('validation_doc'),
                requires_requalification=bool(request.form.get('requires_requalification')),
                location=request.form.get('location'),
                production_area=request.form.get('production_area'),
                room_number=request.form.get('room_number'),
                installation_date=datetime.strptime(request.form.get('installation_date'), '%Y-%m-%d') if request.form.get('installation_date') else None,
                sop_number=request.form.get('sop_number'),
                maintenance_sop=request.form.get('maintenance_sop'),
                cleaning_sop=request.form.get('cleaning_sop'),
                calibration_sop=request.form.get('calibration_sop'),
                gmp_notes=request.form.get('gmp_notes'),
                created_by=session.get('username', 'Sistema'),
                quality_approver=request.form.get('quality_approver'),
                maintenance_responsible=request.form.get('maintenance_responsible'),
                current_status='Operativo'
            )
            
            db.session.add(nuevo_equipo)
            db.session.flush()
            print(f"Equipo creado con ID: {nuevo_equipo.id}")
            
            sistemas_procesados = procesar_sistemas_del_formulario(request.form, nuevo_equipo.id)
            if sistemas_procesados > 0:
                print(f"Se procesaron {sistemas_procesados} sistemas")
            
            db.session.commit()
            
            # ========== QR CORREGIDO ==========
            from utils.qr_system import QRTrazabilidad
            try:
                qr_path = QRTrazabilidad.generar_qr(nuevo_equipo, 'equipo')
                if qr_path:
                    nuevo_equipo.qr_code = qr_path
                    db.session.commit()
                    print(f"✅ QR generado para equipo: {nuevo_equipo.code}")
                else:
                    print(f"⚠️ No se pudo generar QR para {nuevo_equipo.code}")
            except Exception as qr_error:
                print(f"⚠️ Error generando QR: {qr_error}")
            # ==================================
            
            flash(f'Equipo {nuevo_equipo.code} registrado exitosamente con {sistemas_procesados} sistemas', 'success')
            return redirect(url_for('equipos.gestion_equipos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar equipo: {str(e)}', 'error')
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    repuestos = Repuesto.query.all()
    return render_template('equipos/nuevo_equipo.html', repuestos=repuestos)

@equipos_bp.route('/<int:equipo_id>')
@tecnico_required
def detalle_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    return render_template('equipos/detalle_equipo.html', equipo=equipo)

@equipos_bp.route('/<int:equipo_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    if request.method == 'POST':
        try:
            equipo.code = request.form.get('code')
            equipo.name = request.form.get('name')
            equipo.gmp_classification = request.form.get('gmp_classification')
            equipo.product_contact = request.form.get('product_contact')
            equipo.location = request.form.get('location')
            equipo.production_area = request.form.get('production_area')
            equipo.current_status = request.form.get('current_status', equipo.current_status)
            equipo.description = request.form.get('description')
            equipo.risk_level = request.form.get('risk_level')
            equipo.cleaning_level = request.form.get('cleaning_level')
            equipo.manufacturer = request.form.get('manufacturer')
            equipo.model = request.form.get('model')
            equipo.serial_number = request.form.get('serial_number')
            equipo.capacity = request.form.get('capacity')
            equipo.operating_range = request.form.get('operating_range')
            equipo.power_requirements = request.form.get('power_requirements')
            equipo.validation_status = request.form.get('validation_status')
            if request.form.get('validation_date'):
                equipo.validation_date = datetime.strptime(request.form.get('validation_date'), '%Y-%m-%d').date()
            if request.form.get('next_validation'):
                equipo.next_validation = datetime.strptime(request.form.get('next_validation'), '%Y-%m-%d').date()
            equipo.validation_doc = request.form.get('validation_doc')
            equipo.requires_requalification = bool(request.form.get('requires_requalification'))
            equipo.sop_number = request.form.get('sop_number')
            equipo.maintenance_sop = request.form.get('maintenance_sop')
            equipo.cleaning_sop = request.form.get('cleaning_sop')
            equipo.calibration_sop = request.form.get('calibration_sop')
            equipo.gmp_notes = request.form.get('gmp_notes')
            equipo.quality_approver = request.form.get('quality_approver')
            equipo.maintenance_responsible = request.form.get('maintenance_responsible')
            
            procesar_sistemas_edicion(request.form, equipo.id)
            
            db.session.commit()
            flash('Equipo actualizado correctamente', 'success')
            return redirect(url_for('equipos.detalle_equipo', equipo_id=equipo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
            print(f"Error al editar: {e}")
            import traceback
            traceback.print_exc()
    
    return render_template('equipos/editar_equipo.html', equipo=equipo)

@equipos_bp.route('/<int:equipo_id>/cambiar-estado', methods=['POST'])
@tecnico_required
def cambiar_estado(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    nuevo_estado = request.form.get('estado')
    
    try:
        equipo.current_status = nuevo_estado
        db.session.commit()
        flash(f'Estado del equipo cambiado a: {nuevo_estado}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar estado: {str(e)}', 'error')
    
    return redirect(url_for('equipos.detalle_equipo', equipo_id=equipo.id))

@equipos_bp.route('/<int:equipo_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    try:
        db.session.delete(equipo)
        db.session.commit()
        flash(f'Equipo {equipo.code} eliminado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('equipos.gestion_equipos'))

@equipos_bp.route('/<int:equipo_id>/asignar-repuestos')
@tecnico_required
def asignar_repuestos(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    repuestos_asignados_ids = [rp.repuesto_id for rp in equipo.repuestos_asignados]
    repuestos_disponibles = Repuesto.query.filter(~Repuesto.id.in_(repuestos_asignados_ids)).all() if repuestos_asignados_ids else Repuesto.query.all()
    return render_template('equipos/asignar_repuestos.html', equipo=equipo, repuestos_disponibles=repuestos_disponibles)

def procesar_sistemas_del_formulario(form_data, equipo_id):
    """Procesa los sistemas enviados en el formulario"""
    from models.inventario import RepuestoPorTarea, RepuestoPorEquipo, Repuesto
    sistemas_procesados = 0
    patron_sistema = re.compile(r'sistema_(\d+)_nombre')
    indices = set()
    for key in form_data.keys():
        match = patron_sistema.match(key)
        if match:
            indices.add(int(match.group(1)))
    
    for idx in sorted(indices):
        nombre = form_data.get(f'sistema_{idx}_nombre')
        if not nombre:
            continue
            
        sistema = SistemaEquipo(
            equipo_id=equipo_id,
            nombre=nombre,
            descripcion=form_data.get(f'sistema_{idx}_descripcion', ''),
            categoria=form_data.get(f'sistema_{idx}_categoria', 'Otro'),
            color=form_data.get(f'sistema_{idx}_color', '#007bff'),
            fecha_creacion=datetime.now().date()
        )
        db.session.add(sistema)
        db.session.flush()
        
        tarea_idx = 0
        while True:
            tarea_key = f'sistema_{idx}_tarea_{tarea_idx}'
            tarea_desc = form_data.get(tarea_key)
            if not tarea_desc:
                break
            
            frecuencia_key = f'sistema_{idx}_tarea_{tarea_idx}_frecuencia'
            frecuencia = form_data.get(frecuencia_key, '30')
            try:
                frecuencia_dias = int(frecuencia)
            except ValueError:
                frecuencia_dias = 30
            
            plan = PlanMantenimiento(
                sistema_id=sistema.id, 
                tarea_descripcion=tarea_desc, 
                frecuencia_dias=frecuencia_dias,
                activo=True
            )
            db.session.add(plan)
            db.session.flush()
            
            repuesto_idx = 0
            while True:
                repuesto_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}'
                repuesto_id = form_data.get(repuesto_key)
                if not repuesto_id:
                    break
                cantidad_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}_cantidad'
                cantidad = int(form_data.get(cantidad_key, 1))
                
                # Crear relación repuesto-tarea
                repuesto_tarea = RepuestoPorTarea(
                    tarea_id=plan.id, 
                    repuesto_id=int(repuesto_id), 
                    cantidad_requerida=cantidad, 
                    es_obligatorio=True
                )
                db.session.add(repuesto_tarea)
                
                # ========== NUEVO: Asociar repuesto al equipo automáticamente ==========
                # Verificar si ya existe la relación en repuestos_por_equipo
                existente = RepuestoPorEquipo.query.filter_by(
                    equipo_id=equipo_id,
                    repuesto_id=int(repuesto_id)
                ).first()
                
                if not existente:
                    nueva_asignacion = RepuestoPorEquipo(
                        equipo_id=equipo_id,
                        repuesto_id=int(repuesto_id),
                        cantidad_por_uso=cantidad,
                        es_critico=True,
                        observaciones=f"Asignado automáticamente desde tarea: {tarea_desc[:50]}"
                    )
                    db.session.add(nueva_asignacion)
                    print(f"🔗 Repuesto {repuesto_id} asociado automáticamente al equipo {equipo_id}")
                else:
                    print(f"ℹ️ Repuesto {repuesto_id} ya estaba asociado al equipo {equipo_id}")
                
                repuesto_idx += 1
            tarea_idx += 1
        sistemas_procesados += 1
    
    return sistemas_procesados


# ========== AGREGAR ESTE ENDPOINT EN routes/equipos.py ==========
@equipos_bp.route('/<int:equipo_id>/asignar-repuesto', methods=['POST'])
@admin_required
def asignar_repuesto(equipo_id):
    """Asigna un repuesto existente a un equipo (desde la página de asignación)"""
    from models.inventario import RepuestoPorEquipo, Repuesto
    
    equipo = Equipo.query.get_or_404(equipo_id)
    
    try:
        repuesto_id = request.form.get('repuesto_id')
        cantidad_por_uso = int(request.form.get('cantidad_por_uso', 1))
        es_critico = request.form.get('es_critico') == 'on'
        observaciones = request.form.get('observaciones', '')
        
        if not repuesto_id:
            flash('Debe seleccionar un repuesto', 'error')
            return redirect(url_for('equipos.asignar_repuestos', equipo_id=equipo.id))
        
        # Verificar si ya está asignado
        existente = RepuestoPorEquipo.query.filter_by(
            equipo_id=equipo_id,
            repuesto_id=int(repuesto_id)
        ).first()
        
        if existente:
            flash('Este repuesto ya está asignado al equipo', 'warning')
            return redirect(url_for('equipos.asignar_repuestos', equipo_id=equipo.id))
        
        # Crear nueva asignación
        asignacion = RepuestoPorEquipo(
            equipo_id=equipo_id,
            repuesto_id=int(repuesto_id),
            cantidad_por_uso=cantidad_por_uso,
            es_critico=es_critico,
            observaciones=observaciones
        )
        db.session.add(asignacion)
        
        # También actualizar el campo equipo_id en Repuesto para mantener consistencia
        repuesto = Repuesto.query.get(repuesto_id)
        if repuesto and not repuesto.equipo_id:
            repuesto.equipo_id = equipo_id
        
        db.session.commit()
        
        flash(f'✅ Repuesto {repuesto.codigo} asignado correctamente al equipo {equipo.code}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al asignar repuesto: {str(e)}', 'error')
    
    return redirect(url_for('equipos.asignar_repuestos', equipo_id=equipo.id))

@equipos_bp.route('/<int:equipo_id>/eliminar-asignacion/<int:asignacion_id>', methods=['POST'])
@admin_required
def eliminar_asignacion_repuesto(equipo_id, asignacion_id):
    try:
        asignacion = RepuestoPorEquipo.query.get_or_404(asignacion_id)
        db.session.delete(asignacion)
        db.session.commit()
        flash('Asignación eliminada', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('equipos.asignar_repuestos', equipo_id=equipo_id))

# ============ NUEVA RUTA PARA IMPRIMIR FICHA ============
@equipos_bp.route('/<int:equipo_id>/imprimir-ficha')
@tecnico_required
def imprimir_ficha(equipo_id):
    """Vista optimizada para impresión de la ficha técnica del equipo"""
    equipo = Equipo.query.get_or_404(equipo_id)
    from datetime import datetime
    return render_template('equipos/ficha_imprimible.html', equipo=equipo, now=datetime.now())

# ============ FUNCIONES AUXILIARES ============

def procesar_sistemas_edicion(form_data, equipo_id):
    """Procesa los sistemas al editar un equipo"""
    from models.inventario import RepuestoPorTarea, RepuestoPorEquipo
    
    # Obtener sistemas existentes en la BD
    sistemas_actuales = {s.id: s for s in SistemaEquipo.query.filter_by(equipo_id=equipo_id).all()}
    sistemas_procesados = set()
    
    # Buscar TODOS los índices de sistemas en el formulario
    patron_sistema = re.compile(r'sistema_(\d+)_nombre')
    indices = set()
    for key in form_data.keys():
        match = patron_sistema.match(key)
        if match:
            indices.add(int(match.group(1)))
    
    print(f"Procesando {len(indices)} sistemas desde el formulario")
    
    for idx in indices:
        nombre = form_data.get(f'sistema_{idx}_nombre')
        if not nombre:
            continue
        
        sistema_id = form_data.get(f'sistema_{idx}_id')
        descripcion = form_data.get(f'sistema_{idx}_descripcion', '')
        es_nuevo = form_data.get(f'sistema_{idx}_nuevo')
        
        if es_nuevo or not sistema_id:
            sistema = SistemaEquipo(
                equipo_id=equipo_id,
                nombre=nombre,
                descripcion=descripcion,
                categoria='Otro',
                fecha_creacion=datetime.now().date()
            )
            db.session.add(sistema)
            db.session.flush()
            print(f"Sistema NUEVO creado con ID: {sistema.id}")
        else:
            sistema = sistemas_actuales.get(int(sistema_id))
            if sistema:
                sistema.nombre = nombre
                sistema.descripcion = descripcion
                sistemas_procesados.add(int(sistema_id))
                print(f"Sistema EXISTENTE actualizado: ID {sistema.id}")
                PlanMantenimiento.query.filter_by(sistema_id=sistema.id).delete()
            else:
                print(f"⚠️ ADVERTENCIA: Sistema ID {sistema_id} no encontrado")
                continue
        
        # Procesar tareas del sistema
        tarea_idx = 0
        tareas_agregadas = 0
        while True:
            tarea_key = f'sistema_{idx}_tarea_{tarea_idx}'
            tarea_desc = form_data.get(tarea_key)
            if not tarea_desc:
                break
            
            frecuencia_key = f'sistema_{idx}_tarea_{tarea_idx}_frecuencia'
            frecuencia = form_data.get(frecuencia_key, '30')
            try:
                frecuencia_dias = int(frecuencia)
            except ValueError:
                frecuencia_dias = 30
            
            plan = PlanMantenimiento(
                sistema_id=sistema.id,
                tarea_descripcion=tarea_desc,
                frecuencia_dias=frecuencia_dias,
                activo=True
            )
            db.session.add(plan)
            db.session.flush()
            
            # Procesar repuestos de la tarea
            repuesto_idx = 0
            while True:
                repuesto_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}'
                repuesto_id = form_data.get(repuesto_key)
                if not repuesto_id:
                    break
                cantidad_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}_cantidad'
                cantidad = int(form_data.get(cantidad_key, 1))
                
                # 1. Crear relación repuesto-tarea
                repuesto_tarea = RepuestoPorTarea(
                    tarea_id=plan.id,
                    repuesto_id=int(repuesto_id),
                    cantidad_requerida=cantidad,
                    es_obligatorio=True
                )
                db.session.add(repuesto_tarea)
                
                # 2. 🔧 NUEVO: Asociar repuesto al equipo en repuestos_por_equipo
                existente = RepuestoPorEquipo.query.filter_by(
                    equipo_id=equipo_id,
                    repuesto_id=int(repuesto_id)
                ).first()
                
                if not existente:
                    nueva_asignacion = RepuestoPorEquipo(
                        equipo_id=equipo_id,
                        repuesto_id=int(repuesto_id),
                        cantidad_por_uso=cantidad,
                        es_critico=True,
                        observaciones=f"Asignado desde tarea: {tarea_desc[:50]}"
                    )
                    db.session.add(nueva_asignacion)
                    print(f"🔗 Repuesto {repuesto_id} asociado al equipo {equipo_id}")
                
                repuesto_idx += 1
            tarea_idx += 1
            tareas_agregadas += 1
        
        print(f"  → {tareas_agregadas} tareas agregadas al sistema {sistema.nombre}")
    
    # Eliminar sistemas que ya no existen
    for sistema_id, sistema in sistemas_actuales.items():
        if sistema_id not in sistemas_procesados:
            print(f"🗑️ Eliminando sistema: {sistema.nombre} (ID: {sistema_id})")
            db.session.delete(sistema)

def procesar_sistemas_del_formulario(form_data, equipo_id):
    """Procesa los sistemas enviados en el formulario"""
    sistemas_procesados = 0
    patron_sistema = re.compile(r'sistema_(\d+)_nombre')
    indices = set()
    for key in form_data.keys():
        match = patron_sistema.match(key)
        if match:
            indices.add(int(match.group(1)))
    
    for idx in sorted(indices):
        nombre = form_data.get(f'sistema_{idx}_nombre')
        if not nombre:
            continue
            
        sistema = SistemaEquipo(
            equipo_id=equipo_id,
            nombre=nombre,
            descripcion=form_data.get(f'sistema_{idx}_descripcion', ''),
            categoria=form_data.get(f'sistema_{idx}_categoria', 'Otro'),
            color=form_data.get(f'sistema_{idx}_color', '#007bff'),
            fecha_creacion=datetime.now().date()
        )
        db.session.add(sistema)
        db.session.flush()
        
        tarea_idx = 0
        while True:
            tarea_key = f'sistema_{idx}_tarea_{tarea_idx}'
            tarea_desc = form_data.get(tarea_key)
            if not tarea_desc:
                break
            
            # 🔧 CORREGIDO: Leer la frecuencia del formulario
            frecuencia_key = f'sistema_{idx}_tarea_{tarea_idx}_frecuencia'
            frecuencia = form_data.get(frecuencia_key, '30')  # Valor por defecto 30 si no viene
            try:
                frecuencia_dias = int(frecuencia)
            except ValueError:
                frecuencia_dias = 30
            
            plan = PlanMantenimiento(
                sistema_id=sistema.id, 
                tarea_descripcion=tarea_desc, 
                frecuencia_dias=frecuencia_dias,  # ✅ Ahora usa el valor correcto
                activo=True
            )
            db.session.add(plan)
            db.session.flush()
            
            repuesto_idx = 0
            while True:
                repuesto_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}'
                repuesto_id = form_data.get(repuesto_key)
                if not repuesto_id:
                    break
                cantidad_key = f'sistema_{idx}_tarea_{tarea_idx}_repuesto_{repuesto_idx}_cantidad'
                cantidad = int(form_data.get(cantidad_key, 1))
                from models.inventario import RepuestoPorTarea
                repuesto_tarea = RepuestoPorTarea(
                    tarea_id=plan.id, 
                    repuesto_id=int(repuesto_id), 
                    cantidad_requerida=cantidad, 
                    es_obligatorio=True
                )
                db.session.add(repuesto_tarea)
                repuesto_idx += 1
            tarea_idx += 1
        sistemas_procesados += 1
    
    return sistemas_procesados

@equipos_bp.route('/api/repuestos/disponibles')
@tecnico_required
def get_repuestos_disponibles():
    repuestos = Repuesto.query.all()
    return jsonify([{
        'id': r.id,
        'codigo': r.codigo,
        'nombre': r.nombre,
        'stock': r.stock_actual,
        'categoria': r.categoria
    } for r in repuestos])