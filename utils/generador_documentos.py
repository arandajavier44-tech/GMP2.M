# utils/generador_documentos.py
import json
from datetime import datetime, date
from models import db
from models.equipo import Equipo
from models.documento import DocumentoGMP
from models.orden_trabajo import OrdenTrabajo
from models.calibracion import Calibracion
from models.sistema import SistemaEquipo, PlanMantenimiento
from utils.ia_engine import ia_engine
import logging

logger = logging.getLogger(__name__)


class GeneradorDocumentosGMP:
    def __init__(self):
        self.ia = ia_engine

    # ============================================
    # MÉTODOS PRINCIPALES (SOP, FICHA, REPORTE)
    # ============================================

    def generar_sop_equipo(self, equipo_id, usuario=None):
        """Genera un SOP (Procedimiento Operativo Estándar) para un equipo"""
        equipo = Equipo.query.get_or_404(equipo_id)

        # Recopilar datos del equipo
        datos = {
            'equipo': {
                'codigo': equipo.code,
                'nombre': equipo.name,
                'fabricante': equipo.manufacturer,
                'modelo': equipo.model,
                'serie': equipo.serial_number,
                'ubicacion': equipo.location,
                'clasificacion_gmp': equipo.gmp_classification,
                'contacto_producto': equipo.product_contact,
                'fecha_instalacion': equipo.installation_date.strftime('%d/%m/%Y') if equipo.installation_date else 'N/A'
            },
            'sistemas': [],
            'mantenimientos': [],
            'sop_existentes': {
                'operacion': equipo.sop_number,
                'mantenimiento': equipo.maintenance_sop,
                'limpieza': equipo.cleaning_sop,
                'calibracion': equipo.calibration_sop
            }
        }

        # Agregar sistemas
        for sistema in equipo.sistemas:
            sistema_data = {
                'nombre': sistema.nombre,
                'descripcion': sistema.descripcion,
                'categoria': sistema.categoria,
                'tareas': []
            }

            for plan in sistema.planes_pm:
                sistema_data['tareas'].append({
                    'descripcion': plan.tarea_descripcion,
                    'frecuencia': plan.frecuencia_dias,
                    'tiempo_estimado': plan.tiempo_estimado
                })

            datos['sistemas'].append(sistema_data)

        # Crear el documento
        doc = DocumentoGMP(
            titulo=f"SOP - {equipo.code}: {equipo.name}",
            tipo='sop',
            datos_editables=datos,
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Borrador'
        )
        doc.codigo = doc.generar_codigo()

        # Generar contenido con IA
        prompt = self._crear_prompt_sop(equipo, datos)
        respuesta_ia = self.ia._consultar_ollama(prompt, [])

        # Combinar con formato HTML profesional
        doc.contenido = self._formatear_sop_html(equipo, datos, respuesta_ia, doc)

        db.session.add(doc)
        db.session.commit()

        return doc

    def generar_ficha_tecnica(self, equipo_id, usuario=None):
        """Genera una ficha técnica completa del equipo"""
        equipo = Equipo.query.get_or_404(equipo_id)

        doc = DocumentoGMP(
            titulo=f"Ficha Técnica GMP - {equipo.code}",
            tipo='ficha',
            datos_editables={},
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Vigente'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_ficha(equipo, doc)

        db.session.add(doc)
        db.session.commit()

        return doc

    def generar_reporte_mantenimiento(self, equipo_id, usuario=None):
        """Genera un reporte completo de mantenimiento"""
        equipo = Equipo.query.get_or_404(equipo_id)

        ordenes = OrdenTrabajo.query.filter_by(equipo_id=equipo.id).order_by(
            OrdenTrabajo.fecha_creacion.desc()
        ).limit(50).all()

        datos = {
            'equipo': {
                'codigo': equipo.code,
                'nombre': equipo.name
            },
            'estadisticas': {
                'total_ordenes': len(ordenes),
                'preventivas': sum(1 for o in ordenes if o.tipo == 'Preventivo'),
                'correctivas': sum(1 for o in ordenes if o.tipo == 'Correctivo'),
                'servicios': sum(1 for o in ordenes if o.tipo == 'Servicio'),
                'completadas': sum(1 for o in ordenes if o.estado == 'Completada'),
                'pendientes': sum(1 for o in ordenes if o.estado == 'Pendiente'),
                'en_progreso': sum(1 for o in ordenes if o.estado == 'En Progreso')
            }
        }

        doc = DocumentoGMP(
            titulo=f"Reporte de Mantenimiento - {equipo.code}",
            tipo='reporte',
            datos_editables=datos,
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Vigente'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_reporte(equipo, ordenes, doc)

        db.session.add(doc)
        db.session.commit()

        return doc

    # ============================================
    # NUEVOS: SOPs ESPECÍFICOS
    # ============================================

    def generar_sop_mantenimiento(self, equipo_id, usuario=None):
        """Genera SOP de Mantenimiento específico"""
        equipo = Equipo.query.get_or_404(equipo_id)

        # Obtener tareas de mantenimiento del equipo
        tareas_mantenimiento = []
        for sistema in equipo.sistemas:
            for tarea in sistema.planes_pm:
                tareas_mantenimiento.append({
                    'sistema': sistema.nombre,
                    'tarea': tarea.tarea_descripcion,
                    'frecuencia': tarea.frecuencia_dias,
                    'tiempo_estimado': tarea.tiempo_estimado
                })

        doc = DocumentoGMP(
            titulo=f"SOP de Mantenimiento - {equipo.code} - {equipo.name}",
            tipo='sop_mantenimiento',
            datos_editables={
                'equipo_code': equipo.code,
                'equipo_nombre': equipo.name,
                'tareas_mantenimiento': tareas_mantenimiento,
                'frecuencia_recomendada': self._calcular_frecuencia_mantenimiento(equipo)
            },
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Borrador'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_sop_mantenimiento(equipo, doc)

        db.session.add(doc)
        db.session.commit()
        return doc

    def generar_sop_calibracion(self, equipo_id, usuario=None):
        """Genera SOP de Calibración específico"""
        equipo = Equipo.query.get_or_404(equipo_id)

        # Obtener calibraciones históricas
        calibraciones = Calibracion.query.filter_by(equipo_id=equipo.id).order_by(
            Calibracion.fecha_calibracion.desc()
        ).limit(5).all()

        doc = DocumentoGMP(
            titulo=f"SOP de Calibración - {equipo.code} - {equipo.name}",
            tipo='sop_calibracion',
            datos_editables={
                'equipo_code': equipo.code,
                'equipo_nombre': equipo.name,
                'especificaciones_calibracion': {
                    'rango_operacion': equipo.operating_range,
                    'tolerancias': self._calcular_tolerancia_str(equipo),
                    'frecuencia_recomendada': self._calcular_frecuencia_calibracion(equipo)
                },
                'calibraciones_historicas': [c.to_dict() for c in calibraciones] if calibraciones else []
            },
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Borrador'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_sop_calibracion(equipo, doc, calibraciones)

        db.session.add(doc)
        db.session.commit()
        return doc

    def generar_sop_limpieza(self, equipo_id, usuario=None):
        """Genera SOP de Limpieza específico"""
        equipo = Equipo.query.get_or_404(equipo_id)

        doc = DocumentoGMP(
            titulo=f"SOP de Limpieza - {equipo.code} - {equipo.name}",
            tipo='sop_limpieza',
            datos_editables={
                'equipo_code': equipo.code,
                'equipo_nombre': equipo.name,
                'nivel_limpieza': equipo.cleaning_level,
                'product_contact': equipo.product_contact,
                'agentes_limpieza': self._sugerir_agentes_limpieza(equipo),
                'frecuencia_limpieza': self._calcular_frecuencia_limpieza(equipo)
            },
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Borrador'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_sop_limpieza(equipo, doc)

        db.session.add(doc)
        db.session.commit()
        return doc

    # ============================================
    # PROTOCOLO DE VALIDACIÓN (IQ/OQ/PQ)
    # ============================================

    def generar_protocolo_validacion(self, equipo_id, tipo='iq', usuario=None):
        """Genera un protocolo de validación (IQ, OQ o PQ)"""
        equipo = Equipo.query.get_or_404(equipo_id)

        # Datos editables del protocolo
        datos = {
            'equipo': {
                'codigo': equipo.code,
                'nombre': equipo.name,
                'fabricante': equipo.manufacturer,
                'modelo': equipo.model,
                'serie': equipo.serial_number,
                'ubicacion': equipo.location
            },
            'protocolo': {
                'tipo': tipo.upper(),
                'objetivo': '',
                'alcance': '',
                'documentos_referencia': [],
                'criterios_aceptacion': [],
                'procedimientos': [],
                'instrumentos_requeridos': [],
                'personal_requerido': []
            },
            'resultados': {
                'fecha_ejecucion': '',
                'responsable': '',
                'resultados_obtenidos': [],
                'desviaciones': [],
                'conclusion': ''
            }
        }

        # Personalizar según tipo
        if tipo == 'iq':
            datos['protocolo']['objetivo'] = "Verificar que el equipo ha sido instalado correctamente según especificaciones."
            datos['protocolo']['procedimientos'] = [
                "Verificar integridad del equipo",
                "Verificar conexiones eléctricas",
                "Verificar instalación física",
                "Verificar documentación recibida"
            ]
        elif tipo == 'oq':
            datos['protocolo']['objetivo'] = "Verificar que el equipo opera dentro de los parámetros especificados."
            datos['protocolo']['procedimientos'] = [
                "Verificar funcionamiento en vacío",
                "Verificar rangos de operación",
                "Verificar alarmas y seguridad",
                "Verificar ciclos de operación"
            ]
        elif tipo == 'pq':
            datos['protocolo']['objetivo'] = "Verificar que el equipo produce resultados consistentes bajo condiciones normales."
            datos['protocolo']['procedimientos'] = [
                "Ejecutar proceso completo",
                "Verificar calidad del producto",
                "Verificar repetibilidad",
                "Verificar rendimiento"
            ]

        doc = DocumentoGMP(
            titulo=f"Protocolo de Validación {tipo.upper()} - {equipo.code}",
            tipo='protocolo',
            subtipo=tipo,
            datos_editables=datos,
            equipo_id=equipo.id,
            creado_por=usuario or 'Sistema',
            estado='Borrador'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_protocolo(equipo, doc)

        db.session.add(doc)
        db.session.commit()
        return doc

    # ============================================
    # CERTIFICADO DE CALIBRACIÓN
    # ============================================

    def generar_certificado_calibracion(self, calibracion_id, usuario=None):
        """Genera un certificado de calibración"""
        cal = Calibracion.query.get_or_404(calibracion_id)
        equipo = cal.equipo

        datos = {
            'instrumento': {
                'nombre': cal.instrumento,
                'codigo': cal.codigo_instrumento,
                'marca': cal.marca,
                'modelo': cal.modelo,
                'serie': cal.serie
            },
            'equipo': {
                'codigo': equipo.code if equipo else 'N/A',
                'nombre': equipo.name if equipo else 'N/A'
            },
            'calibracion': {
                'fecha': cal.fecha_calibracion.strftime('%d/%m/%Y') if cal.fecha_calibracion else '',
                'proxima': cal.fecha_proxima.strftime('%d/%m/%Y') if cal.fecha_proxima else '',
                'laboratorio': cal.laboratorio or '',
                'certificado_numero': cal.certificado_numero or '',
                'resultado': cal.resultado or '',
                'patron_utilizado': cal.patron_utilizado or '',
                'patron_certificado': cal.patron_certificado or '',
                'temperatura': cal.temperatura or '',
                'humedad': cal.humedad or '',
                'trazabilidad': cal.trazabilidad or ''
            }
        }

        doc = DocumentoGMP(
            titulo=f"Certificado de Calibración - {cal.instrumento}",
            tipo='certificado',
            datos_editables=datos,
            equipo_id=equipo.id if equipo else None,
            calibracion_id=cal.id,
            creado_por=usuario or 'Sistema',
            estado='Vigente'
        )
        doc.codigo = doc.generar_codigo()
        doc.contenido = self._generar_html_certificado(cal, doc)

        db.session.add(doc)
        db.session.commit()
        return doc

    # ============================================
    # MÉTODOS AUXILIARES (HTML Y CÁLCULOS)
    # ============================================

    def _crear_prompt_sop(self, equipo, datos):
        """Crea el prompt para la IA para generar un SOP"""
        return f"""
        Genera un Procedimiento Operativo Estándar (SOP) profesional para el siguiente equipo farmacéutico:

        DATOS DEL EQUIPO:
        - Código: {equipo.code}
        - Nombre: {equipo.name}
        - Fabricante: {equipo.manufacturer or 'N/A'}
        - Modelo: {equipo.model or 'N/A'}
        - Ubicación: {equipo.location or 'N/A'}
        - Clasificación GMP: {equipo.gmp_classification}
        - Contacto con producto: {equipo.product_contact}

        SISTEMAS Y TAREAS:
        {json.dumps(datos['sistemas'], indent=2, ensure_ascii=False)}

        INSTRUCCIONES:
        Genera un SOP completo con las siguientes secciones:

        1. OBJETIVO: Describir el propósito del procedimiento
        2. ALCANCE: Especificar a quién aplica y bajo qué condiciones
        3. RESPONSABILIDADES: Detallar roles (Operador, Supervisor, Calidad)
        4. DEFINICIONES: Términos técnicos relevantes
        5. REFERENCIAS: Documentos relacionados
        6. PROCEDIMIENTO: Pasos detallados para operar el equipo
        7. MANTENIMIENTO: Tareas preventivas y frecuencias
        8. LIMPIEZA: Procedimientos de limpieza
        9. CALIBRACIÓN: Requisitos de calibración
        10. REGISTROS: Documentación a generar
        11. ANEXOS: Diagramas, tablas, etc.

        El tono debe ser técnico, profesional y cumplir con normas GMP.
        Incluye advertencias de seguridad donde corresponda.
        """

    def _formatear_sop_html(self, equipo, datos, contenido_ia, doc):
        """Formatea el SOP en HTML profesional"""
        clasificacion_class = 'critico' if 'Crítico' in str(equipo.gmp_classification) else 'importante' if 'Importante' in str(equipo.gmp_classification) else 'normal'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>SOP - {equipo.code}</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    margin: 2.5cm 2cm;
                    line-height: 1.5;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #2c3e50;
                    padding-bottom: 20px;
                }}
                h1 {{
                    color: #2c3e50;
                    font-size: 24px;
                    margin-bottom: 5px;
                }}
                h2 {{
                    color: #3498db;
                    font-size: 18px;
                    margin-top: 25px;
                    margin-bottom: 15px;
                    border-bottom: 1px solid #bdc3c7;
                    padding-bottom: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }}
                th {{
                    background-color: #34495e;
                    color: white;
                    padding: 8px;
                    text-align: left;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #bdc3c7;
                }}
                .info-box {{
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-left: 4px solid #3498db;
                    margin: 15px 0;
                }}
                .warning {{
                    background-color: #fef9e7;
                    border-left: 4px solid #f1c40f;
                    padding: 15px;
                    margin: 15px 0;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    font-size: 12px;
                    color: #7f8c8d;
                    border-top: 1px solid #bdc3c7;
                    padding-top: 20px;
                }}
                .document-id {{
                    float: right;
                    font-size: 14px;
                    color: #7f8c8d;
                }}
                table.datos-equipo td:first-child {{
                    width: 30%;
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .critico {{ background-color: #e74c3c; color: white; padding: 3px 8px; border-radius: 3px; }}
                .importante {{ background-color: #f39c12; color: white; padding: 3px 8px; border-radius: 3px; }}
                .normal {{ background-color: #27ae60; color: white; padding: 3px 8px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>PROCEDIMIENTO OPERATIVO ESTÁNDAR (SOP)</h1>
                <h2>{equipo.code} - {equipo.name}</h2>
                <div class="document-id">
                    <strong>Código:</strong> {doc.codigo} | 
                    <strong>Versión:</strong> 1.0 | 
                    <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                </div>
            </div>

            <h2>1. DATOS DEL EQUIPO</h2>
            <table class="datos-equipo">
                <tr><td><strong>Código GMP:</strong></td><td>{equipo.code}</td></tr>
                <tr><td><strong>Nombre:</strong></td><td>{equipo.name}</td></tr>
                <tr><td><strong>Fabricante:</strong></td><td>{equipo.manufacturer or 'N/A'}</td></tr>
                <tr><td><strong>Modelo:</strong></td><td>{equipo.model or 'N/A'}</td></tr>
                <tr><td><strong>N° Serie:</strong></td><td>{equipo.serial_number or 'N/A'}</td></tr>
                <tr><td><strong>Ubicación:</strong></td><td>{equipo.location or 'N/A'}</td></tr>
                <tr><td><strong>Clasificación GMP:</strong></td><td><span class="{clasificacion_class}">{equipo.gmp_classification}</span></td></tr>
                <tr><td><strong>Contacto con producto:</strong></td><td>{equipo.product_contact}</td></tr>
                <tr><td><strong>Fecha Instalación:</strong></td><td>{equipo.installation_date.strftime('%d/%m/%Y') if equipo.installation_date else 'N/A'}</td></tr>
            </table>

            {contenido_ia}

            <h2>11. SISTEMAS Y MANTENIMIENTO</h2>
            {self._generar_tabla_sistemas(equipo)}

            <h2>12. DOCUMENTACIÓN RELACIONADA</h2>
            <table>
                <tr><th>Tipo</th><th>Código</th></tr>
                <tr><td>SOP Operación</td><td>{equipo.sop_number or 'N/A'}</td></tr>
                <tr><td>SOP Mantenimiento</td><td>{equipo.maintenance_sop or 'N/A'}</td></tr>
                <tr><td>SOP Limpieza</td><td>{equipo.cleaning_sop or 'N/A'}</td></tr>
                <tr><td>SOP Calibración</td><td>{equipo.calibration_sop or 'N/A'}</td></tr>
            </table>

            <div class="info-box">
                <strong>VALIDACIÓN GMP:</strong>
                <p>Estado de validación: {equipo.validation_status or 'Pendiente'}</p>
                <p>Última validación: {equipo.validation_date.strftime('%d/%m/%Y') if equipo.validation_date else 'N/A'}</p>
                <p>Próxima validación: {equipo.next_validation.strftime('%d/%m/%Y') if equipo.next_validation else 'N/A'}</p>
            </div>

            <div class="warning">
                <strong>⚠️ ADVERTENCIAS DE SEGURIDAD:</strong>
                <ul>
                    <li>Solo personal autorizado puede operar este equipo</li>
                    <li>Usar EPP adecuado durante la operación</li>
                    <li>Verificar calibraciones antes de usar</li>
                    <li>Reportar cualquier anomalía inmediatamente</li>
                </ul>
            </div>

            <h2>13. RESPONSABLES</h2>
            <table>
                <tr><th>Rol</th><th>Nombre</th><th>Fecha</th></tr>
                <tr><td>Elaborado por</td><td>{equipo.created_by or 'Sistema'}</td><td>{equipo.created_at.strftime('%d/%m/%Y') if equipo.created_at else datetime.now().strftime('%d/%m/%Y')}</td></tr>
                <tr><td>Revisado por</td><td>{equipo.quality_approver or '_______________'}</td><td>____/____/______</td></tr>
                <tr><td>Aprobado por</td><td>{equipo.maintenance_responsible or '_______________'}</td><td>____/____/______</td></tr>
            </table>

            <div class="footer">
                <p>Este documento es propiedad de GMP Maintenance System. Prohibida su reproducción sin autorización.</p>
                <p>Documento controlado - Verificar vigencia antes de usar</p>
            </div>
        </body>
        </html>
        """

    def _generar_tabla_sistemas(self, equipo):
        """Genera tabla de sistemas y tareas"""
        if not equipo.sistemas:
            return "<p>No hay sistemas registrados</p>"

        html = ""
        for sistema in equipo.sistemas:
            html += f"""
            <h3>{sistema.nombre} ({sistema.categoria})</h3>
            <p><em>{sistema.descripcion or ''}</em></p>
            <table>
                <tr><th>Tarea</th><th>Frecuencia</th><th>Tiempo estimado</th></tr>
            """
            for plan in sistema.planes_pm:
                html += f"""
                <tr>
                    <td>{plan.tarea_descripcion}</td>
                    <td>c/{plan.frecuencia_dias} días</td>
                    <td>{plan.tiempo_estimado} horas</td>
                </tr>
                """
            html += "</table>"
        return html

    def _generar_html_ficha(self, equipo, doc):
        """Genera HTML para la ficha técnica"""
        clasificacion_class = 'critico' if 'Crítico' in str(equipo.gmp_classification) else 'importante' if 'Importante' in str(equipo.gmp_classification) else 'normal'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Ficha Técnica GMP - {equipo.code}</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    margin: 2cm;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    text-align: center;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #34495e;
                    margin-top: 25px;
                    background-color: #ecf0f1;
                    padding: 8px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }}
                th {{
                    background-color: #34495e;
                    color: white;
                    padding: 8px;
                    text-align: left;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #bdc3c7;
                }}
                .critico {{ background-color: #e74c3c; color: white; padding: 3px 8px; border-radius: 3px; }}
                .importante {{ background-color: #f39c12; color: white; padding: 3px 8px; border-radius: 3px; }}
                .normal {{ background-color: #27ae60; color: white; padding: 3px 8px; border-radius: 3px; }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    font-size: 12px;
                    color: #7f8c8d;
                }}
                .document-id {{
                    text-align: right;
                    font-size: 14px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            <div class="document-id">
                <strong>Código:</strong> {doc.codigo} | <strong>Versión:</strong> 1.0
            </div>
            <div class="header">
                <h1>FICHA TÉCNICA DE EQUIPO - GMP</h1>
                <p><strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>

            <h2>1. IDENTIFICACIÓN DEL EQUIPO</h2>
            <table>
                <tr><td width="30%"><strong>Código GMP</strong></td><td>{equipo.code}</td></tr>
                <tr><td><strong>Nombre del Equipo</strong></td><td>{equipo.name}</td></tr>
                <tr><td><strong>ID GMP Interno</strong></td><td>{equipo.gmp_id or 'N/A'}</td></tr>
                <tr><td><strong>Clasificación GMP</strong></td><td><span class="{clasificacion_class}">{equipo.gmp_classification}</span></td></tr>
                <tr><td><strong>Contacto con Producto</strong></td><td>{equipo.product_contact}</td></tr>
            </table>

            <h2>2. DATOS DE FABRICACIÓN</h2>
            <table>
                <tr><td><strong>Fabricante</strong></td><td>{equipo.manufacturer or 'N/A'}</td></tr>
                <tr><td><strong>Modelo</strong></td><td>{equipo.model or 'N/A'}</td></tr>
                <tr><td><strong>Número de Serie</strong></td><td>{equipo.serial_number or 'N/A'}</td></tr>
                <tr><td><strong>Capacidad</strong></td><td>{equipo.capacity or 'N/A'}</td></tr>
                <tr><td><strong>Rango Operativo</strong></td><td>{equipo.operating_range or 'N/A'}</td></tr>
                <tr><td><strong>Requisitos de Energía</strong></td><td>{equipo.power_requirements or 'N/A'}</td></tr>
            </table>

            <h2>3. UBICACIÓN</h2>
            <table>
                <tr><td><strong>Área de Producción</strong></td><td>{equipo.production_area or 'N/A'}</td></tr>
                <tr><td><strong>Sala/Número</strong></td><td>{equipo.room_number or 'N/A'}</td></tr>
                <tr><td><strong>Ubicación Física</strong></td><td>{equipo.location or 'N/A'}</td></tr>
                <tr><td><strong>Fecha de Instalación</strong></td><td>{equipo.installation_date.strftime('%d/%m/%Y') if equipo.installation_date else 'N/A'}</td></tr>
            </table>

            <h2>4. VALIDACIÓN GMP</h2>
            <table>
                <tr><td><strong>Estado de Validación</strong></td><td>{equipo.validation_status or 'Pendiente'}</td></tr>
                <tr><td><strong>Fecha de Validación</strong></td><td>{equipo.validation_date.strftime('%d/%m/%Y') if equipo.validation_date else 'N/A'}</td></tr>
                <tr><td><strong>Próxima Validación</strong></td><td>{equipo.next_validation.strftime('%d/%m/%Y') if equipo.next_validation else 'N/A'}</td></tr>
                <tr><td><strong>Documento de Validación</strong></td><td>{equipo.validation_doc or 'N/A'}</td></tr>
            </table>

            <h2>5. DOCUMENTACIÓN ASOCIADA</h2>
            <table>
                <tr><th>Documento</th><th>Código</th></tr>
                <tr><td>SOP de Operación</td><td>{equipo.sop_number or 'N/A'}</td></tr>
                <tr><td>SOP de Mantenimiento</td><td>{equipo.maintenance_sop or 'N/A'}</td></tr>
                <tr><td>SOP de Limpieza</td><td>{equipo.cleaning_sop or 'N/A'}</td></tr>
                <tr><td>SOP de Calibración</td><td>{equipo.calibration_sop or 'N/A'}</td></tr>
            </table>

            <h2>6. SISTEMAS Y MANTENIMIENTO</h2>
            {self._generar_tabla_sistemas(equipo)}

            <h2>7. RESPONSABLES</h2>
            <table>
                <tr><th>Rol</th><th>Responsable</th></tr>
                <tr><td>Creado por</td><td>{equipo.created_by or 'Sistema'}</td></tr>
                <tr><td>Aprobación Calidad</td><td>{equipo.quality_approver or 'N/A'}</td></tr>
                <tr><td>Responsable Mantenimiento</td><td>{equipo.maintenance_responsible or 'N/A'}</td></tr>
            </table>

            <div class="footer">
                <p>Documento generado por GMP Maintenance System - {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                <p>Este documento es controlado y debe ser revisado periódicamente según las normas GMP.</p>
            </div>
        </body>
        </html>
        """

    def _generar_html_reporte(self, equipo, ordenes, doc):
        """Genera HTML para el reporte de mantenimiento"""
        datos = doc.datos_editables or {}
        estadisticas = datos.get('estadisticas', {})

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Reporte de Mantenimiento - {equipo.code}</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    margin: 2cm;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                }}
                h2 {{
                    color: #34495e;
                    margin-top: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }}
                th {{
                    background-color: #34495e;
                    color: white;
                    padding: 8px;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #bdc3c7;
                }}
                .estadistica {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #3498db;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    color: #7f8c8d;
                }}
                .document-id {{
                    text-align: right;
                    font-size: 14px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            <div class="document-id">
                <strong>Código:</strong> {doc.codigo} | <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
            </div>
            <h1>REPORTE DE MANTENIMIENTO</h1>
            <p><strong>Equipo:</strong> {equipo.code} - {equipo.name}</p>
            <p><strong>Período:</strong> Todos los registros</p>

            <h2>ESTADÍSTICAS GENERALES</h2>
            <table>
                <tr><th>Métrica</th><th>Valor</th></tr>
                <tr><td>Total de órdenes</td><td class="estadistica">{estadisticas.get('total_ordenes', 0)}</td></tr>
                <tr><td>Órdenes preventivas</td><td>{estadisticas.get('preventivas', 0)}</td></tr>
                <tr><td>Órdenes correctivas</td><td>{estadisticas.get('correctivas', 0)}</td></tr>
                <tr><td>Órdenes de servicio</td><td>{estadisticas.get('servicios', 0)}</td></tr>
                <tr><td>Completadas</td><td>{estadisticas.get('completadas', 0)}</td></tr>
                <tr><td>Pendientes</td><td>{estadisticas.get('pendientes', 0)}</td></tr>
                <tr><td>En progreso</td><td>{estadisticas.get('en_progreso', 0)}</td></tr>
            </table>

            <h2>ÚLTIMAS ÓRDENES DE TRABAJO</h2>
            <table>
                <tr><th>N° OT</th><th>Tipo</th><th>Título</th><th>Fecha</th><th>Estado</th><th>Prioridad</th></tr>
        """

        for o in ordenes[:20]:
            return f"""
                <tr>
                    <td>{o.numero_ot}</td>
                    <td>{o.tipo}</td>
                    <td>{o.titulo}</td>
                    <td>{o.fecha_creacion.strftime('%d/%m/%Y')}</td>
                    <td>{o.estado}</td>
                    <td>{o.prioridad}</td>
                </tr>
            """

        return f"""
            </table>

            <div class="footer">
                <p>Reporte generado por GMP Maintenance System</p>
            </div>
        </body>
        </html>
        """

    # ============================================
    # HTML PARA SOPs ESPECÍFICOS
    # ============================================

    def _generar_html_sop_mantenimiento(self, equipo, doc):
        """Genera HTML para SOP de Mantenimiento"""
        datos = doc.datos_editables or {}
        tareas = datos.get('tareas_mantenimiento', [])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>SOP Mantenimiento - {equipo.code}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #27ae60; }}
                h2 {{ color: #34495e; margin-top: 25px; background: #ecf0f1; padding: 8px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #34495e; color: white; padding: 8px; }}
                td {{ border: 1px solid #bdc3c7; padding: 8px; }}
                .warning {{ background: #fef9e7; border-left: 4px solid #f1c40f; padding: 15px; margin: 15px 0; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>SOP DE MANTENIMIENTO PREVENTIVO</h1>
            <p><strong>Equipo:</strong> {equipo.code} - {equipo.name}</p>
            <p><strong>Fabricante:</strong> {equipo.manufacturer or 'N/E'}</p>
            <p><strong>Modelo:</strong> {equipo.model or 'N/E'}</p>
            <p><strong>Serie:</strong> {equipo.serial_number or 'N/E'}</p>
            <p><strong>Ubicación:</strong> {equipo.location or 'N/E'}</p>

            <h2>1. OBJETIVO</h2>
            <p>Establecer el procedimiento estandarizado para realizar el mantenimiento preventivo del equipo, asegurando su correcto funcionamiento, confiabilidad y cumplimiento con normas GMP.</p>

            <h2>2. ALCANCE</h2>
            <p>Aplica a todo el personal de mantenimiento responsable del equipo en el área de {equipo.production_area or 'producción'}.</p>

            <h2>3. RESPONSABILIDADES</h2>
            <ul>
                <li><strong>Técnico de Mantenimiento:</strong> Ejecutar las tareas según lo especificado.</li>
                <li><strong>Supervisor de Mantenimiento:</strong> Supervisar y aprobar los trabajos realizados.</li>
                <li><strong>Aseguramiento de Calidad:</strong> Validar el cumplimiento del SOP.</li>
            </ul>

            <h2>4. FRECUENCIA DE MANTENIMIENTO</h2>
            <table>
                <thead><tr><th>Tipo</th><th>Frecuencia</th><th>Responsable</th></tr></thead>
                <tbody>
                    <tr><td>Inspección Visual</td><td>Diaria</td><td>Operador</td></tr>
                    <tr><td>Limpieza y Lubricación</td><td>Semanal</td><td>Mantenimiento</td></tr>
                    <tr><td>Mantenimiento Preventivo</td><td>Cada {self._calcular_frecuencia_mantenimiento(equipo)} días</td><td>Mantenimiento</td></tr>
                    <tr><td>Calibración</td><td>Cada {self._calcular_frecuencia_calibracion(equipo)} días</td><td>Metrología</td></tr>
                </tbody>
            </table>

            <h2>5. TAREAS DE MANTENIMIENTO</h2>
            <table>
                <thead><tr><th>Sistema</th><th>Tarea</th><th>Frecuencia</th></tr></thead>
                <tbody>
        """

        for t in tareas:
            return f"""
                    <tr>
                        <td>{t.get('sistema', 'N/A')}</td>
                        <td>{t.get('tarea', 'N/A')}</td>
                        <td>Cada {t.get('frecuencia', 30)} días</td>
                    </tr>
            """

        return f"""
                </tbody>
            </table>

            <div class="warning">
                <strong>⚠️ PRECAUCIONES:</strong>
                <ul>
                    <li>Desconectar energía antes de cualquier intervención</li>
                    <li>Usar bloqueo/etiquetado (LOTO)</li>
                    <li>Usar EPP completo</li>
                    <li>Documentar todas las intervenciones</li>
                </ul>
            </div>

            <h2>6. REGISTROS</h2>
            <ul>
                <li>Registro de Mantenimiento (Formulario MT-{equipo.code})</li>
                <li>Lista de Verificación de Mantenimiento</li>
                <li>Reporte de Novedades</li>
            </ul>

            <div class="footer">
                <p>Documento generado por GMP Maintenance System - Código: {doc.codigo}</p>
            </div>
        </body>
        </html>
        """

    def _generar_html_sop_calibracion(self, equipo, doc, calibraciones_historicas):
        """Genera HTML para SOP de Calibración"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>SOP Calibración - {equipo.code}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; }}
                h2 {{ color: #34495e; margin-top: 25px; background: #ecf0f1; padding: 8px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #34495e; color: white; padding: 8px; }}
                td {{ border: 1px solid #bdc3c7; padding: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>SOP DE CALIBRACIÓN</h1>
            <p><strong>Equipo:</strong> {equipo.code} - {equipo.name}</p>
            <p><strong>Fabricante:</strong> {equipo.manufacturer or 'N/E'}</p>
            <p><strong>Modelo:</strong> {equipo.model or 'N/E'}</p>
            <p><strong>Rango de Operación:</strong> {equipo.operating_range or 'N/E'}</p>

            <h2>1. OBJETIVO</h2>
            <p>Establecer el procedimiento para la calibración del equipo, garantizando la trazabilidad de las mediciones y el cumplimiento de los requisitos GMP.</p>

            <h2>2. FRECUENCIA DE CALIBRACIÓN</h2>
            <p>La calibración se realizará cada <strong>{self._calcular_frecuencia_calibracion(equipo)} días</strong> o antes si se detectan desviaciones.</p>

            <h2>3. EQUIPOS Y PATRONES REQUERIDOS</h2>
            <ul>
                <li>Patrón de referencia certificado (trazable a patrones nacionales)</li>
                <li>Instrumentos de medición verificados</li>
                <li>Software de calibración (si aplica)</li>
                <li>Formatos de registro</li>
            </ul>

            <h2>4. CRITERIOS DE ACEPTACIÓN</h2>
            <p>El equipo se considera calibrado cuando el error máximo es ≤ {self._calcular_tolerancia_str(equipo)} del rango o según especificación del fabricante.</p>
        """

        if calibraciones_historicas:
            return """
            <h2>5. HISTORIAL DE CALIBRACIONES</h2>
            <table>
                <thead><tr><th>Fecha</th><th>Instrumento</th><th>Resultado</th><th>Certificado</th></tr></thead>
                <tbody>
            """
            for cal in calibraciones_historicas:
                if hasattr(cal, 'fecha_calibracion'):
                    return f"""
                    <tr>
                        <td>{cal.fecha_calibracion.strftime('%d/%m/%Y')}</td>
                        <td>{cal.instrumento}</td>
                        <td>{cal.resultado}</td>
                        <td>{cal.certificado_numero or 'N/A'}</td>
                    </tr>
                    """
            return """
                </tbody>
            </table>
            """

        return """
            <div class="footer">
                <p>Documento generado por GMP Maintenance System</p>
            </div>
        </body>
        </html>
        """

    def _generar_html_sop_limpieza(self, equipo, doc):
        """Genera HTML para SOP de Limpieza"""
        nivel_limpieza = equipo.cleaning_level or "Estándar"
        product_contact = equipo.product_contact or "No"

        frecuencia = "Diaria" if product_contact == "Si" else "Semanal"
        if nivel_limpieza == "Alto":
            frecuencia = "Diaria"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>SOP Limpieza - {equipo.code}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #f39c12; }}
                h2 {{ color: #34495e; margin-top: 25px; background: #ecf0f1; padding: 8px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #34495e; color: white; padding: 8px; }}
                td {{ border: 1px solid #bdc3c7; padding: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>SOP DE LIMPIEZA Y SANITIZACIÓN</h1>
            <p><strong>Equipo:</strong> {equipo.code} - {equipo.name}</p>
            <p><strong>Ubicación:</strong> {equipo.location or 'N/E'}</p>
            <p><strong>Nivel de Limpieza:</strong> {nivel_limpieza}</p>
            <p><strong>Contacto con Producto:</strong> {product_contact}</p>

            <h2>1. OBJETIVO</h2>
            <p>Establecer el procedimiento de limpieza y sanitización del equipo para prevenir contaminación cruzada y asegurar la calidad del producto.</p>

            <h2>2. FRECUENCIA DE LIMPIEZA</h2>
            <table>
                <thead><tr><th>Tipo de Limpieza</th><th>Frecuencia</th><th>Duración Estimada</th></tr></thead>
                <tbody>
                    <tr><td>Limpieza Intermedia</td><td>Entre lotes/Cambio de producto</td><td>15-30 min</td></tr>
                    <tr><td>Limpieza Diaria</td><td>{frecuencia}</td><td>30-60 min</td></tr>
                    <tr><td>Limpieza Profunda</td><td>Semanal/Mensual</td><td>2-4 horas</td></tr>
                </tbody>
            </table>

            <h2>3. MATERIALES Y AGENTES DE LIMPIEZA</h2>
            <ul>
                <li><strong>Detergente:</strong> {self._sugerir_detergente(equipo)}</li>
                <li><strong>Desinfectante:</strong> {self._sugerir_desinfectante(equipo)}</li>
                <li><strong>Paños de microfibra (sin pelusa)</strong></li>
                <li><strong>Cepillos de cerdas suaves</strong></li>
                <li><strong>Agua purificada para enjuague final</strong></li>
                <li><strong>EPP: Guantes, lentes, overol, mascarilla</strong></li>
            </ul>

            <h2>4. PROCEDIMIENTO</h2>
            <ol>
                <li>Retirar producto residual del equipo.</li>
                <li>Desconectar energía (si aplica para limpieza húmeda).</li>
                <li>Aplicar detergente en todas las superficies de contacto.</li>
                <li>Fregar con cepillo/paño según tiempo de contacto requerido.</li>
                <li>Enjuagar con agua purificada hasta eliminar residuos.</li>
                <li>Aplicar desinfectante en todas las superficies.</li>
                <li>Respetar tiempo de contacto mínimo (5-10 minutos).</li>
                <li>Enjuagar con agua purificada (si es requerido).</li>
                <li>Secar con paño estéril o dejar secar al aire.</li>
            </ol>

            <div class="footer">
                <p>Documento generado por GMP Maintenance System - Código: {doc.codigo}</p>
            </div>
        </body>
        </html>
        """

    def _generar_html_protocolo(self, equipo, doc):
        """Genera HTML para protocolo de validación"""
        datos = doc.datos_editables or {}
        tipo = doc.subtipo.upper() if doc.subtipo else 'IQ'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Protocolo de Validación {tipo} - {equipo.code}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2.5cm 2cm; }}
                .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #2c3e50; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #3498db; margin-top: 25px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #34495e; color: white; padding: 8px; }}
                td {{ border: 1px solid #bdc3c7; padding: 8px; }}
                .footer {{ margin-top: 50px; text-align: center; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>PROTOCOLO DE VALIDACIÓN {tipo}</h1>
                <h2>{equipo.code} - {equipo.name}</h2>
                <p><strong>Código:</strong> {doc.codigo} | <strong>Versión:</strong> {doc.version}</p>
            </div>

            <h2>1. DATOS DEL EQUIPO</h2>
            <tr>
                <tr><td width="30%"><strong>Código GMP</strong></td><td>{equipo.code}</td></tr>
                <tr><td><strong>Nombre</strong></td><td>{equipo.name}</td></tr>
                <tr><td><strong>Fabricante</strong></td><td>{equipo.manufacturer or 'N/A'}</td></tr>
                <tr><td><strong>Modelo</strong></td><td>{equipo.model or 'N/A'}</td></tr>
                <tr><td><strong>N° Serie</strong></td><td>{equipo.serial_number or 'N/A'}</td></tr>
                <tr><td><strong>Ubicación</strong></td><td>{equipo.location or 'N/A'}</td></tr>
            </table>

            <h2>2. OBJETIVO</h2>
            <p>{datos.get('protocolo', {}).get('objetivo', 'Haga clic para editar...')}</p>

            <h2>3. PROCEDIMIENTOS</h2>
            <ol>
        """
        for proc in datos.get('protocolo', {}).get('procedimientos', []):
            return f"<li>{proc}</li>"
        return f"""
            </ol>

            <h2>4. CRITERIOS DE ACEPTACIÓN</h2>
            <ul>
        """
        for crit in datos.get('protocolo', {}).get('criterios_aceptacion', []):
            return f"<li>{crit}</li>"
        return f"""
            </ul>

            <div class="footer">
                <p>Documento generado por GMP Maintenance System</p>
            </div>
        </body>
        </html>
        """

    def _generar_html_certificado(self, cal, doc):
        """Genera HTML para certificado de calibración"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Certificado de Calibración - {cal.instrumento}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                .header {{ text-align: center; border-bottom: 3px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px; }}
                h1 {{ color: #2c3e50; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #34495e; color: white; padding: 10px; }}
                td {{ padding: 10px; border: 1px solid #bdc3c7; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 11px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>CERTIFICADO DE CALIBRACIÓN</h1>
                <p><strong>N° {doc.codigo}</strong></p>
            </div>

            <table>
                <tr><th colspan="2">DATOS DEL INSTRUMENTO</th></tr>
                <tr><td width="30%"><strong>Instrumento</strong></td><td>{cal.instrumento}</td></tr>
                <tr><td><strong>Código</strong></td><td>{cal.codigo_instrumento or 'N/A'}</td></tr>
                <tr><td><strong>Marca</strong></td><td>{cal.marca or 'N/A'}</td></tr>
                <tr><td><strong>Modelo</strong></td><td>{cal.modelo or 'N/A'}</td></tr>
                <tr><td><strong>Serie</strong></td><td>{cal.serie or 'N/A'}</td></tr>
            </table>

            </table>
                <tr><th colspan="2">DATOS DE LA CALIBRACIÓN</th></tr>
                <tr><td><strong>Fecha de calibración</strong></td><td>{cal.fecha_calibracion.strftime('%d/%m/%Y') if cal.fecha_calibracion else 'N/A'}</td></tr>
                <tr><td><strong>Próxima calibración</strong></td><td>{cal.fecha_proxima.strftime('%d/%m/%Y') if cal.fecha_proxima else 'N/A'}</td></tr>
                <tr><td><strong>Laboratorio</strong></td><td>{cal.laboratorio or 'N/A'}</td></tr>
                <tr><td><strong>N° Certificado</strong></td><td>{cal.certificado_numero or 'N/A'}</td></tr>
                <tr><td><strong>Resultado</strong></td><td class="{'resultado-conforme' if cal.resultado == 'Conforme' else 'resultado-no-conforme'}">{cal.resultado or 'Pendiente'}</td></tr>
            </table>

            <div class="footer">
                <p>Este certificado es válido solo para el instrumento indicado.</p>
                <p>Documento generado por GMP Maintenance System</p>
            </div>
        </body>
        </html>
        """

    # ============================================
    # MÉTODOS AUXILIARES DE CÁLCULO
    # ============================================

    def _calcular_frecuencia_mantenimiento(self, equipo):
        if equipo.gmp_classification == "Crítico":
            return 30
        elif equipo.gmp_classification == "Importante":
            return 60
        return 90

    def _calcular_frecuencia_calibracion(self, equipo):
        if equipo.gmp_classification == "Crítico":
            return 180
        elif equipo.gmp_classification == "Importante":
            return 365
        return 730

    def _calcular_frecuencia_limpieza(self, equipo):
        if equipo.product_contact == "Si":
            return "Diaria (o entre lotes)"
        elif equipo.cleaning_level == "Alto":
            return "Diaria"
        return "Semanal"

    def _calcular_tolerancia_str(self, equipo):
        if equipo.gmp_classification == "Crítico":
            return "±1%"
        elif equipo.gmp_classification == "Importante":
            return "±2%"
        return "±5%"

    def _sugerir_agentes_limpieza(self, equipo):
        if equipo.product_contact == "Si":
            return ["Detergente alcalino grado alimenticio", "Ácido peracético", "Agua purificada"]
        return ["Detergente neutro", "Alcohol 70%", "Agua potable"]

    def _sugerir_detergente(self, equipo):
        if equipo.product_contact == "Si":
            return "Detergente alcalino grado farmacéutico (Ej: Alconox, Liqui-Nox)"
        return "Detergente neutro industrial"

    def _sugerir_desinfectante(self, equipo):
        if equipo.product_contact == "Si":
            return "Ácido peracético (0.2%) o Hipoclorito de sodio (100 ppm)"
        return "Alcohol isopropílico 70% o Amonio cuaternario"


# Instancia global
generador_docs = GeneradorDocumentosGMP()