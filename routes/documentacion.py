# routes/documentacion.py
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models.documento import DocumentoGMP
from models.equipo import Equipo
from models.calibracion import Calibracion
from utils.generador_documentos import generador_docs  # UNIFICADO
from datetime import datetime
from utils.decorators import tecnico_required, admin_required
from utils.qr_system import QRTrazabilidad
import io

documentacion_bp = Blueprint('documentacion', __name__)


@documentacion_bp.route('/')
@tecnico_required
def index():
    """Página principal de documentación"""
    documentos = DocumentoGMP.query.order_by(DocumentoGMP.fecha_creacion.desc()).limit(50).all()
    equipos = Equipo.query.all()
    calibraciones = Calibracion.query.order_by(Calibracion.fecha_calibracion.desc()).limit(20).all()
    return render_template('documentacion/index.html',
                         documentos=documentos,
                         equipos=equipos,
                         calibraciones=calibraciones)


# ============================================
# RUTAS PARA GENERAR DOCUMENTOS
# ============================================

@documentacion_bp.route('/api/generar/sop/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_sop(equipo_id):
    try:
        doc = generador_docs.generar_sop_equipo(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/sop-mantenimiento/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_sop_mantenimiento(equipo_id):
    try:
        doc = generador_docs.generar_sop_mantenimiento(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/sop-calibracion/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_sop_calibracion(equipo_id):
    try:
        doc = generador_docs.generar_sop_calibracion(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/sop-limpieza/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_sop_limpieza(equipo_id):
    try:
        doc = generador_docs.generar_sop_limpieza(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/ficha/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_ficha(equipo_id):
    try:
        doc = generador_docs.generar_ficha_tecnica(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/reporte/<int:equipo_id>', methods=['POST'])
@tecnico_required
def api_generar_reporte(equipo_id):
    try:
        doc = generador_docs.generar_reporte_mantenimiento(equipo_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/protocolo/<int:equipo_id>/<tipo>', methods=['POST'])
@tecnico_required
def api_generar_protocolo(equipo_id, tipo):
    try:
        doc = generador_docs.generar_protocolo_validacion(equipo_id, tipo, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/generar/certificado/<int:calibracion_id>', methods=['POST'])
@tecnico_required
def api_generar_certificado(calibracion_id):
    try:
        doc = generador_docs.generar_certificado_calibracion(calibracion_id, current_user.username)
        _generar_qr_documento(doc)
        return jsonify({'success': True, 'documento_id': doc.id, 'codigo': doc.codigo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _generar_qr_documento(doc):
    """Función auxiliar para generar QR de un documento"""
    try:
        qr_path = QRTrazabilidad.generar_qr(doc, 'documento')
        if qr_path:
            doc.qr_code = qr_path
            db.session.commit()
            print(f"✅ QR generado para documento: {doc.codigo}")
    except Exception as qr_error:
        print(f"⚠️ Error generando QR: {qr_error}")


# ============================================
# RUTAS PARA VER Y EDITAR DOCUMENTOS
# ============================================

@documentacion_bp.route('/ver/<int:documento_id>')
@tecnico_required
def ver_documento(documento_id):
    doc = DocumentoGMP.query.get_or_404(documento_id)
    return render_template('documentacion/ver.html', documento=doc)


@documentacion_bp.route('/print/<int:documento_id>')
@tecnico_required
def print_documento(documento_id):
    doc = DocumentoGMP.query.get_or_404(documento_id)
    return render_template('documentacion/print.html', documento=doc)


@documentacion_bp.route('/editar/<int:documento_id>')
@tecnico_required
def editar_documento(documento_id):
    doc = DocumentoGMP.query.get_or_404(documento_id)
    return render_template('documentacion/editar.html', documento=doc)


# ============================================
# API PARA GUARDAR Y EDITAR
# ============================================

@documentacion_bp.route('/api/guardar/<int:documento_id>', methods=['POST'])
@tecnico_required
def api_guardar_documento(documento_id):
    data = request.json
    doc = DocumentoGMP.query.get_or_404(documento_id)

    try:
        if data.get('titulo'):
            doc.titulo = data['titulo']
        if data.get('contenido'):
            doc.contenido = data['contenido']

        cambios = data.get('cambios', [])
        historial_actual = doc.historial_cambios or []

        for cambio in cambios:
            historial_actual.append({
                'campo': cambio['campo'],
                'valor': cambio['valor'],
                'usuario': current_user.username,
                'fecha': datetime.now().isoformat()
            })

        doc.historial_cambios = historial_actual
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/api/eliminar/<int:documento_id>', methods=['POST'])
@admin_required
def api_eliminar_documento(documento_id):
    try:
        doc = DocumentoGMP.query.get_or_404(documento_id)
        db.session.delete(doc)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@documentacion_bp.route('/por-equipo/<int:equipo_id>')
@tecnico_required
def por_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    documentos_asignados = DocumentoGMP.query.filter(
        db.or_(
            DocumentoGMP.equipo_id == equipo_id,
            DocumentoGMP.equipos_asignados.any(id=equipo_id)
        )
    ).order_by(DocumentoGMP.fecha_creacion.desc()).all()

    return render_template('documentacion/equipo_docs.html',
                         equipo=equipo,
                         documentos=documentos_asignados)


# routes/documentacion.py - Agregar esta nueva ruta

@documentacion_bp.route('/por-equipos')
@tecnico_required
def documentacion_por_equipos():
    """Vista organizada por equipos con toda su documentación"""
    equipos = Equipo.query.order_by(Equipo.code).all()
    
    # Organizar documentación por equipo
    equipos_docs = []
    for equipo in equipos:
        # Buscar todos los documentos del equipo
        documentos = DocumentoGMP.query.filter(
            db.or_(
                DocumentoGMP.equipo_id == equipo.id,
                DocumentoGMP.equipos_asignados.any(id=equipo.id)
            )
        ).order_by(DocumentoGMP.fecha_creacion.desc()).all()
        
        # Clasificar documentos por tipo
        docs_por_tipo = {
            'sop': [],
            'sop_mantenimiento': [],
            'sop_calibracion': [],
            'sop_limpieza': [],
            'ficha': [],
            'reporte': [],
            'protocolo': [],
            'certificado': [],
            'plan': []
        }
        
        for doc in documentos:
            tipo = doc.tipo
            if tipo in docs_por_tipo:
                docs_por_tipo[tipo].append(doc)
            else:
                docs_por_tipo['sop'].append(doc)
        
        # Obtener matriz de riesgos asociada al equipo
        riesgos = []
        try:
            from models.riesgo import MatrizRiesgo, RiesgoIdentificado
            
            # Buscar matrices de riesgo para este equipo
            matrices = MatrizRiesgo.query.filter_by(equipo_id=equipo.id).all()
            
            # Recopilar todos los riesgos identificados
            for matriz in matrices:
                # Si la matriz tiene riesgos en JSON
                if matriz.riesgos:
                    for riesgo_data in matriz.riesgos:
                        if isinstance(riesgo_data, dict):
                            riesgos.append({
                                'id': riesgo_data.get('id', 0),
                                'descripcion': riesgo_data.get('descripcion', ''),
                                'probabilidad': riesgo_data.get('probabilidad', 'N/A'),
                                'severidad': riesgo_data.get('severidad', 'N/A'),
                                'nivel_riesgo': riesgo_data.get('nivel_riesgo', 'Bajo'),
                                'estado': matriz.estado if hasattr(matriz, 'estado') else 'Activo'
                            })
                
                # Si tiene riesgos relacionados via relationship
                if hasattr(matriz, 'riesgos_list'):
                    for riesgo in matriz.riesgos_list:
                        # Calcular nivel de riesgo basado en NPR
                        nivel = 'Bajo'
                        if riesgo.npr and riesgo.npr >= 100:
                            nivel = 'Alto'
                        elif riesgo.npr and riesgo.npr >= 40:
                            nivel = 'Medio'
                        
                        riesgos.append({
                            'id': riesgo.id,
                            'codigo': riesgo.codigo,
                            'descripcion': riesgo.descripcion,
                            'probabilidad': riesgo.ocurrencia,
                            'severidad': riesgo.severidad,
                            'nivel_riesgo': nivel,
                            'estado': riesgo.estado,
                            'npr': riesgo.npr
                        })
        except ImportError as e:
            print(f"⚠️ Error importando modelo de riesgos: {e}")
        except Exception as e:
            print(f"⚠️ Error consultando riesgos: {e}")
        
        # Obtener color de estado
        estado_color = 'green'
        if equipo.current_status == 'En Mantenimiento':
            estado_color = 'yellow'
        elif equipo.current_status == 'Fuera de Servicio':
            estado_color = 'red'
        elif equipo.current_status == 'Calibración Vencida':
            estado_color = 'red'
        
        equipos_docs.append({
            'equipo': equipo,
            'documentos': docs_por_tipo,
            'total_documentos': len(documentos),
            'riesgos': riesgos,
            'estado_color': estado_color
        })
    
    return render_template('documentacion/por_equipos.html', equipos_docs=equipos_docs)