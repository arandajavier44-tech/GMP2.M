# utils/scraper_normativas.py
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import time
import hashlib
import logging

logger = logging.getLogger(__name__)

class ScraperNormativas:
    def __init__(self):
        self.fuentes = [
            {
                'nombre': 'ANMAT',
                'url': 'https://www.argentina.gob.ar/noticias/anmat',
                'tipo': 'web',
                'selector': '.view-content .node__content'
            },
            {
                'nombre': 'FDA',
                'url': 'https://www.fda.gov/news-events/fda-newsroom/press-announcements',
                'tipo': 'rss',
                'feed': 'https://www.fda.gov/AboutFDA/ContactFDA/StayInformed/RSSFeeds/CMSPressAnnouncements/rss.xml'
            },
            {
                'nombre': 'EMA',
                'url': 'https://www.ema.europa.eu/en/news-events',
                'tipo': 'web',
                'selector': '.ecl-row .ecl-teaser__content'
            },
            {
                'nombre': 'WHO',
                'url': 'https://www.who.int/news-room',
                'tipo': 'web',
                'selector': '.list-view--item'
            }
        ]
    
    def obtener_novedades(self, ultima_consulta):
        """Obtiene nuevas normativas desde la última consulta"""
        nuevas = []
        
        for fuente in self.fuentes:
            try:
                logger.info(f"📡 Consultando fuente: {fuente['nombre']}")
                
                if fuente['tipo'] == 'rss':
                    noticias = self._scrapear_rss(fuente)
                else:
                    noticias = self._scrapear_web(fuente)
                
                # Filtrar solo las nuevas (desde última consulta)
                for noticia in noticias:
                    if noticia['fecha'] > ultima_consulta:
                        # Verificar si es relevante (GMP, ANMAT, farmacéutica)
                        if self._es_relevante(noticia):
                            nuevas.append(noticia)
                            logger.info(f"✅ Nueva normativa encontrada: {noticia['titulo'][:50]}...")
                
            except Exception as e:
                logger.error(f"Error scraping {fuente['nombre']}: {e}")
        
        return nuevas
    
    def _scrapear_web(self, fuente):
        """Scrapea una página web"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(fuente['url'], headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            noticias = []
            
            # Intentar diferentes selectores según el sitio
            if 'anmat' in fuente['url'].lower():
                items = soup.select('.view-content .node') or soup.select('.node') or soup.select('article')
                for item in items[:10]:
                    titulo_elem = item.select_one('.node__title, h2, h3')
                    fecha_elem = item.select_one('.node__date, .date, time')
                    link_elem = item.select_one('a')
                    
                    if titulo_elem and link_elem:
                        titulo = titulo_elem.text.strip()
                        fecha = self._extraer_fecha(fecha_elem.text if fecha_elem else '')
                        enlace = link_elem.get('href', '')
                        
                        if not enlace.startswith('http'):
                            enlace = 'https://www.argentina.gob.ar' + enlace
                        
                        noticias.append({
                            'titulo': titulo,
                            'fecha': fecha,
                            'url': enlace,
                            'fuente': fuente['nombre']
                        })
            
            return noticias
            
        except Exception as e:
            logger.error(f"Error en scrapeo web: {e}")
            return []
    
    def _scrapear_rss(self, fuente):
        """Scrapea un feed RSS"""
        try:
            feed = feedparser.parse(fuente['feed'])
            noticias = []
            
            for entry in feed.entries[:10]:  # Últimas 10
                fecha = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
                noticias.append({
                    'titulo': entry.title,
                    'fecha': fecha,
                    'url': entry.link,
                    'fuente': fuente['nombre'],
                    'descripcion': entry.get('description', '')
                })
            
            return noticias
            
        except Exception as e:
            logger.error(f"Error en RSS: {e}")
            return []
    
    def _es_relevante(self, noticia):
        """Determina si la noticia es relevante para normativas GMP"""
        palabras_clave = [
            'GMP', 'buenas prácticas', 'manufactura', 'farmacéutic',
            'ANMAT', 'disposición', 'resolución', 'normativa',
            'calidad', 'validación', 'calibración', 'limpieza',
            'medicamento', 'fármaco', 'pharmaceutical', 'drug',
            'regulatory', 'guideline', 'guidance', 'compliance',
            'buenas prácticas de manufactura', 'good manufacturing'
        ]
        
        texto = (noticia['titulo'] + ' ' + noticia.get('descripcion', '')).lower()
        
        for palabra in palabras_clave:
            if palabra.lower() in texto:
                return True
        
        return False
    
    def _extraer_fecha(self, texto_fecha):
        """Extrae fecha de texto en español"""
        try:
            # Intentar varios formatos comunes
            formatos = [
                '%d/%m/%Y', '%Y-%m-%d', '%d de %B de %Y', 
                '%d %B %Y', '%B %d, %Y'
            ]
            
            for formato in formatos:
                try:
                    return datetime.strptime(texto_fecha.strip(), formato)
                except:
                    continue
            
            return datetime.now()
            
        except:
            return datetime.now()