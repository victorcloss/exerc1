# Projeto: Coleta de Dados da Wikipédia e Cálculo de 6 Graus de Separação

## Descrição do Projeto
Este projeto implementa um sistema para coleta de páginas de pessoas da Wikipédia em português e cálculo dos graus de separação entre elas, baseado na teoria dos "seis graus de separação".

## Estrutura dos Arquivos

### 1. wiki_crawler.py
**Função**: Crawler para coleta de páginas de pessoas da Wikipédia
**Descrição**: 
- Coletamos 1000 páginas de pessoas diferentes da Wikipédia portuguesa
- Identifica automaticamente se uma página se refere a uma pessoa
- Salva as páginas como arquivos HTML
- Implementa filtros avançados para evitar páginas de eventos, obras, lugares, etc.

### 2. graus_sep.py
**Função**: Calculadora de graus de separação entre pessoas
**Descrição**:
- Constrói um grafo de conexões baseado nos links entre páginas
- Calcula o menor caminho entre duas pessoas usando algoritmo BFS
- Interface interativa para consultas
- Comandos de debug para análise do grafo

### 3. Diretório wikipedia_pessoas/
**Função**: Armazenamento das páginas coletadas
**Conteúdo**: 
- Arquivos HTML das páginas de pessoas coletadas
- Arquivo estatisticas.json com dados do crawling

## Configuração do Ambiente

### Dependências Necessárias:

install requests
install beautifulsoup4
install html5lib
install lxml

### Versões Testadas:
- Python 3.8+
- requests 2.28+
- beautifulsoup4 4.11+
- html5lib 1.1+

## Como Executar

### ETAPA 1: Coleta de Dados

python wiki_crawler.py

**O que acontece**:
1. Inicia na página principal da Wikipédia portuguesa
2. Navega pelos links coletando páginas de pessoas
3. Aplica filtros para identificar biografias
4. Salva as páginas no diretório wikipedia_pessoas/
5. Para automaticamente ao atingir 1000 páginas

**Tempo estimado**: dentro de 5h

**Parâmetros configuráveis no código**:
- `target_count = 1000`: Número de páginas a coletar
- `output_dir = "wikipedia_pessoas"`: Diretório de saída
- `time.sleep(1)`: Pausa entre requisições (não remover!)

### ETAPA 2: Cálculo de Graus de Separação

python graus_sep.py


**O que acontece**:
1. Carrega todas as páginas coletadas
2. Constrói o grafo de conexões entre pessoas
3. Inicia interface interativa
4. Permite consultar graus de separação entre pessoas

**Comandos disponíveis**:
- `stats`: Mostra estatísticas do grafo
- `debug <nome>`: Mostra conexões de uma pessoa específica
- `sair`: Encerra o programa

## Exemplos de Uso

### Exemplo 1: Coleta básica
```bash
python wiki_crawler.py
# Aguardar conclusão da coleta
```

### Exemplo 2: Consulta de separação
```bash
python graus_sep.py

# Interface interativa:
Digite o nome da primeira pessoa: Pelé
Digite o nome da segunda pessoa: Caetano Veloso

# Resultado:
GRAU DE SEPARAÇÃO: 2
Caminho de conexão:
1. Pelé (início)
2. Chico Buarque  
3. Caetano Veloso (fim)
```

### Exemplo 3: Debug de conexões
```bash
python graus_sep.py

# No prompt:
debug Pelé

# Resultado:
Conexões de Pelé:
Total: 15 conexões
1. Carlos Alberto Torres
2. Garrincha
3. Tostão
...
```

## Solução de Problemas

### Problema: "Não estão sendo capturadas apenas pessoas"
**Causa**: Filtros insuficientes na função is_person_page()
**Solução**: Implementamos filtros avançados que excluem:
- Páginas de eventos (assassinato de, guerra de, etc.)
- Obras (livro de, filme de, etc.)
- Lugares (museu de, cidade de, etc.)
- Acordos e tratados

### Problema: "Pessoas não são encontradas na busca"
**Causa**: Normalização de nomes muito restritiva
**Solução**: Implementamos busca flexível com:
- Busca por substring
- Busca por palavras individuais
- Busca fuzzy (primeiras letras)
- Seleção interativa para múltiplos resultados

### Problema: "Não há conexão entre pessoas conhecidas"
**Causa**: Extração de links inadequada
**Solução**: Melhoramos a extração com:
- Seletores CSS mais específicos
- Decodificação de URLs
- Matching mais flexível de nomes
- Busca bidirecional

### Problema: "Programa muito lento"
**Causa**: Busca sem limitações
**Solução**: Implementamos:
- Limitação a 6 graus de separação
- Otimização do algoritmo BFS
- Cache de resultados

## Estrutura Técnica

### Algoritmos Utilizados:
- **Crawler**: BFS (Breadth-First Search) para navegação
- **Detecção de pessoas**: Análise de infobox, categorias e padrões textuais
- **Graus de separação**: BFS com limitação de profundidade

### Estruturas de Dados:
- **Grafo**: defaultdict(set) para conexões
- **Mapeamentos**: Dicionários para nome ↔ arquivo
- **Fila**: deque para BFS eficiente

## Configurações Avançadas

### Modificar critérios de pessoa:
Edite a função `is_person_page()` em wiki_crawler.py:
```python
# Adicionar novos padrões de exclusão
non_person_patterns = [
    'seu_novo_padrao_aqui',
    # ...
]
```

### Ajustar número de páginas:
Modifique em wiki_crawler.py:
```python
self.target_count = 500  # Para coletar 500 páginas
```

### Configurar timeout:
Modifique em wiki_crawler.py:
```python
response = self.session.get(full_url, timeout=30)  # 30 segundos
```

## Limitações Conhecidas

1. **Dependente da estrutura da Wikipédia**: Mudanças no layout podem afetar o funcionamento
2. **Conexões unidirecionais**: Uma pessoa pode linkar para outra sem reciprocidade
3. **Qualidade dos links**: Nem todos os links são semanticamente relevantes
4. **Páginas em português**: Limitado à Wikipédia portuguesa

## Melhorias Futuras

1. **Análise semântica**: Determinar relevância dos links
2. **Conexões bidirecionais**: Tornar o grafo mais conectado
3. **Cache persistente**: Salvar grafo em disco
4. **Interface gráfica**: Visualização das conexões
5. **Múltiplos idiomas**: Suporte a outras Wikipédias

## Contato e Suporte

Para problemas técnicos:
1. Verifique as dependências instaladas
2. Confirme a conexão com a internet
3. Consulte os logs de erro no terminal
4. Verifique se o diretório wikipedia_pessoas/ foi criado

## Observações Importantes

- **Respeite os servidores**: Não remova o `time.sleep(1)` do crawler
- **Backup dos dados**: As páginas coletadas podem ser reutilizadas
- **Conexão estável**: O processo de coleta requer internet estável
- **Espaço em disco**: 1.000 páginas ocupam aproximadamente 50-100MB

---
Projeto desenvolvido para a disciplina de Coleta, Preparação e Análise de Dados
PUCRS - Pontifícia Universidade Católica do Rio Grande do Sul