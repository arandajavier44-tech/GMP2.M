# routes/inventario.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.inventario import Repuesto, RepuestoPorEquipo, ConsumoRepuesto, MovimientoStock
from models.proveedor import Proveedor, RepuestoProveedor
from models.equipo import Equipo
from datetime import datetime

inventario_bp = Blueprint('inventario', __name__)


@inventario_bp.route('/')
def gestion_inventario():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    repuestos = Repuesto.query.order_by(Repuesto.codigo).all()
    equipos = Equipo.query.order_by(Equipo.code).all()
    return render_template('inventario/gestion_inventario.html', repuestos=repuestos, equipos=equipos)


@inventario_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_repuesto():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            # Obtener equipo_id (puede ser None)
            equipo_id = request.form.get('equipo_id')
            equipo_id = int(equipo_id) if equipo_id and equipo_id.isdigit() else None
            
            # Crear el repuesto
            nuevo = Repuesto(
                codigo=request.form.get('codigo'),
                nombre=request.form.get('nombre'),
                descripcion=request.form.get('descripcion'),
                categoria=request.form.get('categoria'),
                stock_actual=int(request.form.get('stock_actual', 0)),
                stock_minimo=int(request.form.get('stock_minimo', 5)),
                stock_maximo=int(request.form.get('stock_maximo', 50)),
                ubicacion=request.form.get('ubicacion'),
                costo_unitario=float(request.form.get('costo_unitario')) if request.form.get('costo_unitario') else None,
                fabricante=request.form.get('fabricante'),
                modelo=request.form.get('modelo'),
                numero_parte=request.form.get('numero_parte'),
                requiere_trazabilidad=bool(request.form.get('requiere_trazabilidad')),
                numero_lote=request.form.get('numero_lote'),
                fecha_vencimiento=datetime.strptime(request.form.get('fecha_vencimiento'), '%Y-%m-%d').date() if request.form.get('fecha_vencimiento') else None,
                equipo_id=equipo_id  # Relación directa (opcional)
            )
            
            db.session.add(nuevo)
            db.session.flush()
            
            # Si se seleccionó un equipo, crear también la relación en RepuestoPorEquipo
            if equipo_id:
                existente = RepuestoPorEquipo.query.filter_by(
                    equipo_id=equipo_id,
                    repuesto_id=nuevo.id
                ).first()
                if not existente:
                    relacion = RepuestoPorEquipo(
                        equipo_id=equipo_id,
                        repuesto_id=nuevo.id,
                        cantidad_por_uso=1,
                        es_critico=False,
                        observaciones="Asignado desde creación de repuesto"
                    )
                    db.session.add(relacion)
            
            # Procesar proveedores
            proveedor_ids = request.form.getlist('proveedores')
            es_principal = request.form.get('proveedor_principal')
            
            for proveedor_id in proveedor_ids:
                if proveedor_id:
                    repuesto_proveedor = RepuestoProveedor(
                        repuesto_id=nuevo.id,
                        proveedor_id=int(proveedor_id),
                        codigo_proveedor=request.form.get(f'codigo_proveedor_{proveedor_id}'),
                        precio_referencia=float(request.form.get(f'precio_{proveedor_id}')) if request.form.get(f'precio_{proveedor_id}') else None,
                        plazo_entrega_dias=int(request.form.get(f'plazo_{proveedor_id}')) if request.form.get(f'plazo_{proveedor_id}') else None,
                        es_proveedor_principal=(str(proveedor_id) == es_principal)
                    )
                    db.session.add(repuesto_proveedor)
            
            db.session.commit()
            
            if nuevo.equipo:
                flash(f'Repuesto {nuevo.codigo} creado exitosamente para el equipo {nuevo.equipo.code}', 'success')
            else:
                flash(f'Repuesto {nuevo.codigo} creado exitosamente (inventario general)', 'success')
            
            return redirect(url_for('inventario.gestion_inventario'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear repuesto: {str(e)}', 'error')
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    # GET request
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    equipos = Equipo.query.order_by(Equipo.code).all()
    return render_template('inventario/nuevo_repuesto.html', proveedores=proveedores, equipos=equipos)


@inventario_bp.route('/<int:repuesto_id>')
def detalle_repuesto(repuesto_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    repuesto = Repuesto.query.get_or_404(repuesto_id)
    equipos = Equipo.query.order_by(Equipo.code).all()
    return render_template('inventario/detalle_repuesto.html', repuesto=repuesto, equipos=equipos, now=datetime.now())


@inventario_bp.route('/<int:repuesto_id>/editar', methods=['POST'])
def editar_repuesto(repuesto_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    repuesto = Repuesto.query.get_or_404(repuesto_id)
    
    try:
        repuesto.codigo = request.form.get('codigo')
        repuesto.nombre = request.form.get('nombre')
        repuesto.descripcion = request.form.get('descripcion')
        repuesto.categoria = request.form.get('categoria')
        repuesto.stock_minimo = int(request.form.get('stock_minimo', 5))
        repuesto.stock_maximo = int(request.form.get('stock_maximo', 50))
        repuesto.ubicacion = request.form.get('ubicacion')
        repuesto.costo_unitario = float(request.form.get('costo_unitario')) if request.form.get('costo_unitario') else None
        
        # Actualizar equipo principal si cambia
        nuevo_equipo_id = request.form.get('equipo_id')
        nuevo_equipo_id = int(nuevo_equipo_id) if nuevo_equipo_id and nuevo_equipo_id.isdigit() else None
        repuesto.equipo_id = nuevo_equipo_id
        
        # Sincronizar RepuestoPorEquipo
        if nuevo_equipo_id:
            existente = RepuestoPorEquipo.query.filter_by(
                equipo_id=nuevo_equipo_id,
                repuesto_id=repuesto.id
            ).first()
            if not existente:
                relacion = RepuestoPorEquipo(
                    equipo_id=nuevo_equipo_id,
                    repuesto_id=repuesto.id,
                    cantidad_por_uso=1,
                    es_critico=False
                )
                db.session.add(relacion)
        
        db.session.commit()
        flash('Repuesto actualizado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar: {str(e)}', 'error')
    
    return redirect(url_for('inventario.detalle_repuesto', repuesto_id=repuesto.id))


@inventario_bp.route('/<int:repuesto_id>/movimiento', methods=['POST'])
def registrar_movimiento(repuesto_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    repuesto = Repuesto.query.get_or_404(repuesto_id)
    
    try:
        tipo = request.form.get('tipo')
        cantidad = int(request.form.get('cantidad'))
        observaciones = request.form.get('observaciones')
        proveedor_id = request.form.get('proveedor')
        numero_documento = request.form.get('numero_documento')
        
        stock_anterior = repuesto.stock_actual
        
        if tipo == 'entrada':
            repuesto.stock_actual += cantidad
        elif tipo == 'salida':
            if repuesto.stock_actual < cantidad:
                flash('Stock insuficiente para realizar la salida', 'error')
                return redirect(url_for('inventario.detalle_repuesto', repuesto_id=repuesto.id))
            repuesto.stock_actual -= cantidad
        
        # Registrar movimiento
        movimiento = MovimientoStock(
            repuesto_id=repuesto.id,
            tipo=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=repuesto.stock_actual,
            referencia=numero_documento or f"Movimiento {tipo}",
            realizado_por=session.get('username', 'Sistema')
        )
        db.session.add(movimiento)
        
        db.session.commit()
        
        flash(f'Movimiento registrado: {tipo} de {cantidad} unidades. Stock actual: {repuesto.stock_actual}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar movimiento: {str(e)}', 'error')
    
    return redirect(url_for('inventario.detalle_repuesto', repuesto_id=repuesto.id))


@inventario_bp.route('/api/listar')
def listar_repuestos_api():
    """API para obtener lista de repuestos (para selects)"""
    repuestos = Repuesto.query.all()
    return jsonify([{
        'id': r.id,
        'codigo': r.codigo,
        'nombre': r.nombre,
        'stock': r.stock_actual
    } for r in repuestos])


@inventario_bp.route('/equipo/<int:equipo_id>')
def inventario_por_equipo(equipo_id):
    """Muestra los repuestos asignados a un equipo específico"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    equipo = Equipo.query.get_or_404(equipo_id)
    
    # Obtener repuestos a través de la tabla RepuestoPorEquipo
    repuestos_asignados = [asignacion.repuesto for asignacion in equipo.repuestos_asignados]
    
    return render_template('inventario/inventario_equipo.html', equipo=equipo, repuestos=repuestos_asignados)