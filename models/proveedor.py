# models/proveedor.py
from models import db
from datetime import datetime

class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    
    # Información básica
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50))  # 'insumos', 'servicios', 'equipos', 'calibraciones', 'varios'
    rubro = db.Column(db.String(100))
    
    # Contacto
    contacto_nombre = db.Column(db.String(100))
    contacto_cargo = db.Column(db.String(100))
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(100))
    sitio_web = db.Column(db.String(200))
    
    # Dirección
    direccion = db.Column(db.String(200))
    ciudad = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    pais = db.Column(db.String(100), default='Argentina')
    
    # Datos fiscales
    cuit = db.Column(db.String(20))
    condicion_iva = db.Column(db.String(50))  # 'Responsable Inscripto', 'Monotributista', etc.
    
    # Calificaciones
    calificacion = db.Column(db.Integer, default=0)  # 1-5 estrellas
    observaciones = db.Column(db.Text)
    
    # Estado GMP (para proveedores calificados)
    es_proveedor_gmp = db.Column(db.Boolean, default=False)
    certificacion_gmp = db.Column(db.String(200))  # Ruta a certificado
    fecha_calificacion = db.Column(db.Date)
    fecha_vencimiento_calificacion = db.Column(db.Date)
    
    # Bancario
    banco = db.Column(db.String(100))
    cbu = db.Column(db.String(50))
    alias = db.Column(db.String(50))
    
    # Fechas
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_ultima_compra = db.Column(db.DateTime)
    
    # Estado
    activo = db.Column(db.Boolean, default=True)
    
    # Auditoría
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    repuestos = db.relationship('RepuestoProveedor', back_populates='proveedor', lazy=True, cascade='all, delete-orphan')
    servicios = db.relationship('ServicioProveedor', back_populates='proveedor', lazy=True, cascade='all, delete-orphan')
    compras = db.relationship('Compra', back_populates='proveedor', lazy=True)
    
    def __repr__(self):
        return f'<Proveedor {self.codigo}: {self.nombre}>'
    
    def generar_codigo(self):
        """Genera código único para proveedor"""
        import random
        import string
        año = datetime.now().year
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"PROV-{año}-{random_chars}"
    
    def get_calificacion_estrellas(self):
        """Devuelve estrellas HTML para calificación"""
        estrellas = ''
        for i in range(5):
            if i < self.calificacion:
                estrellas += '<i class="fas fa-star text-warning"></i>'
            else:
                estrellas += '<i class="far fa-star text-warning"></i>'
        return estrellas

class RepuestoProveedor(db.Model):
    __tablename__ = 'repuestos_proveedores'
    
    id = db.Column(db.Integer, primary_key=True)
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'), nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    
    codigo_proveedor = db.Column(db.String(100))  # Código que usa el proveedor para este repuesto
    precio_referencia = db.Column(db.Float)
    plazo_entrega_dias = db.Column(db.Integer)
    es_proveedor_principal = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relaciones
    repuesto = db.relationship('Repuesto', back_populates='proveedores')
    proveedor = db.relationship('Proveedor', back_populates='repuestos')
    
    __table_args__ = (db.UniqueConstraint('repuesto_id', 'proveedor_id', name='unique_repuesto_proveedor'),)

class ServicioProveedor(db.Model):
    __tablename__ = 'servicios_proveedor'
    
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    
    tipo_servicio = db.Column(db.String(50))  # 'mantenimiento', 'calibracion', 'validacion', 'reparacion'
    descripcion = db.Column(db.String(200))
    especialidad = db.Column(db.String(100))  # Ej: 'Equipos críticos', 'Instrumentos', etc.
    
    # Relación
    proveedor = db.relationship('Proveedor', back_populates='servicios')

class Compra(db.Model):
    __tablename__ = 'compras'
    
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    
    numero_compra = db.Column(db.String(50), unique=True)
    fecha_compra = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(20))  # 'repuesto', 'servicio', 'equipo'
    
    # Montos
    subtotal = db.Column(db.Float)
    impuestos = db.Column(db.Float)
    total = db.Column(db.Float)
    
    # Documentos
    orden_compra = db.Column(db.String(200))  # Ruta a PDF
    factura = db.Column(db.String(200))  # Ruta a PDF
    
    estado = db.Column(db.String(20), default='Pendiente')  # Pendiente, Recibida, Cancelada
    
    # Relaciones
    proveedor = db.relationship('Proveedor', back_populates='compras')
    items = db.relationship('CompraItem', back_populates='compra', lazy=True, cascade='all, delete-orphan')

class CompraItem(db.Model):
    __tablename__ = 'compras_items'
    
    id = db.Column(db.Integer, primary_key=True)
    compra_id = db.Column(db.Integer, db.ForeignKey('compras.id'), nullable=False)
    
    tipo_item = db.Column(db.String(20))  # 'repuesto', 'servicio'
    repuesto_id = db.Column(db.Integer, db.ForeignKey('repuestos.id'))
    
    descripcion = db.Column(db.String(200))
    cantidad = db.Column(db.Integer, default=1)
    precio_unitario = db.Column(db.Float)
    
    # Relaciones
    compra = db.relationship('Compra', back_populates='items')
    repuesto = db.relationship('Repuesto', foreign_keys=[repuesto_id])