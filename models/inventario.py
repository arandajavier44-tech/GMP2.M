# models/inventario.py
from models import db
from datetime import datetime
from models.proveedor import RepuestoProveedor
from models.equipo import Equipo

class Repuesto(db.Model):
    __tablename__ = 'repuestos'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    categoria = db.Column(db.String(50))
    
    stock_actual = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    stock_maximo = db.Column(db.Integer, default=50)
    ubicacion = db.Column(db.String(100))

    # Costos
    costo_unitario = db.Column(db.Float)
    
    # Especificaciones
    fabricante = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    numero_parte = db.Column(db.String(50))
    
    # GMP
    requiere_trazabilidad = db.Column(db.Boolean, default=True)
    certificado_calidad = db.Column(db.String(200))
    numero_lote = db.Column(db.String(50))
    fecha_vencimiento = db.Column(db.Date)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relación con equipo (opcional - para indicar equipo principal)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'), nullable=True)
    equipo = db.relationship('Equipo', backref='repuestos_principales')
    
    # Relaciones existentes
    equipos_asignados = db.relationship('RepuestoPorEquipo', back_populates='repuesto', lazy=True)
    tareas_asignadas = db.relationship('RepuestoPorTarea', back_populates='repuesto', lazy=True)
    consumos = db.relationship('ConsumoRepuesto', back_populates='repuesto', lazy=True)
    
    # Relación con proveedores
    proveedores = db.relationship('models.proveedor.RepuestoProveedor', back_populates='repuesto', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Repuesto {self.codigo}: {self.nombre}>'

    def get_equipos_que_usan(self):
        """Devuelve lista de equipos que usan este repuesto en sus tareas"""
        equipos = set()
        for tarea_asignada in self.tareas_asignadas:
            if tarea_asignada.tarea and tarea_asignada.tarea.sistema:
                equipos.add(tarea_asignada.tarea.sistema.equipo)
        return list(equipos)

    def calcular_stock_minimo_recomendado(self):
        """Calcula stock mínimo basado en la suma de requerimientos de todos los equipos"""
        total_requerido = 0
        for tarea_asignada in self.tareas_asignadas:
            total_requerido += tarea_asignada.cantidad_requerida
        return max(total_requerido, 5)  # Mínimo 5 unidades    
    
    def get_proveedores_lista(self):
        return [{
            'id': rp.proveedor.id,
            'nombre': rp.proveedor.nombre,
            'codigo_proveedor': rp.codigo_proveedor,
            'precio': rp.precio_referencia,
            'plazo': rp.plazo_entrega_dias,
            'es_principal': rp.es_proveedor_principal
        } for rp in self.proveedores]
    
    def get_proveedor_principal(self):
        for rp in self.proveedores:
            if rp.es_proveedor_principal:
                return {
                    'id': rp.proveedor.id,
                    'nombre': rp.proveedor.nombre,
                    'codigo_proveedor': rp.codigo_proveedor
                }
        return None


class RepuestoPorEquipo(db.Model):
    __tablename__ = 'repuestos_por_equipo'
    
    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'), nullable=False)
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'), nullable=False)
    
    cantidad_por_uso = db.Column(db.Integer, default=1)
    es_critico = db.Column(db.Boolean, default=False)
    observaciones = db.Column(db.Text)
    
    equipo = db.relationship('Equipo', back_populates='repuestos_asignados')
    repuesto = db.relationship('Repuesto', back_populates='equipos_asignados')
    
    __table_args__ = (db.UniqueConstraint('equipo_id', 'repuesto_id', name='unique_equipo_repuesto'),)


class RepuestoPorTarea(db.Model):
    __tablename__ = 'repuestos_por_tarea'
    
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('planes_mantenimiento.id'), nullable=False)
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'), nullable=False)
    
    cantidad_requerida = db.Column(db.Integer, default=1)
    es_obligatorio = db.Column(db.Boolean, default=False)
    
    tarea = db.relationship('PlanMantenimiento', back_populates='repuestos_necesarios')
    repuesto = db.relationship('Repuesto', back_populates='tareas_asignadas')
    
    __table_args__ = (db.UniqueConstraint('tarea_id', 'repuesto_id', name='unique_tarea_repuesto'),)


class ConsumoRepuesto(db.Model):
    __tablename__ = 'consumos_repuesto'
    
    id = db.Column(db.Integer, primary_key=True)
    orden_trabajo_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'), nullable=False)
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    fecha_consumo = db.Column(db.DateTime, default=datetime.utcnow)
    observaciones = db.Column(db.Text)
    lote = db.Column(db.String(50))
    registrado_por = db.Column(db.String(100))
    tipo_accion = db.Column(db.String(20), default='reemplazo')  # reemplazo, inspeccion, alerta, manual, no_aplica
    
    orden = db.relationship('OrdenTrabajo', back_populates='consumos')
    repuesto = db.relationship('Repuesto', back_populates='consumos')


class MovimientoStock(db.Model):
    __tablename__ = 'movimientos_stock'
    
    id = db.Column(db.Integer, primary_key=True)
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # entrada, salida
    cantidad = db.Column(db.Integer, nullable=False)
    stock_anterior = db.Column(db.Integer, nullable=False)
    stock_nuevo = db.Column(db.Integer, nullable=False)
    referencia = db.Column(db.String(100))
    realizado_por = db.Column(db.String(100))
    fecha_movimiento = db.Column(db.DateTime, default=datetime.utcnow)
    
    repuesto = db.relationship('Repuesto', backref='movimientos')