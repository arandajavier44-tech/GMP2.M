# routes/notificaciones.py
from flask import Blueprint, render_template, jsonify, request, Response
from flask_login import login_required, current_user
from models import db
from models.notificacion import Notificacion
from datetime import datetime
from utils.decorators import tecnico_required

notificaciones_bp = Blueprint('notificaciones', __name__)

# ============================================
# ENDPOINTS PRINCIPALES
# ============================================

@notificaciones_bp.route('/')
@tecnico_required
def panel():
    """Panel de notificaciones"""
    return render_template('notificaciones/panel.html')

@notificaciones_bp.route('/api/listar')
@tecnico_required
def api_listar():
    """API para listar notificaciones del usuario"""
    notificaciones = Notificacion.query.filter(
        (Notificacion.area == current_user.area_principal) |
        (Notificacion.usuario_id == current_user.id)
    ).order_by(
        Notificacion.fecha_creacion.desc()
    ).limit(100).all()
    
    return jsonify([{
        'id': n.id,
        'tipo': n.tipo,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'prioridad': n.prioridad,
        'leida': n.leida,
        'fecha': n.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_creacion': n.fecha_creacion.isoformat() if n.fecha_creacion else None,
        'fecha_vencimiento': n.fecha_vencimiento.isoformat() if n.fecha_vencimiento else None,
        'url': n.url or None,
        'elemento_id': n.elemento_id,
        'elemento_tipo': n.elemento_tipo
    } for n in notificaciones])

@notificaciones_bp.route('/api/marcar-leida/<int:notif_id>', methods=['POST'])
@tecnico_required
def api_marcar_leida(notif_id):
    """Marca una notificación como leída"""
    notif = Notificacion.query.get_or_404(notif_id)
    notif.marcar_leida()
    return jsonify({'success': True})

@notificaciones_bp.route('/api/marcar-todas-leidas', methods=['POST'])
@tecnico_required
def api_marcar_todas_leidas():
    """Marca todas las notificaciones como leídas"""
    notificaciones = Notificacion.query.filter(
        (Notificacion.area == current_user.area_principal) |
        (Notificacion.usuario_id == current_user.id),
        Notificacion.leida == False
    ).all()
    
    for n in notificaciones:
        n.marcar_leida()
    
    return jsonify({'success': True, 'cantidad': len(notificaciones)})

@notificaciones_bp.route('/api/contar-no-leidas')
@tecnico_required
def api_contar_no_leidas():
    """Cuenta notificaciones no leídas"""
    cantidad = Notificacion.query.filter(
        (Notificacion.area == current_user.area_principal) |
        (Notificacion.usuario_id == current_user.id),
        Notificacion.leida == False
    ).count()
    
    return jsonify({'cantidad': cantidad})

# ============================================
# PREFERENCIAS Y EXPORTACIÓN
# ============================================

@notificaciones_bp.route('/api/preferencias', methods=['GET', 'POST'])
@tecnico_required
def api_preferencias():
    """Gestiona preferencias de notificaciones del usuario"""
    import json
    
    if request.method == 'POST':
        preferencias = request.json
        if hasattr(current_user, 'preferencias_notificaciones'):
            current_user.preferencias_notificaciones = json.dumps(preferencias)
            db.session.commit()
        return jsonify({'success': True})
    else:
        preferencias = {}
        if hasattr(current_user, 'preferencias_notificaciones') and current_user.preferencias_notificaciones:
            try:
                preferencias = json.loads(current_user.preferencias_notificaciones)
            except:
                pass
        
        default_preferencias = {
            'tipos': ['orden', 'calibracion', 'capa', 'mantenimiento', 'documento', 'recordatorio'],
            'sonido': False,
            'toast': True,
            'emailDigest': False
        }
        
        for key, value in default_preferencias.items():
            if key not in preferencias:
                preferencias[key] = value
        
        return jsonify(preferencias)

@notificaciones_bp.route('/api/exportar')
@tecnico_required
def api_exportar():
    """Exporta notificaciones a CSV"""
    import csv
    from io import StringIO
    
    tipo = request.args.get('tipo', 'todos')
    prioridad = request.args.get('prioridad', 'todas')
    
    query = Notificacion.query.filter(
        (Notificacion.area == current_user.area_principal) |
        (Notificacion.usuario_id == current_user.id)
    )
    
    if tipo != 'todos':
        query = query.filter(Notificacion.tipo == tipo)
    if prioridad != 'todas':
        query = query.filter(Notificacion.prioridad == prioridad)
    
    notificaciones = query.order_by(Notificacion.fecha_creacion.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Título', 'Mensaje', 'Tipo', 'Prioridad', 'Fecha', 'Leída', 'URL'])
    
    for n in notificaciones:
        writer.writerow([
            n.id, n.titulo, n.mensaje, n.tipo, n.prioridad,
            n.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S'),
            'Sí' if n.leida else 'No', n.url or ''
        ])
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=notificaciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )

# ============================================
# LIMPIEZA
# ============================================

@notificaciones_bp.route('/api/limpiar-todas')
@tecnico_required
def api_limpiar_todas():
    """Elimina todas las notificaciones del usuario"""
    notificaciones = Notificacion.query.filter(
        (Notificacion.area == current_user.area_principal) |
        (Notificacion.usuario_id == current_user.id)
    ).all()
    
    cantidad = len(notificaciones)
    for n in notificaciones:
        db.session.delete(n)
    
    db.session.commit()
    return jsonify({'success': True, 'mensaje': f'{cantidad} notificaciones eliminadas'})

# ============================================
# VERIFICACIÓN DE DATOS
# ============================================

@notificaciones_bp.route('/api/verificar-datos')
@tecnico_required
def api_verificar_datos():
    """Verifica cuántos datos reales existen para generar notificaciones"""
    from models.orden_trabajo import OrdenTrabajo
    from models.calibracion import Calibracion
    from models.capa import CAPA
    from models.documento import DocumentoGMP
    from models.inventario import Repuesto
    from datetime import date, timedelta
    
    hoy = date.today()
    
    ordenes_pendientes = OrdenTrabajo.query.filter(
        OrdenTrabajo.estado.in_(['Pendiente', 'En Progreso', 'Aprobada'])
    ).count()
    
    ordenes_vencimiento = OrdenTrabajo.query.filter(
        OrdenTrabajo.fecha_estimada <= hoy + timedelta(days=3),
        OrdenTrabajo.fecha_estimada >= hoy,
        OrdenTrabajo.estado.in_(['Pendiente', 'En Progreso'])
    ).count()
    
    calibraciones_activas = Calibracion.query.filter(
        Calibracion.estado == 'Activo'
    ).count()
    
    calibraciones_vencidas = Calibracion.query.filter(
        Calibracion.fecha_proxima < hoy,
        Calibracion.estado == 'Activo'
    ).count()
    
    calibraciones_proximas = Calibracion.query.filter(
        Calibracion.fecha_proxima.between(hoy, hoy + timedelta(days=30)),
        Calibracion.estado == 'Activo'
    ).count()
    
    capas_abiertas = CAPA.query.filter(
        CAPA.estado != 'Cerrado'
    ).count()
    
    documentos_revision = DocumentoGMP.query.filter(
        DocumentoGMP.fecha_proxima_revision <= hoy + timedelta(days=30),
        DocumentoGMP.estado == 'Vigente'
    ).count()
    
    stock_bajo = Repuesto.query.filter(
        Repuesto.stock_actual <= Repuesto.stock_minimo
    ).count()
    
    return jsonify({
        'ordenes': {
            'pendientes': ordenes_pendientes,
            'proximas_vencer': ordenes_vencimiento
        },
        'calibraciones': {
            'activas': calibraciones_activas,
            'vencidas': calibraciones_vencidas,
            'proximas': calibraciones_proximas
        },
        'capas': {'abiertas': capas_abiertas},
        'documentos': {'por_revisar': documentos_revision},
        'inventario': {'stock_bajo': stock_bajo},
        'total_notificaciones_potenciales': (
            ordenes_vencimiento + calibraciones_vencidas + 
            calibraciones_proximas + capas_abiertas + 
            documentos_revision + stock_bajo
        )
    })

# ============================================
# GENERACIÓN DE NOTIFICACIONES
# ============================================

@notificaciones_bp.route('/api/generar-reales')
@tecnico_required
def api_generar_reales():
    """Genera notificaciones a partir de datos REALES del sistema"""
    from tasks.generar_notificaciones_reales import generar_todas_notificaciones_reales
    
    try:
        cantidad = generar_todas_notificaciones_reales()
        return jsonify({
            'success': True,
            'mensaje': f'Se generaron {cantidad} notificaciones a partir de datos reales',
            'cantidad': cantidad
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notificaciones_bp.route('/api/crear-prueba')
@tecnico_required
def api_crear_prueba():
    """Crea notificaciones de prueba"""
    from services.notification_service import NotificationService
    
    tipos = ['orden', 'calibracion', 'capa', 'documento', 'recordatorio']
    prioridades = ['Alta', 'Media', 'Baja']
    titulos = [
        'Nueva orden de trabajo asignada',
        'Calibración próxima a vencer',
        'CAPA requiere atención urgente',
        'Documento listo para revisión',
        'Recordatorio de mantenimiento programado'
    ]
    mensajes = [
        'Se ha creado una nueva orden de trabajo para el equipo.',
        'La calibración del instrumento vence próximamente.',
        'La CAPA requiere su atención y seguimiento.',
        'El documento ha sido actualizado y requiere revisión.',
        'Mantenimiento programado para la próxima semana.'
    ]
    
    creadas = 0
    for i in range(5):
        notif = NotificationService.crear_notificacion(
            tipo=tipos[i % len(tipos)],
            titulo=titulos[i % len(titulos)],
            mensaje=mensajes[i % len(mensajes)],
            prioridad=prioridades[i % len(prioridades)],
            area=current_user.area_principal or 'mantenimiento'
        )
        if notif:
            creadas += 1
    
    return jsonify({'success': True, 'mensaje': f'{creadas} notificaciones de prueba creadas'})

@notificaciones_bp.route('/api/ejecutar-automatico')
@tecnico_required
def api_ejecutar_automatico():
    """Ejecuta el notificador automático manualmente"""
    from utils.notificador_automatico import notificador_automatico
    
    try:
        notificador = notificador_automatico()
        notificador.ejecutar_notificaciones()
        
        return jsonify({
            'success': True,
            'mensaje': 'Notificador automático ejecutado correctamente'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notificaciones_bp.route('/api/test-email')
@tecnico_required
def api_test_email():
    """Envía un email de prueba al usuario actual"""
    from utils.notificador_email import notificador_email
    
    resultado = notificador_email.enviar(
        current_user.email,
        "🧪 Prueba GMP Maintenance - Notificaciones",
        f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <div style="background-color: #2c3e50; color: white; padding: 15px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h2>🔧 GMP Maintenance</h2>
                    <h3>Sistema de Notificaciones</h3>
                </div>
                <div style="padding: 20px;">
                    <p>Hola <strong>{current_user.nombre_completo or current_user.username}</strong>,</p>
                    <p>Este es un <strong>email de prueba</strong> para verificar que el sistema de notificaciones está funcionando correctamente.</p>
                    <p>Si recibes este mensaje, la configuración de email es correcta y recibirás notificaciones cuando:</p>
                    <ul>
                        <li>Te asignen una orden de trabajo</li>
                        <li>Te mencionen en un comentario con @</li>
                        <li>Te reasignen un tema de conversación</li>
                        <li>Haya calibraciones próximas a vencer</li>
                    </ul>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        Enviado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                    </p>
                </div>
                <div style="background-color: #f8f9fa; padding: 10px; text-align: center; border-radius: 0 0 10px 10px; font-size: 12px; color: #666;">
                    GMP Maintenance System - Notificaciones Automáticas
                </div>
            </div>
        </body>
        </html>
        """
    )
    
    if resultado:
        return jsonify({'success': True, 'mensaje': f'Email enviado a {current_user.email}'})
    else:
        return jsonify({'error': 'No se pudo enviar el email. Verifique la configuración.'}), 500
