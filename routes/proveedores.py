# routes/proveedores.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from models import db
from models.proveedor import Proveedor, RepuestoProveedor, ServicioProveedor, Compra, CompraItem
from models.inventario import Repuesto
from datetime import datetime
from utils.decorators import tecnico_required, admin_required
import random
import string

proveedores_bp = Blueprint('proveedores', __name__)

@proveedores_bp.route('/')
@tecnico_required
def gestion_proveedores():
    """Listado de proveedores"""
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    
    # Estadísticas
    total_insumos = Proveedor.query.filter_by(tipo='insumos').count()
    total_servicios = Proveedor.query.filter_by(tipo='servicios').count()
    total_equipos = Proveedor.query.filter_by(tipo='equipos').count()
    proveedores_gmp = Proveedor.query.filter_by(es_proveedor_gmp=True).count()
    
    return render_template('proveedores/gestion_proveedores.html',
                         proveedores=proveedores,
                         total_insumos=total_insumos,
                         total_servicios=total_servicios,
                         total_equipos=total_equipos,
                         proveedores_gmp=proveedores_gmp)

@proveedores_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_required
def nuevo_proveedor():
    """Crear nuevo proveedor"""
    if request.method == 'POST':
        try:
            # Generar código
            año = datetime.now().year
            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            codigo = f"PROV-{año}-{random_chars}"
            
            # Validar si ya existe
            while Proveedor.query.filter_by(codigo=codigo).first():
                random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                codigo = f"PROV-{año}-{random_chars}"
            
            nuevo = Proveedor(
                codigo=codigo,
                nombre=request.form.get('nombre'),
                tipo=request.form.get('tipo'),
                rubro=request.form.get('rubro'),
                contacto_nombre=request.form.get('contacto_nombre'),
                contacto_cargo=request.form.get('contacto_cargo'),
                telefono=request.form.get('telefono'),
                email=request.form.get('email'),
                sitio_web=request.form.get('sitio_web'),
                direccion=request.form.get('direccion'),
                ciudad=request.form.get('ciudad'),
                provincia=request.form.get('provincia'),
                pais=request.form.get('pais'),
                cuit=request.form.get('cuit'),
                condicion_iva=request.form.get('condicion_iva'),
                calificacion=int(request.form.get('calificacion', 0)),
                observaciones=request.form.get('observaciones'),
                es_proveedor_gmp=bool(request.form.get('es_proveedor_gmp')),
                fecha_calificacion=datetime.strptime(request.form.get('fecha_calificacion'), '%Y-%m-%d').date() if request.form.get('fecha_calificacion') else None,
                fecha_vencimiento_calificacion=datetime.strptime(request.form.get('fecha_vencimiento_calificacion'), '%Y-%m-%d').date() if request.form.get('fecha_vencimiento_calificacion') else None,
                banco=request.form.get('banco'),
                cbu=request.form.get('cbu'),
                alias=request.form.get('alias'),
                created_by=current_user.username,
                activo=True
            )
            
            db.session.add(nuevo)
            db.session.commit()
            
            flash(f'Proveedor {nuevo.codigo} creado exitosamente', 'success')
            return redirect(url_for('proveedores.gestion_proveedores'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear proveedor: {str(e)}', 'error')
    
    return render_template('proveedores/nuevo_proveedor.html')

@proveedores_bp.route('/<int:proveedor_id>')
@tecnico_required
def detalle_proveedor(proveedor_id):
    """Ver detalle de proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    
    # Obtener repuestos asociados
    repuestos = RepuestoProveedor.query.filter_by(proveedor_id=proveedor.id).all()
    
    # Obtener servicios
    servicios = ServicioProveedor.query.filter_by(proveedor_id=proveedor.id).all()
    
    # Obtener compras recientes
    compras = Compra.query.filter_by(proveedor_id=proveedor.id).order_by(Compra.fecha_compra.desc()).limit(10).all()
    
    return render_template('proveedores/detalle_proveedor.html',
                         proveedor=proveedor,
                         repuestos=repuestos,
                         servicios=servicios,
                         compras=compras)

@proveedores_bp.route('/<int:proveedor_id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_proveedor(proveedor_id):
    """Editar proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    
    if request.method == 'POST':
        try:
            proveedor.nombre = request.form.get('nombre')
            proveedor.tipo = request.form.get('tipo')
            proveedor.rubro = request.form.get('rubro')
            proveedor.contacto_nombre = request.form.get('contacto_nombre')
            proveedor.contacto_cargo = request.form.get('contacto_cargo')
            proveedor.telefono = request.form.get('telefono')
            proveedor.email = request.form.get('email')
            proveedor.sitio_web = request.form.get('sitio_web')
            proveedor.direccion = request.form.get('direccion')
            proveedor.ciudad = request.form.get('ciudad')
            proveedor.provincia = request.form.get('provincia')
            proveedor.pais = request.form.get('pais')
            proveedor.cuit = request.form.get('cuit')
            proveedor.condicion_iva = request.form.get('condicion_iva')
            proveedor.calificacion = int(request.form.get('calificacion', 0))
            proveedor.observaciones = request.form.get('observaciones')
            proveedor.es_proveedor_gmp = bool(request.form.get('es_proveedor_gmp'))
            
            if request.form.get('fecha_calificacion'):
                proveedor.fecha_calificacion = datetime.strptime(request.form.get('fecha_calificacion'), '%Y-%m-%d').date()
            if request.form.get('fecha_vencimiento_calificacion'):
                proveedor.fecha_vencimiento_calificacion = datetime.strptime(request.form.get('fecha_vencimiento_calificacion'), '%Y-%m-%d').date()
            
            proveedor.banco = request.form.get('banco')
            proveedor.cbu = request.form.get('cbu')
            proveedor.alias = request.form.get('alias')
            proveedor.activo = bool(request.form.get('activo', True))
            
            db.session.commit()
            
            flash('Proveedor actualizado correctamente', 'success')
            return redirect(url_for('proveedores.detalle_proveedor', proveedor_id=proveedor.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    return render_template('proveedores/editar_proveedor.html', proveedor=proveedor)

@proveedores_bp.route('/<int:proveedor_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_proveedor(proveedor_id):
    """Eliminar proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    
    try:
        db.session.delete(proveedor)
        db.session.commit()
        flash(f'Proveedor {proveedor.nombre} eliminado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('proveedores.gestion_proveedores'))

@proveedores_bp.route('/api/repuestos-disponibles')
@tecnico_required
def api_repuestos_disponibles():
    """API para listar repuestos disponibles"""
    repuestos = Repuesto.query.all()
    return jsonify([{
        'id': r.id,
        'codigo': r.codigo,
        'nombre': r.nombre
    } for r in repuestos])

@proveedores_bp.route('/<int:proveedor_id>/asignar-repuesto', methods=['POST'])
@admin_required
def asignar_repuesto(proveedor_id):
    """Asigna un repuesto a un proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    
    try:
        repuesto_id = request.form.get('repuesto_id')
        codigo_proveedor = request.form.get('codigo_proveedor')
        precio = float(request.form.get('precio_referencia')) if request.form.get('precio_referencia') else None
        plazo = int(request.form.get('plazo_entrega')) if request.form.get('plazo_entrega') else None
        es_principal = bool(request.form.get('es_principal'))
        
        # Verificar si ya existe
        existente = RepuestoProveedor.query.filter_by(
            proveedor_id=proveedor.id,
            repuesto_id=repuesto_id
        ).first()
        
        if existente:
            flash('Este repuesto ya está asignado a este proveedor', 'warning')
        else:
            asignacion = RepuestoProveedor(
                proveedor_id=proveedor.id,
                repuesto_id=repuesto_id,
                codigo_proveedor=codigo_proveedor,
                precio_referencia=precio,
                plazo_entrega_dias=plazo,
                es_proveedor_principal=es_principal
            )
            db.session.add(asignacion)
            db.session.commit()
            flash('Repuesto asignado correctamente', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error al asignar repuesto: {str(e)}', 'error')
    
    return redirect(url_for('proveedores.detalle_proveedor', proveedor_id=proveedor.id))

@proveedores_bp.route('/<int:proveedor_id>/eliminar-repuesto/<int:asignacion_id>', methods=['POST'])
@admin_required
def eliminar_repuesto_asignado(proveedor_id, asignacion_id):
    """Elimina asignación de repuesto"""
    try:
        asignacion = RepuestoProveedor.query.get_or_404(asignacion_id)
        db.session.delete(asignacion)
        db.session.commit()
        flash('Asignación eliminada', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('proveedores.detalle_proveedor', proveedor_id=proveedor_id))

@proveedores_bp.route('/<int:proveedor_id>/agregar-servicio', methods=['POST'])
@admin_required
def agregar_servicio(proveedor_id):
    """Agrega un servicio al proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    
    try:
        servicio = ServicioProveedor(
            proveedor_id=proveedor.id,
            tipo_servicio=request.form.get('tipo_servicio'),
            descripcion=request.form.get('descripcion'),
            especialidad=request.form.get('especialidad')
        )
        
        db.session.add(servicio)
        db.session.commit()
        flash('Servicio agregado correctamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al agregar servicio: {str(e)}', 'error')
    
    return redirect(url_for('proveedores.detalle_proveedor', proveedor_id=proveedor.id))

@proveedores_bp.route('/api/toggle-estado/<int:proveedor_id>', methods=['POST'])
@admin_required
def toggle_estado(proveedor_id):
    """Activa/desactiva proveedor"""
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    proveedor.activo = not proveedor.activo
    db.session.commit()
    
    estado = "activado" if proveedor.activo else "desactivado"
    return jsonify({'success': True, 'estado': estado})