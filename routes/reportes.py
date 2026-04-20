# routes/reportes.py
from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request, send_file
from flask_login import login_required
from models import db
from models.equipo import Equipo
from models.orden_trabajo import OrdenTrabajo
from models.inventario import Repuesto, ConsumoRepuesto
from models.sistema import PlanMantenimiento
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import pandas as pd
import io
import xlsxwriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from utils.decorators import tecnico_required

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/')
@tecnico_required
def index():
    """Página principal de reportes"""
    return render_template('reportes/index.html')

@reportes_bp.route('/cumplimiento')
@tecnico_required
def cumplimiento():
    """Reporte de cumplimiento de mantenimientos"""
    equipos = Equipo.query.all()
    return render_template('reportes/cumplimiento.html', equipos=equipos, now=datetime.now())

@reportes_bp.route('/api/cumplimiento/data')
@tecnico_required
def api_cumplimiento_data():
    """API con datos de cumplimiento"""
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    equipo_id = request.args.get('equipo_id')
    
    # Convertir fechas
    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    else:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    
    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    else:
        fecha_fin = datetime.now().date()
    
    # Query base
    query = OrdenTrabajo.query.filter(
        OrdenTrabajo.fecha_creacion >= fecha_inicio,
        OrdenTrabajo.fecha_creacion <= fecha_fin
    )
    
    if equipo_id and equipo_id != 'todos':
        query = query.filter_by(equipo_id=equipo_id)
    
    ordenes = query.all()
    
    # Estadísticas
    total_ordenes = len(ordenes)
    completadas = sum(1 for o in ordenes if o.estado == 'Completada')
    pendientes = sum(1 for o in ordenes if o.estado == 'Pendiente')
    en_progreso = sum(1 for o in ordenes if o.estado == 'En Progreso')
    canceladas = sum(1 for o in ordenes if o.estado == 'Cancelada')
    
    # Por tipo
    preventivas = sum(1 for o in ordenes if o.tipo == 'Preventivo')
    correctivas = sum(1 for o in ordenes if o.tipo == 'Correctivo')
    servicios = sum(1 for o in ordenes if o.tipo == 'Servicio')
    
    # Tiempos
    tiempos = []
    for o in ordenes:
        if o.fecha_inicio and o.fecha_fin:
            tiempo = (o.fecha_fin - o.fecha_inicio).total_seconds() / 3600
            tiempos.append(tiempo)
    
    tiempo_promedio = sum(tiempos) / len(tiempos) if tiempos else 0
    
    return jsonify({
        'fecha_inicio': fecha_inicio.strftime('%d/%m/%Y'),
        'fecha_fin': fecha_fin.strftime('%d/%m/%Y'),
        'total_ordenes': total_ordenes,
        'completadas': completadas,
        'pendientes': pendientes,
        'en_progreso': en_progreso,
        'canceladas': canceladas,
        'preventivas': preventivas,
        'correctivas': correctivas,
        'servicios': servicios,
        'tiempo_promedio': round(tiempo_promedio, 2),
        'cumplimiento': round((completadas / total_ordenes * 100) if total_ordenes > 0 else 0, 2)
    })

@reportes_bp.route('/api/cumplimiento/chart')
@tecnico_required
def api_cumplimiento_chart():
    """Datos para gráfico de cumplimiento por día"""
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    else:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    
    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    else:
        fecha_fin = datetime.now().date()
    
    # Generar lista de fechas
    fechas = []
    completadas_por_dia = []
    creadas_por_dia = []
    
    delta = fecha_fin - fecha_inicio
    for i in range(delta.days + 1):
        fecha = fecha_inicio + timedelta(days=i)
        fechas.append(fecha.strftime('%d/%m'))
        
        # Órdenes completadas en esta fecha
        completadas = OrdenTrabajo.query.filter(
            OrdenTrabajo.estado == 'Completada',
            func.date(OrdenTrabajo.fecha_fin) == fecha
        ).count()
        completadas_por_dia.append(completadas)
        
        # Órdenes creadas en esta fecha
        creadas = OrdenTrabajo.query.filter(
            func.date(OrdenTrabajo.fecha_creacion) == fecha
        ).count()
        creadas_por_dia.append(creadas)
    
    return jsonify({
        'fechas': fechas,
        'completadas': completadas_por_dia,
        'creadas': creadas_por_dia
    })

@reportes_bp.route('/inventario')
@tecnico_required
def inventario():
    """Reporte de inventario"""
    return render_template('reportes/inventario.html')

@reportes_bp.route('/api/inventario/data')
@tecnico_required
def api_inventario_data():
    """Datos para reporte de inventario con datos REALES"""
    repuestos = Repuesto.query.all()
    
    data = []
    for r in repuestos:
        # Calcular consumo en los últimos 30 días
        fecha_limite = datetime.now().date() - timedelta(days=30)
        consumos = ConsumoRepuesto.query.filter(
            ConsumoRepuesto.repuesto_id == r.id,
            ConsumoRepuesto.fecha_consumo >= fecha_limite
        ).all()
        
        consumo_30d = sum(c.cantidad for c in consumos)
        
        # Valor del inventario
        valor_total = (r.stock_actual * (r.costo_unitario or 0)) if r.costo_unitario else 0
        
        # Equipos que lo usan (datos reales de la relación)
        equipos = []
        for asig in r.equipos_asignados:
            if asig.equipo:
                equipos.append(f"{asig.equipo.code} ({asig.cantidad_por_uso}/uso)")
        
        # Estado según stock real
        if r.stock_actual <= r.stock_minimo:
            estado = 'Crítico'
            estado_color = 'danger'
        elif r.stock_actual <= r.stock_minimo * 2:
            estado = 'Bajo'
            estado_color = 'warning'
        else:
            estado = 'Normal'
            estado_color = 'success'
        
        data.append({
            'id': r.id,
            'codigo': r.codigo,
            'nombre': r.nombre,
            'categoria': r.categoria or 'Sin categoría',
            'stock_actual': r.stock_actual,
            'stock_minimo': r.stock_minimo,
            'stock_maximo': r.stock_maximo,
            'costo_unitario': r.costo_unitario,
            'valor_total': round(valor_total, 2),
            'consumo_30d': consumo_30d,
            'proveedor': r.proveedor or 'No especificado',
            'ubicacion': r.ubicacion or 'Sin ubicación',
            'estado': estado,
            'estado_color': estado_color,
            'equipos': equipos[:5]  # Máximo 5 equipos
        })
    
    return jsonify(data)

@reportes_bp.route('/indicadores')
@tecnico_required
def indicadores():
    """Reporte de indicadores GMP con datos REALES"""
    return render_template('reportes/indicadores.html')

@reportes_bp.route('/api/indicadores/data')
@tecnico_required
def api_indicadores_data():
    """Datos para indicadores GMP con datos REALES"""
    
    # Período (últimos 12 meses)
    hoy = datetime.now().date()
    hace_12_meses = hoy - timedelta(days=365)
    
    # 1. MTBF (Tiempo Medio Entre Fallas)
    # Contamos órdenes correctivas completadas en el último año
    ordenes_correctivas = OrdenTrabajo.query.filter(
        OrdenTrabajo.tipo == 'Correctivo',
        OrdenTrabajo.estado == 'Completada',
        OrdenTrabajo.fecha_creacion >= hace_12_meses
    ).count()
    
    equipos_activos = Equipo.query.count()
    # MTBF = días totales / número de fallas
    mtbf = (365 / ordenes_correctivas) if ordenes_correctivas > 0 else 365
    
    # 2. MTTR (Tiempo Medio de Reparación)
    tiempos_reparacion = []
    ordenes = OrdenTrabajo.query.filter(
        OrdenTrabajo.estado == 'Completada',
        OrdenTrabajo.fecha_inicio.isnot(None),
        OrdenTrabajo.fecha_fin.isnot(None),
        OrdenTrabajo.fecha_creacion >= hace_12_meses
    ).all()
    
    for o in ordenes:
        if o.fecha_inicio and o.fecha_fin:
            horas = (o.fecha_fin - o.fecha_inicio).total_seconds() / 3600
            if horas > 0:  # Solo tiempos positivos
                tiempos_reparacion.append(horas)
    
    mttr = sum(tiempos_reparacion) / len(tiempos_reparacion) if tiempos_reparacion else 0
    
    # 3. Cumplimiento de mantenimientos preventivos
    total_planes = PlanMantenimiento.query.filter_by(activo=True).count()
    
    # Consideramos ejecutados si tienen ultima_ejecucion en los últimos 30 días
    fecha_limite = hoy - timedelta(days=30)
    planes_ejecutados = PlanMantenimiento.query.filter(
        PlanMantenimiento.activo == True,
        PlanMantenimiento.ultima_ejecucion >= fecha_limite
    ).count()
    
    cumplimiento_pm = (planes_ejecutados / total_planes * 100) if total_planes > 0 else 0
    
    # 4. Disponibilidad de equipos
    total_equipos = Equipo.query.count()
    equipos_operativos = Equipo.query.filter_by(current_status='Operativo').count()
    equipos_mantenimiento = Equipo.query.filter_by(current_status='En Mantenimiento').count()
    equipos_fuera_servicio = Equipo.query.filter_by(current_status='Fuera de Servicio').count()
    
    disponibilidad = (equipos_operativos / total_equipos * 100) if total_equipos > 0 else 0
    
    # 5. Rotación de inventario (consumo / stock promedio)
    # Consumo anual
    consumo_anual = db.session.query(func.sum(ConsumoRepuesto.cantidad)).scalar() or 0
    
    # Stock promedio (aproximado)
    stock_promedio = db.session.query(func.avg(Repuesto.stock_actual)).scalar() or 1
    
    rotacion = (consumo_anual / stock_promedio) if stock_promedio > 0 else 0
    
    return jsonify({
        'mtbf': round(mtbf, 2),
        'mttr': round(mttr, 2),
        'cumplimiento_pm': round(cumplimiento_pm, 2),
        'disponibilidad': round(disponibilidad, 2),
        'rotacion': round(rotacion, 2),
        'equipos_operativos': equipos_operativos,
        'equipos_mantenimiento': equipos_mantenimiento,
        'equipos_fuera_servicio': equipos_fuera_servicio,
        'total_equipos': total_equipos,
        'ordenes_correctivas': ordenes_correctivas,
        'tiempo_medio_reparacion': round(mttr, 2)
    })

@reportes_bp.route('/api/indicadores/equipos')
@tecnico_required
def api_indicadores_equipos():
    """Datos de indicadores por equipo"""
    equipos = Equipo.query.all()
    data = []
    
    for equipo in equipos:
        # Órdenes del equipo
        ordenes_equipo = OrdenTrabajo.query.filter_by(equipo_id=equipo.id).all()
        total_ordenes = len(ordenes_equipo)
        correctivas = sum(1 for o in ordenes_equipo if o.tipo == 'Correctivo' and o.estado == 'Completada')
        
        # MTBF por equipo (simplificado)
        mtbf_equipo = (365 / correctivas) if correctivas > 0 else 365
        
        # Última falla
        ultima_falla = OrdenTrabajo.query.filter_by(
            equipo_id=equipo.id, 
            tipo='Correctivo'
        ).order_by(OrdenTrabajo.fecha_creacion.desc()).first()
        
        data.append({
            'nombre': equipo.name,
            'codigo': equipo.code,
            'clasificacion': equipo.gmp_classification,
            'total_ordenes': total_ordenes,
            'correctivas': correctivas,
            'mtbf': round(mtbf_equipo, 2),
            'ultima_falla': ultima_falla.fecha_creacion.strftime('%d/%m/%Y') if ultima_falla else 'N/A'
        })
    
    return jsonify(data)

@reportes_bp.route('/exportar/pdf/<tipo>')
@tecnico_required
def exportar_pdf(tipo):
    """Exportar reporte a PDF"""
    # Crear PDF en memoria
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    
    # Título
    titulo = Paragraph(f"Reporte GMP - {tipo.upper()}", title_style)
    story.append(titulo)
    story.append(Spacer(1, 0.2*inch))
    
    # Fecha
    fecha = Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style)
    story.append(fecha)
    story.append(Spacer(1, 0.2*inch))
    
    if tipo == 'cumplimiento':
        # Datos de cumplimiento
        ordenes = OrdenTrabajo.query.count()
        completadas = OrdenTrabajo.query.filter_by(estado='Completada').count()
        
        data = [
            ['Métrica', 'Valor'],
            ['Total Órdenes', str(ordenes)],
            ['Completadas', str(completadas)],
            ['Pendientes', str(OrdenTrabajo.query.filter_by(estado='Pendiente').count())],
            ['En Progreso', str(OrdenTrabajo.query.filter_by(estado='En Progreso').count())],
            ['Cumplimiento', f"{round((completadas/ordenes*100) if ordenes>0 else 0, 2)}%"]
        ]
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'reporte_{tipo}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
        mimetype='application/pdf'
    )

@reportes_bp.route('/exportar/excel/<tipo>')
@tecnico_required
def exportar_excel(tipo):
    """Exportar reporte a Excel"""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # Formatos
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4e73df',
        'color': 'white',
        'align': 'center',
        'border': 1
    })
    
    cell_format = workbook.add_format({
        'align': 'center',
        'border': 1
    })
    
    if tipo == 'cumplimiento':
        # Headers
        headers = ['Fecha', 'Órdenes Creadas', 'Órdenes Completadas', 'Cumplimiento %']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos de los últimos 30 días
        fecha_fin = datetime.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        row = 1
        delta = fecha_fin - fecha_inicio
        for i in range(delta.days + 1):
            fecha = fecha_inicio + timedelta(days=i)
            
            creadas = OrdenTrabajo.query.filter(
                func.date(OrdenTrabajo.fecha_creacion) == fecha
            ).count()
            
            completadas = OrdenTrabajo.query.filter(
                OrdenTrabajo.estado == 'Completada',
                func.date(OrdenTrabajo.fecha_fin) == fecha
            ).count()
            
            cumplimiento = (completadas / creadas * 100) if creadas > 0 else 0
            
            worksheet.write(row, 0, fecha.strftime('%d/%m/%Y'), cell_format)
            worksheet.write(row, 1, creadas, cell_format)
            worksheet.write(row, 2, completadas, cell_format)
            worksheet.write(row, 3, round(cumplimiento, 2), cell_format)
            row += 1
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'reporte_{tipo}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )