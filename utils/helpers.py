# utils/helpers.py
from models.usuario import Usuario

def get_tecnicos_disponibles(area='mantenimiento', incluir_supervisores=True):
    """
    Obtiene técnicos disponibles para asignación
    area: área específica (mantenimiento, calidad, etc.)
    incluir_supervisores: si incluir jefes y supervisores
    """
    query = Usuario.query.filter(
        Usuario.area_principal == area,
        Usuario.activo == True
    )
    
    if not incluir_supervisores:
        query = query.filter(Usuario.nivel_jerarquico == 'operador')
    
    return query.order_by(Usuario.nivel_jerarquico, Usuario.nombre_completo).all()

def get_usuarios_por_area(area):
    """Obtiene usuarios de un área específica"""
    return Usuario.query.filter_by(area_principal=area, activo=True).all()

def get_usuarios_por_nivel(nivel):
    """Obtiene usuarios por nivel jerárquico"""
    return Usuario.query.filter_by(nivel_jerarquico=nivel, activo=True).all()