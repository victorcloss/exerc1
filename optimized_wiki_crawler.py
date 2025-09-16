import requests
from bs4 import BeautifulSoup
import time
import re
import os
import signal
import sys
from urllib.parse import urljoin, unquote
from collections import deque
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

class OptimizedWikipediaCrawler:
    def __init__(self):
        self.base_url = "https://pt.wikipedia.org/"
        # ESTRATÉGIA MELHORADA: Começar em páginas que sabidamente têm muitas biografias
        self.seed_pages = [
            "wiki/Categoria:Nascidos_em_1990",
            "wiki/Categoria:Nascidos_em_1985", 
            "wiki/Categoria:Nascidos_em_1980",
            "wiki/Categoria:Políticos_do_Brasil",
            "wiki/Categoria:Atores_do_Brasil",
            "wiki/Categoria:Cantores_do_Brasil",
            "wiki/Categoria:Escritores_do_Brasil",
            "wiki/Categoria:Jogadores_de_futebol_do_Brasil",
            "wiki/Lista_de_presidentes_do_Brasil",
            "wiki/Lista_de_governadores_de_São_Paulo"
        ]
        
        self.visited_links = set()
        self.person_pages = set()
        self.non_person_pages = set()
        self.links_to_visit = deque()
        self.collected_count = 0
        self.target_count = 1000
        self.max_pages_to_visit = 3000  # Aumentado para compensar melhor seleção
        
        # Pool de sessões para requests paralelos
        self.session_pool = []
        for _ in range(3):  # 3 sessões simultâneas
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            self.session_pool.append(session)
        self.current_session = 0
        self.session_lock = threading.Lock()
        
        # Controle de tempo
        self.start_time = time.time()
        self.max_runtime = 3600  # 1 hora máximo
        
        # Setup de interrupção segura
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Criar diretório para salvar páginas
        self.output_dir = "wikipedia_pessoas"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Cache para evitar reprocessamento
        self.processed_urls = set()
        
        # Filtros inteligentes por URL
        self.high_priority_patterns = [
            r'/wiki/[A-Z][a-z]+_[A-Z][a-z]+',  # Nome_Sobrenome
            r'/wiki/[A-Z][a-z]+_[a-z]+_[A-Z][a-z]+',  # Nome_de_Sobrenome
        ]
        
        self.exclude_url_patterns = [
            r'/wiki/Lista_de_',
            r'/wiki/Categoria:',
            r'/wiki/Anexo:',
            r'/wiki/\d{4}$',  # Anos
            r'/wiki/\d{1,2}_de_',  # Datas
            r'/wiki/.*[Gg]uerra.*',
            r'/wiki/.*[Bb]atalha.*',
            r'/wiki/.*[Cc]idade.*',
            r'/wiki/.*[Ee]stado.*',
            r'/wiki/.*[Pp]aís.*',
            r'/wiki/.*[Uu]niversidade.*',
            r'/wiki/.*[Ee]mpresa.*',
            r'/wiki/.*[Ff]ilme.*',
            r'/wiki/.*[Ll]ivro.*',
        ]

    def get_session(self):
        """Rotaciona entre sessões para requests paralelos"""
        with self.session_lock:
            session = self.session_pool[self.current_session]
            self.current_session = (self.current_session + 1) % len(self.session_pool)
            return session

    def signal_handler(self, signum, frame):
        """Manipula Ctrl+C para parada segura"""
        print(f"\n\n{'='*50}")
        print("INTERRUPÇÃO DETECTADA - SALVANDO DADOS...")
        print(f"{'='*50}")
        self.save_statistics()
        print(f"Dados salvos. Pessoas coletadas: {self.collected_count}")
        print(f"Páginas visitadas: {len(self.visited_links)}")
        sys.exit(0)

    def is_person_page_fast(self, soup, url=""):
        """
        Versão ULTRA-OTIMIZADA da detecção de pessoas
        Foca nos indicadores mais rápidos e precisos
        """
        try:
            # Obter título para análise rápida
            title_element = soup.find("span", {"class": "mw-page-title-main"})
            if not title_element:
                return False
                
            page_title = title_element.get_text(strip=True)
            title_lower = page_title.lower()
            
            # 1. EXCLUSÕES ULTRA-RÁPIDAS por título
            fast_exclusions = [
                'lista de', 'categoria:', 'anexo:', 'portal:', 'guerra', 'batalha',
                'cidade', 'estado', 'país', 'município', 'empresa', 'organização',
                'universidade', 'escola', 'hospital', 'museu', 'rio', 'montanha',
                'mortes em', 'nascidos em', 'bibliografia', 'cronologia',
                'sistema', 'método', 'teoria', 'conceito', 'movimento'
            ]
            
            for exclusion in fast_exclusions:
                if exclusion in title_lower:
                    return False
            
            # 2. INDICADORES RÁPIDOS DE PESSOA no título
            title_person_indicators = [
                r'\b\d{4}[-–]\d{4}\b',  # (1950-2020) no título
                r'\b\d{4}[-–]\b',       # (1950-) no título
            ]
            
            for pattern in title_person_indicators:
                if re.search(pattern, page_title):
                    self.logger.info(f"PESSOA por título (datas): {page_title}")
                    return True
            
            # 3. VERIFICAÇÃO INFOBOX ULTRA-FOCADA
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                return False
            
            # Buscar APENAS os campos mais críticos
            infobox_text = infobox.get_text().lower()
            
            # Campos que GARANTEM pessoa (alta precisão)
            critical_person_fields = [
                'nascimento:', 'morte:', 'nasceu em', 'morreu em',
                'cônjuge:', 'esposa:', 'marido:', 'filhos:',
                'ocupação:', 'profissão:', 'nome completo:'
            ]
            
            person_score = 0
            for field in critical_person_fields:
                if field in infobox_text:
                    person_score += 1
            
            # Campos que EXCLUEM pessoa (alta precisão)
            critical_non_person_fields = [
                'fundação:', 'criação:', 'sede:', 'população:',
                'área:', 'gênero musical:', 'editora:', 'lançamento:',
                'duração:', 'formato:', 'tipo:'
            ]
            
            for field in critical_non_person_fields:
                if field in infobox_text:
                    return False
            
            # 4. DECISÃO RÁPIDA
            if person_score >= 2:
                self.logger.info(f"PESSOA CONFIRMADA (score: {person_score}): {page_title}")
                return True
            elif person_score == 1:
                # Verificação rápida no primeiro parágrafo
                return self._quick_paragraph_check(soup, page_title)
            
            return False
                
        except Exception as e:
            self.logger.error(f"Erro ao verificar pessoa em {url}: {e}")
            return False

    def _quick_paragraph_check(self, soup, page_title):
        """Verificação ultra-rápida do primeiro parágrafo"""
        try:
            content = soup.find("div", {"id": "mw-content-text"})
            if content:
                first_para = content.find("p")
                if first_para:
                    para_text = first_para.get_text()[:200].lower()  # Apenas primeiros 200 chars
                    
                    # Padrões ultra-específicos de biografia
                    quick_bio_patterns = [
                        r'\bé um (ator|político|escritor|cantor|jogador|atleta|cientista|médico|advogado)',
                        r'\bé uma (atriz|política|escritora|cantora|jogadora|atleta|cientista|médica|advogada)',
                        r'\bfoi um (ator|político|escritor|cantor|jogador|atleta|cientista|médico)',
                        r'\bfoi uma (atriz|política|escritora|cantora|jogadora|atleta|cientista|médica)',
                        r'\(.*\d{4}.*[-–].*\d{4}.*\)',  # (1950-2020)
                        r'\(.*\d{4}.*[-–].*\)'         # (1950-)
                    ]
                    
                    for pattern in quick_bio_patterns:
                        if re.search(pattern, para_text):
                            self.logger.info(f"PESSOA por parágrafo: {page_title}")
                            return True
            
            return False
            
        except Exception:
            return False

    def should_visit_url(self, href):
        """Filtro inteligente de URLs para priorizar biografias"""
        if not href or not href.startswith('/wiki/'):
            return False
        
        # Excluir padrões obviamente não-pessoa
        for pattern in self.exclude_url_patterns:
            if re.search(pattern, href):
                return False
        
        # Priorizar padrões que sugerem nomes de pessoas
        for pattern in self.high_priority_patterns:
            if re.search(pattern, href):
                return True
        
        # Aceitar URLs simples sem padrões óbvios de exclusão
        return True

    def extract_smart_links(self, soup, current_url=""):
        """Extração inteligente de links priorizando biografias"""
        links = []
        try:
            content = soup.find("div", {"id": "mw-content-text"})
            if not content:
                return links
            
            # ESTRATÉGIA 1: Se estamos em página de categoria, pegar links diretos
            if 'Categoria:' in current_url:
                category_links = content.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                for link in category_links[:50]:  # Máximo 50 por categoria
                    href = link.get('href')
                    if self.should_visit_url(href):
                        links.append(href)
                return links
            
            # ESTRATÉGIA 2: Para páginas normais, focar em links em contexto biográfico
            # Procurar em parágrafos que mencionam pessoas
            paragraphs = content.find_all("p")
            for para in paragraphs[:5]:  # Apenas primeiros 5 parágrafos
                para_text = para.get_text().lower()
                
                # Se o parágrafo menciona biografias, extrair seus links
                bio_keywords = ['nasceu', 'morreu', 'casou', 'filho de', 'político', 'ator', 'escritor', 'cantor']
                if any(keyword in para_text for keyword in bio_keywords):
                    para_links = para.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                    for link in para_links:
                        href = link.get('href')
                        if self.should_visit_url(href):
                            links.append(href)
            
            # ESTRATÉGIA 3: Procurar em listas que podem conter nomes
            lists = content.find_all(["ul", "ol"])
            for lst in lists[:3]:  # Apenas primeiras 3 listas
                list_links = lst.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                for link in list_links[:10]:  # Máximo 10 por lista
                    href = link.get('href')
                    if self.should_visit_url(href):
                        links.append(href)
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair links: {e}")
        
        return list(set(links))  # Remove duplicatas

    def save_page(self, content, title):
        """Salva página como HTML de forma otimizada"""
        try:
            # Sanitizar nome do arquivo
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            if len(safe_title) > 100:
                safe_title = safe_title[:100]
            
            filename = f"{safe_title}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            # Verificar se já existe
            if os.path.exists(filepath):
                return True
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar {title}: {e}")
            return False

    def check_safety_limits(self):
        """Verifica limites de segurança"""
        # Limite de tempo
        elapsed = time.time() - self.start_time
        if elapsed > self.max_runtime:
            self.logger.warning(f"LIMITE DE TEMPO ATINGIDO ({self.max_runtime}s)")
            return False
        
        # Limite de páginas visitadas
        if len(self.visited_links) >= self.max_pages_to_visit:
            self.logger.warning(f"LIMITE DE PÁGINAS ATINGIDO ({self.max_pages_to_visit})")
            return False
        
        return True

    def process_single_page(self, current_link):
        """Processa uma única página"""
        try:
            full_url = urljoin(self.base_url, current_link)
            
            if full_url in self.visited_links or full_url in self.processed_urls:
                return None, []
            
            session = self.get_session()
            response = session.get(full_url, timeout=8)
            response.raise_for_status()
            
            self.visited_links.add(full_url)
            self.processed_urls.add(full_url)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = None
            new_links = []
            
            # Verificar se é pessoa
            if self.is_person_page_fast(soup, full_url):
                title_elem = soup.find("span", {"class": "mw-page-title-main"})
                title = title_elem.get_text(strip=True) if title_elem else "Sem título"
                
                if self.save_page(response.text, title):
                    result = title
                    self.person_pages.add(full_url)
            else:
                self.non_person_pages.add(full_url)
            
            # Extrair novos links apenas se ainda precisamos
            if self.collected_count < self.target_count:
                new_links = self.extract_smart_links(soup, current_link)
            
            return result, new_links
            
        except Exception as e:
            self.logger.error(f"Erro ao processar {current_link}: {e}")
            return None, []

    def run_crawler_optimized(self):
        """Executa o crawler otimizado"""
        self.logger.info("Iniciando crawler OTIMIZADO da Wikipedia...")
        self.logger.info(f"Meta: {self.target_count} pessoas")
        self.logger.info(f"Estratégia: Focar em categorias e páginas com biografias")
        
        # Adicionar páginas sementes
        for seed in self.seed_pages:
            self.links_to_visit.append(seed)
        
        consecutive_failures = 0
        max_consecutive_failures = 20
        
        while (self.links_to_visit and 
               self.collected_count < self.target_count and 
               self.check_safety_limits() and
               consecutive_failures < max_consecutive_failures):
            
            current_link = self.links_to_visit.popleft()
            
            self.logger.info(f"Visitando ({len(self.visited_links)+1}): {current_link}")
            
            result, new_links = self.process_single_page(current_link)
            
            if result:  # Encontrou uma pessoa
                self.collected_count += 1
                consecutive_failures = 0
                self.logger.info(f"✅ PESSOA SALVA ({self.collected_count}/{self.target_count}): {result}")
            else:
                consecutive_failures += 1
            
            # Adicionar novos links com priorização
            priority_links = []
            normal_links = []
            
            for link in new_links:
                if any(re.search(pattern, link) for pattern in self.high_priority_patterns):
                    priority_links.append(link)
                else:
                    normal_links.append(link)
            
            # Adicionar links prioritários primeiro
            for link in priority_links[:5]:  # Máximo 5 prioritários
                if link not in [l for l in self.links_to_visit]:
                    self.links_to_visit.appendleft(link)  # Adicionar no início
            
            for link in normal_links[:3]:  # Máximo 3 normais
                if link not in [l for l in self.links_to_visit]:
                    self.links_to_visit.append(link)
            
            # Pausa menor para otimização
            time.sleep(0.5)
            
            # Log de progresso otimizado
            if len(self.visited_links) % 20 == 0:
                rate = self.collected_count / len(self.visited_links) if self.visited_links else 0
                self.logger.info(f"PROGRESSO: {self.collected_count} pessoas, "
                               f"{len(self.visited_links)} visitadas, "
                               f"taxa: {rate:.2%}, falhas consecutivas: {consecutive_failures}")
        
        # Finalizar
        self.save_statistics()
        self.logger.info("Crawler OTIMIZADO finalizado!")
        self.logger.info(f"Pessoas coletadas: {self.collected_count}")
        self.logger.info(f"Páginas visitadas: {len(self.visited_links)}")
        rate = self.collected_count / len(self.visited_links) if self.visited_links else 0
        self.logger.info(f"Taxa de sucesso: {rate:.2%}")

    def save_statistics(self):
        """Salva estatísticas detalhadas"""
        stats = {
            'pessoas_coletadas': self.collected_count,
            'paginas_visitadas': len(self.visited_links),
            'paginas_pessoa': len(self.person_pages),
            'paginas_nao_pessoa': len(self.non_person_pages),
            'taxa_sucesso': self.collected_count / len(self.visited_links) if self.visited_links else 0,
            'tempo_execucao': time.time() - self.start_time,
            'person_pages': list(self.person_pages),
            'non_person_pages': list(self.non_person_pages)
        }
        
        with open(os.path.join(self.output_dir, 'estatisticas_otimizadas.json'), 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawler = OptimizedWikipediaCrawler()
    crawler.run_crawler_optimized()