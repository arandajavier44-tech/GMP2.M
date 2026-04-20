# utils/qr_system.py
import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
import json
from flask import current_app, url_for
from datetime import datetime

class QRTrazabilidad:
    """Sistema centralizado de generación de QR con datos de trazabilidad"""
    
    # Configuración por tipo de documento
    CONFIG = {
        'orden': {
            'color': '#1a5276',  # Azul
            'icono': '🔧',
            'campos': ['numero_ot', 'titulo', 'estado', 'equipo', 'fecha_creacion', 'prioridad']
        },
        'calibracion': {
            'color': '#28a745',  # Verde
            'icono': '📏',
            'campos': ['instrumento', 'certificado_numero', 'fecha_calibracion', 'fecha_proxima', 'resultado']
        },
        'equipo': {
            'color': '#007bff',  # Azul claro
            'icono': '⚙️',
            'campos': ['code', 'name', 'gmp_classification', 'current_status', 'ubicacion']
        },
        'capa': {
            'color': '#dc3545',  # Rojo
            'icono': '⚠️',
            'campos': ['numero_capa', 'titulo', 'estado', 'fecha_apertura', 'prioridad']
        },
        'inspeccion': {
            'color': '#fd7e14',  # Naranja
            'icono': '🔍',
            'campos': ['tipo', 'fecha', 'inspector', 'resultado', 'observaciones']
        }
    }
    
    @staticmethod
    def generar_qr(documento, tipo, incluir_logo=True, tamano=300):
        """
        Genera QR con datos de trazabilidad para cualquier documento
        
        Args:
            documento: Objeto del documento (orden, calibracion, equipo, etc.)
            tipo: 'orden', 'calibracion', 'equipo', 'capa', 'inspeccion'
            incluir_logo: bool - incluir logo GMP
            tamano: int - tamaño del QR en pixeles
        
        Returns:
            str: Ruta del archivo QR generado
        """
        try:
            # Configurar directorio
            qr_dir = os.path.join(current_app.static_folder, 'qrcodes', tipo)
            os.makedirs(qr_dir, exist_ok=True)
            
            # Obtener configuración
            config = QRTrazabilidad.CONFIG.get(tipo, QRTrazabilidad.CONFIG['orden'])
            
            # Recopilar datos de trazabilidad
            datos = QRTrazabilidad._recopilar_datos(documento, tipo, config['campos'])
            
            # Agregar metadatos de trazabilidad
            datos['metadata'] = {
                'tipo': tipo,
                'fecha_generacion': datetime.now().isoformat(),
                'version': '1.0',
                'sistema': 'GMP Maintenance System'
            }
            
            # Agregar URL para vista web
            datos['url'] = QRTrazabilidad._get_url(documento, tipo)
            
            # Convertir a JSON para el QR
            qr_data = json.dumps(datos, ensure_ascii=False, default=str)
            
            # Configurar colores
            colores = QRTrazabilidad._get_colores_segun_estado(documento, tipo, config['color'])
            
            # Crear QR mejorado
            qr = qrcode.QRCode(
                version=QRTrazabilidad._calcular_version(len(qr_data)),
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Generar imagen
            img = qr.make_image(
                fill_color=colores['color'],
                back_color=colores['fondo']
            ).convert('RGB')
            
            # Redimensionar
            img = img.resize((tamano, tamano), Image.Resampling.LANCZOS)
            
            # Agregar logo si se solicita
            if incluir_logo:
                img = QRTrazabilidad._agregar_logo_con_icono(img, config['icono'], colores['color'])
            
            # Agregar información de trazabilidad alrededor del QR
            img = QRTrazabilidad._agregar_marco_trazabilidad(img, documento, tipo, datos)
            
            # Guardar imagen
            nombre_archivo = QRTrazabilidad._generar_nombre(documento, tipo)
            ruta_completa = os.path.join(qr_dir, nombre_archivo)
            img.save(ruta_completa, 'PNG', quality=95)
            
            # Guardar también los datos JSON para consulta rápida
            json_path = os.path.join(qr_dir, f"{nombre_archivo.replace('.png', '.json')}")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
            
            # Actualizar el documento con la ruta del QR
            ruta_relativa = f"qrcodes/{tipo}/{nombre_archivo}"
            QRTrazabilidad._actualizar_documento(documento, tipo, ruta_relativa)
            
            print(f"✅ QR de trazabilidad generado para {tipo}: {nombre_archivo}")
            return ruta_relativa
            
        except Exception as e:
            print(f"❌ Error generando QR: {e}")
            return QRTrazabilidad._generar_qr_fallback(documento, tipo)
    
    @staticmethod
    def _recopilar_datos(documento, tipo, campos):
        """Recopila los datos de trazabilidad del documento"""
        datos = {}
        
        if tipo == 'orden':
            datos = {
                'numero_ot': documento.numero_ot,
                'titulo': documento.titulo,
                'estado': documento.estado,
                'equipo': documento.equipo.code if documento.equipo else 'N/A',
                'equipo_nombre': documento.equipo.name if documento.equipo else 'N/A',
                'fecha_creacion': documento.fecha_creacion.strftime('%d/%m/%Y %H:%M') if documento.fecha_creacion else 'N/A',
                'prioridad': documento.prioridad,
                'tipo': documento.tipo,
                'asignado_a': documento.asignado_a or 'No asignado',
                'fecha_estimada': documento.fecha_estimada.strftime('%d/%m/%Y') if documento.fecha_estimada else 'N/A'
            }
            
        elif tipo == 'calibracion':
            datos = {
                'instrumento': documento.instrumento,
                'certificado_numero': documento.certificado_numero or 'N/A',
                'fecha_calibracion': documento.fecha_calibracion.strftime('%d/%m/%Y'),
                'fecha_proxima': documento.fecha_proxima.strftime('%d/%m/%Y'),
                'resultado': documento.resultado or 'Pendiente',
                'laboratorio': documento.laboratorio or 'N/A',
                'clasificacion_gmp': documento.clasificacion_gmp or 'N/A',
                'estado': documento.estado
            }
            
        elif tipo == 'equipo':
            datos = {
                'code': documento.code,
                'name': documento.name,
                'gmp_classification': documento.gmp_classification,
                'current_status': documento.current_status,
                'ubicacion': documento.location or 'N/A',
                'manufacturer': documento.manufacturer or 'N/A',
                'model': documento.model or 'N/A'
            }
        
        return datos
    
    @staticmethod
    def _get_url(documento, tipo):
        """Genera URL para acceder al documento"""
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        
        urls = {
            'orden': f"{base_url}/ordenes/{documento.id}",
            'calibracion': f"{base_url}/calibraciones/{documento.id}",
            'equipo': f"{base_url}/equipos/{documento.id}"
        }
        
        return urls.get(tipo, f"{base_url}/")
    
    @staticmethod
    def _get_colores_segun_estado(documento, tipo, color_default):
        """Determina colores según el estado del documento"""
        colores_base = {
            'fondo': '#FFFFFF',
            'color': color_default
        }
        
        if tipo == 'orden':
            if documento.estado == 'Pendiente':
                colores_base['color'] = '#ffc107'  # Amarillo
            elif documento.estado == 'En Progreso':
                colores_base['color'] = '#17a2b8'  # Cyan
            elif documento.estado == 'Completada':
                colores_base['color'] = '#28a745'  # Verde
            elif documento.estado == 'Cancelada':
                colores_base['color'] = '#dc3545'  # Rojo
                
        elif tipo == 'calibracion':
            if documento.get_estado_texto() == 'Vencida':
                colores_base['color'] = '#dc3545'
            elif documento.get_estado_texto() == 'Por Vencer':
                colores_base['color'] = '#ffc107'
                
        return colores_base
    
    @staticmethod
    def _calcular_version(longitud_datos):
        """Calcula la versión del QR según la cantidad de datos"""
        if longitud_datos < 100:
            return 3
        elif longitud_datos < 200:
            return 5
        elif longitud_datos < 400:
            return 7
        else:
            return 10
    
    @staticmethod
    def _agregar_logo_con_icono(img, icono, color):
        """Agrega logo con ícono personalizado"""
        try:
            logo_size = img.size[0] // 4
            logo = Image.new('RGBA', (logo_size, logo_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(logo)
            
            # Fondo circular
            center = logo_size // 2
            radio = logo_size // 2 - 5
            draw.ellipse([center - radio, center - radio, center + radio, center + radio], 
                        fill=color)
            
            # Círculo blanco interior
            draw.ellipse([center - radio + 5, center - radio + 5, 
                         center + radio - 5, center + radio - 5], 
                        fill='white')
            
            # Ícono
            try:
                from PIL import ImageFont
                font = ImageFont.truetype("segoeui.ttf", logo_size // 2)
            except:
                font = ImageFont.load_default()
            
            # Centrar ícono
            bbox = draw.textbbox((0, 0), icono, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((center - text_width//2, center - text_height//2), 
                     icono, fill=color, font=font)
            
            # Pegar logo
            pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)
            img.paste(logo, pos, logo)
            
            return img
            
        except Exception as e:
            print(f"Error agregando logo: {e}")
            return img
    
    @staticmethod
    def _agregar_marco_trazabilidad(img, documento, tipo, datos):
        """Agrega marco con información de trazabilidad alrededor del QR"""
        try:
            # Dimensiones
            ancho_qr, alto_qr = img.size
            ancho_total = ancho_qr + 40
            alto_total = alto_qr + 120
            
            # Crear imagen con marco
            marco = Image.new('RGB', (ancho_total, alto_total), 'white')
            draw = ImageDraw.Draw(marco)
            
            # Dibujar borde
            draw.rectangle([2, 2, ancho_total - 2, alto_total - 2], outline='#cccccc', width=1)
            
            # Pegar QR centrado
            marco.paste(img, (20, 60))
            
            # Configurar fuentes
            try:
                font_titulo = ImageFont.truetype("arial.ttf", 14)
                font_texto = ImageFont.truetype("arial.ttf", 10)
                font_pequeno = ImageFont.truetype("arial.ttf", 8)
            except:
                font_titulo = ImageFont.load_default()
                font_texto = ImageFont.load_default()
                font_pequeno = ImageFont.load_default()
            
            # Título
            titulos = {
                'orden': f"OT: {datos.get('numero_ot', 'N/A')}",
                'calibracion': f"Certificado: {datos.get('certificado_numero', 'N/A')}",
                'equipo': f"Equipo: {datos.get('code', 'N/A')}"
            }
            titulo = titulos.get(tipo, f"Documento {tipo.upper()}")
            
            # Calcular posición centrada para el título
            bbox = draw.textbbox((0, 0), titulo, font=font_titulo)
            text_width = bbox[2] - bbox[0]
            draw.text(((ancho_total - text_width) // 2, 15), titulo, fill='#1a5276', font=font_titulo)
            
            # Información de trazabilidad
            y_offset = alto_qr + 80
            
            if tipo == 'orden':
                draw.text((25, y_offset), f"📋 Estado: {datos.get('estado', 'N/A')}", fill='black', font=font_texto)
                draw.text((25, y_offset + 18), f"⚙️ Equipo: {datos.get('equipo', 'N/A')}", fill='black', font=font_texto)
                draw.text((25, y_offset + 36), f"📅 Fecha: {datos.get('fecha_creacion', 'N/A')}", fill='black', font=font_texto)
                draw.text((ancho_total - 200, y_offset), f"🎯 Prioridad: {datos.get('prioridad', 'N/A')}", fill='black', font=font_texto)
                
            elif tipo == 'calibracion':
                draw.text((25, y_offset), f"📏 Instrumento: {datos.get('instrumento', 'N/A')[:30]}", fill='black', font=font_texto)
                draw.text((25, y_offset + 18), f"📅 Válida hasta: {datos.get('fecha_proxima', 'N/A')}", fill='black', font=font_texto)
                draw.text((25, y_offset + 36), f"🔬 Laboratorio: {datos.get('laboratorio', 'N/A')}", fill='black', font=font_texto)
            
            # Footer
            fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')
            draw.text((10, alto_total - 15), f"Generado: {fecha_gen}", fill='#999999', font=font_pequeno)
            draw.text((ancho_total - 180, alto_total - 15), "Sistema GMP v2.0", fill='#999999', font=font_pequeno)
            
            return marco
            
        except Exception as e:
            print(f"Error agregando marco: {e}")
            return img
    
    @staticmethod
    def _generar_nombre(documento, tipo):
        """Genera nombre único para el archivo QR"""
        if tipo == 'orden':
            return f"ot_{documento.id}_{documento.numero_ot.replace('-', '_')}.png"
        elif tipo == 'calibracion':
            return f"cal_{documento.id}_{documento.instrumento.replace(' ', '_')[:20]}.png"
        elif tipo == 'equipo':
            return f"eq_{documento.id}_{documento.code}.png"
        else:
            return f"{tipo}_{documento.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    @staticmethod
    def _actualizar_documento(documento, tipo, ruta_qr):
        """Actualiza el campo QR en el documento"""
        if tipo == 'orden':
            documento.qr_code = ruta_qr
        elif tipo == 'calibracion':
            documento.qr_code = ruta_qr
        # Agregar más tipos según necesidad
        
        from models import db
        db.session.commit()
    
    @staticmethod
    def _generar_qr_fallback(documento, tipo):
        """Genera QR simple como fallback"""
        try:
            import qrcode
            qr_dir = os.path.join(current_app.static_folder, 'qrcodes', tipo)
            os.makedirs(qr_dir, exist_ok=True)
            
            url = QRTrazabilidad._get_url(documento, tipo)
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            nombre = QRTrazabilidad._generar_nombre(documento, tipo)
            ruta = os.path.join(qr_dir, nombre)
            img.save(ruta)
            
            ruta_relativa = f"qrcodes/{tipo}/{nombre}"
            QRTrazabilidad._actualizar_documento(documento, tipo, ruta_relativa)
            
            return ruta_relativa
            
        except Exception as e:
            print(f"Error en QR fallback: {e}")
            return None