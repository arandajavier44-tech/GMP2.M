# utils/generador_ordenes.py
from datetime import date, timedelta
import logging
from models import db
from models.sistema import PlanMantenimiento
from models.orden_trabajo import OrdenTrabajo
import random
import string

logger = logging.getLogger(__name__)

class GeneradorOrdenesPreventivas:
    def __init__(self):
        self.planes_procesados = 0
        self.ordenes_generadas = 0
    
    def generar_ordenes_pendientes(self):
        """Genera órdenes de trabajo para todos los planes que lo requieran"""
        try:
            hoy = date.today()
            
            # Buscar todos los planes activos que necesitan generar orden
            planes = PlanMantenimiento.query.filter(
                PlanMantenimiento.activo == True,
                PlanMantenimiento.proxima_ejecucion <= hoy
            ).all()
            
            logger.info(f"📋 Se encontraron {len(planes)} planes para generar órdenes")
            
            for plan in planes:
                self._generar_orden_para_plan(plan)
            
            db.session.commit()
            logger.info(f"✅ Generadas {self.ordenes_generadas} órdenes preventivas")
            
            return self.ordenes_generadas
            
        except Exception as e:
            logger.error(f"❌ Error generando órdenes: {e}")
            db.session.rollback()
            return 0
    
    def _generar_orden_para_plan(self, plan):
        """Genera una orden de trabajo para un plan específico"""
        try:
            # Verificar si ya hay una orden pendiente para este plan
            orden_existente = OrdenTrabajo.query.filter_by(
                tarea_origen_id=plan.id,
                estado='Pendiente'
            ).first()
            
            if orden_existente:
                logger.info(f"⏩ Ya existe orden pendiente para plan {plan.id}")
                return
            
            if not plan.sistema or not plan.sistema.equipo:
                logger.warning(f"⚠️ Plan {plan.id} no tiene sistema o equipo asociado")
                return
            
            equipo = plan.sistema.equipo
            
            # Generar número de OT
            fecha = datetime.now().strftime('%Y%m')
            random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            numero_ot = f"OT-P-{fecha}-{random_chars}"
            
            # Crear la orden
            nueva_orden = OrdenTrabajo(
                numero_ot=numero_ot,
                equipo_id=equipo.id,
                sistema_id=plan.sistema_id,
                tipo='Preventivo',
                titulo=f"Preventivo: {plan.tarea_descripcion}",
                descripcion=f"Mantenimiento preventivo generado automáticamente\n"
                           f"Equipo: {equipo.code} - {equipo.name}\n"
                           f"Sistema: {plan.sistema.nombre}\n"
                           f"Tarea: {plan.tarea_descripcion}",
                tareas_seleccionadas=[{
                    'id': plan.id,
                    'sistema': plan.sistema.nombre,
                    'descripcion': plan.tarea_descripcion,
                    'tiempo': plan.tiempo_estimado
                }],
                estado='Pendiente',
                prioridad='Media',
                fecha_estimada=plan.proxima_ejecucion,
                creado_por='Sistema Automático',
                tiempo_estimado=plan.tiempo_estimado,
                tarea_origen_id=plan.id
            )
            
            db.session.add(nueva_orden)
            self.ordenes_generadas += 1
            logger.info(f"✅ Orden generada: {numero_ot} para equipo {equipo.code}")
            
        except Exception as e:
            logger.error(f"❌ Error generando orden para plan {plan.id}: {e}")
            raise
    
    def recalcular_todas_fechas(self):
        """Recalcula las próximas fechas para todos los planes"""
        try:
            planes = PlanMantenimiento.query.all()
            for plan in planes:
                plan.calcular_proxima_ejecucion()
            
            db.session.commit()
            logger.info(f"✅ Recalculadas fechas para {len(planes)} planes")
            
        except Exception as e:
            logger.error(f"❌ Error recalculando fechas: {e}")
            db.session.rollback()