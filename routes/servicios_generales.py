# routes/servicios_generales.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_required, current_user
from models import db
from models.instalacion import Instalacion, PlanMantenimientoInstalacion, HistorialEstadoInstalacion
from models.orden_servicio_general import OrdenServicioGeneral, SeguimientoOrdenSG
from models.usuario import Usuario
from models.inventario import Repuesto, ConsumoRepuesto, MovimientoStock
from datetime import datetime, timedelta
from utils.decorators import login_required, tecnico_required, admin_required
import json
import os
import qrcode
from io import BytesIO
import base64

servicios_bp = Blueprint('servicios_generales', __name__, url_prefix='/servicios-generales')


# ========== FUNCIONES AUXILIARES ==========

def generar_numero_osg():
    """Genera número de orden para servicios generales"""
    anio = datetime.now().strftime('%Y')
    ultima = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.numero_ot.like(f'SG-{anio}-%')
    ).order_by(OrdenServicioGeneral.id.desc()).first()
    
    if ultima:
        try:
            correlativo = int(ultima.numero_ot.split('-')[-1]) + 1
        except:
            correlativo = 1
    else:
        correlativo = 1
    
    return f"SG-{anio}-{correlativo:04d}", correlativo


def generar_qr_orden(orden):
    """Genera código QR para la orden"""
    try:
        qr_dir = os.path.join('static', 'qrcodes', 'servicios')
        os.makedirs(qr_dir, exist_ok=True)
        
        # URL para acceder a la orden
        url = f"/servicios-generales/orden/{orden.id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        filename = f"osg_{orden.id}_{orden.numero_ot}.png"
        filepath = os.path.join(qr_dir, filename)
        img.save(filepath)
        
        orden.qr_code = f"qrcodes/servicios/{filename}"
        db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error generando QR: {e}")
        return False


def check_permiso_mantenimiento():
    """Verifica si el usuario tiene permisos de mantenimiento"""
    area = session.get('area', '')
    role = session.get('role', '')
    return area == 'mantenimiento' or role in ['jefe', 'supervisor']


# ========== VISTAS PARA SOLICITANTES ==========

@servicios_bp.route('/solicitar', methods=['GET', 'POST'])
@login_required
def solicitar_servicio():
    """Formulario para solicitar un servicio"""
    instalaciones = Instalacion.query.filter(
        Instalacion.estado.in_(['Operativo', 'En Mantenimiento'])
    ).order_by(Instalacion.categoria, Instalacion.nombre).all()
    
    # Categorías para el formulario
    categorias = [
        'Eléctrico', 'Edilicio', 'Climatización', 'Sanitario', 
        'Seguridad', 'Iluminación', 'Puertas/Accesos', 'Redes/Datos',
        'Mobiliario', 'Jardinería', 'Limpieza', 'Otros'
    ]
    
    if request.method == 'POST':
        try:
            numero_ot, correlativo = generar_numero_osg()
            
            # Procesar ubicación
            ubicacion = request.form.get('ubicacion', '')
            if request.form.get('edificio'):
                ubicacion = f"{request.form.get('edificio')} - {request.form.get('piso', '')} - {ubicacion}".strip(' -')
            
            nueva_solicitud = OrdenServicioGeneral(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                instalacion_id=request.form.get('instalacion_id') or None,
                tipo='Solicitud',
                subtipo=request.form.get('categoria'),
                origen='Externo',
                solicitante_id=current_user.id,
                solicitante_nombre=current_user.nombre_completo or current_user.username,
                solicitante_sector=current_user.area_principal or request.form.get('sector', ''),
                solicitante_contacto=current_user.telefono or request.form.get('contacto', ''),
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                ubicacion_detallada=ubicacion,
                prioridad=request.form.get('prioridad', 'Media'),
                estado='Pendiente',
                requiere_aprobacion=True,
                creado_por=current_user.username,
                tiempo_estimado=float(request.form.get('tiempo_estimado', 0)) or None
            )
            
            db.session.add(nueva_solicitud)
            db.session.flush()
            
            # Agregar seguimiento inicial
            nueva_solicitud.agregar_seguimiento(
                current_user.username,
                f"Solicitud creada - Prioridad: {nueva_solicitud.prioridad}",
                None,
                'Pendiente'
            )
            
            db.session.commit()
            
            # Generar QR
            generar_qr_orden(nueva_solicitud)
            
            flash(f'✅ Solicitud {numero_ot} registrada correctamente. El departamento de Mantenimiento la revisará a la brevedad.', 'success')
            return redirect(url_for('servicios_generales.mis_solicitudes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar solicitud: {str(e)}', 'error')
            print(f"Error: {e}")
    
    return render_template('servicios_generales/solicitar.html',
                         instalaciones=instalaciones,
                         categorias=categorias)


@servicios_bp.route('/mis-solicitudes')
@login_required
def mis_solicitudes():
    """Ver solicitudes del usuario"""
    solicitudes = OrdenServicioGeneral.query.filter_by(
        solicitante_id=current_user.id
    ).order_by(OrdenServicioGeneral.fecha_creacion.desc()).all()
    
    # Estadísticas
    pendientes = sum(1 for s in solicitudes if s.estado in ['Pendiente', 'Aprobada', 'En Progreso'])
    completadas = sum(1 for s in solicitudes if s.estado == 'Completada')
    
    return render_template('servicios_generales/mis_solicitudes.html',
                         solicitudes=solicitudes,
                         pendientes=pendientes,
                         completadas=completadas)


# ========== VISTAS PARA MANTENIMIENTO ==========

@servicios_bp.route('/panel')
@login_required
def panel_mantenimiento():
    """Panel principal para mantenimiento"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para acceder a esta sección', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    # Solicitudes pendientes de aprobación
    solicitudes_pendientes = OrdenServicioGeneral.query.filter_by(
        estado='Pendiente',
        requiere_aprobacion=True
    ).order_by(
        OrdenServicioGeneral.prioridad.desc(),
        OrdenServicioGeneral.fecha_creacion.asc()
    ).limit(10).all()
    
    # Órdenes en progreso
    ordenes_progreso = OrdenServicioGeneral.query.filter_by(
        estado='En Progreso'
    ).order_by(OrdenServicioGeneral.prioridad.desc()).limit(10).all()
    
    # Órdenes completadas hoy
    hoy = datetime.now().date()
    completadas_hoy = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.estado == 'Completada',
        db.func.date(OrdenServicioGeneral.fecha_cierre) == hoy
    ).count()
    
    # Estadísticas generales
    total_pendientes = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.estado.in_(['Pendiente', 'Aprobada'])
    ).count()
    
    total_progreso = OrdenServicioGeneral.query.filter_by(estado='En Progreso').count()
    
    # Preventivas programadas para esta semana
    inicio_semana = hoy
    fin_semana = hoy + timedelta(days=7)
    preventivas_semana = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.tipo == 'Preventivo',
        OrdenServicioGeneral.estado == 'Pendiente',
        OrdenServicioGeneral.fecha_estimada.between(inicio_semana, fin_semana)
    ).count()
    
    # Instalaciones fuera de servicio
    instalaciones_fuera = Instalacion.query.filter_by(estado='Fuera de Servicio').count()
    
    return render_template('servicios_generales/panel_mantenimiento.html',
                         solicitudes_pendientes=solicitudes_pendientes,
                         ordenes_progreso=ordenes_progreso,
                         completadas_hoy=completadas_hoy,
                         total_pendientes=total_pendientes,
                         total_progreso=total_progreso,
                         preventivas_semana=preventivas_semana,
                         instalaciones_fuera=instalaciones_fuera)


@servicios_bp.route('/gestion')
@login_required
def gestion_ordenes():
    """Gestión completa de órdenes"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para acceder a esta sección', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    # Filtros
    estado = request.args.get('estado', '')
    tipo = request.args.get('tipo', '')
    prioridad = request.args.get('prioridad', '')
    asignado = request.args.get('asignado', '')
    
    query = OrdenServicioGeneral.query
    
    if estado:
        query = query.filter_by(estado=estado)
    else:
        # Por defecto, no mostrar completadas ni canceladas
        query = query.filter(OrdenServicioGeneral.estado.notin_(['Completada', 'Verificada', 'Cancelada', 'Rechazada']))
    
    if tipo:
        query = query.filter_by(tipo=tipo)
    
    if prioridad:
        query = query.filter_by(prioridad=prioridad)
    
    if asignado:
        query = query.filter(OrdenServicioGeneral.asignado_a.ilike(f'%{asignado}%'))
    
    ordenes = query.order_by(
        OrdenServicioGeneral.prioridad.desc(),
        OrdenServicioGeneral.fecha_creacion.desc()
    ).all()
    
    # Técnicos disponibles
    tecnicos = Usuario.query.filter_by(area_principal='mantenimiento', activo=True).all()
    
    # Tipos de orden para filtros
    tipos = ['Preventivo', 'Correctivo', 'Solicitud', 'Mejora', 'Refacción']
    estados = ['Pendiente', 'Aprobada', 'En Progreso', 'Pausada', 'Completada', 'Verificada', 'Cancelada', 'Rechazada']
    prioridades = ['Baja', 'Media', 'Alta', 'Urgente', 'Emergencia']
    
    return render_template('servicios_generales/gestion_ordenes.html',
                         ordenes=ordenes,
                         tecnicos=tecnicos,
                         tipos=tipos,
                         estados=estados,
                         prioridades=prioridades,
                         filtros={'estado': estado, 'tipo': tipo, 'prioridad': prioridad, 'asignado': asignado})


@servicios_bp.route('/orden/<int:orden_id>')
@login_required
def detalle_orden(orden_id):
    """Ver detalle de una orden"""
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    # Verificar permisos
    area = session.get('area', '')
    role = session.get('role', '')
    
    if area != 'mantenimiento' and role not in ['jefe', 'supervisor']:
        if orden.solicitante_id != current_user.id:
            flash('No tienes permisos para ver esta orden', 'error')
            return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    # Obtener técnicos disponibles
    tecnicos = Usuario.query.filter_by(area_principal='mantenimiento', activo=True).all()
    
    # Obtener seguimientos
    seguimientos = SeguimientoOrdenSG.query.filter_by(orden_id=orden_id).order_by(SeguimientoOrdenSG.fecha.desc()).all()
    
    # Materiales disponibles (para ejecución)
    materiales = Repuesto.query.filter(Repuesto.stock_actual > 0).order_by(Repuesto.codigo).all()
    
    return render_template('servicios_generales/detalle_orden.html',
                         orden=orden,
                         tecnicos=tecnicos,
                         seguimientos=seguimientos,
                         materiales=materiales)


@servicios_bp.route('/orden/<int:orden_id>/aprobar', methods=['POST'])
@login_required
def aprobar_orden(orden_id):
    """Aprobar una solicitud"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para aprobar solicitudes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado != 'Pendiente':
            flash(f'No se puede aprobar una orden en estado {orden.estado}', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        estado_anterior = orden.estado
        orden.estado = 'Aprobada'
        orden.aprobado_por = current_user.username
        orden.fecha_aprobacion = datetime.utcnow()
        
        # Asignar técnico si se especifica
        asignado_a = request.form.get('asignado_a')
        if asignado_a:
            orden.asignado_a = asignado_a
            tecnico = Usuario.query.filter_by(username=asignado_a).first()
            if tecnico:
                orden.asignado_id = tecnico.id
        
        # Establecer fecha estimada
        fecha_estimada = request.form.get('fecha_estimada')
        if fecha_estimada:
            orden.fecha_estimada = datetime.strptime(fecha_estimada, '%Y-%m-%d').date()
        
        # Agregar seguimiento
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden aprobada. Asignada a: {asignado_a or 'Pendiente de asignación'}",
            estado_anterior,
            'Aprobada'
        )
        
        db.session.commit()
        
        # Generar QR actualizado
        generar_qr_orden(orden)
        
        flash(f'✅ Orden {orden.numero_ot} aprobada correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al aprobar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/rechazar', methods=['POST'])
@login_required
def rechazar_orden(orden_id):
    """Rechazar una solicitud"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para rechazar solicitudes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado != 'Pendiente':
            flash(f'No se puede rechazar una orden en estado {orden.estado}', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        motivo = request.form.get('motivo_rechazo', 'No especificado')
        estado_anterior = orden.estado
        
        orden.estado = 'Rechazada'
        orden.motivo_rechazo = motivo
        orden.aprobado_por = current_user.username
        orden.fecha_aprobacion = datetime.utcnow()
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Solicitud rechazada. Motivo: {motivo}",
            estado_anterior,
            'Rechazada'
        )
        
        db.session.commit()
        
        flash(f'⚠️ Orden {orden.numero_ot} rechazada', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al rechazar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/iniciar', methods=['POST'])
@login_required
def iniciar_orden(orden_id):
    """Iniciar una orden aprobada"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para iniciar órdenes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado not in ['Pendiente', 'Aprobada', 'Pausada']:
            flash(f'No se puede iniciar una orden en estado {orden.estado}', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        estado_anterior = orden.estado
        orden.estado = 'En Progreso'
        orden.fecha_inicio = datetime.utcnow()
        
        # Calcular tiempo de respuesta
        orden.calcular_tiempo_respuesta()
        
        # Asignar si no tiene
        if not orden.asignado_a:
            asignado_a = request.form.get('asignado_a') or current_user.username
            orden.asignado_a = asignado_a
            tecnico = Usuario.query.filter_by(username=asignado_a).first()
            if tecnico:
                orden.asignado_id = tecnico.id
        
        # Actualizar estado de la instalación
        if orden.instalacion:
            orden.instalacion.cambiar_estado('En Mantenimiento', current_user.username, f"OT {orden.numero_ot} iniciada")
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden iniciada por {current_user.username}",
            estado_anterior,
            'En Progreso'
        )
        
        db.session.commit()
        
        flash(f'🚀 Orden {orden.numero_ot} iniciada', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al iniciar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/pausar', methods=['POST'])
@login_required
def pausar_orden(orden_id):
    """Pausar una orden en progreso"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para pausar órdenes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado != 'En Progreso':
            flash(f'Solo se pueden pausar órdenes en progreso', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        motivo = request.form.get('motivo_pausa', '')
        estado_anterior = orden.estado
        
        orden.estado = 'Pausada'
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden pausada. Motivo: {motivo or 'No especificado'}",
            estado_anterior,
            'Pausada'
        )
        
        db.session.commit()
        
        flash(f'⏸️ Orden {orden.numero_ot} pausada', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al pausar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/completar', methods=['POST'])
@login_required
def completar_orden(orden_id):
    """Completar una orden en progreso"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para completar órdenes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado not in ['En Progreso', 'Pausada']:
            flash(f'Solo se pueden completar órdenes en progreso', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        estado_anterior = orden.estado
        
        # Datos del formulario
        orden.diagnostico = request.form.get('diagnostico', '')
        orden.trabajo_realizado = request.form.get('trabajo_realizado', '')
        orden.observaciones = request.form.get('observaciones', '')
        orden.recomendaciones = request.form.get('recomendaciones', '')
        
        # Tiempo real
        tiempo_real = request.form.get('tiempo_real')
        if tiempo_real:
            orden.tiempo_real = float(tiempo_real)
        
        # Firmas
        orden.firma_tecnico = request.form.get('firma_tecnico') or current_user.username
        orden.firma_supervisor = request.form.get('firma_supervisor')
        
        # Fechas
        orden.fecha_fin = datetime.utcnow()
        orden.fecha_cierre = datetime.utcnow()
        orden.estado = 'Completada'
        
        # Procesar materiales utilizados
        procesar_materiales(orden, request)
        
        # Actualizar instalación
        if orden.instalacion:
            orden.instalacion.cambiar_estado('Operativo', current_user.username, f"OT {orden.numero_ot} completada")
            
            # Si es preventivo, actualizar plan
            if orden.tipo == 'Preventivo' and orden.plan_mantenimiento_id:
                plan = PlanMantenimientoInstalacion.query.get(orden.plan_mantenimiento_id)
                if plan:
                    plan.ultima_ejecucion = datetime.utcnow().date()
                    plan.calcular_proxima_ejecucion()
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden completada. Trabajo realizado: {orden.trabajo_realizado[:100]}...",
            estado_anterior,
            'Completada'
        )
        
        db.session.commit()
        
        # Generar QR actualizado
        generar_qr_orden(orden)
        
        flash(f'✅ Orden {orden.numero_ot} completada exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al completar: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/verificar', methods=['POST'])
@login_required
def verificar_orden(orden_id):
    """Verificar una orden completada (supervisor)"""
    if session.get('role') not in ['jefe', 'supervisor']:
        flash('Solo supervisores pueden verificar órdenes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado != 'Completada':
            flash('Solo se pueden verificar órdenes completadas', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        estado_anterior = orden.estado
        orden.estado = 'Verificada'
        orden.verificado_por = current_user.username
        orden.fecha_verificacion = datetime.utcnow()
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden verificada y aprobada por {current_user.username}",
            estado_anterior,
            'Verificada'
        )
        
        db.session.commit()
        
        flash(f'✅ Orden {orden.numero_ot} verificada correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al verificar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/cancelar', methods=['POST'])
@login_required
def cancelar_orden(orden_id):
    """Cancelar una orden"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para cancelar órdenes', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        if orden.estado in ['Completada', 'Verificada']:
            flash('No se puede cancelar una orden completada', 'error')
            return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
        
        motivo = request.form.get('motivo_cancelacion', 'Cancelada por el usuario')
        estado_anterior = orden.estado
        
        orden.estado = 'Cancelada'
        orden.observaciones = f"{orden.observaciones or ''}\nCANCELADA: {motivo}"
        
        # Restaurar instalación
        if orden.instalacion and orden.instalacion.estado == 'En Mantenimiento':
            orden.instalacion.cambiar_estado('Operativo', current_user.username, f"OT {orden.numero_ot} cancelada")
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden cancelada. Motivo: {motivo}",
            estado_anterior,
            'Cancelada'
        )
        
        db.session.commit()
        
        flash(f'⚠️ Orden {orden.numero_ot} cancelada', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al cancelar: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))


@servicios_bp.route('/orden/<int:orden_id>/reasignar', methods=['POST'])
@login_required
def reasignar_orden(orden_id):
    """Reasignar orden a otro técnico"""
    if not check_permiso_mantenimiento():
        return jsonify({'success': False, 'message': 'Sin permisos'}), 403
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    try:
        nuevo_tecnico = request.form.get('asignado_a')
        if not nuevo_tecnico:
            return jsonify({'success': False, 'message': 'Debe especificar un técnico'}), 400
        
        tecnico_anterior = orden.asignado_a
        orden.asignado_a = nuevo_tecnico
        
        tecnico = Usuario.query.filter_by(username=nuevo_tecnico).first()
        if tecnico:
            orden.asignado_id = tecnico.id
        
        orden.agregar_seguimiento(
            current_user.username,
            f"Orden reasignada de {tecnico_anterior or 'Nadie'} a {nuevo_tecnico}",
            orden.estado,
            orden.estado
        )
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Orden reasignada a {nuevo_tecnico}'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


def procesar_materiales(orden, request):
    """Procesa los materiales utilizados en la orden"""
    materiales = []
    i = 0
    
    while True:
        codigo = request.form.get(f'material_codigo_{i}')
        if not codigo:
            break
        
        cantidad = float(request.form.get(f'material_cantidad_{i}', 0))
        if cantidad <= 0:
            i += 1
            continue
        
        repuesto = Repuesto.query.filter_by(codigo=codigo).first()
        if repuesto:
            if repuesto.stock_actual >= cantidad:
                # Actualizar stock
                stock_anterior = repuesto.stock_actual
                repuesto.stock_actual -= cantidad
                
                # Registrar consumo
                consumo = ConsumoRepuesto(
                    repuesto_id=repuesto.id,
                    orden_id=orden.id,
                    cantidad=cantidad,
                    registrado_por=current_user.username,
                    observaciones=f"Consumo en OSG {orden.numero_ot}"
                )
                db.session.add(consumo)
                
                # Registrar movimiento
                movimiento = MovimientoStock(
                    repuesto_id=repuesto.id,
                    tipo='salida',
                    cantidad=cantidad,
                    stock_anterior=stock_anterior,
                    stock_nuevo=repuesto.stock_actual,
                    referencia=f"OSG {orden.numero_ot}",
                    realizado_por=current_user.username
                )
                db.session.add(movimiento)
                
                materiales.append({
                    'codigo': codigo,
                    'nombre': repuesto.nombre,
                    'cantidad': cantidad,
                    'unidad': repuesto.unidad_medida or 'UN',
                    'costo_unitario': repuesto.costo_unitario or 0,
                    'costo_total': cantidad * (repuesto.costo_unitario or 0)
                })
            else:
                flash(f'Stock insuficiente para {repuesto.codigo}. Disponible: {repuesto.stock_actual}', 'warning')
        
        i += 1
    
    if materiales:
        orden.materiales_utilizados = json.dumps(materiales)
        orden.costo_total_materiales = sum(m.get('costo_total', 0) for m in materiales)


# ========== VISTAS PARA IMPRESIÓN ==========

@servicios_bp.route('/orden/<int:orden_id>/print')
@login_required
def print_orden(orden_id):
    """Versión imprimible de la orden"""
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    # Verificar permisos
    area = session.get('area', '')
    role = session.get('role', '')
    
    if area != 'mantenimiento' and role not in ['jefe', 'supervisor']:
        if orden.solicitante_id != current_user.id:
            flash('No tienes permisos para ver esta orden', 'error')
            return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    now = datetime.now()
    
    # Generar QR para impresión
    qr_base64 = None
    if orden.qr_code:
        qr_path = os.path.join('static', orden.qr_code)
        if os.path.exists(qr_path):
            with open(qr_path, 'rb') as f:
                qr_base64 = base64.b64encode(f.read()).decode()
    
    return render_template('servicios_generales/print_orden.html',
                         orden=orden,
                         now=now,
                         qr_base64=qr_base64)


@servicios_bp.route('/orden/<int:orden_id>/print-ejecucion')
@login_required
def print_orden_ejecucion(orden_id):
    """Formulario imprimible para ejecución en campo"""
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    now = datetime.now()
    
    return render_template('servicios_generales/print_ejecucion.html',
                         orden=orden,
                         now=now)


# ========== GESTIÓN DE INSTALACIONES ==========

@servicios_bp.route('/instalaciones')
@login_required
def gestion_instalaciones():
    """Listado de instalaciones"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para acceder a esta sección', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    categoria = request.args.get('categoria', '')
    estado = request.args.get('estado', '')
    
    query = Instalacion.query
    
    if categoria:
        query = query.filter_by(categoria=categoria)
    if estado:
        query = query.filter_by(estado=estado)
    
    instalaciones = query.order_by(Instalacion.categoria, Instalacion.nombre).all()
    
    # Estadísticas
    total_operativas = Instalacion.query.filter_by(estado='Operativo').count()
    total_mantenimiento = Instalacion.query.filter_by(estado='En Mantenimiento').count()
    total_fuera = Instalacion.query.filter_by(estado='Fuera de Servicio').count()
    
    categorias = db.session.query(Instalacion.categoria).distinct().all()
    categorias = [c[0] for c in categorias if c[0]]
    
    return render_template('servicios_generales/instalaciones.html',
                         instalaciones=instalaciones,
                         total_operativas=total_operativas,
                         total_mantenimiento=total_mantenimiento,
                         total_fuera=total_fuera,
                         categorias=categorias,
                         filtro_categoria=categoria,
                         filtro_estado=estado)


@servicios_bp.route('/instalaciones/nueva', methods=['GET', 'POST'])
@login_required
def nueva_instalacion():
    """Crear nueva instalación"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para crear instalaciones', 'error')
        return redirect(url_for('servicios_generales.gestion_instalaciones'))
    
    if request.method == 'POST':
        try:
            nueva = Instalacion(
                codigo=request.form.get('codigo'),
                nombre=request.form.get('nombre'),
                categoria=request.form.get('categoria'),
                subcategoria=request.form.get('subcategoria'),
                ubicacion=request.form.get('ubicacion'),
                sector=request.form.get('sector'),
                edificio=request.form.get('edificio'),
                piso=request.form.get('piso'),
                marca=request.form.get('marca'),
                modelo=request.form.get('modelo'),
                anio_instalacion=int(request.form.get('anio_instalacion')) if request.form.get('anio_instalacion') else None,
                especificaciones=request.form.get('especificaciones'),
                requiere_mantenimiento_periodico=bool(request.form.get('requiere_mantenimiento')),
                frecuencia_mantenimiento_dias=int(request.form.get('frecuencia_dias')) if request.form.get('frecuencia_dias') else None,
                responsable_area=request.form.get('responsable_area'),
                proveedor_servicio=request.form.get('proveedor_servicio'),
                created_by=current_user.username
            )
            
            db.session.add(nueva)
            db.session.flush()
            
            # Registrar historial
            nueva.cambiar_estado('Operativo', current_user.username, 'Instalación creada')
            
            db.session.commit()
            
            flash(f'✅ Instalación {nueva.codigo} creada correctamente', 'success')
            return redirect(url_for('servicios_generales.gestion_instalaciones'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al crear instalación: {str(e)}', 'error')
    
    categorias = ['Eléctrico', 'Edilicio', 'Climatización', 'Sanitario', 'Seguridad', 
                  'Iluminación', 'Puertas/Accesos', 'Redes/Datos', 'Mobiliario', 'Otros']
    sectores = ['Producción', 'Administración', 'Almacén', 'Calidad', 'Mantenimiento', 'Común']
    edificios = ['Planta Principal', 'Edificio Administrativo', 'Almacén', 'Laboratorio', 'Comedor', 'Otros']
    
    return render_template('servicios_generales/nueva_instalacion.html',
                         categorias=categorias,
                         sectores=sectores,
                         edificios=edificios)


@servicios_bp.route('/instalaciones/<int:instalacion_id>')
@login_required
def detalle_instalacion(instalacion_id):
    """Ver detalle de instalación"""
    instalacion = Instalacion.query.get_or_404(instalacion_id)
    
    # Órdenes relacionadas
    ordenes = OrdenServicioGeneral.query.filter_by(instalacion_id=instalacion_id)\
        .order_by(OrdenServicioGeneral.fecha_creacion.desc()).limit(20).all()
    
    # Historial de estados
    historial = HistorialEstadoInstalacion.query.filter_by(instalacion_id=instalacion_id)\
        .order_by(HistorialEstadoInstalacion.fecha_cambio.desc()).all()
    
    return render_template('servicios_generales/detalle_instalacion.html',
                         instalacion=instalacion,
                         ordenes=ordenes,
                         historial=historial)


# ========== ÓRDENES PREVENTIVAS ==========

@servicios_bp.route('/preventiva/nueva', methods=['GET', 'POST'])
@login_required
def nueva_preventiva():
    """Crear orden preventiva"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para crear preventivas', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    instalaciones = Instalacion.query.filter_by(requiere_mantenimiento_periodico=True).all()
    tecnicos = Usuario.query.filter_by(area_principal='mantenimiento', activo=True).all()
    
    if request.method == 'POST':
        try:
            numero_ot, correlativo = generar_numero_osg()
            
            nueva = OrdenServicioGeneral(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                instalacion_id=request.form.get('instalacion_id'),
                tipo='Preventivo',
                subtipo=request.form.get('categoria'),
                origen='Interno',
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                ubicacion_detallada=request.form.get('ubicacion'),
                prioridad=request.form.get('prioridad', 'Media'),
                fecha_estimada=datetime.strptime(request.form.get('fecha_estimada'), '%Y-%m-%d').date() if request.form.get('fecha_estimada') else None,
                tiempo_estimado=float(request.form.get('tiempo_estimado')) if request.form.get('tiempo_estimado') else None,
                estado='Pendiente',
                requiere_aprobacion=False,
                asignado_a=request.form.get('asignado_a'),
                creado_por=current_user.username
            )
            
            db.session.add(nueva)
            db.session.flush()
            
            nueva.agregar_seguimiento(
                current_user.username,
                f"Orden preventiva creada. Programada para: {nueva.fecha_estimada}",
                None,
                'Pendiente'
            )
            
            db.session.commit()
            
            generar_qr_orden(nueva)
            
            flash(f'✅ Orden preventiva {numero_ot} creada', 'success')
            return redirect(url_for('servicios_generales.gestion_ordenes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al crear orden: {str(e)}', 'error')
    
    categorias = ['Eléctrico', 'Edilicio', 'Climatización', 'Sanitario', 'Seguridad', 
                  'Iluminación', 'Puertas/Accesos', 'Redes/Datos', 'Otros']
    
    return render_template('servicios_generales/nueva_preventiva.html',
                         instalaciones=instalaciones,
                         tecnicos=tecnicos,
                         categorias=categorias)


# ========== REPORTES ==========

@servicios_bp.route('/reportes')
@login_required
def reportes():
    """Reportes del módulo"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para ver reportes', 'error')
        return redirect(url_for('servicios_generales.mis_solicitudes'))
    
    return render_template('servicios_generales/reportes.html')


# ========== API ENDPOINTS ==========

@servicios_bp.route('/api/orden/<int:orden_id>/seguimientos')
@login_required
def api_seguimientos(orden_id):
    """API para obtener seguimientos"""
    seguimientos = SeguimientoOrdenSG.query.filter_by(orden_id=orden_id)\
        .order_by(SeguimientoOrdenSG.fecha.desc()).all()
    
    return jsonify([{
        'id': s.id,
        'usuario': s.usuario,
        'fecha': s.fecha.strftime('%d/%m/%Y %H:%M'),
        'comentario': s.comentario,
        'estado_anterior': s.estado_anterior,
        'estado_nuevo': s.estado_nuevo
    } for s in seguimientos])


@servicios_bp.route('/api/estadisticas')
@login_required
def api_estadisticas():
    """API para estadísticas"""
    if not check_permiso_mantenimiento():
        return jsonify({'error': 'Sin permisos'}), 403
    
    # Conteo por estado
    estados = ['Pendiente', 'Aprobada', 'En Progreso', 'Pausada', 'Completada', 'Verificada', 'Cancelada']
    conteo = {}
    for estado in estados:
        conteo[estado] = OrdenServicioGeneral.query.filter_by(estado=estado).count()
    
    # Por tipo
    tipos = ['Preventivo', 'Correctivo', 'Solicitud', 'Mejora', 'Refacción']
    por_tipo = {}
    for tipo in tipos:
        por_tipo[tipo] = OrdenServicioGeneral.query.filter_by(tipo=tipo).count()
    
    # Por prioridad
    prioridades = ['Baja', 'Media', 'Alta', 'Urgente', 'Emergencia']
    por_prioridad = {}
    for p in prioridades:
        por_prioridad[p] = OrdenServicioGeneral.query.filter_by(prioridad=p).count()
    
    # Últimos 30 días
    hace_30_dias = datetime.utcnow() - timedelta(days=30)
    creadas_30d = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.fecha_creacion >= hace_30_dias
    ).count()
    completadas_30d = OrdenServicioGeneral.query.filter(
        OrdenServicioGeneral.estado.in_(['Completada', 'Verificada']),
        OrdenServicioGeneral.fecha_cierre >= hace_30_dias
    ).count()
    
    return jsonify({
        'por_estado': conteo,
        'por_tipo': por_tipo,
        'por_prioridad': por_prioridad,
        'creadas_30d': creadas_30d,
        'completadas_30d': completadas_30d
    })

# Agregar estas rutas al final del archivo

# Agregar estas rutas al final del archivo

@servicios_bp.route('/instalaciones/<int:instalacion_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_instalacion(instalacion_id):
    """Editar instalación existente"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos para editar instalaciones', 'error')
        return redirect(url_for('servicios_generales.gestion_instalaciones'))
    
    instalacion = Instalacion.query.get_or_404(instalacion_id)
    
    if request.method == 'POST':
        try:
            instalacion.nombre = request.form.get('nombre')
            instalacion.categoria = request.form.get('categoria')
            instalacion.subcategoria = request.form.get('subcategoria')
            instalacion.ubicacion = request.form.get('ubicacion')
            instalacion.sector = request.form.get('sector')
            instalacion.edificio = request.form.get('edificio')
            instalacion.piso = request.form.get('piso')
            instalacion.marca = request.form.get('marca')
            instalacion.modelo = request.form.get('modelo')
            instalacion.anio_instalacion = int(request.form.get('anio_instalacion')) if request.form.get('anio_instalacion') else None
            instalacion.especificaciones = request.form.get('especificaciones')
            instalacion.requiere_mantenimiento_periodico = bool(request.form.get('requiere_mantenimiento'))
            instalacion.frecuencia_mantenimiento_dias = int(request.form.get('frecuencia_dias')) if request.form.get('frecuencia_dias') else None
            instalacion.responsable_area = request.form.get('responsable_area')
            instalacion.proveedor_servicio = request.form.get('proveedor_servicio')
            instalacion.updated_by = current_user.username
            
            # Proxima ejecución
            prox = request.form.get('proxima_ejecucion')
            if prox:
                instalacion.proxima_ejecucion = datetime.strptime(prox, '%Y-%m-%d').date()
            
            db.session.commit()
            
            flash(f'✅ Instalación {instalacion.codigo} actualizada correctamente', 'success')
            return redirect(url_for('servicios_generales.detalle_instalacion', instalacion_id=instalacion.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar: {str(e)}', 'error')
    
    categorias = ['Eléctrico', 'Edilicio', 'Climatización', 'Sanitario', 'Seguridad', 
                  'Iluminación', 'Puertas/Accesos', 'Redes/Datos', 'Mobiliario', 'Otros']
    sectores = ['Producción', 'Administración', 'Almacén', 'Calidad', 'Mantenimiento', 'Común']
    edificios = ['Planta Principal', 'Edificio Administrativo', 'Almacén', 'Laboratorio', 'Comedor', 'Otros']
    
    return render_template('servicios_generales/editar_instalacion.html',
                         instalacion=instalacion,
                         categorias=categorias,
                         sectores=sectores,
                         edificios=edificios,
                         now=datetime.now())


@servicios_bp.route('/instalaciones/<int:instalacion_id>/cambiar-estado', methods=['POST'])
@login_required
def cambiar_estado_instalacion(instalacion_id):
    """Cambiar estado de instalación"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos', 'error')
        return redirect(url_for('servicios_generales.gestion_instalaciones'))
    
    instalacion = Instalacion.query.get_or_404(instalacion_id)
    
    try:
        nuevo_estado = request.form.get('nuevo_estado')
        motivo = request.form.get('motivo', '')
        
        instalacion.cambiar_estado(nuevo_estado, current_user.username, motivo)
        
        flash(f'✅ Estado de {instalacion.codigo} cambiado a {nuevo_estado}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al cambiar estado: {str(e)}', 'error')
    
    return redirect(url_for('servicios_generales.detalle_instalacion', instalacion_id=instalacion_id))


@servicios_bp.route('/ejecutar/<int:orden_id>')
@login_required
def ejecutar_orden(orden_id):
    """Formulario para ejecutar/completar orden"""
    if not check_permiso_mantenimiento():
        flash('No tienes permisos', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    orden = OrdenServicioGeneral.query.get_or_404(orden_id)
    
    if orden.estado not in ['En Progreso', 'Pausada']:
        flash('Solo se pueden ejecutar órdenes en progreso', 'error')
        return redirect(url_for('servicios_generales.detalle_orden', orden_id=orden_id))
    
    materiales = Repuesto.query.filter(Repuesto.stock_actual > 0).order_by(Repuesto.codigo).all()
    
    return render_template('servicios_generales/ejecutar_orden.html',
                         orden=orden,
                         materiales=materiales)