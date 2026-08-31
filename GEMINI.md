# GEMINI — anifuse

> **Projeto:** `anifuse` — Motor inteligente para detecção de movimento de câmera, alinhamento afim e fusão/costura de cenas panorâmicas (*pan shots*) de animes.

---

## 1. Visão Geral

- **Descrição curta:** Biblioteca e motor em Python para reconstrução não-destrutiva de cenas panorâmicas de animes a partir de sequências de frames/vídeos. Utiliza algoritmos de visão computacional para estimar trajetórias de câmera e alimenta o motor gráfico [`anicrop`](https://github.com/turpek/anicrop) para composição, fatiamento afim e renderização em alta resolução.
- **Motivação:** Cenas de *panning* em animes (*Tate-Pan* vertical e *Yoko-Pan* horizontal) possuem ilustrações contínuas de cenários e personagens que são cortadas pelo enquadramento da câmera. O `anifuse` reconstrói a imagem panorâmica original completa com máxima fidelidade visual e consistência de iluminação.
- **Papel na Arquitetura:**
  - **`anifuse` (Visão Computacional & Orquestração):** Detecta movimento, estima matrizes afins entre frames, mascara regiões dinâmicas/legendas e orquestra a sequência de entrada.
  - **`anicrop` (Backend Gráfico & Composição):** Gerencia pilha de camadas (`LayerStack`, `Layer`), árvores de nós, transformações 3x3 sem acúmulo de erro, blend modes e renderização sob demanda (*LOD / Patch rendering*).

---

## 2. Escopo e Recursos Principais

### O que o projeto FAZ (Core Features):
- **Detecção e Rastreamento de Movimento:** Análise de fluxo óptico (Optical Flow denso e esparso) e alinhamento por correlação estocástica (ECC - *Enhanced Correlation Coefficient*).
- **Alinhamento Afim & Homografia:** Cálculo robusto de matrizes de translação e transformações geométricas 2D com rejeição de *outliers* (RANSAC).
- **Segmentação e Filtragem de Ruído:** Identificação e mascaramento automático de legendas, logos de transmissão, tarjas pretas (*letterboxing/pillarbox*) e elementos móveis em primeiro plano.
- **Orquestração de Fusão (`SceneStitcher`):** Alimentação contínua de frames no `anicrop.Document`, ajustando posições, opacidades e máscaras para composição perfeita.

### O que o projeto NÃO faz:
- Não implementa renderização de matrizes afins de baixo nível (delega 100% para o `anicrop`).
- Não provê Interface Gráfica (GUI) nativa embutida neste repositório.

---

## 3. Stack Tecnológica e Dependências

- **Linguagem:** Python 3.12+ (gerenciado via `uv`).
- **Dependências Principais:**
  - `anicrop` (consumido via GitHub: `https://github.com/turpek/anicrop.git`).
  - `numpy>=2.0.0`
  - `opencv-python>=4.10.0`
  - `loguru>=0.7.0`
  - `pytest>=8.0.0`, `pytest-cov`, `ruff`, `mypy`.

---

## 4. Estrutura Arquitetural de Pastas

```text
src/anifuse/
├── detection/       # Algoritmos de rastreamento e fluxo óptico (Optical Flow, Matchers)
├── alignment/       # Estimadores afins, homografia e acumuladores de trajetória
├── segmentation/    # Máscaras de exclusão (legendas, logos, bordas estáticas)
├── pipeline/        # Orquestrador SceneStitcher integrando com anicrop.Document
├── io/              # Decodificação e extração otimizada de frames de vídeo
└── utils.py         # Funções auxiliares puras de matemática e geometria
```

---

## 5. Testes, Qualidade e Regras de Interação com a IA (GEMINI)

- **Desenvolvimento Orientado a Testes (TDD):** A suíte de testes (`pytest`) é a fonte de verdade absoluta para validação de algoritmos de alinhamento e orquestração.
- **Formatação Automática (ruff format):** Sempre que a IA for autorizada a alterar, criar ou refatorar qualquer arquivo Python (`.py`), DEVE obrigatoriamente executar:
  ```bash
  uv run ruff format <arquivo.py>
  ```
- **Arquivos Temporários e Scratch:** Scripts de teste temporários ou de debug DEVEM ser gerados em `scratch/` ou `scripts/`, nunca na raiz do projeto.

### 5.1. Diretrizes Estritas para Criação de Testes (Pytest):
1. **Docstring Concisa:** Exatamente 1 linha limpa na primeira linha de cada função de teste.
2. **Zero Lógica Condicional (`if/else`):** Proibido `if/else` ou ternários no corpo do teste. O fluxo deve ser estritamente linear: *Arrange -> Act -> Assert*.
3. **Parametrização Declarativa (`@pytest.mark.parametrize`):** Variações de entrada e expectativa devem ser expressas como dados na tabela de parâmetros com IDs descritivos (`id="..."`).
4. **Helpers de Dados Dedicados:** Usar geradores sintéticos de frames com movimento controlado para evitar testes lentos ou não-determinísticos.
5. **Asserts Coesos:** Múltiplos asserts são permitidos somente quando pertencerem ao mesmo objeto sob teste e validarem facetas complementares do mesmo resultado.

### 5.2. Padrão de Commits (Conventional Commits em Português):
- **Estrutura básica:**
  ```text
  tipo: descrição curta no imperativo

  [corpo opcional explicando o porquê]
  ```
- **Tipos mais comuns:**
  - `feat`: nova funcionalidade
  - `fix`: correção de bug
  - `perf`: melhoria de performance
  - `docs`: documentação
  - `style`: formatação (sem mudar comportamento)
  - `refactor`: refatoração sem alterar funcionalidade
  - `test`: testes
  - `chore`: tarefas de manutenção/configuração

---

## 6. Fluxo de Git e Sincronização Multi-PC (`dev` <-> `main`)

- **Branch `dev` (Ambiente de Trabalho Ativo):** Contém todo o repositório rastreado (`GEMINI.md`, `docs/`, `planos/`, código e testes) para sincronização perfeita entre múltiplos computadores.
  - Enviar alterações de dev: `make push-dev` (ou `git push origin dev`).
  - Puxar no outro computador: `make pull-dev` (ou `git pull origin dev`).
- **Branch `main` (Produção e Distribuição Limpa):** Mantém estritamente os arquivos essenciais de código, testes, `README.md` e build, com histórico semântico gerado automaticamente pelo Makefile.
  - Sincronizar código limpo para a main: `make sync-main`.
  - Publicar a main no GitHub: `make push-main`.
- **Atualizar o Motor `anicrop`:**
  - Quando houver novidades no `anicrop` no GitHub: `make update-core`.
  - Para sincronizar a documentação local: `make sync-docs`.

---

## 7. Referência da API do Core Engine (`anicrop`)

O `anifuse` consome o motor gráfico `anicrop`. Sempre que precisar consultar métodos, assinaturas de classes, matrizes afins e tipos do `anicrop`, consulte a documentação local espelhada em `docs/anicrop/`:

- **Fachada `Document` & `Viewer`:** [docs/anicrop/anicrop_guide.md](file:///home/gui/python/anifuse/docs/anicrop/anicrop_guide.md)
- **Transformações & Matrizes 3x3 (`Composer` / `Transform`):** [docs/anicrop/transform.md](file:///home/gui/python/anifuse/docs/anicrop/transform.md)
- **Operações Espaciais & Layout (`fit`, `align`):** [docs/anicrop/layout.md](file:///home/gui/python/anifuse/docs/anicrop/layout.md)
- **Manipulação de Conteúdo (`crop`, `resize`, `fit`):** [docs/anicrop/content.md](file:///home/gui/python/anifuse/docs/anicrop/content.md)
- **Camadas & EditLayer (`Layer`, `GroupLayer`):** [docs/anicrop/layer.md](file:///home/gui/python/anifuse/docs/anicrop/layer.md)
- **Geometria 2D & Álgebra Espacial (`Region`, `Span`, `Point`):** [docs/anicrop/spatial.md](file:///home/gui/python/anifuse/docs/anicrop/spatial.md)
- **Composição & Mesclagem (`merge`, `flatten`, `bake`):** [docs/anicrop/composition.md](file:///home/gui/python/anifuse/docs/anicrop/composition.md)
- **Imagens, LOD & Subsistema I/O (`Image`, `PyvipsBackend`):** [docs/anicrop/image.md](file:///home/gui/python/anifuse/docs/anicrop/image.md)
- **Projeção de Viewport & Câmera:** [docs/anicrop/viewport.md](file:///home/gui/python/anifuse/docs/anicrop/viewport.md)

