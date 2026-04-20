# routes/api_temas.py
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from models import db
from models.tema_conversacion import TemaConversacion, MensajeTema
from models.usuario import Usuario
from datetime import datetime
import re
import json

api_temas_bp = Blueprint('api_temas', __name__)


# ============================================
# LISTAR TEMAS
# ============================================
@api_temas_bp.route('/temas', methods=['GET'])
@login_required
def listar_temas():
    """Listar temas con filtros"""
    estado = request.args.get('estado', 'todos')
    sector = request.args.get('sector', '')
    tipo = request.args.get('tipo', '')
    busqueda = request.args.get('busqueda', '')
    
    query = TemaConversacion.query
    
    if estado != 'todos':
        query = query.filter(TemaConversacion.estado == estado)
    else:
        query = query.filter(TemaConversacion.estado != 'Archivado')
    
    if sector:
        query = query.filter(TemaConversacion.sector == sector)
    
    if tipo:
        query = query.filter(TemaConversacion.tipo == tipo)
    
    if busqueda:
        query = query.filter(
            TemaConversacion.titulo.contains(busqueda) |
            TemaConversacion.codigo.contains(busqueda)
        )
    
    temas = query.order_by(TemaConversacion.fecha_creacion.desc()).all()
    
    # Filtrar por sector si no es admin
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        temas = [t for t in temas if t.sector == current_user.area_principal]
    
    return jsonify([{
        'id': t.id,
        'codigo': t.codigo,
        'titulo': t.titulo,
        'sector': t.sector,
        'tipo': t.tipo,
        'prioridad': t.prioridad,
        'estado': t.estado,
        'creado_por_nombre': t.creado_por_nombre,
        'asignado_a_nombre': t.asignado_a_nombre,
        'fecha_creacion_formateada': t.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'mensajes_count': len(t.mensajes)
    } for t in temas])


# ============================================
# CREAR TEMA
# ============================================
@api_temas_bp.route('/temas', methods=['POST'])
@login_required
def crear_tema():
    """Crear un nuevo tema"""
    data = request.form
    titulo = data.get('titulo')
    sector = data.get('sector')
    tipo = data.get('tipo')
    prioridad = data.get('prioridad', 'Media')
    descripcion = data.get('descripcion')
    asignado_a_id = data.get('asignado_a')
    
    if not all([titulo, sector, tipo, descripcion]):
        return jsonify({'error': 'Faltan campos requeridos'}), 400
    
    tema = TemaConversacion(
        codigo=TemaConversacion().generar_codigo(),
        titulo=titulo,
        sector=sector,
        tipo=tipo,
        prioridad=prioridad,
        descripcion=descripcion,
        creado_por_id=current_user.id,
        creado_por_nombre=current_user.nombre_completo or current_user.username,
        estado='Abierto'
    )
    
    if asignado_a_id:
        usuario = Usuario.query.get(asignado_a_id)
        if usuario:
            tema.asignado_a_id = usuario.id
            tema.asignado_a_nombre = usuario.nombre_completo or usuario.username
    
    db.session.add(tema)
    db.session.flush()
    
    # Crear mensaje inicial
    mensaje = MensajeTema(
        tema_id=tema.id,
        contenido=descripcion,
        usuario_id=current_user.id,
        usuario_nombre=current_user.nombre_completo or current_user.username
    )
    db.session.add(mensaje)
    
    db.session.commit()
    
    # Notificar al asignado
    if asignado_a_id and int(asignado_a_id) != current_user.id:
        from utils.notificador_bd import notificador_bd
        notificador_bd.crear_notificacion(
            tipo='tema',
            titulo=f'📋 Nuevo tema asignado: {tema.codigo}',
            mensaje=f'Se te ha asignado el tema: {titulo}',
            prioridad='Media',
            usuario_id=int(asignado_a_id),
            url=f'/dashboard#tema-{tema.id}'
        )
    
    return jsonify({'success': True, 'tema_id': tema.id, 'codigo': tema.codigo})


# ============================================
# OBTENER TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>', methods=['GET'])
@login_required
def obtener_tema(tema_id):
    tema = TemaConversacion.query.get_or_404(tema_id)
    
    return jsonify({
        'id': tema.id,
        'codigo': tema.codigo,
        'titulo': tema.titulo,
        'sector': tema.sector,
        'tipo': tema.tipo,
        'prioridad': tema.prioridad,
        'estado': tema.estado,
        'creado_por_nombre': tema.creado_por_nombre,
        'asignado_a_nombre': tema.asignado_a_nombre,
        'fecha_creacion_formateada': tema.fecha_creacion.strftime('%d/%m/%Y %H:%M')
    })


# ============================================
# MENSAJES DEL TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/mensajes', methods=['GET'])
@login_required
def obtener_mensajes(tema_id):
    mensajes = MensajeTema.query.filter_by(tema_id=tema_id).order_by(MensajeTema.created_at.asc()).all()
    
    return jsonify([{
        'id': m.id,
        'contenido': m.contenido,
        'usuario_id': m.usuario_id,
        'usuario_nombre': m.usuario_nombre,
        'created_at_formateada': m.created_at.strftime('%d/%m/%Y %H:%M'),
        'adjuntos': m.adjuntos
    } for m in mensajes])


@api_temas_bp.route('/temas/<int:tema_id>/mensajes', methods=['POST'])
@login_required
def enviar_mensaje(tema_id):
    data = request.json
    contenido = data.get('contenido', '').strip()
    
    if not contenido:
        return jsonify({'error': 'El mensaje no puede estar vacío'}), 400
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    
    # Detectar menciones
    menciones_usernames = re.findall(r'@(\w+)', contenido)
    
    mensaje = MensajeTema(
        tema_id=tema_id,
        contenido=contenido,
        usuario_id=current_user.id,
        usuario_nombre=current_user.nombre_completo or current_user.username
    )
    mensaje.menciones = menciones_usernames
    db.session.add(mensaje)
    
    if tema.estado == 'Abierto':
        tema.estado = 'En Proceso'
    
    db.session.commit()
    
    # Notificar menciones
    from utils.notificador_bd import notificador_bd
    for username in menciones_usernames:
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.id != current_user.id:
            notificador_bd.crear_notificacion(
                tipo='mencion_tema',
                titulo=f'📢 Te mencionaron en tema {tema.codigo}',
                mensaje=f'{current_user.nombre_completo or current_user.username} te mencionó: {contenido[:100]}',
                prioridad='Media',
                usuario_id=usuario.id,
                url=f'/dashboard#tema-{tema.id}'
            )
    
    return jsonify({'success': True, 'mensaje_id': mensaje.id})


# ============================================
# CAMBIAR ESTADO
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/estado', methods=['PUT'])
@login_required
def cambiar_estado(tema_id):
    data = request.json
    nuevo_estado = data.get('estado')
    
    if nuevo_estado not in ['Abierto', 'En Proceso', 'Resuelto', 'Cerrado']:
        return jsonify({'error': 'Estado no válido'}), 400
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    tema.estado = nuevo_estado
    
    if nuevo_estado == 'Cerrado':
        tema.fecha_cierre = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True})


# ============================================
# RESOLVER TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/resolver', methods=['POST'])
@login_required
def resolver_tema(tema_id):
    tema = TemaConversacion.query.get_or_404(tema_id)
    tema.estado = 'Resuelto'
    tema.resuelto_por_id = current_user.id
    tema.resuelto_por_nombre = current_user.nombre_completo or current_user.username
    tema.fecha_cierre = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True})


# ============================================
# ARCHIVAR TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/archivar', methods=['POST'])
@login_required
def archivar_tema(tema_id):
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        return jsonify({'error': 'No autorizado'}), 403
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    tema.estado = 'Archivado'
    tema.fecha_archivo = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True})


# ============================================
# REABRIR TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/reabrir', methods=['POST'])
@login_required
def reabrir_tema(tema_id):
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        return jsonify({'error': 'No autorizado'}), 403
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    
    if tema.estado not in ['Cerrado', 'Archivado', 'Resuelto']:
        return jsonify({'error': 'Solo se pueden reabrir temas cerrados, resueltos o archivados'}), 400
    
    tema.estado = 'Abierto'
    tema.fecha_cierre = None
    tema.fecha_archivo = None
    db.session.commit()
    
    from utils.notificador_bd import notificador_bd
    if tema.asignado_a_id:
        notificador_bd.crear_notificacion(
            tipo='tema',
            titulo=f'🔄 Tema reabierto: {tema.codigo}',
            mensaje=f'El tema "{tema.titulo}" ha sido reabierto',
            prioridad='Alta',
            usuario_id=tema.asignado_a_id,
            url=f'/dashboard#tema-{tema.id}'
        )
    
    return jsonify({'success': True})


# ============================================
# REASIGNAR TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/reasignar', methods=['POST'])
@login_required
def reasignar_tema(tema_id):
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    nuevo_asignado_id = data.get('asignado_id')
    comentario = data.get('comentario', '')
    
    if not nuevo_asignado_id:
        return jsonify({'error': 'Debe seleccionar un usuario'}), 400
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    usuario_anterior = tema.asignado_a_nombre
    nuevo_usuario = Usuario.query.get(nuevo_asignado_id)
    
    if not nuevo_usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    asignacion_anterior = tema.asignado_a_id
    
    tema.asignado_a_id = nuevo_asignado_id
    tema.asignado_a_nombre = nuevo_usuario.nombre_completo or nuevo_usuario.username
    
    tema.registrar_asignacion(
        usuario_id=current_user.id,
        usuario_nombre=current_user.nombre_completo or current_user.username,
        comentario=comentario
    )
    
    db.session.commit()
    
    from utils.notificador_bd import notificador_bd
    
    notificador_bd.crear_notificacion(
        tipo='tema',
        titulo=f'📋 Tema reasignado: {tema.codigo}',
        mensaje=f'Se te ha reasignado el tema "{tema.titulo}"',
        prioridad='Alta',
        usuario_id=nuevo_asignado_id,
        url=f'/dashboard#tema-{tema.id}'
    )
    
    if asignacion_anterior and asignacion_anterior != nuevo_asignado_id:
        notificador_bd.crear_notificacion(
            tipo='tema',
            titulo=f'📋 Tema reasignado: {tema.codigo}',
            mensaje=f'El tema "{tema.titulo}" ha sido reasignado a {tema.asignado_a_nombre}',
            prioridad='Media',
            usuario_id=asignacion_anterior,
            url=f'/dashboard#tema-{tema.id}'
        )
    
    return jsonify({'success': True, 'mensaje': f'Tema reasignado a {tema.asignado_a_nombre}'})


# ============================================
# ELIMINAR TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/eliminar', methods=['DELETE'])
@login_required
def eliminar_tema(tema_id):
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        return jsonify({'error': 'No autorizado'}), 403
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    
    if tema.estado not in ['Cerrado', 'Archivado']:
        return jsonify({'error': 'Solo se pueden eliminar temas cerrados o archivados'}), 400
    
    for mensaje in tema.mensajes:
        db.session.delete(mensaje)
    
    db.session.delete(tema)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': f'Tema {tema.codigo} eliminado'})


@api_temas_bp.route('/temas/eliminar-multiples', methods=['POST'])
@login_required
def eliminar_temas_multiples():
    if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.json
    temas_ids = data.get('ids', [])
    
    eliminados = 0
    for tema_id in temas_ids:
        tema = TemaConversacion.query.get(tema_id)
        if tema and tema.estado in ['Cerrado', 'Archivado']:
            for mensaje in tema.mensajes:
                db.session.delete(mensaje)
            db.session.delete(tema)
            eliminados += 1
    
    db.session.commit()
    return jsonify({'success': True, 'eliminados': eliminados})


# ============================================
# HISTORIAL DEL TEMA
# ============================================
@api_temas_bp.route('/temas/<int:tema_id>/historial', methods=['GET'])
@login_required
def obtener_historial(tema_id):
    tema = TemaConversacion.query.get_or_404(tema_id)
    return jsonify({'historial': tema.historial_asignaciones})


# ============================================
# USUARIOS ASIGNABLES
# ============================================
@api_temas_bp.route('/usuarios/asignables', methods=['GET'])
@login_required
def usuarios_asignables():
    usuarios = Usuario.query.filter_by(activo=True).all()
    return jsonify([{
        'id': u.id,
        'nombre': u.nombre_completo or u.username,
        'area': u.area_principal,
        'nivel': u.nivel_jerarquico
    } for u in usuarios])


# ============================================
# ESTADÍSTICAS
# ============================================
@api_temas_bp.route('/temas/estadisticas', methods=['GET'])
@login_required
def estadisticas_temas():
    temas_abiertos = TemaConversacion.query.filter(
        TemaConversacion.estado.in_(['Abierto', 'En Proceso'])
    ).count()
    
    temas_alta = TemaConversacion.query.filter(
        TemaConversacion.prioridad == 'Alta',
        TemaConversacion.estado.in_(['Abierto', 'En Proceso'])
    ).count()
    
    temas_media = TemaConversacion.query.filter(
        TemaConversacion.prioridad == 'Media',
        TemaConversacion.estado.in_(['Abierto', 'En Proceso'])
    ).count()
    
    return jsonify({
        'abiertos': temas_abiertos,
        'alta': temas_alta,
        'media': temas_media
    })

# Agregar al final de routes/api_temas.py

@api_temas_bp.route('/temas/<int:tema_id>/adjuntar', methods=['POST'])
@login_required
def adjuntar_archivo_tema(tema_id):
    """Adjuntar archivo a un mensaje del tema"""
    from models.tema_conversacion import MensajeTema
    from datetime import datetime
    import os
    from werkzeug.utils import secure_filename
    
    tema = TemaConversacion.query.get_or_404(tema_id)
    
    # Verificar permisos
    if tema.creado_por_id != current_user.id and tema.asignado_a_id != current_user.id:
        if current_user.nivel_jerarquico != 'jefe' and current_user.area_principal != 'administracion':
            return jsonify({'error': 'No autorizado'}), 403
    
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    # Validar tipo de archivo
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xls', '.xlsx'}
    ext = os.path.splitext(archivo.filename)[1].lower()
    
    if ext not in allowed_extensions:
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    # Validar tamaño (10MB)
    archivo.seek(0, os.SEEK_END)
    size = archivo.tell()
    archivo.seek(0)
    
    if size > 10 * 1024 * 1024:
        return jsonify({'error': 'El archivo no puede superar los 10MB'}), 400
    
    filename = secure_filename(archivo.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    
    # Usar la carpeta static/uploads/temas
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'temas')
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    archivo.save(filepath)
    
    # URL para acceder al archivo
    url = f'/static/uploads/temas/{filename}'
    
    # Crear un mensaje con el adjunto
    mensaje = MensajeTema(
        tema_id=tema_id,
        contenido=f"📎 Archivo adjunto: {archivo.filename}",
        usuario_id=current_user.id,
        usuario_nombre=current_user.nombre_completo or current_user.username
    )
    
    # Guardar adjunto en el mensaje
    mensaje.adjuntos = [{
        'nombre': archivo.filename,
        'url': url,
        'tamano': size,
        'fecha': datetime.now().isoformat()
    }]
    
    db.session.add(mensaje)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mensaje': 'Archivo adjuntado correctamente',
        'adjunto': {
            'nombre': archivo.filename,
            'url': url
        }
    })