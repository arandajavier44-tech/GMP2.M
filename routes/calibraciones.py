# routes/calibraciones.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.calibracion import Calibracion, HistorialCalibracion
from models.equipo import Equipo
from datetime import datetime, date, timedelta
from utils.decorators import admin_required, tecnico_required
from utils.notificador_bd import notificador_bd
from utils.qr_generator import QRPersonalizado
from werkzeug.utils import secure_filename
from utils.qr_system import QRTrazabilidad
import os
import uuid


calibraciones_bp = Blueprint('calibraciones', __name__)


@calibraciones_bp.route('/')
@tecnico_required
def gestion_calibraciones():
    """Listado de calibraciones con semáforo"""
    calibraciones = Calibracion.query.order_by(Calibracion.fecha_proxima).all()
    
    hoy = date.today()
    vencidas = sum(1 for c in calibraciones if c.fecha_proxima < hoy)
    por_vencer = sum(1 for c in calibraciones if (c.fecha_proxima - hoy).days <= 30 and c.fecha_proxima >= hoy)
    vigentes = sum(1 for c in calibraciones if (c.fecha_proxima - hoy).days > 30)
    
    return render_template('calibraciones/gestion_calibraciones.html',
                         calibraciones=calibraciones,
                         vencidas=vencidas,
                         por_vencer=por_vencer,
                         vigentes=vigentes)


@calibraciones_bp.route('/<int:calibracion_id>')
@tecnico_required
def detalle_calibracion(calibracion_id):
    """Ver detalle de calibración"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    return render_template('calibraciones/detalle_calibracion.html', calibracion=calibracion)


@calibraciones_bp.route('/nueva', methods=['GET', 'POST'])
@admin_required
def nueva_calibracion():
    """Registrar nueva calibración"""
    if request.method == 'POST':
        try:
            fecha_cal = datetime.strptime(request.form.get('fecha_calibracion'), '%Y-%m-%d').date()
            frecuencia = int(request.form.get('frecuencia_dias', 365))
            fecha_prox = fecha_cal + timedelta(days=frecuencia)
            fecha_aviso = fecha_prox - timedelta(days=30)
            
            nueva = Calibracion(
                equipo_id=request.form.get('equipo_id'),
                instrumento=request.form.get('instrumento'),
                codigo_instrumento=request.form.get('codigo_instrumento'),
                marca=request.form.get('marca'),
                modelo=request.form.get('modelo'),
                serie=request.form.get('serie'),
                rango=request.form.get('rango'),
                unidad=request.form.get('unidad'),
                tolerancia=request.form.get('tolerancia'),
                precision=request.form.get('precision'),
                clasificacion_gmp=request.form.get('clasificacion_gmp'),
                frecuencia_dias=frecuencia,
                fecha_calibracion=fecha_cal,
                fecha_proxima=fecha_prox,
                fecha_aviso=fecha_aviso,
                laboratorio=request.form.get('laboratorio'),
                certificado_numero=request.form.get('certificado_numero'),
                resultado=request.form.get('resultado'),
                observaciones=request.form.get('observaciones'),
                acciones_correctivas=request.form.get('acciones_correctivas'),
                patron_utilizado=request.form.get('patron_utilizado'),
                patron_certificado=request.form.get('patron_certificado'),
                trazabilidad=request.form.get('trazabilidad'),
                temperatura=request.form.get('temperatura'),
                humedad=request.form.get('humedad'),
                realizado_por=request.form.get('realizado_por'),
                revisado_por=request.form.get('revisado_por'),
                aprobado_por=request.form.get('aprobado_por'),
                estado='Activo',
                created_by=session.get('username')
            )
            
            # Procesar archivo de certificado
            if 'certificado_archivo' in request.files:
                file = request.files['certificado_archivo']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    nuevo_nombre = f"cert_{uuid.uuid4().hex}.{ext}"
                    
                    upload_dir = os.path.join('static', 'uploads', 'certificados')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    file.save(os.path.join(upload_dir, nuevo_nombre))
                    nueva.certificado_archivo = f"uploads/certificados/{nuevo_nombre}"
            
            db.session.add(nueva)
            db.session.commit()
            
            # Registrar en historial
            registrar_historial(nueva.id, 'CREACIÓN', '', 'Nueva calibración', session.get('username'))
            
            # Generar notificación de calibración
            try:
                notificador_bd.notificar_calibracion(nueva, frecuencia)
            except:
                pass
            
            flash('Calibración registrada exitosamente', 'success')
            return redirect(url_for('calibraciones.gestion_calibraciones'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    now = datetime.now()
    return render_template('calibraciones/nueva_calibracion.html', equipos=equipos, now=now)


@calibraciones_bp.route('/<int:calibracion_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_calibracion(calibracion_id):
    """Editar calibración"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    
    if request.method == 'POST':
        try:
            valores_anteriores = {
                'instrumento': calibracion.instrumento,
                'fecha_calibracion': calibracion.fecha_calibracion,
                'fecha_proxima': calibracion.fecha_proxima,
                'resultado': calibracion.resultado,
                'estado': calibracion.estado
            }
            
            calibracion.instrumento = request.form.get('instrumento')
            calibracion.marca = request.form.get('marca')
            calibracion.modelo = request.form.get('modelo')
            calibracion.serie = request.form.get('serie')
            calibracion.codigo_instrumento = request.form.get('codigo_instrumento')
            calibracion.rango = request.form.get('rango')
            calibracion.unidad = request.form.get('unidad')
            calibracion.tolerancia = request.form.get('tolerancia')
            calibracion.precision = request.form.get('precision')
            calibracion.clasificacion_gmp = request.form.get('clasificacion_gmp')
            calibracion.laboratorio = request.form.get('laboratorio')
            calibracion.certificado_numero = request.form.get('certificado_numero')
            calibracion.resultado = request.form.get('resultado')
            calibracion.observaciones = request.form.get('observaciones')
            calibracion.acciones_correctivas = request.form.get('acciones_correctivas')
            calibracion.patron_utilizado = request.form.get('patron_utilizado')
            calibracion.patron_certificado = request.form.get('patron_certificado')
            calibracion.trazabilidad = request.form.get('trazabilidad')
            calibracion.temperatura = request.form.get('temperatura')
            calibracion.humedad = request.form.get('humedad')
            calibracion.realizado_por = request.form.get('realizado_por')
            calibracion.revisado_por = request.form.get('revisado_por')
            calibracion.aprobado_por = request.form.get('aprobado_por')
            calibracion.estado = request.form.get('estado')
            
            # Actualizar frecuencia y fechas si cambió
            nueva_frecuencia = int(request.form.get('frecuencia_dias', calibracion.frecuencia_dias))
            if nueva_frecuencia != calibracion.frecuencia_dias:
                calibracion.frecuencia_dias = nueva_frecuencia
                calibracion.fecha_proxima = calibracion.fecha_calibracion + timedelta(days=nueva_frecuencia)
                calibracion.fecha_aviso = calibracion.fecha_proxima - timedelta(days=30)
            
            # Actualizar fecha de calibración si cambió
            nueva_fecha_cal = datetime.strptime(request.form.get('fecha_calibracion'), '%Y-%m-%d').date()
            if nueva_fecha_cal != calibracion.fecha_calibracion:
                calibracion.fecha_calibracion = nueva_fecha_cal
                calibracion.fecha_proxima = nueva_fecha_cal + timedelta(days=calibracion.frecuencia_dias)
                calibracion.fecha_aviso = calibracion.fecha_proxima - timedelta(days=30)
            
            # Procesar nuevo certificado si se subió
            if 'certificado_archivo' in request.files:
                file = request.files['certificado_archivo']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    nuevo_nombre = f"cert_{uuid.uuid4().hex}.{ext}"
                    
                    upload_dir = os.path.join('static', 'uploads', 'certificados')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Eliminar archivo anterior si existe
                    if calibracion.certificado_archivo:
                        old_path = os.path.join('static', calibracion.certificado_archivo)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    file.save(os.path.join(upload_dir, nuevo_nombre))
                    calibracion.certificado_archivo = f"uploads/certificados/{nuevo_nombre}"
            
            db.session.commit()
            
            # Registrar cambios en historial
            for campo, valor_anterior in valores_anteriores.items():
                valor_nuevo = getattr(calibracion, campo)
                if str(valor_anterior) != str(valor_nuevo):
                    registrar_historial(
                        calibracion.id,
                        campo,
                        str(valor_anterior),
                        str(valor_nuevo),
                        session.get('username')
                    )
            
            flash('Calibración actualizada exitosamente', 'success')
            return redirect(url_for('calibraciones.detalle_calibracion', calibracion_id=calibracion.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    return render_template('calibraciones/editar_calibracion.html', calibracion=calibracion, equipos=equipos)


@calibraciones_bp.route('/<int:calibracion_id>/cambiar-estado', methods=['POST'])
@tecnico_required
def cambiar_estado(calibracion_id):
    """Cambiar estado (Activo/Baja/Fuera de Servicio)"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    nuevo_estado = request.form.get('estado')
    motivo = request.form.get('motivo')
    
    try:
        estado_anterior = calibracion.estado
        calibracion.estado = nuevo_estado
        calibracion.observaciones = f"{calibracion.observaciones or ''}\nCambio de estado: {estado_anterior} -> {nuevo_estado}. Motivo: {motivo}".strip()
        
        db.session.commit()
        
        registrar_historial(
            calibracion.id,
            'ESTADO',
            estado_anterior,
            nuevo_estado,
            session.get('username'),
            motivo
        )
        
        flash(f'Estado cambiado a {nuevo_estado}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar estado: {str(e)}', 'error')
    
    return redirect(url_for('calibraciones.detalle_calibracion', calibracion_id=calibracion.id))


@calibraciones_bp.route('/<int:calibracion_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_calibracion(calibracion_id):
    """Eliminar calibración (solo admin)"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    
    try:
        if calibracion.certificado_archivo:
            ruta = os.path.join('static', calibracion.certificado_archivo)
            if os.path.exists(ruta):
                os.remove(ruta)
        
        db.session.delete(calibracion)
        db.session.commit()
        flash('Calibración eliminada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('calibraciones.gestion_calibraciones'))


@calibraciones_bp.route('/<int:calibracion_id>/print')
@tecnico_required
def detalle_calibracion_print(calibracion_id):
    """Vista optimizada para impresión del certificado"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    return render_template('calibraciones/detalle_calibracion_print.html', calibracion=calibracion)


@calibraciones_bp.route('/<int:calibracion_id>/adjuntar', methods=['POST'])
@admin_required
def adjuntar_documento(calibracion_id):
    """Adjuntar documento adicional a la calibración"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    
    if 'documento' not in request.files:
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('calibraciones.detalle_calibracion', calibracion_id=calibracion.id))
    
    file = request.files['documento']
    if file and file.filename:
        try:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            nuevo_nombre = f"doc_{calibracion_id}_{uuid.uuid4().hex}.{ext}"
            
            upload_dir = os.path.join('static', 'uploads', 'calibraciones', str(calibracion_id))
            os.makedirs(upload_dir, exist_ok=True)
            
            file.save(os.path.join(upload_dir, nuevo_nombre))
            
            # Aquí puedes guardar la referencia en una tabla de documentos adicionales
            # Por ahora, agregamos al campo observaciones
            tipo_doc = request.form.get('tipo_documento', 'documento')
            descripcion = request.form.get('descripcion', 'Documento adjunto')
            
            observacion_adicional = f"\n[{tipo_doc}] {descripcion}: {nuevo_nombre}"
            calibracion.observaciones = (calibracion.observaciones or '') + observacion_adicional
            db.session.commit()
            
            flash('Documento adjuntado correctamente', 'success')
        except Exception as e:
            flash(f'Error al adjuntar documento: {str(e)}', 'error')
    
    return redirect(url_for('calibraciones.detalle_calibracion', calibracion_id=calibracion.id))


@calibraciones_bp.route('/api/resumen')
@tecnico_required
def api_resumen_calibraciones():
    """API para obtener resumen de calibraciones"""
    calibraciones = Calibracion.query.all()
    hoy = date.today()
    
    vencidas = sum(1 for c in calibraciones if c.fecha_proxima < hoy)
    por_vencer = sum(1 for c in calibraciones if (c.fecha_proxima - hoy).days <= 30 and c.fecha_proxima >= hoy)
    vigentes = sum(1 for c in calibraciones if (c.fecha_proxima - hoy).days > 30)
    
    return jsonify({
        'vencidas': vencidas,
        'por_vencer': por_vencer,
        'vigentes': vigentes,
        'total': len(calibraciones)
    })


def registrar_historial(calibracion_id, campo, valor_anterior, valor_nuevo, usuario, motivo=None):
    """Registra cambios en el historial"""
    historial = HistorialCalibracion(
        calibracion_id=calibracion_id,
        campo_modificado=campo,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
        modificado_por=usuario
    )
    db.session.add(historial)
    db.session.commit()

@calibraciones_bp.route('/<int:calibracion_id>/generar_qr', methods=['POST'])
@admin_required
def generar_qr_calibracion(calibracion_id):
    """Generar código QR personalizado para calibración"""
    calibracion = Calibracion.query.get_or_404(calibracion_id)
    
    try:
        qr_path = QRPersonalizado.generar_qr_calibracion(calibracion)
        if qr_path:
            calibracion.qr_code = qr_path
            db.session.commit()
            flash('Código QR generado exitosamente', 'success')
        else:
            flash('Error al generar QR', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('calibraciones.detalle_calibracion', calibracion_id=calibracion.id))

def generar_qr_calibracion(calibracion):
    """Genera QR de trazabilidad para la calibración"""
    try:
        return QRTrazabilidad.generar_qr(calibracion, 'calibracion')
    except Exception as e:
        print(f"Error generando QR para calibración: {e}")
        return None


