# utils/scraper_inteligente.py
import requests
from bs4 import BeautifulSoup
import logging
from googlesearch import search
import time
import re

logger = logging.getLogger(__name__)

class ScraperInteligente:
    def __init__(self):
        self.palabras_clave = [
            'ANMAT nueva normativa',
            'ANMAT disposición GMP',
            'ANMAT buenas prácticas manufactura',
            'ANMAT actualización normativa',
            'Boletín Oficial ANMAT',
            'ANMAT regulatory update',
            'pharmaceutical regulations Argentina'
        ]
        self.fuentes_descubiertas = []
    
    def buscar_nuevas_fuentes(self):
        """Busca en Google nuevas fuentes de normativas"""
        nuevas_fuentes = []
        
        for keyword in self.palabras_clave:
            try:
                logger.info(f"🔍 Buscando: {keyword}")
                
                # Buscar en Google (necesita google-api-python-client o librería googlesearch-python)
                for url in search(keyword, num_results=5, lang="es"):
                    # Verificar si es un dominio relevante
                    if self._es_fuente_relevante(url):
                        fuente = {
                            'nombre': self._extraer_nombre_sitio(url),
                            'url': url,
                            'keyword': keyword,
                            'fecha_descubrimiento': datetime.now().isoformat()
                        }
                        
                        if url not in [f['url'] for f in self.fuentes_descubiertas]:
                            nuevas_fuentes.append(fuente)
                            logger.info(f"✅ Nueva fuente descubierta: {url}")
                
                # Pausa para no ser bloqueado
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error buscando {keyword}: {e}")
        
        self.fuentes_descubiertas.extend(nuevas_fuentes)
        return nuevas_fuentes
    
    def _es_fuente_relevante(self, url):
        """Determina si una URL es una fuente relevante de normativas"""
        dominios_confiables = [
            'anmat.gob.ar',
            'argentina.gob.ar',
            'boletinoficial.gob.ar',
            'who.int',
            'fda.gov',
            'ema.europa.eu',
            'paho.org',
            'msal.gob.ar'
        ]
        
        for dominio in dominios_confiables:
            if dominio in url:
                return True
        
        # Si no está en la lista blanca, verificar palabras clave en la URL
        palabras_url = ['normativa', 'disposicion', 'resolucion', 'gmp', 'pharmaceutical', 'regulatory']
        for palabra in palabras_url:
            if palabra in url.lower():
                return True
        
        return False
    
    def _extraer_nombre_sitio(self, url):
        """Extrae un nombre legible del sitio"""
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            dominio = match.group(1)
            return dominio.replace('.gob.ar', '').replace('.gov', '').upper()
        return 'Fuente Web'
    
    def explorar_fuente(self, fuente):
        """Explora una fuente descubierta para extraer normativas"""
        try:
            logger.info(f"📡 Explorando fuente: {fuente['url']}")
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(fuente['url'], headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            normativas = []
            
            # Buscar enlaces que parezcan normativas
            enlaces = soup.find_all('a', href=True)
            
            for enlace in enlaces[:20]:  # Limitar a 20 enlaces
                texto = enlace.get_text(strip=True)
                href = enlace['href']
                
                # Completar URL si es relativa
                if href.startswith('/'):
                    href = fuente['url'] + href
                
                # Verificar si el enlace parece una normativa
                if self._es_enlace_normativa(texto, href):
                    normativas.append({
                        'titulo': texto,
                        'url': href,
                        'fuente': fuente['nombre'],
                        'tipo': 'descubierta'
                    })
            
            return normativas
            
        except Exception as e:
            logger.error(f"Error explorando fuente {fuente['url']}: {e}")
            return []
    
    def _es_enlace_normativa(self, texto, url):
        """Determina si un enlace parece ser una normativa"""
        indicadores = [
            'disposición', 'resolución', 'normativa', 'reglamento',
            'anmat', 'gmp', 'buenas prácticas', 'farmacopea',
            'pharmacopoeia', 'guideline', 'guidance', 'regulatory'
        ]
        
        texto_lower = texto.lower()
        url_lower = url.lower()
        
        for indicador in indicadores:
            if indicador in texto_lower or indicador in url_lower:
                return True
        
        return False