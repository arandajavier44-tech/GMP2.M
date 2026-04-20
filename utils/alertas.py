# utils/alertas.py
from utils.notificador_email import notificador
from utils.operadores import OPERADORES
from models.usuario import Usuario

class SistemaAlertas:
    def __init__(self):
        self.notificador = notificador
    
    def alertar_calibracion(self, calibracion, dias):
        """Alerta de calibración próxima"""
        equipo = calibracion.equipo
        
        mensaje = f"""
⚠️ ALERTA DE CALIBRACIÓN GMP

Instrumento: {calibracion.instrumento}
Código: {calibracion.codigo_instrumento or 'N/A'}
Equipo: {equipo.code if equipo else 'N/A'} - {equipo.name if equipo else 'N/A'}
Vence en: {dias} días
Fecha: {calibracion.fecha_proxima.strftime('%d/%m/%Y')}

Por favor programar calibración.
        """
        
        # Buscar técnicos de mantenimiento
        tecnicos = Usuario.query.filter_by(
            area_principal='mantenimiento',
            activo=True
        ).all()
        
        for tecnico in tecnicos:
            if tecnico.email:
                self.notificador.enviar(
                    destino=tecnico.email,
                    asunto=f"🔔 Calibración: {calibracion.instrumento}",
                    mensaje=mensaje
                )
    
    def alertar_mantenimiento(self, plan, dias_atraso):
        """Alerta de mantenimiento vencido"""
        equipo = plan.sistema.equipo if plan.sistema else None
        
        mensaje = f"""
🔧 MANTENIMIENTO VENCIDO

Equipo: {equipo.code if equipo else 'N/A'} - {equipo.name if equipo else 'N/A'}
Tarea: {plan.tarea_descripcion}
Vencido hace: {dias_atraso} días
Frecuencia: cada {plan.frecuencia_dias} días

Programar mantenimiento urgente.
        """
        
        # Enviar a supervisor
        supervisores = Usuario.query.filter_by(
            nivel_jerarquico='supervisor',
            area_principal='mantenimiento'
        ).all()
        
        for sup in supervisores:
            if sup.email:
                self.notificador.enviar(
                    destino=sup.email,
                    asunto=f"⚠️ Mantenimiento vencido - {equipo.code if equipo else 'N/A'}",
                    mensaje=mensaje
                )
    
    def alertar_capa(self, capa, dias):
        """Alerta de CAPA abierta"""
        mensaje = f"""
⚠️ CAPA ABIERTA POR MÁS DE {dias} DÍAS

Número: {capa.numero_capa}
Título: {capa.titulo}
Responsable: {capa.responsable or 'No asignado'}
Fecha detección: {capa.fecha_deteccion.strftime('%d/%m/%Y')}

Requiere atención inmediata.
        """
        
        # Enviar a calidad y administración
        responsables = Usuario.query.filter(
            Usuario.area_principal.in_(['calidad', 'administracion']),
            Usuario.activo == True
        ).all()
        
        for resp in responsables:
            if resp.email:
                self.notificador.enviar(
                    destino=resp.email,
                    asunto=f"⚠️ CAPA urgente: {capa.numero_capa}",
                    mensaje=mensaje
                )