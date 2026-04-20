# routes/inspecciones.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db
from models.equipo import Equipo
from models.inspeccion import PlantillaInspeccion, InspeccionRealizada, ItemInspeccion
from datetime import datetime, date, timedelta
from utils.decorators import tecnico_required, admin_required
import json
import os
from werkzeug.utils import secure_filename

inspecciones_bp = Blueprint('inspecciones', __name__)

# Configuración para fotos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================
# GESTIÓN DE PLANTILLAS
# ============================================

@inspecciones_bp.route('/')
@tecnico_required
def index():
    plantillas = PlantillaInspeccion.query.filter_by(activo=True).all()
    equipos = Equipo.query.all()
    # Estadísticas rápidas
    total_inspecciones_hoy = InspeccionRealizada.query.filter(
        InspeccionRealizada.fecha == date.today()
    ).count()
    return render_template('inspecciones/index.html', 
                         plantillas=plantillas, 
                         equipos=equipos,
                         total_inspecciones_hoy=total_inspecciones_hoy)

@inspecciones_bp.route('/plantillas')
@tecnico_required
def listar_plantillas():
    plantillas = PlantillaInspeccion.query.order_by(PlantillaInspeccion.frecuencia, PlantillaInspeccion.nombre).all()
    return render_template('inspecciones/plantillas.html', plantillas=plantillas)

@inspecciones_bp.route('/plantillas/nueva', methods=['GET', 'POST'])
@admin_required
def nueva_plantilla():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            descripcion = request.form.get('descripcion')
            frecuencia = request.form.get('frecuencia')
            tipo = request.form.get('tipo')
            equipo_id = request.form.get('equipo_id') or None
            area = request.form.get('area')
            
            # Nuevos campos GMP
            categoria_gmp = request.form.get('categoria_gmp')
            gmp_grade = request.form.get('gmp_grade')
            requiere_foto = request.form.get('requiere_foto') == 'on'
            tiempo_estimado_min = request.form.get('tiempo_estimado_min', 15)
            
            plantilla = PlantillaInspeccion(
                nombre=nombre,
                descripcion=descripcion,
                frecuencia=frecuencia,
                tipo=tipo,
                equipo_id=equipo_id,
                area=area,
                categoria_gmp=categoria_gmp,
                gmp_grade=gmp_grade,
                requiere_foto=requiere_foto,
                tiempo_estimado_min=int(tiempo_estimado_min),
                creado_por=current_user.username,
                activo=True
            )
            
            db.session.add(plantilla)
            db.session.flush()
            
            items_desc = request.form.getlist('items_desc[]')
            items_criterio = request.form.getlist('items_criterio[]')
            items_tipo = request.form.getlist('items_tipo[]')
            items_critico = request.form.getlist('items_critico[]')
            items_unidad = request.form.getlist('items_unidad[]')
            items_min = request.form.getlist('items_min[]')
            items_max = request.form.getlist('items_max[]')
            
            for i in range(len(items_desc)):
                if items_desc[i].strip():
                    item = ItemInspeccion(
                        plantilla_id=plantilla.id,
                        orden=i+1,
                        descripcion=items_desc[i],
                        criterio=items_criterio[i] if i < len(items_criterio) else '',
                        tipo_respuesta=items_tipo[i] if i < len(items_tipo) else 'booleano',
                        es_critico=(str(i) in items_critico),
                        unidad=items_unidad[i] if i < len(items_unidad) else '',
                        valor_minimo=float(items_min[i]) if i < len(items_min) and items_min[i] else None,
                        valor_maximo=float(items_max[i]) if i < len(items_max) and items_max[i] else None,
                        activo=True
                    )
                    db.session.add(item)
            
            db.session.commit()
            flash(f'Plantilla "{nombre}" creada exitosamente', 'success')
            return redirect(url_for('inspecciones.listar_plantillas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear plantilla: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    return render_template('inspecciones/nueva_plantilla.html', equipos=equipos)


@inspecciones_bp.route('/plantillas/<int:plantilla_id>')
@tecnico_required
def ver_plantilla(plantilla_id):
    plantilla = PlantillaInspeccion.query.get_or_404(plantilla_id)
    items = ItemInspeccion.query.filter_by(plantilla_id=plantilla_id, activo=True).order_by(ItemInspeccion.orden).all()
    return render_template('inspecciones/ver_plantilla.html', plantilla=plantilla, items=items)


@inspecciones_bp.route('/plantillas/<int:plantilla_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_plantilla(plantilla_id):
    plantilla = PlantillaInspeccion.query.get_or_404(plantilla_id)
    
    if request.method == 'POST':
        try:
            plantilla.nombre = request.form.get('nombre')
            plantilla.descripcion = request.form.get('descripcion')
            plantilla.frecuencia = request.form.get('frecuencia')
            plantilla.tipo = request.form.get('tipo')
            plantilla.equipo_id = request.form.get('equipo_id') or None
            plantilla.area = request.form.get('area')
            plantilla.categoria_gmp = request.form.get('categoria_gmp')
            plantilla.gmp_grade = request.form.get('gmp_grade')
            plantilla.requiere_foto = request.form.get('requiere_foto') == 'on'
            plantilla.tiempo_estimado_min = int(request.form.get('tiempo_estimado_min', 15))
            
            # Desactivar items existentes
            ItemInspeccion.query.filter_by(plantilla_id=plantilla_id).update({'activo': False})
            
            items_desc = request.form.getlist('items_desc[]')
            items_criterio = request.form.getlist('items_criterio[]')
            items_tipo = request.form.getlist('items_tipo[]')
            items_critico = request.form.getlist('items_critico[]')
            items_unidad = request.form.getlist('items_unidad[]')
            items_min = request.form.getlist('items_min[]')
            items_max = request.form.getlist('items_max[]')
            
            for i in range(len(items_desc)):
                if items_desc[i].strip():
                    item = ItemInspeccion(
                        plantilla_id=plantilla.id,
                        orden=i+1,
                        descripcion=items_desc[i],
                        criterio=items_criterio[i] if i < len(items_criterio) else '',
                        tipo_respuesta=items_tipo[i] if i < len(items_tipo) else 'booleano',
                        es_critico=(str(i) in items_critico),
                        unidad=items_unidad[i] if i < len(items_unidad) else '',
                        valor_minimo=float(items_min[i]) if i < len(items_min) and items_min[i] else None,
                        valor_maximo=float(items_max[i]) if i < len(items_max) and items_max[i] else None,
                        activo=True
                    )
                    db.session.add(item)
            
            db.session.commit()
            flash('Plantilla actualizada correctamente', 'success')
            return redirect(url_for('inspecciones.ver_plantilla', plantilla_id=plantilla.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    items = ItemInspeccion.query.filter_by(plantilla_id=plantilla_id, activo=True).order_by(ItemInspeccion.orden).all()
    equipos = Equipo.query.all()
    return render_template('inspecciones/editar_plantilla.html', plantilla=plantilla, items=items, equipos=equipos)


@inspecciones_bp.route('/plantillas/<int:plantilla_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_plantilla(plantilla_id):
    plantilla = PlantillaInspeccion.query.get_or_404(plantilla_id)
    try:
        plantilla.activo = False
        db.session.commit()
        flash(f'Plantilla "{plantilla.nombre}" eliminada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('inspecciones.listar_plantillas'))


# ============================================
# EJECUCIÓN DE INSPECCIONES
# ============================================

@inspecciones_bp.route('/realizar')
@tecnico_required
def seleccionar_plantilla():
    plantillas = PlantillaInspeccion.query.filter_by(activo=True).all()
    return render_template('inspecciones/seleccionar.html', plantillas=plantillas)


@inspecciones_bp.route('/realizar/<int:plantilla_id>', methods=['GET', 'POST'])
@tecnico_required
def realizar_inspeccion(plantilla_id):
    plantilla = PlantillaInspeccion.query.get_or_404(plantilla_id)
    items = ItemInspeccion.query.filter_by(plantilla_id=plantilla_id, activo=True).order_by(ItemInspeccion.orden).all()
    
    if request.method == 'POST':
        try:
            resultados = []
            conforme_general = True
            items_no_conformes_criticos = []
            
            for item in items:
                respuesta = request.form.get(f'item_{item.id}')
                observacion = request.form.get(f'obs_{item.id}', '')
                valor_numerico = request.form.get(f'valor_{item.id}')
                
                # Evaluar según tipo de respuesta
                if item.tipo_respuesta == 'booleano':
                    es_conforme = (respuesta == 'si')
                elif item.tipo_respuesta == 'numerico' or item.tipo_respuesta == 'rango':
                    try:
                        valor = float(valor_numerico) if valor_numerico else None
                        if valor is not None:
                            if item.valor_minimo is not None and valor < item.valor_minimo:
                                es_conforme = False
                            elif item.valor_maximo is not None and valor > item.valor_maximo:
                                es_conforme = False
                            else:
                                es_conforme = True
                        else:
                            es_conforme = False
                    except (ValueError, TypeError):
                        es_conforme = False
                else:
                    es_conforme = bool(respuesta) if respuesta else False
                
                resultado_item = {
                    'item_id': item.id,
                    'descripcion': item.descripcion,
                    'respuesta': respuesta or valor_numerico,
                    'observacion': observacion,
                    'conforme': es_conforme,
                    'es_critico': item.es_critico,
                    'tipo_respuesta': item.tipo_respuesta
                }
                
                resultados.append(resultado_item)
                
                # Validar items críticos con observación requerida
                if item.es_critico and not es_conforme:
                    conforme_general = False
                    items_no_conformes_criticos.append(item.descripcion)
                    if not observacion.strip():
                        flash(f'El item crítico "{item.descripcion}" requiere una observación detallada', 'error')
                        return render_template('inspecciones/realizar.html', 
                                              plantilla=plantilla, items=items, now=datetime.now())
            
            # Manejo de fotos
            fotos_adjuntas = False
            if plantilla.requiere_foto and request.files:
                for key, file in request.files.items():
                    if file and allowed_file(file.filename):
                        fotos_adjuntas = True
                        break
            
            inspeccion = InspeccionRealizada(
                plantilla_id=plantilla_id,
                equipo_id=plantilla.equipo_id,
                fecha=date.today(),
                hora_inicio=datetime.strptime(request.form.get('hora_inicio'), '%Y-%m-%dT%H:%M') if request.form.get('hora_inicio') else datetime.now(),
                realizada_por=current_user.username,
                resultados=resultados,
                conforme=conforme_general,
                observaciones=request.form.get('observaciones_generales', ''),
                acciones=request.form.get('acciones', ''),
                lotes_afectados=request.form.get('lotes_afectados', ''),
                requiere_capa=request.form.get('requiere_capa') == 'on',
                fotos_adjuntas=fotos_adjuntas
            )
            
            db.session.add(inspeccion)
            db.session.commit()
            
            if not conforme_general:
                flash(f'⚠️ Inspección NO CONFORME. Items críticos fallidos: {", ".join(items_no_conformes_criticos[:3])}', 'warning')
            else:
                flash('✅ Inspección registrada correctamente - CONFORME', 'success')
            
            return redirect(url_for('inspecciones.ver_inspeccion', inspeccion_id=inspeccion.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar inspección: {str(e)}', 'error')
    
    return render_template('inspecciones/realizar.html', plantilla=plantilla, items=items, now=datetime.now())


@inspecciones_bp.route('/ver/<int:inspeccion_id>')
@tecnico_required
def ver_inspeccion(inspeccion_id):
    inspeccion = InspeccionRealizada.query.get_or_404(inspeccion_id)
    return render_template('inspecciones/ver_inspeccion.html', inspeccion=inspeccion)


@inspecciones_bp.route('/historial')
@tecnico_required
def historial():
    # Filtros opcionales
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    conforme = request.args.get('conforme')
    categoria = request.args.get('categoria')
    
    query = InspeccionRealizada.query
    
    if fecha_desde:
        query = query.filter(InspeccionRealizada.fecha >= datetime.strptime(fecha_desde, '%Y-%m-%d').date())
    if fecha_hasta:
        query = query.filter(InspeccionRealizada.fecha <= datetime.strptime(fecha_hasta, '%Y-%m-%d').date())
    if conforme is not None:
        query = query.filter(InspeccionRealizada.conforme == (conforme == 'true'))
    if categoria:
        query = query.join(PlantillaInspeccion).filter(PlantillaInspeccion.categoria_gmp == categoria)
    
    inspecciones = query.order_by(InspeccionRealizada.fecha.desc()).limit(200).all()
    
    # Estadísticas
    total = InspeccionRealizada.query.count()
    conformes = InspeccionRealizada.query.filter_by(conforme=True).count()
    no_conformes = total - conformes
    porcentaje_conformidad = int((conformes / total * 100)) if total > 0 else 0
    
    return render_template('inspecciones/historial.html', 
                         inspecciones=inspecciones,
                         total=total,
                         conformes=conformes,
                         no_conformes=no_conformes,
                         porcentaje_conformidad=porcentaje_conformidad)


@inspecciones_bp.route('/historial/equipo/<int:equipo_id>')
@tecnico_required
def historial_equipo(equipo_id):
    inspecciones = InspeccionRealizada.query.filter_by(equipo_id=equipo_id).order_by(InspeccionRealizada.fecha.desc()).all()
    equipo = Equipo.query.get_or_404(equipo_id)
    return render_template('inspecciones/historial_equipo.html', inspecciones=inspecciones, equipo=equipo)


# ============================================
# DASHBOARD Y ESTADÍSTICAS
# ============================================

@inspecciones_bp.route('/dashboard')
@tecnico_required
def dashboard_inspecciones():
    """Dashboard específico de inspecciones GMP"""
    from sqlalchemy import func
    
    # Totales
    total_inspecciones = InspeccionRealizada.query.count()
    ultimos_30_dias = InspeccionRealizada.query.filter(
        InspeccionRealizada.fecha >= date.today() - timedelta(days=30)
    ).count()
    
    # Conformes y no conformes
    conformes = InspeccionRealizada.query.filter_by(conforme=True).count()
    no_conformes = total_inspecciones - conformes
    
    # Por categoría GMP - CONVERTIR A DICCIONARIO SERIALIZABLE
    categorias_raw = db.session.query(
        PlantillaInspeccion.categoria_gmp,
        func.count(InspeccionRealizada.id)
    ).outerjoin(
        InspeccionRealizada, PlantillaInspeccion.id == InspeccionRealizada.plantilla_id
    ).group_by(
        PlantillaInspeccion.categoria_gmp
    ).all()
    
    # Convertir a formato serializable para JSON
    categorias = []
    for cat in categorias_raw:
        categoria_nombre = cat[0] if cat[0] else 'sin_categoria'
        # Mapear nombres legibles
        nombre_legible = {
            'ambiental': 'Ambiental',
            'contencion': 'Contención',
            'equipo': 'Equipos',
            'limpieza': 'Limpieza',
            'calidad': 'Calidad',
            'documentacion': 'Documentación',
            'servicios': 'Servicios',
            'sin_categoria': 'Sin categoría'
        }.get(categoria_nombre, categoria_nombre or 'Sin categoría')
        
        categorias.append({
            'nombre': nombre_legible,
            'total': cat[1] or 0
        })
    
    # Tendencia últimos 30 días
    tendencia = []
    for i in range(30, -1, -1):
        fecha = date.today() - timedelta(days=i)
        dia_conformes = InspeccionRealizada.query.filter(
            InspeccionRealizada.fecha == fecha,
            InspeccionRealizada.conforme == True
        ).count()
        dia_totales = InspeccionRealizada.query.filter(
            InspeccionRealizada.fecha == fecha
        ).count()
        tendencia.append({
            'fecha': fecha.strftime('%d/%m'),
            'conformes': dia_conformes,
            'totales': dia_totales,
            'porcentaje': int(dia_conformes / dia_totales * 100) if dia_totales > 0 else 100
        })
    
    return render_template('inspecciones/dashboard_gmp.html',
                         total_inspecciones=total_inspecciones,
                         ultimos_30_dias=ultimos_30_dias,
                         conformes=conformes,
                         no_conformes=no_conformes,
                         categorias=categorias,
                         tendencia=tendencia)

# ============================================
# API PARA GRÁFICOS Y ESTADÍSTICAS
# ============================================

@inspecciones_bp.route('/api/estadisticas')
@tecnico_required
def api_estadisticas():
    from sqlalchemy import func
    
    total = InspeccionRealizada.query.count()
    conformes = InspeccionRealizada.query.filter_by(conforme=True).count()
    no_conformes = total - conformes
    
    fecha_limite = date.today() - timedelta(days=30)
    recientes = InspeccionRealizada.query.filter(InspeccionRealizada.fecha >= fecha_limite).count()
    
    # Por frecuencia
    por_frecuencia = db.session.query(
        PlantillaInspeccion.frecuencia,
        func.count(InspeccionRealizada.id)
    ).outerjoin(
        InspeccionRealizada, PlantillaInspeccion.id == InspeccionRealizada.plantilla_id
    ).group_by(
        PlantillaInspeccion.frecuencia
    ).all()
    
    return jsonify({
        'total': total,
        'conformes': conformes,
        'no_conformes': no_conformes,
        'recientes': recientes,
        'por_frecuencia': [{'frecuencia': f, 'total': t} for f, t in por_frecuencia]
    })


@inspecciones_bp.route('/api/plantillas/<int:plantilla_id>/items')
@tecnico_required
def api_get_items(plantilla_id):
    items = ItemInspeccion.query.filter_by(plantilla_id=plantilla_id, activo=True).order_by(ItemInspeccion.orden).all()
    return jsonify([{
        'id': i.id,
        'orden': i.orden,
        'descripcion': i.descripcion,
        'criterio': i.criterio,
        'tipo_respuesta': i.tipo_respuesta,
        'es_critico': i.es_critico,
        'unidad': i.unidad,
        'valor_minimo': i.valor_minimo,
        'valor_maximo': i.valor_maximo
    } for i in items])


# ============================================
# REPORTES
# ============================================

@inspecciones_bp.route('/reporte/mensual/<int:ano>/<int:mes>')
@tecnico_required
def reporte_mensual(ano, mes):
    """Genera reporte mensual de inspecciones GMP"""
    desde = date(ano, mes, 1)
    if mes == 12:
        hasta = date(ano+1, 1, 1) - timedelta(days=1)
    else:
        hasta = date(ano, mes+1, 1) - timedelta(days=1)
    
    inspecciones = InspeccionRealizada.query.filter(
        InspeccionRealizada.fecha.between(desde, hasta)
    ).all()
    
    total = len(inspecciones)
    conformes = sum(1 for i in inspecciones if i.conforme)
    no_conformes = total - conformes
    
    # Agrupar por plantilla
    por_plantilla = {}
    for i in inspecciones:
        nombre = i.plantilla.nombre
        if nombre not in por_plantilla:
            por_plantilla[nombre] = {'total': 0, 'conformes': 0}
        por_plantilla[nombre]['total'] += 1
        if i.conforme:
            por_plantilla[nombre]['conformes'] += 1
    
    return render_template('inspecciones/reporte_mensual.html',
                         ano=ano, mes=mes,
                         nombre_mes=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][mes-1],
                         total=total, conformes=conformes, no_conformes=no_conformes,
                         por_plantilla=por_plantilla,
                         inspecciones=inspecciones[:50])


@inspecciones_bp.route('/api/inspecciones-recientes')
@tecnico_required
def api_inspecciones_recientes():
    """API para obtener inspecciones recientes"""
    inspecciones = InspeccionRealizada.query.order_by(
        InspeccionRealizada.fecha.desc()
    ).limit(20).all()
    
    resultado = []
    for i in inspecciones:
        resultado.append({
            'id': i.id,
            'fecha': i.fecha.strftime('%d/%m/%Y'),
            'plantilla_nombre': i.plantilla.nombre if i.plantilla else 'N/A',
            'categoria': i.plantilla.categoria_gmp if i.plantilla else 'N/A',
            'realizada_por': i.realizada_por,
            'conforme': i.conforme
        })
    
    return jsonify(resultado)


@inspecciones_bp.route('/imprimir-plantilla/<int:plantilla_id>')
@tecnico_required
def imprimir_plantilla(plantilla_id):
    """Genera vista imprimible de la plantilla para registro en papel (sin sidebar)"""
    plantilla = PlantillaInspeccion.query.get_or_404(plantilla_id)
    items = ItemInspeccion.query.filter_by(plantilla_id=plantilla_id, activo=True).order_by(ItemInspeccion.orden).all()
    # Usar template específico para impresión SIN base.html
    return render_template('inspecciones/imprimir_plantilla_print.html', 
                         plantilla=plantilla, 
                         items=items,
                         now=datetime.now())

@inspecciones_bp.route('/imprimir-inspeccion/<int:inspeccion_id>')
@tecnico_required
def imprimir_inspeccion(inspeccion_id):
    """Genera vista imprimible de una inspección ya realizada"""
    inspeccion = InspeccionRealizada.query.get_or_404(inspeccion_id)
    return render_template('inspecciones/ver_inspeccion.html', inspeccion=inspeccion)