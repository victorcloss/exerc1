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

class ImprovedAccuracyCrawler:
    def __init__(self, target_count=1000):
        self.base_url = "https://pt.wikipedia.org/"
        # ESTRATÉGIA HÍBRIDA: Começar em páginas com mais biografias
        self.start_pages = [
            "https://pt.wikipedia.org/wiki/Categoria:Brasileiros",
            "https://pt.wikipedia.org/wiki/Categoria:Nascidos_em_1980",
            "https://pt.wikipedia.org/wiki/Categoria:Políticos_do_Brasil",
            "https://pt.wikipedia.org/wiki/Lista_de_presidentes_do_Brasil",
            "https://pt.wikipedia.org"  # Página original também
        ]
        
        self.target_count = target_count
        self.collected_count = 0
        self.visited_links = set()
        self.person_pages = []
        self.links_to_visit = deque()
        
        # Sessões com bypass
        self.sessions = []
        self.create_sessions()
        self.current_session = 0
        
        # Diretório
        self.output_dir = "wikipedia_pessoas"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Contadores para análise
        self.pages_visited = 0
        self.false_negatives = 0  # Páginas que deveriam ser pessoas mas não detectamos

    def create_sessions(self):
        """Cria sessões para bypass"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        for ua in user_agents:
            session = requests.Session()
            session.headers.update({
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
            })
            self.sessions.append(session)

    def get_session(self):
        session = self.sessions[self.current_session]
        self.current_session = (self.current_session + 1) % len(self.sessions)
        return session

    def make_request(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                session = self.get_session()
                time.sleep(random.uniform(0.8, 1.5))  # Pausa menor mas respeitosa
                
                response = session.get(url, timeout=12)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(3.0, 6.0))
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(1.0, 3.0))
        
        return None

    def is_person_aggressive(self, soup, url):
        """
        Detecção MUITO mais agressiva - prioriza recall sobre precision
        Melhor detectar algumas páginas erradas do que perder pessoas reais
        """
        try:
            # Título
            title_elem = soup.find("span", {"class": "mw-page-title-main"})
            if not title_elem:
                return False, ""
            
            title = title_elem.get_text(strip=True)
            title_lower = title.lower()
            
            # EXCLUSÕES HARD (só o que tem 100% certeza que não é pessoa)
            hard_exclusions = [
                'lista de', 'categoria:', 'anexo:', 'portal:', 'predefinição:',
                'ficheiro:', 'ajuda:', 'wikipédia:', 'especial:'
            ]
            
            for exclusion in hard_exclusions:
                if exclusion in title_lower:
                    return False, title
            
            # INDICADORES SUPER FORTES de pessoa no título
            title_person_indicators = [
                r'\(\d{4}[-–]\d{4}\)',  # (1950-2020)
                r'\(\d{4}[-–]\)',       # (1950-)
                r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}',  # 15 de março de 1980
            ]
            
            for pattern in title_person_indicators:
                if re.search(pattern, title):
                    self.logger.info(f"PESSOA por título (datas): {title}")
                    return True, title
            
            # PADRÕES DE NOME no título (muito comum em biografias)
            name_patterns = [
                r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # Nome Sobrenome
                r'^[A-Z][a-z]+ [a-z]+ [A-Z][a-z]+$',  # Nome de Sobrenome
                r'^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$',  # Nome Meio Sobrenome
            ]
            
            for pattern in name_patterns:
                if re.match(pattern, title):
                    # Verificar que não é lugar comum
                    place_words = ['rio', 'serra', 'lago', 'cidade', 'estado', 'país']
                    if not any(word in title_lower for word in place_words):
                        self.logger.info(f"PESSOA por padrão de nome: {title}")
                        return True, title
            
            # ANÁLISE DA INFOBOX (mais permissiva)
            infobox = soup.find("table", {"class": "infobox"})
            if infobox:
                infobox_text = infobox.get_text().lower()
                
                # Campos que GARANTEM pessoa
                strong_person_fields = [
                    'nascimento:', 'nasceu:', 'nascido:', 'nascida:',
                    'morte:', 'morreu:', 'morto:', 'morta:', 'faleceu:',
                    'cônjuge:', 'esposa:', 'esposo:', 'marido:', 'mulher:',
                    'filhos:', 'filho(a)s:', 'prole:',
                    'ocupação:', 'profissão:', 'atividade:', 'carreira:'
                ]
                
                person_score = 0
                found_fields = []
                
                for field in strong_person_fields:
                    if field in infobox_text:
                        person_score += 1
                        found_fields.append(field)
                
                # Campos mais fracos mas ainda indicativos
                weak_person_fields = [
                    'nacionalidade:', 'natural de:', 'formação:',
                    'conhecido por:', 'pseudônimo:', 'nome artístico:'
                ]
                
                for field in weak_person_fields:
                    if field in infobox_text:
                        person_score += 0.5
                        found_fields.append(field)
                
                # EXCLUSÕES FORTES na infobox
                anti_person_fields = [
                    'fundação:', 'fundado:', 'criação:', 'criado:',
                    'sede:', 'população:', 'área:', 'território:',
                    'gênero musical:', 'editora:', 'lançamento:',
                    'formato:', 'duração:', 'tipo de:'
                ]
                
                for field in anti_person_fields:
                    if field in infobox_text:
                        return False, title  # Exclusão definitiva
                
                # Decisão por score
                if person_score >= 1.5:  # Mais permissivo
                    self.logger.info(f"PESSOA por infobox (score: {person_score}, campos: {found_fields}): {title}")
                    return True, title
            
            # ANÁLISE DO PRIMEIRO PARÁGRAFO (muito mais agressiva)
            first_para = soup.find("p")
            if first_para:
                para_text = first_para.get_text().lower()[:400]
                
                # Padrões biográficos expandidos
                bio_patterns = [
                    r'\bé um (ator|político|escritor|cantor|jogador|atleta|cientista|médico|advogado|jornalista|apresentador|diretor|produtor)',
                    r'\bé uma (atriz|política|escritora|cantora|jogadora|atleta|cientista|médica|advogada|jornalista|apresentadora|diretora|produtora)',
                    r'\bfoi um (ator|político|escritor|cantor|jogador|atleta|cientista|médico|advogado|jornalista|apresentador|diretor|produtor)',
                    r'\bfoi uma (atriz|política|escritora|cantora|jogadora|atleta|cientista|médica|advogada|jornalista|apresentadora|diretora|produtora)',
                    r'\bnasceu em \d{1,2} de \w+ de \d{4}',
                    r'\bmorreu em \d{1,2} de \w+ de \d{4}',
                    r'\(.*\d{4}.*[-–].*\d{4}.*\)',  # (1950-2020)
                    r'\(.*\d{4}.*[-–].*\)',         # (1950-)
                    r'\bfilho de .* e .*',
                    r'\bcasou.* com .*',
                    r'\bformou.* em .*',
                    r'\bconhecido.*por.*'
                ]
                
                for pattern in bio_patterns:
                    if re.search(pattern, para_text):
                        self.logger.info(f"PESSOA por parágrafo biográfico: {title}")
                        return True, title
                
                # Padrões de data de nascimento/morte no texto
                date_patterns = [
                    r'\b\d{1,2} de (janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro) de \d{4}',
                    r'\bem \d{4}',
                    r'\banos? \d{4}'
                ]
                
                date_mentions = sum(1 for pattern in date_patterns if re.search(pattern, para_text))
                if date_mentions >= 2:  # Múltiplas datas sugerem biografia
                    self.logger.info(f"PESSOA por múltiplas datas: {title}")
                    return True, title
            
            # Se chegou até aqui, provavelmente não é pessoa
            return False, title
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar {url}: {e}")
            return False, ""

    def prioritize_links(self, links):
        """Prioriza links que têm maior chance de serem pessoas"""
        priority_links = []
        normal_links = []
        
        for link in links:
            link_lower = link.lower()
            
            # ALTA PRIORIDADE: URLs que parecem nomes
            if re.search(r'/wiki/[A-Z][a-z]+_[A-Z][a-z]+', link):  # Nome_Sobrenome
                priority_links.append(link)
            elif re.search(r'/wiki/[A-Z][a-z]+_[a-z]+_[A-Z][a-z]+', link):  # Nome_de_Sobrenome
                priority_links.append(link)
            elif any(word in link_lower for word in ['categoria:brasileiros', 'categoria:nascidos', 'categoria:atores', 
                                                    'categoria:cantores', 'categoria:políticos', 'categoria:escritores']):
                priority_links.append(link)
            else:
                normal_links.append(link)
        
        # Retornar prioritários primeiro
        return priority_links + normal_links

    def extract_smart_links(self, soup, current_url):
        """Extrai links com foco em encontrar mais biografias"""
        links = []
        try:
            content = soup.find("div", {"id": "mw-content-text"})
            if not content:
                return links
            
            # Se estamos em categoria, pegar muitos links
            if 'categoria:' in current_url.lower():
                category_links = content.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                for link in category_links[:100]:  # Mais links de categorias
                    href = link.get('href')
                    if href and self.is_valid_link(href):
                        full_url = urljoin(self.base_url, href)
                        links.append(full_url)
            else:
                # Para páginas normais, focar em contexto biográfico
                bio_sections = content.find_all(["p", "li", "td"])
                for section in bio_sections[:20]:
                    section_text = section.get_text().lower()
                    
                    # Se a seção menciona biografias, extrair links
                    if any(word in section_text for word in ['nasceu', 'morreu', 'filho', 'casou', 'formou']):
                        section_links = section.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                        for link in section_links:
                            href = link.get('href')
                            if href and self.is_valid_link(href):
                                full_url = urljoin(self.base_url, href)
                                links.append(full_url)
            
            # Priorizar links
            return self.prioritize_links(list(set(links)))[:30]  # Top 30
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair links: {e}")
            return links

    def is_valid_link(self, href):
        """Filtro de links mais permissivo"""
        if not href or not href.startswith('/wiki/'):
            return False
        
        # Apenas exclusões essenciais
        hard_exclusions = [
            'Ficheiro:', 'Categoria:', 'Predefinição:', 'Ajuda:', 
            'Wikipédia:', 'MediaWiki:', 'Especial:'
        ]
        
        for exclusion in hard_exclusions:
            if exclusion in href:
                return False
        
        return True

    def save_person_page(self, content, title):
        """Salva página"""
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:80]
            filename = f"{safe_title}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar {title}: {e}")
            return False

    def crawl_improved(self):
        """Crawler com precisão melhorada"""
        self.logger.info(f"Crawler com detecção agressiva iniciado")
        self.logger.info(f"Meta: {self.target_count} pessoas")
        self.logger.info("Estratégia: Detecção mais permissiva + navegação direcionada")
        
        # Adicionar páginas iniciais (estratégia híbrida)
        for start_page in self.start_pages:
            self.links_to_visit.append(start_page)
        
        while self.links_to_visit and self.collected_count < self.target_count:
            current_url = self.links_to_visit.popleft()
            
            if current_url in self.visited_links:
                continue
            
            self.pages_visited += 1
            self.logger.info(f"Visitando {self.pages_visited}: {current_url}")
            
            response = self.make_request(current_url)
            if not response:
                continue
            
            self.visited_links.add(current_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Detecção agressiva
            is_person, title = self.is_person_aggressive(soup, current_url)
            
            if is_person:
                if self.save_person_page(response.text, title):
                    self.collected_count += 1
                    self.person_pages.append({
                        'url': current_url,
                        'title': title
                    })
                    self.logger.info(f"✅ PESSOA ({self.collected_count}/{self.target_count}): {title}")
            
            # Extrair novos links
            new_links = self.extract_smart_links(soup, current_url)
            for link in new_links:
                if link not in self.visited_links and link not in self.links_to_visit:
                    self.links_to_visit.append(link)
            
            # Log melhorado
            if self.pages_visited % 15 == 0:
                current_rate = self.collected_count / self.pages_visited * 100
                self.logger.info(f"TAXA ATUAL: {current_rate:.1f}% ({self.collected_count}/{self.pages_visited})")
                
                # Se taxa muito baixa, adicionar páginas conhecidas
                if current_rate < 5 and len(self.links_to_visit) < 10:
                    self.logger.warning("Taxa baixa - adicionando páginas de categorias")
                    boost_pages = [
                        "https://pt.wikipedia.org/wiki/Categoria:Atores_do_Brasil",
                        "https://pt.wikipedia.org/wiki/Categoria:Cantores_do_Brasil"
                    ]
                    for page in boost_pages:
                        if page not in self.visited_links:
                            self.links_to_visit.appendleft(page)  # Prioridade
        
        # Estatísticas finais
        final_rate = self.collected_count / self.pages_visited * 100 if self.pages_visited > 0 else 0
        self.logger.info("FINALIZADO!")
        self.logger.info(f"Taxa final: {final_rate:.1f}% ({self.collected_count}/{self.pages_visited})")
        
        self.save_statistics()

    def save_statistics(self):
        stats = {
            'pessoas_coletadas': self.collected_count,
            'paginas_visitadas': self.pages_visited,
            'taxa_precisao': self.collected_count / self.pages_visited if self.pages_visited > 0 else 0,
            'estrategia': 'Detecção agressiva + navegação direcionada',
            'person_pages': self.person_pages
        }
        
        with open(os.path.join(self.output_dir, 'estatisticas_melhoradas.json'), 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

def main():
    print("CRAWLER COM PRECISÃO MELHORADA")
    print("Meta: >30% de taxa de detecção")
    print("=" * 40)
    
    import sys
    target = 1000
    if len(sys.argv) > 1:
        try:
            target = int(sys.argv[1])
        except ValueError:
            print("Uso: python improved_crawler.py [numero]")
            return
    
    crawler = ImprovedAccuracyCrawler(target_count=target)
    crawler.crawl_improved()

if __name__ == "__main__":
    main()