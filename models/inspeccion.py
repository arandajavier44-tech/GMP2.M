# models/inspeccion.py
from models import db
from datetime import datetime, date

class PlantillaInspeccion(db.Model):
    __tablename__ = 'plantillas_inspeccion'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    frecuencia = db.Column(db.String(20))  # 'diaria', 'semanal', 'mensual'
    tipo = db.Column(db.String(50))  # 'equipo', 'area', 'general'
    
    # CAMPOS GMP ONCOLÓGICO
    categoria_gmp = db.Column(db.String(50))  # 'contencion', 'ambiental', 'equipo', 'limpieza', 'documentacion', 'seguridad'
    gmp_grade = db.Column(db.String(10))      # 'A', 'B', 'C', 'D', 'NC'
    requiere_foto = db.Column(db.Boolean, default=False)
    tiempo_estimado_min = db.Column(db.Integer, default=15)
    requiere_validacion = db.Column(db.Boolean, default=False)
    
    # Items de inspección (JSON) - para compatibilidad
    items = db.Column(db.JSON)
    
    # Aplicabilidad
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    area = db.Column(db.String(50))
    
    activo = db.Column(db.Boolean, default=True)
    creado_por = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    equipo = db.relationship('Equipo')
    
    def __repr__(self):
        return f'<Plantilla {self.nombre}>'
    
    def get_items_activos(self):
        """Obtiene los items activos ordenados"""
        return ItemInspeccion.query.filter_by(
            plantilla_id=self.id, 
            activo=True
        ).order_by(ItemInspeccion.orden).all()


class InspeccionRealizada(db.Model):
    __tablename__ = 'inspecciones_realizadas'
    
    id = db.Column(db.Integer, primary_key=True)
    plantilla_id = db.Column(db.Integer, db.ForeignKey('plantillas_inspeccion.id'), nullable=False)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    
    fecha = db.Column(db.Date, default=date.today)
    hora_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    hora_fin = db.Column(db.DateTime)
    realizada_por = db.Column(db.String(100))
    
    # Resultados (JSON)
    resultados = db.Column(db.JSON)
    
    # Resultado general
    conforme = db.Column(db.Boolean)
    observaciones = db.Column(db.Text)
    acciones = db.Column(db.Text)
    
    # Campos GMP adicionales
    lotes_afectados = db.Column(db.String(200))  # Lotes que podrían verse afectados
    requiere_capa = db.Column(db.Boolean, default=False)
    fotos_adjuntas = db.Column(db.Boolean, default=False)
    
    # Relaciones
    plantilla = db.relationship('PlantillaInspeccion')
    equipo = db.relationship('Equipo')
    
    def __repr__(self):
        return f'<Inspeccion {self.fecha} - {self.plantilla.nombre}>'
    
    def get_porcentaje_conformidad(self):
        """Calcula el porcentaje de conformidad"""
        if not self.resultados:
            return 0
        total = len(self.resultados)
        if total == 0:
            return 0
        conformes = sum(1 for r in self.resultados if r.get('conforme', False))
        return int((conformes / total) * 100)


class ItemInspeccion(db.Model):
    __tablename__ = 'items_inspeccion'
    
    id = db.Column(db.Integer, primary_key=True)
    plantilla_id = db.Column(db.Integer, db.ForeignKey('plantillas_inspeccion.id'), nullable=False)
    
    orden = db.Column(db.Integer)
    descripcion = db.Column(db.String(200), nullable=False)
    criterio = db.Column(db.Text)
    
    tipo_respuesta = db.Column(db.String(20), default='booleano')  # 'booleano', 'texto', 'numerico', 'opciones', 'rango'
    opciones = db.Column(db.JSON)
    valor_esperado = db.Column(db.String(100))
    unidad = db.Column(db.String(20))
    
    # Campos GMP
    valor_minimo = db.Column(db.Float)
    valor_maximo = db.Column(db.Float)
    requiere_foto_si_no_conforme = db.Column(db.Boolean, default=False)
    
    es_critico = db.Column(db.Boolean, default=False)
    
    activo = db.Column(db.Boolean, default=True)
    
    plantilla = db.relationship('PlantillaInspeccion', foreign_keys=[plantilla_id])
    
    def __repr__(self):
        return f'<Item {self.orden}: {self.descripcion[:50]}>'