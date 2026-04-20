# routes/riesgos.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models.riesgo import MatrizRiesgo, RiesgoIdentificado
from models.equipo import Equipo
from datetime import datetime, date
from utils.decorators import tecnico_required, admin_required
import json

riesgos_bp = Blueprint('riesgos', __name__)

@riesgos_bp.route('/')
@tecnico_required
def index():
    """Listado de matrices de riesgo"""
    matrices = MatrizRiesgo.query.order_by(MatrizRiesgo.fecha_creacion.desc()).all()
    equipos = Equipo.query.all()
    return render_template('riesgos/index.html', matrices=matrices, equipos=equipos)

@riesgos_bp.route('/nueva', methods=['GET', 'POST'])
@tecnico_required
def nueva_matriz():
    """Crear nueva matriz de riesgo"""
    if request.method == 'POST':
        try:
            # Calcular NPR y clasificación
            metodologia = request.form.get('metodologia', 'FMEA')
            
            nueva = MatrizRiesgo(
                nombre=request.form.get('nombre'),
                version='1.0',
                equipo_id=request.form.get('equipo_id') or None,
                area=request.form.get('area'),
                proceso=request.form.get('proceso'),
                metodologia=metodologia,
                elaborado_por=current_user.nombre_completo or current_user.username,
                riesgos=[],
                acciones={}
            )
            
            db.session.add(nueva)
            db.session.commit()
            
            flash(f'Matriz de riesgos "{nueva.nombre}" creada', 'success')
            return redirect(url_for('riesgos.editar_matriz', matriz_id=nueva.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear matriz: {str(e)}', 'error')
    
    equipos = Equipo.query.all()
    return render_template('riesgos/nueva.html', equipos=equipos)

@riesgos_bp.route('/<int:matriz_id>')
@tecnico_required
def ver_matriz(matriz_id):
    """Ver matriz de riesgo"""
    matriz = MatrizRiesgo.query.get_or_404(matriz_id)
    return render_template('riesgos/ver.html', matriz=matriz)

@riesgos_bp.route('/<int:matriz_id>/editar')
@tecnico_required
def editar_matriz(matriz_id):
    """Editar matriz de riesgo"""
    matriz = MatrizRiesgo.query.get_or_404(matriz_id)
    equipos = Equipo.query.all()
    return render_template('riesgos/editar.html', matriz=matriz, equipos=equipos)

# ============================================
# API PARA GESTIÓN DE RIESGOS
# ============================================

@riesgos_bp.route('/api/riesgos/<int:matriz_id>', methods=['GET'])
@tecnico_required
def api_get_riesgos(matriz_id):
    """Obtiene todos los riesgos de una matriz"""
    matriz = MatrizRiesgo.query.get_or_404(matriz_id)
    
    # Obtener de la base de datos o del JSON
    riesgos = []
    if matriz.riesgos:
        riesgos = matriz.riesgos
    else:
        # Consultar la tabla de riesgos identificados
        for r in RiesgoIdentificado.query.filter_by(matriz_id=matriz_id).all():
            riesgos.append({
                'id': r.id,
                'codigo': r.codigo,
                'descripcion': r.descripcion,
                'causa': r.causa,
                'efecto': r.efecto,
                'categoria': r.categoria,
                'severidad': r.severidad,
                'ocurrencia': r.ocurrencia,
                'detectabilidad': r.detectabilidad,
                'npr': r.npr,
                'controles_actuales': r.controles_actuales,
                'controles_propuestos': r.controles_propuestos,
                'responsable': r.responsable,
                'fecha_limite': r.fecha_limite.strftime('%Y-%m-%d') if r.fecha_limite else None,
                'estado': r.estado
            })
    
    return jsonify(riesgos)

@riesgos_bp.route('/api/riesgos/<int:matriz_id>', methods=['POST'])
@tecnico_required
def api_agregar_riesgo(matriz_id):
    """Agrega un nuevo riesgo a la matriz"""
    data = request.json
    matriz = MatrizRiesgo.query.get_or_404(matriz_id)
    
    try:
        # Generar código automático
        count = RiesgoIdentificado.query.filter_by(matriz_id=matriz_id).count() + 1
        codigo = f"R-{count:03d}"
        
        # Calcular NPR
        severidad = int(data.get('severidad', 1))
        ocurrencia = int(data.get('ocurrencia', 1))
        detectabilidad = int(data.get('detectabilidad', 1))
        npr = severidad * ocurrencia * detectabilidad
        
        # Determinar nivel de riesgo
        if npr >= 200:
            nivel = 'Crítico'
        elif npr >= 100:
            nivel = 'Alto'
        elif npr >= 50:
            nivel = 'Medio'
        else:
            nivel = 'Bajo'
        
        nuevo = RiesgoIdentificado(
            matriz_id=matriz_id,
            codigo=codigo,
            descripcion=data.get('descripcion'),
            causa=data.get('causa'),
            efecto=data.get('efecto'),
            categoria=data.get('categoria'),
            severidad=severidad,
            ocurrencia=ocurrencia,
            detectabilidad=detectabilidad,
            npr=npr,
            controles_actuales=data.get('controles_actuales'),
            controles_propuestos=data.get('controles_propuestos'),
            responsable=data.get('responsable'),
            fecha_limite=datetime.strptime(data.get('fecha_limite'), '%Y-%m-%d').date() if data.get('fecha_limite') else None,
            estado=data.get('estado', 'Identificado')
        )
        
        db.session.add(nuevo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'riesgo': {
                'id': nuevo.id,
                'codigo': nuevo.codigo,
                'descripcion': nuevo.descripcion,
                'causa': nuevo.causa,
                'efecto': nuevo.efecto,
                'categoria': nuevo.categoria,
                'severidad': nuevo.severidad,
                'ocurrencia': nuevo.ocurrencia,
                'detectabilidad': nuevo.detectabilidad,
                'npr': nuevo.npr,
                'nivel': nivel,
                'controles_actuales': nuevo.controles_actuales,
                'controles_propuestos': nuevo.controles_propuestos,
                'responsable': nuevo.responsable,
                'fecha_limite': nuevo.fecha_limite.strftime('%Y-%m-%d') if nuevo.fecha_limite else None,
                'estado': nuevo.estado
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@riesgos_bp.route('/api/riesgos/<int:riesgo_id>', methods=['PUT'])
@tecnico_required
def api_actualizar_riesgo(riesgo_id):
    """Actualiza un riesgo existente"""
    riesgo = RiesgoIdentificado.query.get_or_404(riesgo_id)
    data = request.json
    
    try:
        riesgo.descripcion = data.get('descripcion', riesgo.descripcion)
        riesgo.causa = data.get('causa', riesgo.causa)
        riesgo.efecto = data.get('efecto', riesgo.efecto)
        riesgo.categoria = data.get('categoria', riesgo.categoria)
        
        riesgo.severidad = int(data.get('severidad', riesgo.severidad))
        riesgo.ocurrencia = int(data.get('ocurrencia', riesgo.ocurrencia))
        riesgo.detectabilidad = int(data.get('detectabilidad', riesgo.detectabilidad))
        riesgo.npr = riesgo.severidad * riesgo.ocurrencia * riesgo.detectabilidad
        
        riesgo.controles_actuales = data.get('controles_actuales')
        riesgo.controles_propuestos = data.get('controles_propuestos')
        riesgo.responsable = data.get('responsable')
        
        if data.get('fecha_limite'):
            riesgo.fecha_limite = datetime.strptime(data.get('fecha_limite'), '%Y-%m-%d').date()
        
        riesgo.estado = data.get('estado', riesgo.estado)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@riesgos_bp.route('/api/riesgos/<int:riesgo_id>', methods=['DELETE'])
@admin_required
def api_eliminar_riesgo(riesgo_id):
    """Elimina un riesgo"""
    riesgo = RiesgoIdentificado.query.get_or_404(riesgo_id)
    
    try:
        db.session.delete(riesgo)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@riesgos_bp.route('/api/matriz/<int:matriz_id>/publicar', methods=['POST'])
@admin_required
def api_publicar_matriz(matriz_id):
    """Publica la matriz (cambia a versión final)"""
    matriz = MatrizRiesgo.query.get_or_404(matriz_id)
    
    try:
        matriz.version = '1.0'
        matriz.fecha_revision = date.today()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500