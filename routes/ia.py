# routes/ia.py
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from models import db
from models.conocimiento import Normativa, ConsultaIA, RecomendacionIA
from utils.ia_engine import ia_engine
from datetime import datetime, timedelta
from utils.decorators import tecnico_required, admin_required  # <--- ESTOS FALTABAN

ia_bp = Blueprint('ia', __name__)

@ia_bp.route('/')
@tecnico_required
def index():
    """Página principal del asistente IA"""
    return render_template('ia/index.html')

@ia_bp.route('/chat')
@tecnico_required
def chat():
    """Interfaz de chat con IA"""
    return render_template('ia/chat.html')

@ia_bp.route('/api/consultar', methods=['POST'])
@tecnico_required
def api_consultar():
    """API para consultar a la IA"""
    data = request.json
    pregunta = data.get('pregunta', '').strip()
    
    if not pregunta:
        return jsonify({'error': 'La pregunta no puede estar vacía'}), 400
    
    # Inicializar motor si es necesario
    if not ia_engine.inicializado:
        ia_engine.inicializar()
    
    # Realizar consulta
    resultado = ia_engine.consultar(pregunta, usuario=session.get('username'))
    
    return jsonify(resultado)

@ia_bp.route('/api/recomendaciones')
@tecnico_required
def api_recomendaciones():
    """API para obtener recomendaciones"""
    if not ia_engine.inicializado:
        ia_engine.inicializar()
    
    recomendaciones = ia_engine.obtener_recomendaciones()
    
    return jsonify([{
        'id': r.id,
        'tipo': r.tipo,
        'titulo': r.titulo,
        'descripcion': r.descripcion,
        'prioridad': r.prioridad,
        'fecha': r.created_at.strftime('%d/%m/%Y'),
        'equipo': r.equipo.code if r.equipo else None
    } for r in recomendaciones])

@ia_bp.route('/api/recomendaciones/<int:rec_id>/leer', methods=['POST'])
@tecnico_required
def api_marcar_leida(rec_id):
    """Marca una recomendación como leída"""
    success = ia_engine.marcar_recomendacion_leida(rec_id)
    return jsonify({'success': success})

@ia_bp.route('/api/generar-recomendaciones', methods=['POST'])
@tecnico_required
def api_generar_recomendaciones():
    """Genera nuevas recomendaciones"""
    if not ia_engine.inicializado:
        ia_engine.inicializar()
    
    recomendaciones = ia_engine.generar_recomendaciones(usuario=session.get('username'))
    
    return jsonify({
        'success': True,
        'cantidad': len(recomendaciones)
    })

@ia_bp.route('/api/historial')
@tecnico_required
def api_historial():
    """Obtiene historial de consultas"""
    consultas = ConsultaIA.query.filter_by(usuario=session.get('username')).order_by(
        ConsultaIA.created_at.desc()
    ).limit(20).all()
    
    return jsonify([{
        'id': c.id,
        'pregunta': c.pregunta,
        'respuesta': c.respuesta,
        'fecha': c.created_at.strftime('%d/%m/%Y %H:%M'),
        'feedback': c.feedback
    } for c in consultas])

@ia_bp.route('/api/feedback/<int:consulta_id>', methods=['POST'])
@tecnico_required
def api_feedback(consulta_id):
    """Registra feedback de una consulta"""
    data = request.json
    puntuacion = data.get('puntuacion')
    comentario = data.get('comentario', '')
    
    consulta = ConsultaIA.query.get_or_404(consulta_id)
    consulta.feedback = puntuacion
    consulta.comentario_feedback = comentario
    db.session.commit()
    
    return jsonify({'success': True})

# routes/ia.py (agregar esta ruta)

@ia_bp.route('/api/actualizar-normativas', methods=['POST'])
@admin_required
def api_actualizar_normativas():
    """Endpoint para forzar actualización manual de normativas"""
    try:
        from utils.actualizador_automatico import ActualizadorAutomatico
        actualizador = ActualizadorAutomatico()
        actualizador.ejecutar_actualizacion()
        
        return jsonify({
            'success': True,
            'message': 'Actualización completada'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ia_bp.route('/api/normativas/recientes')
@tecnico_required
def api_normativas_recientes():
    """Obtiene las normativas más recientes"""
    try:
        normativas = Normativa.query.order_by(Normativa.fecha_publicacion.desc()).limit(10).all()
        
        return jsonify({
            'normativas': [{
                'codigo': n.codigo,
                'titulo': n.titulo,
                'tipo': n.tipo,
                'categoria': n.categoria,
                'fecha': n.fecha_publicacion.strftime('%d/%m/%Y') if n.fecha_publicacion else 'N/A'
            } for n in normativas],
            'total': Normativa.query.count()
        })
    except Exception as e:
        print(f"Error en normativas recientes: {e}")
        return jsonify({'normativas': [], 'total': 0})

@ia_bp.route('/api/forzar-actualizacion', methods=['POST'])
@admin_required
def forzar_actualizacion():
    """Fuerza una actualización manual de normativas"""
    try:
        from utils.actualizador_automatico import ActualizadorAutomatico
        actualizador = ActualizadorAutomatico()
        nuevas = actualizador.ejecutar_actualizacion()
        
        return jsonify({
            'success': True,
            'message': f'Actualización completada. {len(nuevas) if nuevas else 0} nuevas normativas.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ia_bp.route('/api/estadisticas')
@tecnico_required
def api_estadisticas():
    """Obtiene estadísticas de uso de la IA"""
    try:
        from sqlalchemy import func
        
        # Total de consultas
        total_consultas = ConsultaIA.query.count()
        
        # Consultas hoy
        hoy = datetime.now().date()
        consultas_hoy = ConsultaIA.query.filter(
            func.date(ConsultaIA.created_at) == hoy
        ).count()
        
        # Consultas esta semana
        semana = hoy - timedelta(days=7)
        consultas_semana = ConsultaIA.query.filter(
            func.date(ConsultaIA.created_at) >= semana
        ).count()
        
        # Feedback promedio
        feedback = ConsultaIA.query.filter(ConsultaIA.feedback.isnot(None)).all()
        feedback_promedio = sum(f.feedback for f in feedback) / len(feedback) if feedback else 0
        
        # Normativas más consultadas
        from models.conocimiento import Normativa
        normativas_top = Normativa.query.order_by(Normativa.veces_consultada.desc()).limit(5).all()
        
        return jsonify({
            'total_consultas': total_consultas,
            'consultas_hoy': consultas_hoy,
            'consultas_semana': consultas_semana,
            'feedback_promedio': round(feedback_promedio, 1),
            'normativas_top': [{
                'codigo': n.codigo,
                'titulo': n.titulo,
                'veces': n.veces_consultada
            } for n in normativas_top]
        })
    except Exception as e:
        print(f"Error en estadísticas: {e}")
        return jsonify({
            'total_consultas': 0,
            'consultas_hoy': 0,
            'consultas_semana': 0,
            'feedback_promedio': 0,
            'normativas_top': []
        })

@ia_bp.route('/dashboard')
@tecnico_required
def dashboard():
    """Dashboard de estadísticas de IA"""
    return render_template('ia/dashboard.html')

# routes/ia.py - Agrega estas rutas al final

import io
import json
import pandas as pd
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime

@ia_bp.route('/api/exportar/excel')
@admin_required
def exportar_excel():
    """Exporta todas las normativas a Excel"""
    try:
        # Obtener todas las normativas
        normativas = Normativa.query.order_by(Normativa.fecha_publicacion.desc()).all()
        
        # Crear DataFrame
        data = []
        for n in normativas:
            data.append({
                'Código': n.codigo,
                'Título': n.titulo,
                'Descripción': n.descripcion,
                'Tipo': n.tipo,
                'Categoría': n.categoria,
                'Subcategoría': n.subcategoria,
                'Fecha Publicación': n.fecha_publicacion.strftime('%d/%m/%Y') if n.fecha_publicacion else '',
                'Palabras Clave': n.palabras_clave,
                'Veces Consultada': n.veces_consultada,
                'Versión': n.version
            })
        
        df = pd.DataFrame(data)
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Normativas', index=False)
            
            # Ajustar ancho de columnas
            worksheet = writer.sheets['Normativas']
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(column_width, 50))
        
        output.seek(0)
        
        # Generar nombre de archivo
        fecha = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f'normativas_gmp_{fecha}.xlsx'
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/api/exportar/json')
@admin_required
def exportar_json():
    """Exporta todas las normativas a JSON"""
    try:
        normativas = Normativa.query.order_by(Normativa.fecha_publicacion.desc()).all()
        
        data = []
        for n in normativas:
            data.append({
                'codigo': n.codigo,
                'titulo': n.titulo,
                'descripcion': n.descripcion,
                'contenido': n.contenido,
                'tipo': n.tipo,
                'categoria': n.categoria,
                'subcategoria': n.subcategoria,
                'aplica_a': n.aplica_a,
                'palabras_clave': n.palabras_clave,
                'fecha_publicacion': n.fecha_publicacion.strftime('%Y-%m-%d') if n.fecha_publicacion else None,
                'version': n.version,
                'veces_consultada': n.veces_consultada,
                'url_fuente': getattr(n, 'url_fuente', '')
            })
        
        output = io.BytesIO()
        output.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        output.seek(0)
        
        fecha = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f'normativas_gmp_{fecha}.json'
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/api/exportar/pdf')
@admin_required
def exportar_pdf():
    """Exporta las normativas más relevantes a PDF"""
    try:
        # Crear PDF en memoria
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        story = []
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        normal_style = styles['Normal']
        
        # Título
        titulo = Paragraph("Normativas GMP/ANMAT", title_style)
        story.append(titulo)
        story.append(Spacer(1, 0.2*inch))
        
        # Fecha
        fecha = Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style)
        story.append(fecha)
        story.append(Spacer(1, 0.2*inch))
        
        # Obtener normativas (últimas 50 para no saturar el PDF)
        normativas = Normativa.query.order_by(Normativa.fecha_publicacion.desc()).limit(50).all()
        
        if normativas:
            # Crear tabla
            data = [['Código', 'Título', 'Tipo', 'Categoría', 'Fecha']]
            
            for n in normativas:
                data.append([
                    n.codigo,
                    n.titulo[:50] + '...' if len(n.titulo) > 50 else n.titulo,
                    n.tipo,
                    n.categoria,
                    n.fecha_publicacion.strftime('%d/%m/%Y') if n.fecha_publicacion else ''
                ])
            
            table = Table(data, colWidths=[100, 200, 80, 100, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(table)
            
            # Agregar estadísticas
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph(f"Total de normativas: {len(normativas)}", normal_style))
            story.append(Paragraph(f"Tipos: GMP: {sum(1 for n in normativas if n.tipo=='GMP')}, ANMAT: {sum(1 for n in normativas if n.tipo=='ANMAT')}", normal_style))
        else:
            story.append(Paragraph("No hay normativas cargadas en el sistema.", normal_style))
        
        doc.build(story)
        buffer.seek(0)
        
        fecha = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f'normativas_gmp_{fecha}.pdf'
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/api/exportar/seleccion', methods=['POST'])
@admin_required
def exportar_seleccion():
    """Exporta normativas seleccionadas"""
    try:
        data = request.json
        ids = data.get('ids', [])
        formato = data.get('formato', 'json')
        
        if not ids:
            return jsonify({'error': 'No se seleccionaron normativas'}), 400
        
        normativas = Normativa.query.filter(Normativa.id.in_(ids)).all()
        
        if formato == 'json':
            # Exportar a JSON
            output = io.BytesIO()
            data = []
            for n in normativas:
                data.append({
                    'codigo': n.codigo,
                    'titulo': n.titulo,
                    'descripcion': n.descripcion,
                    'contenido': n.contenido,
                    'tipo': n.tipo,
                    'categoria': n.categoria
                })
            
            output.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
            output.seek(0)
            
            filename = f'normativas_seleccionadas_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
            mimetype = 'application/json'
            
        elif formato == 'excel':
            # Exportar a Excel
            data = []
            for n in normativas:
                data.append({
                    'Código': n.codigo,
                    'Título': n.titulo,
                    'Descripción': n.descripcion,
                    'Tipo': n.tipo,
                    'Categoría': n.categoria
                })
            
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Normativas', index=False)
            
            output.seek(0)
            filename = f'normativas_seleccionadas_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

