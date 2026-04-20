# models/documento.py
from models import db
from datetime import datetime
import json

# Tabla intermedia para relación muchos a muchos entre documentos y equipos
documento_equipo = db.Table('documento_equipo',
    db.Column('documento_id', db.Integer, db.ForeignKey('documentos_gmp.id'), primary_key=True),
    db.Column('equipo_id', db.Integer, db.ForeignKey('equipos.id'), primary_key=True)
)

class DocumentoGMP(db.Model):
    __tablename__ = 'documentos_gmp'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(50))  # 'sop', 'validacion', 'calibracion', 'ficha', 'plan', 'reporte', 'certificado', 'protocolo'
    subtipo = db.Column(db.String(50))  # 'iq', 'oq', 'pq', 'diario', 'semanal', 'mensual', 'anual'
    codigo = db.Column(db.String(50), unique=True)
    version = db.Column(db.String(10), default='1.0')
    qr_code = db.Column(db.String(200))

    # Contenido del documento (HTML generado)
    contenido = db.Column(db.Text)
    
    # Datos estructurados editables (JSON)
    datos_editables = db.Column(db.JSON)
    
    # Campos editables definidos por el usuario
    campos_personalizados = db.Column(db.JSON, default={})
    
    # Metadatos (relaciones existentes)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id'))
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'))
    calibracion_id = db.Column(db.Integer, db.ForeignKey('calibraciones.id'))
    sistema_id = db.Column(db.Integer, db.ForeignKey('sistemas_equipo.id'))
    tarea_id = db.Column(db.Integer, db.ForeignKey('planes_mantenimiento.id'))
    
    # NUEVA: Relación muchos a muchos con equipos
    equipos_asignados = db.relationship('Equipo', secondary=documento_equipo, backref='documentos_asignados')
    
    # Fechas
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_revision = db.Column(db.Date)
    fecha_proxima_revision = db.Column(db.Date)
    fecha_emision = db.Column(db.Date)
    
    # Responsables
    creado_por = db.Column(db.String(100))
    revisado_por = db.Column(db.String(100))
    aprobado_por = db.Column(db.String(100))
    
    # Firmas
    firma_creador = db.Column(db.String(200))
    firma_revisor = db.Column(db.String(200))
    firma_aprobador = db.Column(db.String(200))
    
    # Estado
    estado = db.Column(db.String(20), default='Borrador')  # Borrador, Vigente, Obsoleto, En Revision
    
    # Historial de cambios
    historial_cambios = db.Column(db.JSON, default=[])
    
    # Relaciones existentes
    equipo = db.relationship('Equipo', foreign_keys=[equipo_id])
    orden = db.relationship('OrdenTrabajo', foreign_keys=[orden_id])
    calibracion = db.relationship('Calibracion', foreign_keys=[calibracion_id])
    sistema = db.relationship('SistemaEquipo', foreign_keys=[sistema_id])
    tarea = db.relationship('PlanMantenimiento', foreign_keys=[tarea_id])
    
    def __repr__(self):
        return f'<DocumentoGMP {self.codigo}: {self.titulo}>'
    
    def generar_codigo(self):
        """Genera código único para el documento"""
        import random
        import string
        
        prefijos = {
            'sop': 'SOP',
            'sop_mantenimiento': 'SOP-MT',
            'sop_calibracion': 'SOP-CL', 
            'sop_limpieza': 'SOP-LM',
            'validacion': 'VAL',
            'calibracion': 'CAL',
            'ficha': 'FIC',
            'plan': 'PLN',
            'reporte': 'RPT',
            'certificado': 'CRT',
            'protocolo': 'PTC'
        }
        prefijo = prefijos.get(self.tipo, 'DOC')
        
        if self.subtipo:
            prefijo = f"{prefijo}-{self.subtipo.upper()}"
        
        año = datetime.now().year
        mes = datetime.now().strftime('%m')
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        
        return f"{prefijo}-{año}{mes}-{random_chars}"
    
    def actualizar_datos_editables(self, nuevos_datos, usuario):
        """Actualiza los datos editables y registra el cambio"""
        cambios = []
        
        for key, value in nuevos_datos.items():
            if key in (self.datos_editables or {}) and self.datos_editables.get(key) != value:
                cambios.append({
                    'campo': key,
                    'anterior': self.datos_editables.get(key),
                    'nuevo': value,
                    'fecha': datetime.now().isoformat(),
                    'usuario': usuario
                })
        
        if self.datos_editables is None:
            self.datos_editables = {}
        self.datos_editables.update(nuevos_datos)
        
        if cambios:
            if not self.historial_cambios:
                self.historial_cambios = []
            self.historial_cambios.extend(cambios)
        
        self.regenerar_contenido()
        db.session.commit()
    
    def regenerar_contenido(self):
        """Regenera el HTML del documento a partir de los datos editables"""
        from utils.generador_documentos import generador_docs
        
        if self.tipo == 'sop' and self.equipo:
            self.contenido = generador_docs._formatear_sop_html(
                self.equipo, 
                self.datos_editables or {}, 
                self.datos_editables.get('contenido_ia', '') if self.datos_editables else '',
                self
            )
        elif self.tipo == 'ficha' and self.equipo:
            self.contenido = generador_docs._generar_html_ficha(self.equipo, self)
        elif self.tipo == 'certificado' and self.calibracion:
            self.contenido = generador_docs._generar_html_certificado(self.calibracion, self)
        elif self.tipo == 'protocolo' and self.equipo:
            self.contenido = generador_docs._generar_html_protocolo(self.equipo, self)
    
    def agregar_campo_personalizado(self, nombre, valor, tipo_dato='texto'):
        """Agrega un campo personalizado al documento"""
        if not self.campos_personalizados:
            self.campos_personalizados = {}
        
        self.campos_personalizados[nombre] = {
            'valor': valor,
            'tipo': tipo_dato
        }
        db.session.commit()
    
    def asignar_a_equipo(self, equipo_id):
        """Asigna el documento a un equipo"""
        from models.equipo import Equipo
        equipo = Equipo.query.get(equipo_id)
        if equipo and equipo not in self.equipos_asignados:
            self.equipos_asignados.append(equipo)
            db.session.commit()
            return True
        return False
    
    def get_equipos_nombres(self):
        """Devuelve lista de nombres de equipos asignados"""
        return [e.code for e in self.equipos_asignados]
    
    def get_html_imprimible(self):
        """Genera versión optimizada para impresión del documento"""
        from utils.generador_documentos import generador_docs
        return generador_docs.generar_html_imprimible(self)