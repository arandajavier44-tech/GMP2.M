# routes/ordenes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from models import db
from models.orden_trabajo import OrdenTrabajo
from models.equipo import Equipo
from models.sistema import SistemaEquipo, PlanMantenimiento
from models.inventario import Repuesto, ConsumoRepuesto, MovimientoStock, RepuestoPorTarea
from models.usuario import Usuario
from datetime import datetime
import random
import string
import os
import qrcode
from utils.decorators import tecnico_required, admin_required
from utils.qr_generator import QRPersonalizado, QRColorManager
from utils.helpers import get_tecnicos_disponibles

ordenes_bp = Blueprint('ordenes', __name__)


def generar_numero_ot_con_correlativo(equipo_id, tipo):
    """Genera número OT con correlativo por equipo"""
    equipo = Equipo.query.get(equipo_id)
    if not equipo:
        return None, None
    
    ultima_orden = OrdenTrabajo.query.filter_by(equipo_id=equipo_id)\
        .order_by(OrdenTrabajo.numero_correlativo.desc()).first()
    
    if ultima_orden and ultima_orden.numero_correlativo:
        nuevo_correlativo = ultima_orden.numero_correlativo + 1
    else:
        nuevo_correlativo = 1
    
    anio = datetime.now().strftime('%Y')
    numero_ot = f"OT-{nuevo_correlativo:04d}-{anio}-{equipo.code}"
    
    return numero_ot, nuevo_correlativo


@ordenes_bp.route('/')
@tecnico_required
def gestion_ordenes():
    ordenes = OrdenTrabajo.query.filter(
        OrdenTrabajo.estado != 'Completada'
    ).order_by(OrdenTrabajo.fecha_creacion.desc()).all()
    return render_template('ordenes/gestion_ordenes.html', ordenes=ordenes)


@ordenes_bp.route('/nueva', methods=['GET'])
@tecnico_required
def nueva_orden():
    equipos = Equipo.query.all()
    return render_template('ordenes/seleccionar_tipo.html', equipos=equipos)


@ordenes_bp.route('/nueva/preventiva/<int:equipo_id>', methods=['GET', 'POST'])
@tecnico_required
def nueva_orden_preventiva(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    if request.method == 'POST':
        try:
            numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo_id, 'Preventivo')
            
            tareas_seleccionadas = []
            total_tareas = int(request.form.get('total_tareas', 0))
            
            for i in range(total_tareas):
                tarea_id = request.form.get(f'tarea_{i}_id')
                sistema_id = request.form.get(f'tarea_{i}_sistema')
                descripcion = request.form.get(f'tarea_{i}_descripcion')
                
                if tarea_id and descripcion:
                    tareas_seleccionadas.append({
                        'id': tarea_id,
                        'sistema_id': sistema_id,
                        'descripcion': descripcion
                    })
            
            nueva_orden = OrdenTrabajo(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                codigo_equipo=equipo.code,
                equipo_id=equipo_id,
                tipo='Preventivo',
                titulo=request.form.get('titulo', f"Mantenimiento Preventivo - {equipo.code}"),
                descripcion=request.form.get('descripcion', ''),
                tareas_seleccionadas=tareas_seleccionadas,
                estado='Pendiente',
                prioridad=request.form.get('prioridad', 'Media'),
                fecha_estimada=datetime.strptime(request.form.get('fecha_estimada'), '%Y-%m-%d').date() if request.form.get('fecha_estimada') else None,
                asignado_a=request.form.get('asignado_a'),
                creado_por=session.get('username', 'Sistema'),
                tiempo_estimado=float(request.form.get('tiempo_estimado')) if request.form.get('tiempo_estimado') else None,
                observaciones=request.form.get('observaciones')
            )
            
            db.session.add(nueva_orden)
            db.session.commit()
            
            generar_qr_orden(nueva_orden)
            
            flash(f'Orden preventiva {numero_ot} creada exitosamente', 'success')
            return redirect(url_for('ordenes.detalle_orden', orden_id=nueva_orden.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la orden: {str(e)}', 'error')
            print(f"Error: {e}")
    
    now = datetime.now()
    return render_template('ordenes/nueva_preventiva.html', equipo=equipo, now=now)


@ordenes_bp.route('/nueva/correctiva/<int:equipo_id>', methods=['GET', 'POST'])
@tecnico_required
def nueva_orden_correctiva(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    if request.method == 'POST':
        try:
            numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo_id, 'Correctivo')
            
            nueva_orden = OrdenTrabajo(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                codigo_equipo=equipo.code,
                equipo_id=equipo_id,
                tipo='Correctivo',
                titulo=request.form.get('titulo', 'Correctivo - Falla reportada'),
                falla_reportada=request.form.get('falla_reportada'),
                sintomas=request.form.get('sintomas'),
                causa_probable=request.form.get('causa_probable'),
                estado='Pendiente',
                prioridad=request.form.get('prioridad', 'Media'),
                fecha_estimada=datetime.strptime(request.form.get('fecha_estimada'), '%Y-%m-%d').date() if request.form.get('fecha_estimada') else None,
                asignado_a=request.form.get('asignado_a'),
                creado_por=session.get('username', 'Sistema'),
                tiempo_estimado=float(request.form.get('tiempo_estimado')) if request.form.get('tiempo_estimado') else None,
                observaciones=request.form.get('observaciones')
            )
            
            db.session.add(nueva_orden)
            db.session.commit()
            
            generar_qr_orden(nueva_orden)
            
            flash(f'Orden correctiva {numero_ot} creada exitosamente', 'success')
            return redirect(url_for('ordenes.detalle_orden', orden_id=nueva_orden.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la orden: {str(e)}', 'error')
    
    now = datetime.now()
    return render_template('ordenes/nueva_correctiva.html', equipo=equipo, now=now)


@ordenes_bp.route('/nueva/servicio/<int:equipo_id>', methods=['GET', 'POST'])
@tecnico_required
def nueva_orden_servicio(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    if request.method == 'POST':
        try:
            numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo_id, 'Servicio')
            
            nueva_orden = OrdenTrabajo(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                codigo_equipo=equipo.code,
                equipo_id=equipo_id,
                tipo='Servicio',
                titulo=request.form.get('titulo', 'Solicitud de servicio'),
                solicitante=request.form.get('solicitante'),
                sector=request.form.get('sector'),
                descripcion=request.form.get('descripcion'),
                estado='Pendiente',
                prioridad=request.form.get('prioridad', 'Media'),
                fecha_estimada=datetime.strptime(request.form.get('fecha_estimada'), '%Y-%m-%d').date() if request.form.get('fecha_estimada') else None,
                asignado_a=request.form.get('asignado_a'),
                creado_por=session.get('username', 'Sistema'),
                tiempo_estimado=float(request.form.get('tiempo_estimado')) if request.form.get('tiempo_estimado') else None,
                observaciones=request.form.get('observaciones')
            )
            
            db.session.add(nueva_orden)
            db.session.commit()
            
            generar_qr_orden(nueva_orden)
            
            flash(f'Solicitud de servicio {numero_ot} creada exitosamente', 'success')
            return redirect(url_for('ordenes.detalle_orden', orden_id=nueva_orden.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la solicitud: {str(e)}', 'error')
    
    now = datetime.now()
    return render_template('ordenes/nueva_servicio.html', equipo=equipo, now=now)


# En routes/ordenes.py
from utils.helpers import get_tecnicos_disponibles

@ordenes_bp.route('/<int:orden_id>')
@tecnico_required
def detalle_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    usuarios_mantenimiento = get_tecnicos_disponibles('mantenimiento')
    return render_template('ordenes/detalle_orden.html', 
                         orden=orden,
                         usuarios_mantenimiento=usuarios_mantenimiento)

@ordenes_bp.route('/<int:orden_id>/aprobar', methods=['POST'])
@admin_required
def aprobar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        orden.estado = 'Aprobada'
        orden.aprobado_por = session.get('username')
        orden.fecha_aprobacion = datetime.utcnow()
        db.session.commit()
        flash('Orden aprobada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al aprobar: {str(e)}', 'error')
    
    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/<int:orden_id>/iniciar', methods=['POST'])
@tecnico_required
def iniciar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        if orden.estado not in ['Pendiente', 'Aprobada']:
            flash(f'No se puede iniciar una orden en estado {orden.estado}', 'error')
            return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
        
        if orden.fecha_creacion:
            delta = datetime.utcnow() - orden.fecha_creacion
            orden.tiempo_respuesta = int(delta.total_seconds() / 60)
        
        orden.estado = 'En Progreso'
        orden.fecha_inicio = datetime.utcnow()
        
        asignado_a = request.form.get('asignado_a')
        if asignado_a:
            orden.asignado_a = asignado_a
            flash(f'Orden asignada a {asignado_a}', 'success')
        
        if orden.equipo and orden.equipo.current_status == 'Operativo':
            orden.equipo.current_status = 'En Mantenimiento'
        
        db.session.commit()
        
        from utils.qr_system import QRTrazabilidad
        try:
            QRTrazabilidad.generar_qr(orden, 'orden')
            flash('Orden iniciada y QR actualizado correctamente', 'success')
        except Exception as qr_error:
            print(f"Error actualizando QR: {qr_error}")
            flash('Orden iniciada, pero hubo un error actualizando el QR', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al iniciar: {str(e)}', 'error')
    
    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/<int:orden_id>/completar', methods=['POST'])
@tecnico_required
def completar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        if orden.estado != 'En Progreso':
            flash(f'Solo se pueden completar órdenes en estado "En Progreso". Estado actual: {orden.estado}', 'error')
            return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
        
        # Calcular tiempo de parada
        if orden.fecha_inicio:
            delta = datetime.utcnow() - orden.fecha_inicio
            orden.tiempo_parada = int(delta.total_seconds() / 60)
        
        orden.estado = 'Completada'
        orden.fecha_fin = datetime.utcnow()
        orden.fecha_cierre = datetime.utcnow()
        
        orden.resultado = request.form.get('resultado')
        orden.observaciones = request.form.get('observaciones')
        orden.recomendaciones = request.form.get('recomendaciones')
        orden.diagnostico_final = request.form.get('diagnostico')
        orden.solucion_aplicada = request.form.get('solucion_aplicada')
        orden.trabajo_futuro = request.form.get('trabajo_futuro')
        
        fecha_prox_mant_str = request.form.get('fecha_prox_mant')
        if fecha_prox_mant_str and fecha_prox_mant_str.strip():
            try:
                orden.fecha_prox_mantenimiento = datetime.strptime(fecha_prox_mant_str, '%Y-%m-%d').date()
            except ValueError:
                orden.fecha_prox_mantenimiento = None
        else:
            orden.fecha_prox_mantenimiento = None
        
        tiempo_real = request.form.get('tiempo_real')
        if tiempo_real:
            try:
                orden.tiempo_real = float(tiempo_real)
            except ValueError:
                orden.tiempo_real = None
        
        # ==================== ACTUALIZAR TAREAS PREVENTIVAS ====================
        if orden.tipo == 'Preventivo' and orden.tareas_seleccionadas:
            tareas_actualizadas = []
            for idx, tarea in enumerate(orden.tareas_seleccionadas):
                tarea_actualizada = tarea.copy()
                completada = request.form.get(f'tarea_completada_{idx}') == 'on'
                tarea_actualizada['completada'] = completada
                tarea_actualizada['observaciones_ejecucion'] = request.form.get(f'tarea_obs_{idx}', '')
                tarea_actualizada['fecha_ejecucion'] = orden.fecha_cierre.strftime('%Y-%m-%d')
                tareas_actualizadas.append(tarea_actualizada)
                
                # Recalcular próxima fecha del plan de mantenimiento
                plan_id = tarea.get('id')
                if plan_id and completada:
                    plan = PlanMantenimiento.query.get(plan_id)
                    if plan:
                        plan.ultima_ejecucion = orden.fecha_cierre.date()
                        plan.calcular_proxima_ejecucion()
                        plan.orden_generada = False  # Permitir generar nueva orden
                        print(f"✅ Plan actualizado: {plan.tarea_descripcion[:50]} - Próxima: {plan.proxima_ejecucion}")
            
            orden.tareas_seleccionadas = tareas_actualizadas
        
        # ==================== PROCESAR REPUESTOS CRÍTICOS POR TAREA ====================
        repuestos_utilizados = []
        alertas_generadas = []
        
        if orden.tipo == 'Preventivo' and orden.tareas_seleccionadas:
            for tarea in orden.tareas_seleccionadas:
                tarea_id = tarea.get('id')
                if tarea_id:
                    # Buscar todos los campos de acción para esta tarea
                    prefix_accion = f'repuesto_accion_{tarea_id}_'
                    for key in request.form.keys():
                        if key.startswith(prefix_accion):
                            repuesto_id = key.replace(prefix_accion, '')
                            accion = request.form.get(key)
                            observacion = request.form.get(f'repuesto_obs_{tarea_id}_{repuesto_id}', '')
                            
                            # Obtener la cantidad requerida
                            rpt = RepuestoPorTarea.query.filter_by(tarea_id=tarea_id, repuesto_id=int(repuesto_id)).first()
                            cantidad_requerida = rpt.cantidad_requerida if rpt else 1
                            
                            repuesto = Repuesto.query.get(int(repuesto_id))
                            if not repuesto:
                                continue
                            
                            # Procesar según la acción
                            if accion == 'reemplazado':
                                if repuesto.stock_actual < cantidad_requerida:
                                    flash(f'Stock insuficiente para {repuesto.codigo}. Disponible: {repuesto.stock_actual}', 'error')
                                    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
                                
                                stock_anterior = repuesto.stock_actual
                                repuesto.stock_actual -= cantidad_requerida
                                
                                consumo = ConsumoRepuesto(
                                    repuesto_id=repuesto.id,
                                    orden_trabajo_id=orden.id,
                                    cantidad=cantidad_requerida,
                                    lote=request.form.get(f'repuesto_lote_{tarea_id}_{repuesto_id}', ''),
                                    registrado_por=session.get('username', 'Sistema'),
                                    tipo_accion='reemplazo',
                                    observaciones=observacion or f"Reemplazado en mantenimiento preventivo - Tarea: {tarea.get('descripcion', 'N/A')}"
                                )
                                db.session.add(consumo)
                                
                                movimiento = MovimientoStock(
                                    repuesto_id=repuesto.id,
                                    tipo='salida',
                                    cantidad=cantidad_requerida,
                                    stock_anterior=stock_anterior,
                                    stock_nuevo=repuesto.stock_actual,
                                    referencia=f"OT {orden.numero_ot} - Reemplazo",
                                    realizado_por=session.get('username', 'Sistema')
                                )
                                db.session.add(movimiento)
                                
                                repuestos_utilizados.append({
                                    'codigo': repuesto.codigo,
                                    'nombre': repuesto.nombre,
                                    'cantidad': cantidad_requerida,
                                    'accion': 'reemplazo'
                                })
                                
                                print(f"📦 Repuesto reemplazado: {repuesto.codigo} - Stock: {stock_anterior} → {repuesto.stock_actual}")
                                
                            elif accion == 'inspeccionado':
                                consumo = ConsumoRepuesto(
                                    repuesto_id=repuesto.id,
                                    orden_trabajo_id=orden.id,
                                    cantidad=0,
                                    registrado_por=session.get('username', 'Sistema'),
                                    tipo_accion='inspeccion',
                                    observaciones=observacion or f"Inspeccionado - OK. Tarea: {tarea.get('descripcion', 'N/A')}"
                                )
                                db.session.add(consumo)
                                print(f"🔍 Repuesto inspeccionado: {repuesto.codigo} - OK")
                                
                            elif accion == 'atencion':
                                consumo = ConsumoRepuesto(
                                    repuesto_id=repuesto.id,
                                    orden_trabajo_id=orden.id,
                                    cantidad=0,
                                    registrado_por=session.get('username', 'Sistema'),
                                    tipo_accion='alerta',
                                    observaciones=observacion or f"Requiere atención - Programar cambio. Tarea: {tarea.get('descripcion', 'N/A')}"
                                )
                                db.session.add(consumo)
                                alertas_generadas.append({
                                    'repuesto': repuesto.codigo,
                                    'tarea': tarea.get('descripcion', 'N/A'),
                                    'observacion': observacion
                                })
                                print(f"⚠️ Alerta generada para: {repuesto.codigo}")
                                
                            elif accion == 'no_aplica':
                                consumo = ConsumoRepuesto(
                                    repuesto_id=repuesto.id,
                                    orden_trabajo_id=orden.id,
                                    cantidad=0,
                                    registrado_por=session.get('username', 'Sistema'),
                                    tipo_accion='no_aplica',
                                    observaciones=observacion or f"No aplicó inspección. Tarea: {tarea.get('descripcion', 'N/A')}"
                                )
                                db.session.add(consumo)
                                print(f"⏭️ Repuesto no aplica: {repuesto.codigo}")

        import json
        orden.repuestos_utilizados = json.dumps(repuestos_utilizados) if repuestos_utilizados else None  


        
              # ==================== PROCESAR OTROS REPUESTOS (Manuales) ====================
        repuestos_utilizados = []
        i = 0
        while True:
            codigo = request.form.get(f'repuesto_codigo_{i}')
            if not codigo or not codigo.strip():
                i += 1
                if i > 50:
                    break
                continue
            
            cantidad_str = request.form.get(f'repuesto_cant_{i}', '1')
            try:
                cantidad = int(cantidad_str) if cantidad_str else 1
            except:
                cantidad = 1
            
            if cantidad <= 0:
                i += 1
                continue
            
            descripcion = request.form.get(f'repuesto_desc_{i}', '')
            lote = request.form.get(f'repuesto_lote_{i}', '')
            
            repuesto = Repuesto.query.filter_by(codigo=codigo).first()
            if not repuesto:
                flash(f'Repuesto con código {codigo} no encontrado en el sistema', 'warning')
                i += 1
                continue
            
            if repuesto.stock_actual < cantidad:
                flash(f'Stock insuficiente para {repuesto.codigo}. Disponible: {repuesto.stock_actual}', 'error')
                return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
            
            stock_anterior = repuesto.stock_actual
            repuesto.stock_actual -= cantidad
            
            consumo = ConsumoRepuesto(
                repuesto_id=repuesto.id,
                orden_trabajo_id=orden.id,
                cantidad=cantidad,
                lote=lote if lote else None,
                registrado_por=session.get('username', 'Sistema'),
                tipo_accion='manual',
                observaciones=descripcion or f"Consumo manual en OT {orden.numero_ot}"
            )
            db.session.add(consumo)
            
            movimiento = MovimientoStock(
                repuesto_id=repuesto.id,
                tipo='salida',
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=repuesto.stock_actual,
                referencia=f"OT {orden.numero_ot} - Manual",
                realizado_por=session.get('username', 'Sistema')
            )
            db.session.add(movimiento)
            
            repuestos_utilizados.append({
                'codigo': codigo,
                'nombre': repuesto.nombre,
                'cantidad': cantidad,
                'accion': 'manual'
            })
            
            print(f"📦 Stock manual actualizado: {repuesto.codigo} - {stock_anterior} → {repuesto.stock_actual}")
            
            i += 1
        
        # ⭐ CONVERTIR A JSON STRING ANTES DE GUARDAR ⭐
        import json
        orden.repuestos_utilizados = json.dumps(repuestos_utilizados) if repuestos_utilizados else None
        
        # ==================== FIRMAS ====================
        orden.firma_tecnico = request.form.get('firma_tecnico', session.get('username'))
        orden.fecha_firma_tecnico = datetime.utcnow()
        
        if request.form.get('firma_supervisor'):
            orden.firma_supervisor = request.form.get('firma_supervisor')
            orden.fecha_firma_supervisor = datetime.utcnow()
        
        if request.form.get('firma_calidad'):
            orden.firma_calidad = request.form.get('firma_calidad')
            orden.fecha_firma_calidad = datetime.utcnow()
        
        orden.matricula_tecnico = request.form.get('matricula')
        
        # ==================== CAPA ====================
        if request.form.get('requiere_capa') == 'on':
            orden.requiere_capa = True
            orden.motivo_capa = request.form.get('motivo_capa')
            orden.accion_inmediata_capa = request.form.get('accion_inmediata')
            orden.impacto_calidad_capa = request.form.get('impacto_calidad')
        else:
            orden.requiere_capa = False
            orden.motivo_capa = None
            orden.accion_inmediata_capa = None
            orden.impacto_calidad_capa = None
        
        # Actualizar estado del equipo
        if orden.equipo:
            orden.equipo.current_status = 'Operativo'
        
        db.session.commit()
        
        # ==================== GENERAR QR ACTUALIZADO ====================
        try:
            from utils.qr_system import QRTrazabilidad
            QRTrazabilidad.generar_qr(orden, 'orden')
        except Exception as qr_error:
            print(f"Error actualizando QR: {qr_error}")
        
        mensaje = f'Orden completada exitosamente. '
        if repuestos_utilizados:
            mensaje += f'Se utilizaron {len(repuestos_utilizados)} repuestos. '
        if alertas_generadas:
            mensaje += f'Se generaron {len(alertas_generadas)} alertas por repuestos que requieren atención.'
        flash(mensaje, 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al completar: {str(e)}', 'error')
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/<int:orden_id>/cancelar', methods=['POST'])
@tecnico_required
def cancelar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        orden.estado = 'Cancelada'
        orden.observaciones = request.form.get('motivo', 'Cancelada por el usuario')
        db.session.commit()
        
        from utils.qr_system import QRTrazabilidad
        try:
            QRTrazabilidad.generar_qr(orden, 'orden')
            flash('Orden cancelada y QR actualizado correctamente', 'success')
        except Exception as qr_error:
            print(f"Error actualizando QR: {qr_error}")
            flash('Orden cancelada, pero hubo error actualizando el QR', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cancelar: {str(e)}', 'error')
    
    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/<int:orden_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        if orden.estado in ['En Progreso', 'Completada']:
            flash('No se puede eliminar una orden en progreso o completada', 'error')
            return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
        
        db.session.delete(orden)
        db.session.commit()
        flash(f'Orden {orden.numero_ot} eliminada correctamente', 'success')
        return redirect(url_for('ordenes.gestion_ordenes'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la orden: {str(e)}', 'error')
        return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/<int:orden_id>/generar_qr', methods=['POST'])
@tecnico_required
def generar_qr_orden_route(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        generar_qr_orden(orden)
        flash('Código QR generado correctamente', 'success')
    except Exception as e:
        flash(f'Error al generar QR: {str(e)}', 'error')
    
    return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))


@ordenes_bp.route('/api/equipo/<int:equipo_id>/sistemas')
@tecnico_required
def get_sistemas_con_tareas(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    sistemas_data = []
    for sistema in equipo.sistemas:
        tareas = []
        for plan in sistema.planes_pm:
            if plan.activo:
                tareas.append({
                    'id': plan.id,
                    'descripcion': plan.tarea_descripcion,
                    'frecuencia_dias': plan.frecuencia_dias,
                    'ultima_ejecucion': plan.ultima_ejecucion.strftime('%d/%m/%Y') if plan.ultima_ejecucion else None
                })
        
        sistemas_data.append({
            'id': sistema.id,
            'nombre': sistema.nombre,
            'categoria': sistema.categoria,
            'tareas': tareas
        })
    
    return jsonify(sistemas_data)


def generar_qr_orden(orden):
    try:
        colores = QRColorManager.get_colores(
            orden.tipo.lower(),
            orden.prioridad if orden.prioridad == 'Crítica' else None
        )
        
        estilo = 'rounded'
        if orden.tipo == 'Correctivo':
            estilo = 'circle'
        elif orden.tipo == 'Servicio':
            estilo = 'gapped'
        
        resultado = QRPersonalizado.generar_qr_orden(
            orden,
            estilo=estilo,
            colores=colores,
            incluir_logo=True
        )
        
        if resultado:
            db.session.commit()
            print(f"✅ QR generado para orden {orden.numero_ot}")
        else:
            generar_qr_orden_simple(orden)
        
    except Exception as e:
        print(f"❌ Error generando QR personalizado: {e}")
        generar_qr_orden_simple(orden)


def generar_qr_orden_simple(orden):
    try:
        import qrcode
        import os
        from flask import current_app
        
        qr_dir = os.path.join(current_app.static_folder, 'qrcodes')
        os.makedirs(qr_dir, exist_ok=True)
        
        url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/ordenes/{orden.id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        filename = f"ot_{orden.id}.png"
        filepath = os.path.join(qr_dir, filename)
        img.save(filepath)
        
        orden.qr_code = f"qrcodes/{filename}"
        db.session.commit()
        print(f"✅ QR simple generado para orden {orden.numero_ot}")
        
    except Exception as e:
        print(f"❌ Error generando QR simple: {e}")


@ordenes_bp.route('/<int:orden_id>/regenerar_qr', methods=['POST'])
@tecnico_required
def regenerar_qr_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    try:
        from utils.qr_system import QRTrazabilidad
        resultado = QRTrazabilidad.generar_qr(orden, 'orden')
        
        if resultado:
            return jsonify({'success': True, 'message': 'QR regenerado correctamente'})
        else:
            return jsonify({'success': False, 'message': 'Error al regenerar QR'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@ordenes_bp.route('/<int:orden_id>/cerrar')
@tecnico_required
def cerrar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    
    if orden.estado != 'En Progreso':
        flash('Solo se pueden cerrar órdenes en estado "En Progreso"', 'warning')
        return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
    
    return render_template('ordenes/cerrar_orden.html', orden=orden)


@ordenes_bp.route('/cerradas')
@tecnico_required
def ordenes_cerradas():
    ordenes = OrdenTrabajo.query.filter_by(estado='Completada').order_by(OrdenTrabajo.fecha_cierre.desc()).all()
    return render_template('ordenes/ordenes_cerradas.html', ordenes=ordenes)


@ordenes_bp.route('/cerrada/<int:orden_id>')
@tecnico_required
def detalle_orden_cerrada(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    if orden.estado != 'Completada':
        flash('Esta orden no está cerrada', 'warning')
        return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
    return render_template('ordenes/detalle_orden_cerrada.html', orden=orden)


@ordenes_bp.route('/<int:orden_id>/completar-form')
@tecnico_required
def formulario_completar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    if orden.estado != 'En Progreso':
        flash('Solo se pueden cerrar órdenes en estado "En Progreso"', 'warning')
        return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
    
    from models.usuario import Usuario
    from models.inventario import RepuestoPorTarea, Repuesto
    
    usuarios_mantenimiento = Usuario.query.all()
    repuestos = Repuesto.query.all()
    
    repuestos_por_tarea = {}
    if orden.tipo == 'Preventivo' and orden.tareas_seleccionadas:
        for tarea in orden.tareas_seleccionadas:
            tarea_id = tarea.get('id')
            if tarea_id:
                # PRIMERO: Intentar obtener repuestos del JSON de la tarea
                if tarea.get('repuestos'):
                    repuestos_por_tarea[str(tarea_id)] = tarea.get('repuestos')
                    print(f"✅ Repuestos desde JSON para tarea {tarea_id}: {len(tarea.get('repuestos'))}")
                else:
                    # Si no, buscarlos en la BD
                    repuestos_criticos = RepuestoPorTarea.query.filter_by(tarea_id=tarea_id).all()
                    repuestos_data = []
                    for rpt in repuestos_criticos:
                        repuestos_data.append({
                            'repuesto_id': rpt.repuesto_id,
                            'codigo': rpt.repuesto.codigo,
                            'nombre': rpt.repuesto.nombre,
                            'cantidad_requerida': rpt.cantidad_requerida,
                            'stock_actual': rpt.repuesto.stock_actual,
                            'stock_minimo': rpt.repuesto.stock_minimo
                        })
                    repuestos_por_tarea[str(tarea_id)] = repuestos_data
                    print(f"✅ Repuestos desde BD para tarea {tarea_id}: {len(repuestos_data)}")
    
    return render_template('ordenes/cerrar_orden.html', 
                         orden=orden, 
                         usuarios_mantenimiento=usuarios_mantenimiento,
                         repuestos=repuestos,
                         repuestos_por_tarea=repuestos_por_tarea)

@ordenes_bp.route('/cerrada/<int:orden_id>/print')
@tecnico_required
def print_orden_cerrada(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    if orden.estado != 'Completada':
        flash('Esta orden no está cerrada', 'warning')
        return redirect(url_for('ordenes.detalle_orden', orden_id=orden.id))
    from datetime import datetime
    return render_template('ordenes/print_orden_cerrada.html', orden=orden, now=datetime.now())


@ordenes_bp.route('/<int:orden_id>/print-activa')
@tecnico_required
def print_orden_activa(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    from datetime import datetime
    return render_template('ordenes/print_orden_activa.html', orden=orden, now=datetime.now())


@ordenes_bp.route('/eliminar-todas', methods=['POST'])
@admin_required
def eliminar_todas_ordenes():
    try:
        total = OrdenTrabajo.query.count()
        
        for orden in OrdenTrabajo.query.all():
            if orden.qr_code:
                ruta_qr = os.path.join(current_app.static_folder, orden.qr_code)
                if os.path.exists(ruta_qr):
                    os.remove(ruta_qr)
        
        OrdenTrabajo.query.delete()
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Se eliminaron {total} órdenes'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@ordenes_bp.route('/trazabilidad/equipo/<int:equipo_id>')
@tecnico_required
def trazabilidad_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    
    ordenes = OrdenTrabajo.query.filter_by(equipo_id=equipo_id)\
        .order_by(OrdenTrabajo.fecha_creacion.desc()).all()
    
    total_ordenes = len(ordenes)
    ordenes_completadas = len([o for o in ordenes if o.estado == 'Completada'])
    
    tiempos = []
    for o in ordenes:
        if o.fecha_inicio and o.fecha_creacion:
            delta = (o.fecha_inicio - o.fecha_creacion).total_seconds() / 3600
            tiempos.append(delta)
    tiempo_promedio_respuesta = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0
    
    mtbf = round((sum([o.tiempo_real or 0 for o in ordenes]) / len(ordenes)) if ordenes else 0, 1)
    
    return render_template('ordenes/trazabilidad_equipo.html',
                         equipo=equipo,
                         ordenes=ordenes,
                         total_ordenes=total_ordenes,
                         ordenes_completadas=ordenes_completadas,
                         tiempo_promedio_respuesta=tiempo_promedio_respuesta,
                         mtbf=mtbf)