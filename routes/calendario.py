# routes/calendario.py
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_required
from models import db
from models.sistema import PlanMantenimiento, SistemaEquipo
from models.equipo import Equipo
from models.orden_trabajo import OrdenTrabajo
from models.inventario import RepuestoPorTarea, Repuesto
from utils.decorators import tecnico_required, admin_required

calendario_bp = Blueprint('calendario', __name__)


@calendario_bp.route('/')
@tecnico_required
def index():
    return redirect(url_for('calendario.panel'))


@calendario_bp.route('/panel')
@tecnico_required
def panel():
    return render_template('calendario/panel_preventivos.html')


@calendario_bp.route('/api/eventos')
@tecnico_required
def api_eventos():
    """API para obtener eventos del calendario"""
    try:
        planes = PlanMantenimiento.query.filter_by(activo=True).all()
        eventos = []
        
        for plan in planes:
            if not plan.sistema or not plan.sistema.equipo:
                continue
            
            equipo = plan.sistema.equipo
            
            if not plan.proxima_ejecucion:
                plan.calcular_proxima_ejecucion()
                db.session.commit()
            
            hoy = date.today()
            dias_restantes = (plan.proxima_ejecucion - hoy).days
            
            if dias_restantes < 0:
                color = '#dc3545'
                textColor = '#fff'
            elif dias_restantes <= 7:
                color = '#ffc107'
                textColor = '#000'
            else:
                color = '#28a745'
                textColor = '#fff'
            
            eventos.append({
                'id': f'plan_{plan.id}',
                'title': f'{equipo.code} - {plan.tarea_descripcion[:35]}',
                'start': plan.proxima_ejecucion.strftime('%Y-%m-%d'),
                'color': color,
                'textColor': textColor,
                'extendedProps': {
                    'tipo': 'plan',
                    'equipo': equipo.code,
                    'equipo_id': equipo.id,
                    'sistema': plan.sistema.nombre,
                    'tarea': plan.tarea_descripcion,
                    'dias_restantes': dias_restantes,
                    'frecuencia': plan.frecuencia_dias
                }
            })
        
        return jsonify(eventos)
        
    except Exception as e:
        print(f"Error en api_eventos: {e}")
        return jsonify([])


@calendario_bp.route('/api/resumen')
@tecnico_required
def api_resumen():
    """API para obtener resumen de mantenimientos"""
    try:
        hoy = date.today()
        semana_prox = hoy + timedelta(days=7)
        mes_prox = hoy + timedelta(days=30)
        
        planes = PlanMantenimiento.query.filter_by(activo=True).all()
        
        vencidas = 0
        esta_semana = 0
        este_mes = 0
        total_pendientes = 0
        
        for plan in planes:
            if not plan.sistema or not plan.sistema.equipo:
                continue
            
            if not plan.proxima_ejecucion:
                plan.calcular_proxima_ejecucion()
                db.session.commit()
            
            if plan.proxima_ejecucion < hoy:
                vencidas += 1
                total_pendientes += 1
            elif plan.proxima_ejecucion <= semana_prox:
                esta_semana += 1
                total_pendientes += 1
            elif plan.proxima_ejecucion <= mes_prox:
                este_mes += 1
                total_pendientes += 1
        
        return jsonify({
            'vencidas': vencidas,
            'esta_semana': esta_semana,
            'este_mes': este_mes,
            'total_pendientes': total_pendientes,
            'total_planes': len([p for p in planes if p.sistema and p.sistema.equipo])
        })
        
    except Exception as e:
        print(f"Error en api_resumen: {e}")
        return jsonify({'vencidas': 0, 'esta_semana': 0, 'este_mes': 0, 'total_pendientes': 0, 'total_planes': 0})


@calendario_bp.route('/api/recalcular-fechas', methods=['POST'])
@tecnico_required
def api_recalcular_fechas():
    """Recalcula todas las fechas de los planes de mantenimiento"""
    try:
        planes = PlanMantenimiento.query.filter_by(activo=True).all()
        actualizados = 0
        
        for plan in planes:
            plan.calcular_proxima_ejecucion()
            actualizados += 1
        
        db.session.commit()
        
        return jsonify({'success': True, 'actualizados': actualizados})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@calendario_bp.route('/api/generar-orden-agrupada', methods=['POST'])
@tecnico_required
def api_generar_orden_agrupada():
    """Genera una orden de trabajo con múltiples tareas agrupadas por fecha"""
    try:
        data = request.get_json()
        tareas_ids = data.get('tareas_ids', [])
        fecha_str = data.get('fecha')
        
        if not tareas_ids:
            return jsonify({'success': False, 'error': 'No hay tareas seleccionadas'}), 400
        
        planes = PlanMantenimiento.query.filter(PlanMantenimiento.id.in_(tareas_ids)).all()
        
        if not planes:
            return jsonify({'success': False, 'error': 'No se encontraron las tareas'}), 400
        
        equipos_ids = set(p.sistema.equipo_id for p in planes)
        equipos = {e.id: e for e in Equipo.query.filter(Equipo.id.in_(equipos_ids)).all()}
        
        equipo_principal = equipos[list(equipos_ids)[0]]
        
        from routes.ordenes import generar_numero_ot_con_correlativo
        numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo_principal.id, 'Preventivo')
        
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else None
        
        tareas_seleccionadas = []
        for plan in planes:
            tareas_seleccionadas.append({
                'id': plan.id,
                'sistema_id': plan.sistema.id,
                'sistema_nombre': plan.sistema.nombre,
                'descripcion': plan.tarea_descripcion,
                'frecuencia_dias': plan.frecuencia_dias
            })
        
        if len(equipos_ids) == 1:
            titulo = f"Preventivo - {equipo_principal.code} - {len(planes)} tarea(s)"
        else:
            titulo = f"Preventivo Multiple - {len(equipos_ids)} equipo(s) - {len(planes)} tarea(s)"
        
        observaciones = f"""Orden generada automáticamente desde el panel preventivo.
Fecha programada: {fecha_str}
Total tareas: {len(planes)}
Equipos involucrados: {', '.join(e.code for e in equipos.values())}
"""
        
        nueva_orden = OrdenTrabajo(
            numero_ot=numero_ot,
            numero_correlativo=correlativo,
            codigo_equipo=equipo_principal.code,
            equipo_id=equipo_principal.id,
            tipo='Preventivo',
            titulo=titulo,
            descripcion=f"Tareas programadas para el {fecha_str}",
            tareas_seleccionadas=tareas_seleccionadas,
            estado='Pendiente',
            prioridad='Media',
            fecha_estimada=fecha_obj,
            creado_por=session.get('username', 'Sistema'),
            observaciones=observaciones
        )
        
        db.session.add(nueva_orden)
        db.session.commit()
        
        # Generar QR
        try:
            from routes.ordenes import generar_qr_orden
            generar_qr_orden(nueva_orden)
        except Exception as qr_error:
            print(f"Error generando QR: {qr_error}")
        
        for plan in planes:
            plan.ultima_generacion = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'orden_id': nueva_orden.id,
            'numero_ot': nueva_orden.numero_ot,
            'cantidad_tareas': len(planes)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error en api_generar_orden_agrupada: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@calendario_bp.route('/api/todos-cronogramas')
@tecnico_required
def api_todos_cronogramas():
    """API que devuelve TODOS los equipos con sus tareas INDIVIDUALES"""
    try:
        hoy = date.today()
        equipos = Equipo.query.all()
        
        resultado = []
        
        for equipo in equipos:
            tareas_individuales = []
            
            for sistema in equipo.sistemas:
                for plan in sistema.planes_pm:
                    if not plan.activo:
                        continue
                    
                    if not plan.proxima_ejecucion:
                        plan.calcular_proxima_ejecucion()
                        db.session.commit()
                    
                    fecha = plan.proxima_ejecucion
                    dias_restantes = (fecha - hoy).days
                    
                    if dias_restantes < 0:
                        estado = 'vencido'
                    elif dias_restantes <= 7:
                        estado = 'semana'
                    elif dias_restantes <= 30:
                        estado = 'mes'
                    else:
                        estado = 'futuro'
                    
                    # Obtener repuestos
                    repuestos_tarea = []
                    for rep in plan.repuestos_necesarios:
                        repuestos_tarea.append({
                            'codigo': rep.repuesto.codigo,
                            'nombre': rep.repuesto.nombre,
                            'cantidad_requerida': rep.cantidad_requerida,
                            'stock_actual': rep.repuesto.stock_actual
                        })
                    
                    tareas_individuales.append({
                        'id': plan.id,
                        'fecha': fecha.strftime('%Y-%m-%d'),
                        'fecha_formateada': fecha.strftime('%d/%m/%Y'),
                        'dias_restantes': dias_restantes,
                        'estado': estado,
                        'sistema_nombre': sistema.nombre,
                        'descripcion': plan.tarea_descripcion,
                        'frecuencia_dias': plan.frecuencia_dias,
                        'tiempo_estimado': plan.tiempo_estimado,
                        'repuestos': repuestos_tarea
                    })
            
            if not tareas_individuales:
                continue
            
            tareas_individuales.sort(key=lambda x: x['dias_restantes'])
            
            total_tareas = len(tareas_individuales)
            vencidos = sum(1 for t in tareas_individuales if t['estado'] == 'vencido')
            semana = sum(1 for t in tareas_individuales if t['estado'] == 'semana')
            mes = sum(1 for t in tareas_individuales if t['estado'] == 'mes')
            
            resultado.append({
                'id': equipo.id,
                'codigo': equipo.code,
                'nombre': equipo.name,
                'gmp_classification': equipo.gmp_classification,
                'ubicacion': equipo.location,
                'total_tareas': total_tareas,
                'vencidos': vencidos,
                'proximos_semana': semana,
                'proximos_mes': mes,
                'tareas': tareas_individuales
            })
        
        return jsonify({'equipos': resultado})
        
    except Exception as e:
        print(f"Error en api_todos_cronogramas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'equipos': [], 'error': str(e)}), 500


@calendario_bp.route('/api/tarea/<int:tarea_id>')
@tecnico_required
def api_tarea(tarea_id):
    """API para obtener detalles de una tarea específica"""
    try:
        plan = PlanMantenimiento.query.get_or_404(tarea_id)
        sistema = plan.sistema
        equipo = sistema.equipo
        
        repuestos = []
        for rep in plan.repuestos_necesarios:
            repuestos.append({
                'codigo': rep.repuesto.codigo,
                'nombre': rep.repuesto.nombre,
                'cantidad_requerida': rep.cantidad_requerida,
                'stock_actual': rep.repuesto.stock_actual
            })
        
        return jsonify({
            'equipo': {
                'id': equipo.id,
                'code': equipo.code,
                'name': equipo.name
            },
            'sistema': {
                'id': sistema.id,
                'nombre': sistema.nombre
            },
            'tarea': {
                'id': plan.id,
                'descripcion': plan.tarea_descripcion,
                'frecuencia': plan.frecuencia_dias,
                'tiempo_estimado': plan.tiempo_estimado
            },
            'repuestos': repuestos
        })
        
    except Exception as e:
        print(f"Error en api_tarea: {e}")
        return jsonify({'error': str(e)}), 500


@calendario_bp.route('/api/tareas-por-frecuencia')
@tecnico_required
def api_tareas_por_frecuencia():
    """API que agrupa tareas por equipo y frecuencia"""
    try:
        hoy = date.today()
        equipos = Equipo.query.all()
        
        resultado = []
        
        for equipo in equipos:
            grupos_frecuencia = {}
            
            for sistema in equipo.sistemas:
                for plan in sistema.planes_pm:
                    if not plan.activo:
                        continue
                    
                    if not plan.proxima_ejecucion:
                        plan.calcular_proxima_ejecucion()
                        db.session.commit()
                    
                    fecha = plan.proxima_ejecucion
                    dias_restantes = (fecha - hoy).days
                    frecuencia = plan.frecuencia_dias
                    
                    if dias_restantes < 0:
                        estado = 'vencido'
                    elif dias_restantes <= 7:
                        estado = 'urgente'
                    else:
                        estado = 'programado'
                    
                    repuestos_tarea = []
                    for rep in plan.repuestos_necesarios:
                        repuestos_tarea.append({
                            'codigo': rep.repuesto.codigo,
                            'nombre': rep.repuesto.nombre,
                            'cantidad_requerida': rep.cantidad_requerida,
                            'stock_actual': rep.repuesto.stock_actual
                        })
                    
                    tarea_info = {
                        'id': plan.id,
                        'sistema_nombre': sistema.nombre,
                        'sistema_id': sistema.id,
                        'descripcion': plan.tarea_descripcion,
                        'fecha_programada': fecha.strftime('%Y-%m-%d'),
                        'fecha_formateada': fecha.strftime('%d/%m/%Y'),
                        'dias_restantes': dias_restantes,
                        'estado': estado,
                        'tiempo_estimado': plan.tiempo_estimado,
                        'repuestos': repuestos_tarea,
                        'ultima_ejecucion': plan.ultima_ejecucion.strftime('%d/%m/%Y') if plan.ultima_ejecucion else 'Nunca'
                    }
                    
                    if frecuencia not in grupos_frecuencia:
                        grupos_frecuencia[frecuencia] = {
                            'frecuencia_dias': frecuencia,
                            'frecuencia_texto': _get_frecuencia_texto(frecuencia),
                            'tareas': [],
                            'total_tiempo_estimado': 0,
                            'repuestos_agrupados': {}
                        }
                    
                    grupos_frecuencia[frecuencia]['tareas'].append(tarea_info)
                    grupos_frecuencia[frecuencia]['total_tiempo_estimado'] += (plan.tiempo_estimado or 0)
                    
                    for rep in repuestos_tarea:
                        codigo = rep['codigo']
                        if codigo not in grupos_frecuencia[frecuencia]['repuestos_agrupados']:
                            grupos_frecuencia[frecuencia]['repuestos_agrupados'][codigo] = {
                                'codigo': rep['codigo'],
                                'nombre': rep['nombre'],
                                'cantidad_total': 0,
                                'stock_actual': rep['stock_actual']
                            }
                        grupos_frecuencia[frecuencia]['repuestos_agrupados'][codigo]['cantidad_total'] += rep['cantidad_requerida']
            
            if grupos_frecuencia:
                grupos_lista = list(grupos_frecuencia.values())
                grupos_lista.sort(key=lambda x: x['frecuencia_dias'])
                
                for grupo in grupos_lista:
                    grupo['repuestos'] = list(grupo['repuestos_agrupados'].values())
                    del grupo['repuestos_agrupados']
                
                for grupo in grupos_lista:
                    fechas = [t['fecha_programada'] for t in grupo['tareas']]
                    grupo['fecha_sugerida'] = min(fechas) if fechas else None
                    grupo['fecha_sugerida_formateada'] = datetime.strptime(grupo['fecha_sugerida'], '%Y-%m-%d').strftime('%d/%m/%Y') if grupo['fecha_sugerida'] else None
                
                resultado.append({
                    'id': equipo.id,
                    'codigo': equipo.code,
                    'nombre': equipo.name,
                    'gmp_classification': equipo.gmp_classification,
                    'ubicacion': equipo.location,
                    'grupos': grupos_lista
                })
        
        return jsonify({'equipos': resultado})
        
    except Exception as e:
        print(f"Error en api_tareas_por_frecuencia: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'equipos': [], 'error': str(e)}), 500


def _get_frecuencia_texto(dias):
    """Convierte días en texto legible"""
    if dias == 1:
        return 'Diario'
    elif dias == 7:
        return 'Semanal'
    elif dias == 15:
        return 'Quincenal'
    elif dias == 30:
        return 'Mensual'
    elif dias == 60:
        return 'Bimestral'
    elif dias == 90:
        return 'Trimestral'
    elif dias == 180:
        return 'Semestral'
    elif dias == 365:
        return 'Anual'
    else:
        return f'Cada {dias} días'


@calendario_bp.route('/api/generar-orden-grupo', methods=['POST'])
@tecnico_required
def api_generar_orden_grupo():
    """Genera una orden de trabajo para todas las tareas de un equipo con frecuencia específica"""
    try:
        data = request.get_json()
        equipo_id = data.get('equipo_id')
        frecuencia_dias = data.get('frecuencia_dias')
        fecha_ejecucion_str = data.get('fecha_ejecucion')
        
        if not equipo_id or not frecuencia_dias:
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        planes = PlanMantenimiento.query.filter(
            PlanMantenimiento.activo == True,
            PlanMantenimiento.frecuencia_dias == frecuencia_dias,
            PlanMantenimiento.sistema.has(equipo_id=equipo_id)
        ).all()
        
        if not planes:
            return jsonify({'success': False, 'error': 'No hay tareas para este grupo'}), 400
        
        equipo = Equipo.query.get(equipo_id)
        fecha_ejecucion = datetime.strptime(fecha_ejecucion_str, '%Y-%m-%d').date() if fecha_ejecucion_str else date.today()
        
        # Verificar si ya existe orden pendiente
        for plan in planes:
            orden_existente = OrdenTrabajo.query.filter(
                OrdenTrabajo.tarea_origen_id == plan.id,
                OrdenTrabajo.estado.in_(['Pendiente', 'Aprobada', 'En Progreso'])
            ).first()
            if orden_existente:
                return jsonify({
                    'success': False, 
                    'error': f'La tarea "{plan.tarea_descripcion[:50]}" ya tiene una orden en curso'
                }), 400
        
        from routes.ordenes import generar_numero_ot_con_correlativo
        numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo_id, 'Preventivo')
        
        # Preparar tareas con sus repuestos - INCLUYENDO REPUESTOS
        tareas_seleccionadas = []
        
        for plan in planes:
            # Obtener repuestos de esta tarea desde la base de datos
            repuestos_tarea = []
            for rpt in plan.repuestos_necesarios:
                if rpt.repuesto:
                    repuestos_tarea.append({
                        'repuesto_id': rpt.repuesto.id,
                        'codigo': rpt.repuesto.codigo,
                        'nombre': rpt.repuesto.nombre,
                        'cantidad_requerida': rpt.cantidad_requerida,
                        'stock_actual': rpt.repuesto.stock_actual
                    })
            
            tarea_info = {
                'id': plan.id,
                'sistema_id': plan.sistema.id,
                'sistema_nombre': plan.sistema.nombre,
                'descripcion': plan.tarea_descripcion,
                'frecuencia_dias': plan.frecuencia_dias,
                'tiempo_estimado': plan.tiempo_estimado,
                'repuestos': repuestos_tarea  # <-- CLAVE: guardar repuestos en la tarea
            }
            tareas_seleccionadas.append(tarea_info)
        
        freq_texto = {7: 'Semanal', 15: 'Quincenal', 30: 'Mensual', 60: 'Bimestral', 
                      90: 'Trimestral', 180: 'Semestral', 365: 'Anual'}.get(frecuencia_dias, f'Cada {frecuencia_dias} días')
        
        tiempo_total = sum(p.tiempo_estimado or 0 for p in planes)
        
        nueva_orden = OrdenTrabajo(
            numero_ot=numero_ot,
            numero_correlativo=correlativo,
            codigo_equipo=equipo.code,
            equipo_id=equipo.id,
            tipo='Preventivo',
            titulo=f"[{freq_texto}] Mantenimiento - {equipo.code}",
            tareas_seleccionadas=tareas_seleccionadas,  # <-- Aquí van las tareas CON repuestos
            estado='Pendiente',
            prioridad='Media',
            fecha_estimada=fecha_ejecucion,
            creado_por=session.get('username', 'Sistema'),
            observaciones=f"Orden generada para mantenimiento {freq_texto}. Total tareas: {len(planes)}. Tiempo estimado: {tiempo_total} minutos."
        )
        
        db.session.add(nueva_orden)
        db.session.commit()
        
        # Actualizar flag
        for plan in planes:
            plan.orden_generada = True
        db.session.commit()
        
        # Generar QR
        try:
            from routes.ordenes import generar_qr_orden
            generar_qr_orden(nueva_orden)
        except Exception as qr_error:
            print(f"Error generando QR: {qr_error}")
        
        return jsonify({
            'success': True,
            'orden_id': nueva_orden.id,
            'numero_ot': nueva_orden.numero_ot,
            'cantidad_tareas': len(planes),
            'tiempo_total': tiempo_total
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error en api_generar_orden_grupo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500