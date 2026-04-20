# utils/operadores.py
"""
Diccionario de operadores móviles en Argentina
Formato: número@dominio
"""

OPERADORES = {
    'movistar': {
        'nombre': 'Movistar',
        'email': '@movistar.com.ar',
        'sms': True
    },
    'claro': {
        'nombre': 'Claro',
        'email': '@clarointernet.com.ar',
        'sms': True
    },
    'personal': {
        'nombre': 'Personal',
        'email': '@personal.com.py',  # Paraguay, pero funciona para Argentina
        'sms': True
    },
    'tuenti': {
        'nombre': 'Tuenti',
        'email': '@tuenti.com.ar',
        'sms': True
    }
}

def email_para_celular(numero, operador):
    """Convierte número de celular a email según operador"""
    if operador in OPERADORES:
        # Limpiar número (eliminar espacios, guiones, etc)
        numero_limpio = ''.join(filter(str.isdigit, numero))
        return f"{numero_limpio}{OPERADORES[operador]['email']}"
    return None