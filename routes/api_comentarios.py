# routes/api_comentarios.py
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from models import db
from models.comentario import Comentario, Mencion, Conversacion, MensajeDirecto
from models.usuario import Usuario
from models.notificacion import Notificacion
from datetime import datetime
import re
import os
from werkzeug.utils import secure_filename

api_comentarios_bp = Blueprint('api_comentarios', __name__)


# ============================================
# COMENTARIOS POR ENTIDAD
# ============================================

@api_comentarios_bp.route('/comentarios/<entidad_tipo>/<int:entidad_id>', methods=['GET'])
@login_required
def get_comentarios(entidad_tipo, entidad_id):
    comentarios = Comentario.query.filter_by(
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        respuesta_a_id=None
    ).order_by(Comentario.created_at.asc()).all()
    
    return jsonify([{
        'id': c.id,
        'contenido': c.contenido,
        'usuario_id': c.usuario_id,
        'usuario_nombre': c.usuario_nombre or c.usuario.nombre_completo or c.usuario.username,
        'usuario_area': c.usuario.area_principal if c.usuario else '',
        'usuario_avatar': c.usuario.get_icon_rol() if hasattr(c.usuario, 'get_icon_rol') else 'fa-user',
        'created_at': c.created_at.isoformat(),
        'created_at_formateado': c.created_at.strftime('%d/%m/%Y %H:%M'),
        'adjuntos': c.adjuntos,
        'menciones': c.menciones,
        'respuestas': [{
            'id': r.id,
            'contenido': r.contenido,
            'usuario_nombre': r.usuario_nombre or r.usuario.nombre_completo or r.usuario.username,
            'created_at_formateado': r.created_at.strftime('%d/%m/%Y %H:%M')
        } for r in c.respuestas]
    } for c in comentarios])


@api_comentarios_bp.route('/comentarios/<entidad_tipo>/<int:entidad_id>', methods=['POST'])
@login_required
def add_comentario(entidad_tipo, entidad_id):
    data = request.json
    contenido = data.get('contenido', '').strip()
    respuesta_a_id = data.get('respuesta_a_id')
    
    if not contenido:
        return jsonify({'error': 'El comentario no puede estar vacío'}), 400
    
    menciones_usernames = re.findall(r'@(\w+)', contenido)
    menciones_ids = []
    
    comentario = Comentario(
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        contenido=contenido,
        usuario_id=current_user.id,
        usuario_nombre=current_user.nombre_completo or current_user.username,
        respuesta_a_id=respuesta_a_id
    )
    
    comentario.menciones = menciones_usernames
    db.session.add(comentario)
    db.session.flush()
    
    from utils.notificador_bd import notificador_bd
    
    for username in menciones_usernames:
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.id != current_user.id:
            notif = notificador_bd.crear_notificacion(
                tipo='mencion',
                titulo=f'📢 Te mencionaron en {entidad_tipo.upper()}',
                mensaje=f'{current_user.nombre_completo or current_user.username} te mencionó: {contenido[:100]}',
                prioridad='Media',
                usuario_id=usuario.id,
                url=f'/{entidad_tipo}/ver/{entidad_id}#comentario-{comentario.id}'
            )
            
            mencion = Mencion(
                comentario_id=comentario.id,
                usuario_id=usuario.id,
                notificacion_id=notif.id if notif else None
            )
            db.session.add(mencion)
            menciones_ids.append(usuario.id)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'comentario_id': comentario.id,
        'menciones': menciones_ids,
        'mensaje': f'Comentario agregado. Se notificó a {len(menciones_ids)} usuario(s).'
    })


@api_comentarios_bp.route('/comentarios/<int:comentario_id>/adjuntar', methods=['POST'])
@login_required
def adjuntar_archivo(comentario_id):
    comentario = Comentario.query.get_or_404(comentario_id)
    
    if comentario.usuario_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    filename = secure_filename(archivo.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    
    # Guardar en static/uploads/comentarios
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'comentarios')
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    archivo.save(filepath)
    
    # URL usando la ruta /uploads/ (que ahora está servida por app.py)
    comentario.agregar_adjunto(
        nombre=archivo.filename,
        url=f'/uploads/comentarios/{filename}',
        tamano=os.path.getsize(filepath)
    )
    
    return jsonify({
        'success': True,
        'adjunto': {
            'nombre': archivo.filename,
            'url': f'/uploads/comentarios/{filename}'
        }
    })


# ============================================
# MENSAJERÍA DIRECTA
# ============================================

@api_comentarios_bp.route('/conversaciones', methods=['GET'])
@login_required
def get_conversaciones():
    conversaciones = Conversacion.query.filter(
        Conversacion._participantes.contains(str(current_user.id))
    ).order_by(Conversacion.updated_at.desc()).all()
    
    resultado = []
    for conv in conversaciones:
        ultimo_mensaje = MensajeDirecto.query.filter_by(
            conversacion_id=conv.id
        ).order_by(MensajeDirecto.created_at.desc()).first()
        
        no_leidos = MensajeDirecto.query.filter(
            MensajeDirecto.conversacion_id == conv.id,
            MensajeDirecto.remitente_id != current_user.id,
            MensajeDirecto.leido == False
        ).count()
        
        resultado.append({
            'id': conv.id,
            'titulo': conv.titulo,
            'participantes': conv.participantes,
            'ultimo_mensaje': {
                'contenido': ultimo_mensaje.contenido[:100] if ultimo_mensaje else '',
                'fecha': ultimo_mensaje.created_at.isoformat() if ultimo_mensaje else None,
                'remitente': ultimo_mensaje.remitente.username if ultimo_mensaje else ''
            } if ultimo_mensaje else None,
            'no_leidos': no_leidos,
            'updated_at': conv.updated_at.isoformat()
        })
    
    return jsonify(resultado)


@api_comentarios_bp.route('/conversaciones', methods=['POST'])
@login_required
def crear_conversacion():
    data = request.json
    participantes = data.get('participantes', [])
    titulo = data.get('titulo', '')
    
    if current_user.id not in participantes:
        participantes.append(current_user.id)
    
    conversacion = Conversacion(
        titulo=titulo or f"Conversación con {len(participantes)} participantes",
        creador_id=current_user.id
    )
    conversacion.participantes = participantes
    
    db.session.add(conversacion)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'conversacion_id': conversacion.id
    })


@api_comentarios_bp.route('/conversaciones/<int:conversacion_id>/mensajes', methods=['GET'])
@login_required
def get_mensajes(conversacion_id):
    conversacion = Conversacion.query.get_or_404(conversacion_id)
    
    if current_user.id not in conversacion.participantes:
        return jsonify({'error': 'No autorizado'}), 403
    
    MensajeDirecto.query.filter(
        MensajeDirecto.conversacion_id == conversacion_id,
        MensajeDirecto.remitente_id != current_user.id,
        MensajeDirecto.leido == False
    ).update({'leido': True})
    db.session.commit()
    
    mensajes = MensajeDirecto.query.filter_by(
        conversacion_id=conversacion_id
    ).order_by(MensajeDirecto.created_at.asc()).all()
    
    return jsonify([{
        'id': m.id,
        'contenido': m.contenido,
        'remitente_id': m.remitente_id,
        'remitente_nombre': m.remitente.nombre_completo or m.remitente.username,
        'created_at': m.created_at.isoformat(),
        'created_at_formateado': m.created_at.strftime('%d/%m/%Y %H:%M'),
        'leido': m.leido
    } for m in mensajes])


@api_comentarios_bp.route('/conversaciones/<int:conversacion_id>/mensajes', methods=['POST'])
@login_required
def enviar_mensaje(conversacion_id):
    conversacion = Conversacion.query.get_or_404(conversacion_id)
    
    if current_user.id not in conversacion.participantes:
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    contenido = data.get('contenido', '').strip()
    
    if not contenido:
        return jsonify({'error': 'El mensaje no puede estar vacío'}), 400
    
    mensaje = MensajeDirecto(
        conversacion_id=conversacion_id,
        remitente_id=current_user.id,
        contenido=contenido
    )
    db.session.add(mensaje)
    
    conversacion.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    from utils.notificador_bd import notificador_bd
    
    for participante_id in conversacion.participantes:
        if participante_id != current_user.id:
            notificador_bd.crear_notificacion(
                tipo='mensaje',
                titulo=f'💬 Nuevo mensaje en {conversacion.titulo}',
                mensaje=f'{current_user.nombre_completo or current_user.username}: {contenido[:100]}',
                prioridad='Media',
                usuario_id=participante_id,
                url=f'/mensajes/conversacion/{conversacion_id}'
            )
    
    return jsonify({
        'success': True,
        'mensaje_id': mensaje.id,
        'created_at': mensaje.created_at.isoformat()
    })


# ============================================
# NOTIFICACIONES DE MENCIÓN
# ============================================

@api_comentarios_bp.route('/menciones/no-leidas', methods=['GET'])
@login_required
def get_menciones_no_leidas():
    menciones = Mencion.query.filter_by(
        usuario_id=current_user.id,
        leida=False
    ).order_by(Mencion.created_at.desc()).all()
    
    return jsonify([{
        'id': m.id,
        'comentario_id': m.comentario_id,
        'comentario_contenido': m.comentario.contenido[:100] if m.comentario else '',
        'entidad_tipo': m.comentario.entidad_tipo if m.comentario else '',
        'entidad_id': m.comentario.entidad_id if m.comentario else '',
        'remitente_nombre': m.comentario.usuario_nombre if m.comentario else '',
        'created_at': m.created_at.isoformat(),
        'created_at_formateado': m.created_at.strftime('%d/%m/%Y %H:%M')
    } for m in menciones])


@api_comentarios_bp.route('/menciones/<int:mencion_id>/marcar-leida', methods=['POST'])
@login_required
def marcar_mencion_leida(mencion_id):
    mencion = Mencion.query.get_or_404(mencion_id)
    
    if mencion.usuario_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    mencion.leida = True
    db.session.commit()
    
    return jsonify({'success': True})