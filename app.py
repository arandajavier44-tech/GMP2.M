# app.py
from flask import Flask, render_template, session, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager
from datetime import datetime
import os
from config import Config

from flask_migrate import Migrate

# Importar db desde models
from models import db
from models.usuario import Usuario

# Importar todos los blueprints
from routes.auth import auth_bp
from routes.equipos import equipos_bp
from routes.dashboard import dashboard_bp
from routes.ordenes import ordenes_bp
from routes.calibraciones import calibraciones_bp
from routes.inventario import inventario_bp
from routes.reportes import reportes_bp
from routes.calendario import calendario_bp
from routes.cambios import cambios_bp
from routes.capa import capa_bp
from routes.ia import ia_bp
from routes.usuarios import usuarios_bp
from routes.notificaciones import notificaciones_bp
from routes.documentacion import documentacion_bp
from routes.inspecciones import inspecciones_bp
from routes.plan_anual import plan_anual_bp
from routes.riesgos import riesgos_bp
from routes.proveedores import proveedores_bp
from utils.generador_notificaciones_auto import generador_auto
from routes.servicios_generales import servicios_bp
from routes.api_comentarios import api_comentarios_bp
from routes.api_temas import api_temas_bp

from tasks.notification_tasks import ejecutar_todas_verificaciones

# ========== Scheduler para órdenes automáticas ==========
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import date
import atexit

login_manager = LoginManager()

def generar_ordenes_preventivas_automaticas():
    """Función que se ejecuta automáticamente para generar órdenes de trabajo preventivas"""
    from models import db
    from models.sistema import PlanMantenimiento
    from models.orden_trabajo import OrdenTrabajo
    from models.equipo import Equipo
    
    try:
        hoy = date.today()
        
        tareas_pendientes = PlanMantenimiento.query.filter(
            PlanMantenimiento.activo == True,
            PlanMantenimiento.proxima_ejecucion <= hoy,
            PlanMantenimiento.orden_generada == False
        ).all()
        
        ordenes_creadas = 0
        for tarea in tareas_pendientes:
            if not tarea.sistema or not tarea.sistema.equipo:
                continue
            
            equipo = tarea.sistema.equipo
            
            orden_existente = OrdenTrabajo.query.filter_by(
                equipo_id=equipo.id,
                tarea_origen_id=tarea.id,
                estado='Pendiente'
            ).first()
            
            if orden_existente:
                continue
            
            from routes.ordenes import generar_numero_ot_con_correlativo
            numero_ot, correlativo = generar_numero_ot_con_correlativo(equipo.id, 'Preventivo')
            
            if not numero_ot:
                continue
            
            tareas_seleccionadas = [{
                'id': tarea.id,
                'sistema_id': tarea.sistema.id,
                'descripcion': tarea.tarea_descripcion,
                'frecuencia_dias': tarea.frecuencia_dias
            }]
            
            nueva_orden = OrdenTrabajo(
                numero_ot=numero_ot,
                numero_correlativo=correlativo,
                codigo_equipo=equipo.code,
                equipo_id=equipo.id,
                tipo='Preventivo',
                titulo=f"Mantenimiento Preventivo - {equipo.code} - {tarea.tarea_descripcion[:50]}",
                descripcion=f"Tarea programada automáticamente: {tarea.tarea_descripcion}",
                tareas_seleccionadas=tareas_seleccionadas,
                tarea_origen_id=tarea.id,
                estado='Pendiente',
                prioridad='Media',
                creado_por='Sistema (Automático)',
                fecha_estimada=hoy
            )
            
            db.session.add(nueva_orden)
            tarea.orden_generada = True
            ordenes_creadas += 1
            print(f"✅ OT automática generada: {numero_ot} - {tarea.tarea_descripcion[:40]}")
        
        if ordenes_creadas > 0:
            db.session.commit()
            print(f"📋 {ordenes_creadas} órdenes preventivas generadas automáticamente el {hoy}")
        else:
            print(f"🔄 {datetime.now().strftime('%H:%M:%S')} - No hay tareas pendientes para generar órdenes")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error generando órdenes automáticas: {e}")
        import traceback
        traceback.print_exc()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Asegurar que existe el directorio de uploads
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Crear carpetas para adjuntos
    temas_upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'temas')
    os.makedirs(temas_upload_folder, exist_ok=True)
    
    comentarios_upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'comentarios')
    os.makedirs(comentarios_upload_folder, exist_ok=True)
    
    # Inicializar extensiones con la app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder al sistema.'
    
    # ========== FILTRO PERSONALIZADO PARA JSON ==========
    @app.template_filter('from_json')
    def from_json_filter(value):
        import json
        if not value:
            return []
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except (json.JSONDecodeError, TypeError):
            return []
    
    # Registrar TODOS los blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(equipos_bp, url_prefix='/equipos')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ordenes_bp, url_prefix='/ordenes')
    app.register_blueprint(calibraciones_bp, url_prefix='/calibraciones')
    app.register_blueprint(inventario_bp, url_prefix='/inventario')
    app.register_blueprint(reportes_bp, url_prefix='/reportes')
    app.register_blueprint(calendario_bp, url_prefix='/calendario')
    app.register_blueprint(cambios_bp, url_prefix='/cambios')
    app.register_blueprint(capa_bp, url_prefix='/capa')
    app.register_blueprint(ia_bp, url_prefix='/ia')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
    app.register_blueprint(notificaciones_bp, url_prefix='/notificaciones')
    app.register_blueprint(documentacion_bp, url_prefix='/documentacion')
    app.register_blueprint(inspecciones_bp, url_prefix='/inspecciones')
    app.register_blueprint(plan_anual_bp, url_prefix='/plan-anual')
    app.register_blueprint(riesgos_bp, url_prefix='/riesgos')
    app.register_blueprint(proveedores_bp, url_prefix='/proveedores')
    app.register_blueprint(servicios_bp)
    app.register_blueprint(api_comentarios_bp, url_prefix='/api')
    app.register_blueprint(api_temas_bp, url_prefix='/api')
   
    migrate = Migrate(app, db)

    # ========== CONTEXTO GLOBAL PARA TEMPLATES ==========
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}
    
    # ========== SERVIDOR DE ARCHIVOS ==========
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        """Servir archivos subidos desde cualquier carpeta uploads"""
        static_path = os.path.join(app.root_path, 'static', 'uploads')
        file_path = os.path.join(static_path, filename)
        
        if os.path.exists(file_path):
            return send_from_directory(static_path, filename)
        
        upload_path = app.config.get('UPLOAD_FOLDER', 'uploads')
        file_path = os.path.join(upload_path, filename)
        
        if os.path.exists(file_path):
            return send_from_directory(upload_path, filename)
        
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    # ========== VERIFICAR EXISTENCIA DE LOGO ==========
    logo_path = os.path.join(app.root_path, 'static', 'logo.png')
    app.jinja_env.globals.update(logo_exists=os.path.exists(logo_path))
    
    # Ruta principal
    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('auth.login'))
    
    # Manejo de errores
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

    # Ruta de prueba para generar órdenes manualmente
    @app.route('/test-generar-ots')
    def test_generar_ots():
        from app import generar_ordenes_preventivas_automaticas
        generar_ordenes_preventivas_automaticas()
        return "✅ Órdenes generadas. Revisa la consola y la sección de Órdenes de Trabajo."
    
    return app

# ⚠️ IMPORTANTE: El user_loader debe estar FUERA de la función create_app
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ========== SCHEDULER ==========
_scheduler = None
_scheduler_notificaciones = None

def init_scheduler(app):
    global _scheduler, _scheduler_notificaciones
    
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        
        def job_wrapper_ordenes():
            with app.app_context():
                generar_ordenes_preventivas_automaticas()
        
        _scheduler.add_job(
            func=job_wrapper_ordenes,
            trigger=IntervalTrigger(hours=1),
            id="generar_ordenes_automaticas",
            replace_existing=True
        )
        _scheduler.start()
        print("✅ Scheduler de órdenes automáticas iniciado (revisa cada 1 hora)")
    
    if _scheduler_notificaciones is None:
        _scheduler_notificaciones = BackgroundScheduler()
        
        def job_wrapper_notificaciones():
            with app.app_context():
                ejecutar_todas_verificaciones()
        
        _scheduler_notificaciones.add_job(
            func=job_wrapper_notificaciones,
            trigger=IntervalTrigger(hours=6),
            id="verificar_notificaciones",
            replace_existing=True
        )
        _scheduler_notificaciones.start()
        print("✅ Scheduler de notificaciones iniciado (revisa cada 6 horas)")
        
        with app.app_context():
            ejecutar_todas_verificaciones()

def start_scheduler(app):
    init_scheduler(app)

def shutdown_scheduler():
    global _scheduler, _scheduler_notificaciones
    if _scheduler:
        _scheduler.shutdown()
        print("✅ Scheduler de órdenes cerrado")
    if _scheduler_notificaciones:
        _scheduler_notificaciones.shutdown()
        print("✅ Scheduler de notificaciones cerrado")

atexit.register(shutdown_scheduler)