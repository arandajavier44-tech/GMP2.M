# routes/dashboard.py
from flask import Blueprint, render_template, session, redirect, url_for
from flask_login import login_required
from models import db
from models.equipo import Equipo
from models.orden_trabajo import OrdenTrabajo
from models.calibracion import Calibracion
from models.capa import CAPA
from models.inventario import Repuesto
from models.sistema import PlanMantenimiento
from datetime import datetime, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    # ============================================
    # ESTADÍSTICAS RÁPIDAS - Versión simplificada
    # ============================================
    
    # Equipos
    total_equipos = Equipo.query.count() or 0
    equipos_operativos = Equipo.query.filter_by(current_status='Operativo').count() or 0
    equipos_mantenimiento = Equipo.query.filter_by(current_status='En Mantenimiento').count() or 0
    equipos_fuera_servicio = Equipo.query.filter_by(current_status='Fuera de Servicio').count() or 0
    
    # Órdenes de trabajo
    ordenes_pendientes = OrdenTrabajo.query.filter_by(estado='Pendiente').count() or 0
    ordenes_progreso = OrdenTrabajo.query.filter_by(estado='En Progreso').count() or 0
    ordenes_completadas_hoy = 0  # Simplificado
    
    # Inventario
    repuestos_criticos = Repuesto.query.filter(
        Repuesto.stock_actual <= Repuesto.stock_minimo
    ).count() or 0
    
    repuestos_bajos = 0  # Simplificado
    
    # Calibraciones
    calibraciones_vencidas = 0  # Simplificado
    calibraciones_proximas = 0  # Simplificado
    
    # CAPAs
    capas_abiertas = CAPA.query.filter_by(estado='Abierto').count() or 0
    
    # Datos para gráficos - Versión SIMPLIFICADA con valores seguros
    equipos_estados = {
        'labels': ['Operativo', 'En Mantenimiento', 'Fuera de Servicio'],
        'values': [equipos_operativos, equipos_mantenimiento, equipos_fuera_servicio],
        'colors': ['#28a745', '#ffc107', '#dc3545']
    }
    
    # Stock crítico - Lista vacía por ahora para evitar errores
    repuestos_stock_critico = []
    
    # Próximos mantenimientos - Lista vacía por ahora
    mantenimientos_proximos = []
    
    # Últimas órdenes
    ultimas_ordenes = OrdenTrabajo.query.order_by(
        OrdenTrabajo.fecha_creacion.desc()
    ).limit(5).all()
    
    # Últimos equipos
    ultimos_equipos = Equipo.query.order_by(
        Equipo.created_at.desc()
    ).limit(5).all()
    
    return render_template('dashboard.html',
                         total_equipos=total_equipos,
                         equipos_operativos=equipos_operativos,
                         equipos_mantenimiento=equipos_mantenimiento,
                         equipos_fuera_servicio=equipos_fuera_servicio,
                         ordenes_pendientes=ordenes_pendientes,
                         ordenes_progreso=ordenes_progreso,
                         ordenes_completadas_hoy=ordenes_completadas_hoy,
                         repuestos_criticos=repuestos_criticos,
                         repuestos_bajos=repuestos_bajos,
                         calibraciones_vencidas=calibraciones_vencidas,
                         calibraciones_proximas=calibraciones_proximas,
                         capas_abiertas=capas_abiertas,
                         equipos_estados=equipos_estados,
                         repuestos_stock_critico=repuestos_stock_critico,
                         mantenimientos_proximos=mantenimientos_proximos,
                         ultimas_ordenes=ultimas_ordenes,
                         ultimos_equipos=ultimos_equipos,
                         now=datetime.now())