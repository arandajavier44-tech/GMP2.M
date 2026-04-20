# routes/cambios.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.cambio import Cambio, HistorialCambio
from models.equipo import Equipo
from models.sistema import SistemaEquipo
from models.orden_trabajo import OrdenTrabajo
from models.usuario import Usuario
from datetime import datetime
from utils.decorators import admin_required, tecnico_required
import json

cambios_bp = Blueprint('cambios', __name__)

@cambios_bp.route('/')
@tecnico_required
def gestion_cambios():
    """Listado de cambios"""
    cambios = Cambio.query.order_by(Cambio.fecha_solicitud.desc()).all()
    
    # Estadísticas
    en_revision = Cambio.query.filter_by(estado='En Revisión').count()
    aprobados = Cambio.query.filter_by(estado='Aprobado').count()
    implementados = Cambio.query.filter_by(estado='Implementado').count()
    
    return render_template('cambios/gestion_cambios.html',
                         cambios=cambios,
                         en_revision=en_revision,
                         aprobados=aprobados,
                         implementados=implementados)

@cambios_bp.route('/nuevo', methods=['GET', 'POST'])
@tecnico_required
def nuevo_cambio():
    """Solicitar nuevo cambio"""
    if request.method == 'POST':
        try:
            # Generar número de cambio
            import random
            import string
            año = datetime.now().year
            mes = datetime.now().strftime('%m')
            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            numero_cambio = f"CC-{año}{mes}-{random_chars}"
            
            nuevo = Cambio(
                numero_cambio=numero_cambio,
                equipo_id=request.form.get('equipo_id') or None,
                sistema_id=request.form.get('sistema_id') or None,
                orden_trabajo_id=request.form.get('orden_trabajo_id') or None,
                titulo=request.form.get('titulo'),
                descripcion=request.form.get('descripcion'),
                tipo=request.form.get('tipo'),
                clasificacion_gmp=request.form.get('clasificacion_gmp'),
                impacto_calidad=request.form.get('impacto_calidad'),
                impacto_validacion=request.form.get('impacto_validacion'),
                estado='Borrador',
                solicitante_nombre=session.get('nombre_completo') or session.get('username'),
                departamento=request.form.get('departamento'),
                motivo=request.form.get('motivo'),
                beneficio=request.form.get('beneficio'),
                riesgo=request.form.get('riesgo'),
                cambio_propuesto=request.form.get('cambio_propuesto'),
                estado_actual=request.form.get('estado_actual'),
                estado_nuevo=request.form.get('estado_nuevo'),
                documentos_afectados=request.form.get('documentos_afectados'),
                nuevos_documentos=request.form.get('nuevos_documentos'),
                requiere_validacion=bool(request.form.get('requiere_validacion')),
                plan_validacion=request.form.get('plan_validacion'),
                created_by=session.get('username')
            )
            
            db.session.add(nuevo)
            db.session.flush()
            
            # Registrar historial
            registrar_historial(
                nuevo.id,
                'CREACIÓN',
                None,
                'Solicitud de cambio creada',
                session.get('username')
            )
            
            db.session.commit()
            
            flash(f'Solicitud de cambio {numero_cambio} creada exitosamente', 'success')
            return redirect(url_for('cambios.detalle_cambio', cambio_id=nuevo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear solicitud: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    sistemas = SistemaEquipo.query.all()
    ordenes = OrdenTrabajo.query.filter(OrdenTrabajo.estado.in_(['Pendiente', 'En Progreso'])).all()
    
    return render_template('cambios/nuevo_cambio.html',
                         equipos=equipos,
                         sistemas=sistemas,
                         ordenes=ordenes,
                         now=datetime.now())

@cambios_bp.route('/<int:cambio_id>')
@tecnico_required
def detalle_cambio(cambio_id):
    """Ver detalle del cambio"""
    cambio = Cambio.query.get_or_404(cambio_id)
    return render_template('cambios/detalle_cambio.html', cambio=cambio)

@cambios_bp.route('/<int:cambio_id>/editar', methods=['GET', 'POST'])
@tecnico_required
def editar_cambio(cambio_id):
    """Editar cambio (solo si está en Borrador)"""
    cambio = Cambio.query.get_or_404(cambio_id)
    
    if cambio.estado != 'Borrador':
        flash('No se puede editar un cambio que no está en Borrador', 'error')
        return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))
    
    if request.method == 'POST':
        try:
            # Guardar valores anteriores
            valores_anteriores = {
                'titulo': cambio.titulo,
                'descripcion': cambio.descripcion,
                'clasificacion_gmp': cambio.clasificacion_gmp,
                'impacto_calidad': cambio.impacto_calidad
            }
            
            # Actualizar campos
            cambio.titulo = request.form.get('titulo')
            cambio.descripcion = request.form.get('descripcion')
            cambio.clasificacion_gmp = request.form.get('clasificacion_gmp')
            cambio.impacto_calidad = request.form.get('impacto_calidad')
            cambio.impacto_validacion = request.form.get('impacto_validacion')
            cambio.motivo = request.form.get('motivo')
            cambio.beneficio = request.form.get('beneficio')
            cambio.riesgo = request.form.get('riesgo')
            cambio.cambio_propuesto = request.form.get('cambio_propuesto')
            cambio.estado_actual = request.form.get('estado_actual')
            cambio.estado_nuevo = request.form.get('estado_nuevo')
            cambio.updated_by = session.get('username')
            
            db.session.commit()
            
            # Registrar cambios en historial
            for campo, valor_anterior in valores_anteriores.items():
                valor_nuevo = getattr(cambio, campo)
                if str(valor_anterior) != str(valor_nuevo):
                    registrar_historial(
                        cambio.id,
                        'MODIFICACIÓN',
                        campo,
                        f'{valor_anterior} -> {valor_nuevo}',
                        session.get('username')
                    )
            
            flash('Cambio actualizado correctamente', 'success')
            return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    sistemas = SistemaEquipo.query.all()
    return render_template('cambios/editar_cambio.html', cambio=cambio, equipos=equipos, sistemas=sistemas)

@cambios_bp.route('/<int:cambio_id>/enviar-revision', methods=['POST'])
@tecnico_required
def enviar_revision(cambio_id):
    """Enviar cambio a revisión"""
    cambio = Cambio.query.get_or_404(cambio_id)
    
    try:
        cambio.estado = 'En Revisión'
        registrar_historial(
            cambio.id,
            'ENVÍO A REVISIÓN',
            None,
            'Solicitud enviada para revisión',
            session.get('username')
        )
        db.session.commit()
        flash('Solicitud enviada a revisión', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al enviar: {str(e)}', 'error')
    
    return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))

@cambios_bp.route('/<int:cambio_id>/aprobar', methods=['POST'])
@admin_required
def aprobar_cambio(cambio_id):
    """Aprobar cambio (solo admin/calidad)"""
    cambio = Cambio.query.get_or_404(cambio_id)
    nivel = request.form.get('nivel')  # '1', '2', 'calidad'
    comentarios = request.form.get('comentarios')
    
    try:
        if nivel == '1':
            cambio.aprobador_1_nombre = session.get('nombre_completo') or session.get('username')
            cambio.aprobador_1_fecha = datetime.utcnow()
            cambio.aprobador_1_comentarios = comentarios
            accion = 'APROBACIÓN NIVEL 1'
        elif nivel == '2':
            cambio.aprobador_2_nombre = session.get('nombre_completo') or session.get('username')
            cambio.aprobador_2_fecha = datetime.utcnow()
            cambio.aprobador_2_comentarios = comentarios
            accion = 'APROBACIÓN NIVEL 2'
        elif nivel == 'calidad':
            cambio.aprobador_calidad_nombre = session.get('nombre_completo') or session.get('username')
            cambio.aprobador_calidad_fecha = datetime.utcnow()
            cambio.aprobador_calidad_comentarios = comentarios
            cambio.estado = 'Aprobado'
            cambio.fecha_aprobacion = datetime.utcnow()
            accion = 'APROBACIÓN CALIDAD'
        
        registrar_historial(
            cambio.id,
            accion,
            None,
            f'Aprobado por {session.get("username")}. Comentarios: {comentarios}',
            session.get('username')
        )
        
        db.session.commit()
        flash(f'Cambio aprobado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al aprobar: {str(e)}', 'error')
    
    return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))

@cambios_bp.route('/<int:cambio_id>/rechazar', methods=['POST'])
@admin_required
def rechazar_cambio(cambio_id):
    """Rechazar cambio"""
    cambio = Cambio.query.get_or_404(cambio_id)
    motivo = request.form.get('motivo')
    
    try:
        cambio.estado = 'Rechazado'
        
        registrar_historial(
            cambio.id,
            'RECHAZO',
            None,
            f'Rechazado. Motivo: {motivo}',
            session.get('username')
        )
        
        db.session.commit()
        flash('Cambio rechazado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al rechazar: {str(e)}', 'error')
    
    return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))

@cambios_bp.route('/<int:cambio_id>/implementar', methods=['POST'])
@tecnico_required
def implementar_cambio(cambio_id):
    """Registrar implementación del cambio"""
    cambio = Cambio.query.get_or_404(cambio_id)
    
    try:
        cambio.estado = 'Implementado'
        cambio.implementado_por = session.get('nombre_completo') or session.get('username')
        cambio.fecha_implementacion_real = datetime.utcnow()
        cambio.comentarios_implementacion = request.form.get('comentarios')
        
        registrar_historial(
            cambio.id,
            'IMPLEMENTACIÓN',
            None,
            f'Implementado por {session.get("username")}',
            session.get('username')
        )
        
        db.session.commit()
        flash('Cambio implementado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al implementar: {str(e)}', 'error')
    
    return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))

@cambios_bp.route('/<int:cambio_id>/verificar', methods=['POST'])
@admin_required
def verificar_cambio(cambio_id):
    """Verificar eficacia del cambio"""
    cambio = Cambio.query.get_or_404(cambio_id)
    
    try:
        cambio.estado = 'Cerrado'
        cambio.verificador_nombre = session.get('nombre_completo') or session.get('username')
        cambio.fecha_verificacion = datetime.utcnow()
        cambio.resultado_verificacion = request.form.get('resultado')
        cambio.comentarios_verificacion = request.form.get('comentarios')
        cambio.fecha_cierre = datetime.utcnow()
        
        registrar_historial(
            cambio.id,
            'VERIFICACIÓN',
            None,
            f'Verificado por {session.get("username")}. Resultado: {request.form.get("resultado")}',
            session.get('username')
        )
        
        db.session.commit()
        flash('Verificación registrada. Cambio cerrado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al verificar: {str(e)}', 'error')
    
    return redirect(url_for('cambios.detalle_cambio', cambio_id=cambio.id))

@cambios_bp.route('/api/sistemas-por-equipo/<int:equipo_id>')
@tecnico_required
def api_sistemas_por_equipo(equipo_id):
    """API para obtener sistemas de un equipo"""
    sistemas = SistemaEquipo.query.filter_by(equipo_id=equipo_id).all()
    return jsonify([{
        'id': s.id,
        'nombre': s.nombre,
        'categoria': s.categoria
    } for s in sistemas])

def registrar_historial(cambio_id, accion, campo, detalle, usuario):
    """Registra acción en el historial"""
    historial = HistorialCambio(
        cambio_id=cambio_id,
        usuario=usuario,
        accion=accion,
        campo=campo,
        valor_nuevo=detalle
    )
    db.session.add(historial)