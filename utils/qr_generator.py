# utils/qr_generator.py
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    RoundedModuleDrawer, 
    CircleModuleDrawer,
    SquareModuleDrawer,
    GappedSquareModuleDrawer
)
from qrcode.image.styles.colormasks import (
    SolidFillColorMask,
    RadialGradiantColorMask,
    SquareGradiantColorMask,
    ImageColorMask
)
from PIL import Image, ImageDraw, ImageFont
import os
from flask import current_app
import uuid

class QRPersonalizado:
    """Generador de códigos QR personalizados para GMP"""
    
    @staticmethod
    def generar_qr_orden(orden, estilo='rounded', colores=None, incluir_logo=True):
        """
        Genera QR personalizado para una orden de trabajo
        
        Args:
            orden: Objeto OrdenTrabajo
            estilo: 'rounded', 'circle', 'square', 'gapped'
            colores: dict con 'fondo' y 'color' (ej: {'fondo': '#FFFFFF', 'color': '#1a5276'})
            incluir_logo: bool - si incluye el logo de GMP
        """
        try:
            # Configurar directorio
            qr_dir = os.path.join(current_app.static_folder, 'qrcodes')
            os.makedirs(qr_dir, exist_ok=True)
            
            # Datos para el QR
            url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/ordenes/{orden.id}"
            
            # Datos adicionales para el QR (se pueden codificar)
            datos_qr = {
                'id': orden.id,
                'ot': orden.numero_ot,
                'equipo': orden.equipo.code,
                'tipo': orden.tipo,
                'url': url
            }
            
            # Configurar colores por defecto (GMP)
            if colores is None:
                colores = {
                    'fondo': '#FFFFFF',
                    'color': '#1a5276',  # Azul corporativo
                    'ojo': '#0d3b66'      # Color para los ojos del QR
                }
            
            # Crear QR
            qr = qrcode.QRCode(
                version=5,  # Tamaño (1-40)
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # Alta corrección para logo
                box_size=12,
                border=4
            )
            qr.add_data(datos_qr)
            qr.make(fit=True)
            
            # Seleccionar estilo de módulos
            if estilo == 'rounded':
                module_drawer = RoundedModuleDrawer(radius_ratio=0.5)
            elif estilo == 'circle':
                module_drawer = CircleModuleDrawer()
            elif estilo == 'gapped':
                module_drawer = GappedSquareModuleDrawer()
            else:
                module_drawer = SquareModuleDrawer()
            
            # Crear imagen del QR
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=module_drawer,
                color_mask=SolidFillColorMask(
                    back_color=colores['fondo'],
                    front_color=colores['color']
                )
            ).convert('RGB')
            
            # Agregar logo si se solicita
            if incluir_logo:
                img = QRPersonalizado._agregar_logo(img, colores['color'])
            
            # Agregar texto informativo
            img = QRPersonalizado._agregar_texto(img, orden)
            
            # Guardar imagen
            filename = f"ot_{orden.id}_custom.png"
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath, 'PNG', quality=95)
            
            # Actualizar en la base de datos
            orden.qr_code = f"qrcodes/{filename}"
            return True
            
        except Exception as e:
            print(f"Error generando QR personalizado: {e}")
            return False
    
    @staticmethod
    def generar_qr_calibracion(calibracion, estilo='rounded', incluir_logo=True):
        """Genera QR personalizado para calibración"""
        try:
            qr_dir = os.path.join(current_app.static_folder, 'qrcodes', 'calibraciones')
            os.makedirs(qr_dir, exist_ok=True)
            
            # Datos para el QR
            url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/calibraciones/{calibracion.id}"
            
            datos_qr = {
                'id': calibracion.id,
                'instrumento': calibracion.instrumento,
                'certificado': calibracion.certificado_numero,
                'fecha': calibracion.fecha_calibracion.strftime('%Y-%m-%d'),
                'url': url
            }
            
            # Colores GMP para calibración
            colores = {
                'fondo': '#FFFFFF',
                'color': '#28a745',  # Verde GMP
                'ojo': '#1e7e34'
            }
            
            qr = qrcode.QRCode(
                version=5,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=12,
                border=4
            )
            qr.add_data(datos_qr)
            qr.make(fit=True)
            
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(radius_ratio=0.5),
                color_mask=SolidFillColorMask(
                    back_color=colores['fondo'],
                    front_color=colores['color']
                )
            ).convert('RGB')
            
            if incluir_logo:
                img = QRPersonalizado._agregar_logo(img, colores['color'])
            
            img = QRPersonalizado._agregar_texto_calibracion(img, calibracion)
            
            filename = f"cal_{calibracion.id}_custom.png"
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath, 'PNG', quality=95)
            
            return f"qrcodes/calibraciones/{filename}"
            
        except Exception as e:
            print(f"Error generando QR para calibración: {e}")
            return None
    
    @staticmethod
    def _agregar_logo(img, color_principal):
        """Agrega el logo de GMP al centro del QR"""
        try:
            # Crear logo simple si no existe archivo
            logo_size = img.size[0] // 4
            logo = Image.new('RGB', (logo_size, logo_size), color_principal)
            draw = ImageDraw.Draw(logo)
            
            # Dibujar un símbolo de herramientas en el logo
            center = logo_size // 2
            draw.ellipse([center - 15, center - 15, center + 15, center + 15], fill='white')
            draw.text((center - 8, center - 8), "⚙️", fill=color_principal, font=None)
            
            # Calcular posición para centrar
            pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)
            
            # Pegar logo
            img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
            return img
            
        except Exception as e:
            print(f"Error agregando logo: {e}")
            return img
    
    @staticmethod
    def _agregar_texto(img, orden):
        """Agrega texto informativo debajo del QR"""
        try:
            # Crear nueva imagen con espacio para texto
            nuevo_alto = img.size[1] + 60
            nueva_img = Image.new('RGB', (img.size[0], nuevo_alto), 'white')
            nueva_img.paste(img, (0, 0))
            
            draw = ImageDraw.Draw(nueva_img)
            
            # Intentar usar fuente del sistema
            try:
                font = ImageFont.truetype("arial.ttf", 14)
                font_small = ImageFont.truetype("arial.ttf", 10)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Texto del QR
            draw.text((10, img.size[1] + 5), f"OT: {orden.numero_ot}", fill='black', font=font)
            draw.text((10, img.size[1] + 25), f"Equipo: {orden.equipo.code}", fill='black', font=font_small)
            draw.text((10, img.size[1] + 40), f"Estado: {orden.estado}", fill='black', font=font_small)
            
            return nueva_img
            
        except Exception as e:
            print(f"Error agregando texto: {e}")
            return img
    
    @staticmethod
    def _agregar_texto_calibracion(img, calibracion):
        """Agrega texto informativo para calibración"""
        try:
            nuevo_alto = img.size[1] + 60
            nueva_img = Image.new('RGB', (img.size[0], nuevo_alto), 'white')
            nueva_img.paste(img, (0, 0))
            
            draw = ImageDraw.Draw(nueva_img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 12)
                font_small = ImageFont.truetype("arial.ttf", 9)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            draw.text((10, img.size[1] + 5), f"Certificado: {calibracion.certificado_numero or 'N/A'}", fill='black', font=font)
            draw.text((10, img.size[1] + 25), f"Instrumento: {calibracion.instrumento[:30]}", fill='black', font=font_small)
            draw.text((10, img.size[1] + 40), f"Válido hasta: {calibracion.fecha_proxima.strftime('%d/%m/%Y')}", fill='black', font=font_small)
            
            return nueva_img
            
        except Exception as e:
            print(f"Error agregando texto: {e}")
            return img


class QRColorManager:
    """Gestor de colores para QR según tipo y prioridad"""
    
    COLORES = {
        'preventivo': {
            'fondo': '#FFFFFF',
            'color': '#007bff',  # Azul
            'ojo': '#0056b3'
        },
        'correctivo': {
            'fondo': '#FFFFFF',
            'color': '#dc3545',  # Rojo
            'ojo': '#a71d2a'
        },
        'servicio': {
            'fondo': '#FFFFFF',
            'color': '#17a2b8',  # Cyan
            'ojo': '#0f6674'
        },
        'calibracion': {
            'fondo': '#FFFFFF',
            'color': '#28a745',  # Verde
            'ojo': '#1e7e34'
        },
        'urgente': {
            'fondo': '#FFF3CD',
            'color': '#856404',  # Amarillo oscuro
            'ojo': '#856404'
        }
    }
    
    @staticmethod
    def get_colores(tipo, prioridad=None):
        """Obtiene colores según tipo y prioridad"""
        if prioridad == 'Crítica':
            return QRColorManager.COLORES['urgente']
        return QRColorManager.COLORES.get(tipo, QRColorManager.COLORES['preventivo'])


# Agregar este método a la clase QRPersonalizado en utils/qr_generator.py

@staticmethod
def generar_qr_equipo(equipo):
    """Genera código QR para un equipo"""
    try:
        from flask import current_app
        import qrcode
        import os
        import json
        
        qr_dir = os.path.join(current_app.static_folder, 'qrcodes', 'equipos')
        os.makedirs(qr_dir, exist_ok=True)
        
        url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/equipos/{equipo.id}"
        
        datos_qr = {
            'id': equipo.id,
            'code': equipo.code,
            'name': equipo.name,
            'gmp_classification': equipo.gmp_classification,
            'status': equipo.current_status,
            'url': url
        }
        
        qr_data = json.dumps(datos_qr, ensure_ascii=False)
        
        qr = qrcode.QRCode(
            version=3,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#007bff", back_color="white")
        img = img.resize((300, 300))
        
        filename = f"eq_{equipo.id}_{equipo.code}.png"
        filepath = os.path.join(qr_dir, filename)
        img.save(filepath, 'PNG', quality=95)
        
        return f"qrcodes/equipos/{filename}"
        
    except Exception as e:
        print(f"Error generando QR para equipo: {e}")
        return None