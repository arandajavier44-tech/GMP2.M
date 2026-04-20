# models/__init__.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Importar modelos en orden
from models.usuario import Usuario, ActividadUsuario
from models.equipo import Equipo
from models.sistema import SistemaEquipo, PlanMantenimiento
from models.orden_trabajo import OrdenTrabajo
from models.calibracion import Calibracion, HistorialCalibracion
from models.inventario import Repuesto, RepuestoPorEquipo, RepuestoPorTarea, ConsumoRepuesto
from models.cambio import Cambio, HistorialCambio
from models.capa import CAPA, SeguimientoCAPA
from models.conocimiento import Normativa, ConsultaIA, RecomendacionIA
from models.notificacion import Notificacion
from models.documento import DocumentoGMP  
from models.plan_anual import PlanAnual, ActividadPlanAnual
from models.inspeccion import PlantillaInspeccion, InspeccionRealizada, ItemInspeccion
from models.riesgo import MatrizRiesgo, RiesgoIdentificado
from models.proveedor import Proveedor, RepuestoProveedor, ServicioProveedor, Compra, CompraItem

# ========== NUEVOS MODELOS: SERVICIOS GENERALES ==========
from models.instalacion import Instalacion, PlanMantenimientoInstalacion
from models.orden_servicio_general import OrdenServicioGeneral


__all__ = [
    'db', 'Usuario', 'ActividadUsuario', 'Equipo', 'SistemaEquipo', 'PlanMantenimiento',
    'OrdenTrabajo', 'Calibracion', 'HistorialCalibracion',
    'Repuesto', 'RepuestoPorEquipo', 'RepuestoPorTarea', 'ConsumoRepuesto',
    'Cambio', 'HistorialCambio', 'CAPA', 'SeguimientoCAPA',
    'Normativa', 'ConsultaIA', 'RecomendacionIA', 'Notificacion',
    'DocumentoGMP',
    'PlanAnual', 'ActividadPlanAnual',
    'PlantillaInspeccion', 'InspeccionRealizada', 'ItemInspeccion',
    'MatrizRiesgo', 'RiesgoIdentificado',
    'Proveedor', 'RepuestoProveedor', 'ServicioProveedor', 'Compra', 'CompraItem',
    # Nuevos modelos
    'Instalacion', 'PlanMantenimientoInstalacion', 'OrdenServicioGeneral',
]