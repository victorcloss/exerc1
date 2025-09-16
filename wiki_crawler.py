"""
Crawler para coleta de páginas de pessoas da Wikipedia em Português
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import os
import json
import logging
import random
from urllib.parse import urljoin
from collections import deque
import signal
import sys

class WikipediaCrawler:
    def __init__(self, target_count=1000):
        self.base_url = "https://pt.wikipedia.org/"
        
        self.seed_pages = [
            "wiki/Categoria:Nascidos_em_1990",
            "wiki/Categoria:Nascidos_em_1985", 
            "wiki/Categoria:Nascidos_em_1980",
            "wiki/Categoria:Nascidos_em_1975",
            "wiki/Categoria:Nascidos_em_1970",
            "wiki/Categoria:Políticos_do_Brasil",
            "wiki/Categoria:Atores_do_Brasil",
            "wiki/Categoria:Cantores_do_Brasil",
            "wiki/Categoria:Escritores_do_Brasil",
            "wiki/Categoria:Jogadores_de_futebol_do_Brasil",
            "wiki/Lista_de_presidentes_do_Brasil",
            "wiki/Lista_de_governadores_de_São_Paulo",
            ""
        ]
        
        self.target_count = target_count
        self.collected_count = 0
        self.visited_links = set()
        self.person_pages = []
        self.links_to_visit = deque()
        
        self.max_pages_to_visit = min(target_count * 5, 5000)
        
        self.session = requests.Session()
        self.update_session_headers()
        
        self.output_dir = "wikipedia_pessoas"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.start_time = time.time()
        self.pages_visited = 0
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print("\n\n" + "="*50)
        print("INTERRUPÇÃO DETECTADA - Salvando progresso...")
        print("="*50)
        self.save_statistics()
        print(f"Pessoas coletadas: {self.collected_count}")
        print(f"Páginas visitadas: {self.pages_visited}")
        sys.exit(0)
    
    def update_session_headers(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def make_request(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.5, 1.5))
                
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    self.logger.warning(f"Acesso negado (403) - tentativa {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        self.update_session_headers()
                        time.sleep(random.uniform(3, 5))
                elif response.status_code == 429:
                    self.logger.warning(f"Rate limit (429) - aguardando...")
                    time.sleep(random.uniform(5, 10))
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Erro na requisição (tentativa {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        return None
    
    def is_person_page(self, soup, url=""):
        try:
            title_elem = soup.find("span", {"class": "mw-page-title-main"})
            if not title_elem:
                return False, ""
            
            title = title_elem.get_text(strip=True)
            title_lower = title.lower()
            
            exclusions = [
                'lista de', 'categoria:', 'anexo:', 'portal:', 'predefinição:',
                'ficheiro:', 'ajuda:', 'wikipédia:', 'especial:', 'usuário:',
                'guerra', 'batalha', 'revolução', 'conflito',
                'cidade', 'município', 'estado', 'país', 'continente',
                'rio', 'lago', 'montanha', 'serra', 'ilha',
                'empresa', 'companhia', 'corporação', 'organização',
                'universidade', 'faculdade', 'escola', 'instituto',
                'hospital', 'museu', 'biblioteca', 'teatro',
                'filme', 'livro', 'álbum', 'canção', 'obra',
                'teoria', 'método', 'sistema', 'conceito',
                'prêmio', 'campeonato', 'torneio', 'copa',
                'eleições', 'referendo', 'plebiscito'
            ]
            
            for exclusion in exclusions:
                if exclusion in title_lower:
                    return False, title
            
            if re.search(r'\(\d{4}\s*[-–—]\s*\d{4}\)', title):
                self.logger.info(f"✓ Pessoa detectada por datas no título: {title}")
                return True, title
            
            if re.search(r'\(\d{4}\s*[-–—]\s*\)', title):
                self.logger.info(f"✓ Pessoa detectada por data de nascimento no título: {title}")
                return True, title
            
            infobox = soup.find("table", {"class": "infobox"})
            if infobox:
                infobox_text = infobox.get_text().lower()
                
                person_fields = [
                    'nascimento', 'nascido', 'nascida',
                    'morte', 'falecimento', 'falecido', 'falecida',
                    'cônjuge', 'esposo', 'esposa', 'marido', 'mulher',
                    'filho', 'filha', 'pais', 'mãe', 'pai',
                    'ocupação', 'profissão', 'cargo', 'atividade',
                    'nacionalidade', 'natural de', 'cidadania',
                    'nome completo', 'nome artístico', 'pseudônimo'
                ]
                
                non_person_fields = [
                    'fundação', 'fundado', 'criação', 'criado',
                    'sede', 'localização', 'endereço',
                    'população', 'área', 'altitude', 'clima',
                    'gênero musical', 'editora', 'gravadora',
                    'lançamento', 'publicação', 'estreia',
                    'diretor', 'produção', 'roteiro',
                    'desenvolvedor', 'publicador', 'plataforma'
                ]
                
                person_score = sum(1 for field in person_fields if field in infobox_text)
                non_person_score = sum(1 for field in non_person_fields if field in infobox_text)
                
                if non_person_score > 0:
                    return False, title
                
                if person_score >= 2:
                    self.logger.info(f"✓ Pessoa detectada por infobox (score: {person_score}): {title}")
                    return True, title
            
            content = soup.find("div", {"id": "mw-content-text"})
            if content:
                first_para = content.find("p")
                if first_para:
                    para_text = first_para.get_text()[:300].lower()
                    
                    bio_patterns = [
                        r'\bé um[a]? (.*?)(?:brasileiro|portuguesa|americano|inglês)',
                        r'\bfoi um[a]? (.*?)(?:brasileiro|portuguesa|americano|inglês)',
                        r'nasceu em \d{1,2} de \w+ de \d{4}',
                        r'nascido[a]? em \d{1,2} de \w+ de \d{4}',
                        r'morreu em \d{1,2} de \w+ de \d{4}',
                        r'faleceu em \d{1,2} de \w+ de \d{4}',
                        r'\(\d{1,2} de \w+ de \d{4}.*?\)',
                        r'é um[a]? (?:ator|atriz|político|política|cantor|cantora|escritor|escritora)',
                        r'foi um[a]? (?:ator|atriz|político|política|cantor|cantora|escritor|escritora)'
                    ]
                    
                    for pattern in bio_patterns:
                        if re.search(pattern, para_text):
                            self.logger.info(f"✓ Pessoa detectada por padrão biográfico: {title}")
                            return True, title
            
            return False, title
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar se é pessoa: {e}")
            return False, ""
    
    def extract_links(self, soup, current_url):
        links = []
        
        try:
            if 'Categoria:' in current_url:
                category_area = soup.find("div", {"id": "mw-pages"})
                if category_area:
                    link_elements = category_area.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                    for link in link_elements[:100]:
                        href = link.get('href')
                        if self.is_valid_link(href):
                            full_url = urljoin(self.base_url, href)
                            links.append(full_url)
                    return links
            
            content = soup.find("div", {"id": "mw-content-text"})
            if content:
                paragraphs = content.find_all("p")[:5]
                
                for para in paragraphs:
                    para_text = para.get_text().lower()
                    if any(word in para_text for word in ['nasceu', 'morreu', 'filho', 'casou', 'foi um', 'é um']):
                        para_links = para.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                        for link in para_links:
                            href = link.get('href')
                            if self.is_valid_link(href):
                                full_url = urljoin(self.base_url, href)
                                links.append(full_url)
        
        except Exception as e:
            self.logger.error(f"Erro ao extrair links: {e}")
        
        return list(set(links))[:30]
    
    def is_valid_link(self, href):
        if not href or not href.startswith('/wiki/'):
            return False
        
        excluded_namespaces = [
            'Ficheiro:', 'Categoria:', 'Predefinição:', 'Ajuda:',
            'Wikipédia:', 'MediaWiki:', 'Especial:', 'Portal:',
            'Usuário:', 'Discussão:'
        ]
        
        for namespace in excluded_namespaces:
            if namespace in href:
                return False
        
        if re.search(r'/wiki/[A-Z][a-z]+_[A-Z][a-z]+', href):
            return True
        
        return True
    
    def save_page(self, content, title):
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            safe_title = safe_title[:100]
            
            filename = f"{safe_title}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            if os.path.exists(filepath):
                return False
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar página {title}: {e}")
            return False
    
    def crawl(self):
        self.logger.info("="*60)
        self.logger.info(f"INICIANDO CRAWLER - Meta: {self.target_count} pessoas")
        self.logger.info("="*60)
        
        for seed in self.seed_pages:
            if seed:
                self.links_to_visit.append(urljoin(self.base_url, seed))
            else:
                self.links_to_visit.append(self.base_url)
        
        while (self.links_to_visit and 
               self.collected_count < self.target_count and 
               self.pages_visited < self.max_pages_to_visit):
            
            current_url = self.links_to_visit.popleft()
            
            if current_url in self.visited_links:
                continue
            
            self.pages_visited += 1
            self.visited_links.add(current_url)
            
            self.logger.info(f"Visitando ({self.pages_visited}): {current_url}")
            
            response = self.make_request(current_url)
            if not response:
                continue
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            is_person, title = self.is_person_page(soup, current_url)
            
            if is_person:
                if self.save_page(response.text, title):
                    self.collected_count += 1
                    self.person_pages.append({
                        'url': current_url,
                        'title': title
                    })
                    self.logger.info(f"✅ PESSOA SALVA ({self.collected_count}/{self.target_count}): {title}")
            
            if self.collected_count < self.target_count:
                new_links = self.extract_links(soup, current_url)
                
                for link in new_links:
                    if link not in self.visited_links:
                        self.links_to_visit.append(link)
            
            if self.pages_visited % 10 == 0:
                self.show_progress()
        
        self.finalize()
    
    def show_progress(self):
        if self.pages_visited > 0:
            success_rate = (self.collected_count / self.pages_visited) * 100
            elapsed = time.time() - self.start_time
            rate = self.collected_count / (elapsed / 60) if elapsed > 0 else 0
            
            self.logger.info(f"📊 PROGRESSO: {self.collected_count}/{self.target_count} pessoas | "
                           f"Taxa: {success_rate:.1f}% | "
                           f"Velocidade: {rate:.1f} pessoas/min")
    
    def save_statistics(self):
        stats = {
            'pessoas_coletadas': self.collected_count,
            'paginas_visitadas': self.pages_visited,
            'taxa_sucesso': self.collected_count / self.pages_visited if self.pages_visited > 0 else 0,
            'tempo_execucao': time.time() - self.start_time,
            'person_pages': self.person_pages
        }
        
        stats_file = os.path.join(self.output_dir, 'estatisticas.json')
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Estatísticas salvas em: {stats_file}")
    
    def finalize(self):
        self.save_statistics()
        
        elapsed = time.time() - self.start_time
        success_rate = (self.collected_count / self.pages_visited * 100) if self.pages_visited > 0 else 0
        
        print("\n" + "="*60)
        print("CRAWLER FINALIZADO!")
        print("="*60)
        print(f"Pessoas coletadas: {self.collected_count}/{self.target_count}")
        print(f"Páginas visitadas: {self.pages_visited}")
        print(f"Taxa de sucesso: {success_rate:.1f}%")
        print(f"Tempo de execução: {elapsed/60:.1f} minutos")
        print(f"Proporção coletadas/visitadas: {self.collected_count}/{self.pages_visited}")
        print("="*60)


def main():
    import sys
    
    if len(sys.argv) > 1:
        try:
            target = int(sys.argv[1])
            print(f"Meta configurada: {target} pessoas")
        except ValueError:
            print("Uso: python wiki_crawler.py [numero_de_pessoas]")
            print("Usando valor padrão: 1000 pessoas")
            target = 1000
    else:
        target = 1000
    
    crawler = WikipediaCrawler(target_count=target)
    crawler.crawl()


if __name__ == "__main__":
    main()