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
- **Alinhamento Afim & Homografia:** Cálculo robusto de matrizes de translação e transformações geométricas 2D com rejeição de *outliers* (RANSAC, LMEDS, MODA).
- **Segmentação e Filtragem de Ruído:** Identificação e mascaramento automático de legendas, logos de transmissão, tarjas pretas (*letterboxing/pillarbox*) e elementos móveis em primeiro plano.
- **Orquestração de Fusão (`SceneStitcher`):** Alimentação contínua de frames no `anicrop`, ajustando posições, opacidades e máscaras para composição perfeita.

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
├── pipeline/        # Orquestrador SceneStitcher integrando com anicrop
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
- **Modos de Mesclagem & Fusão de Pixels (`BlendMode`, `blend.py`):** [docs/anicrop/blend.md](file:///home/gui/python/anifuse/docs/anicrop/blend.md)
- **Imagens, LOD & Subsistema I/O (`Image`, `PyvipsBackend`):** [docs/anicrop/image.md](file:///home/gui/python/anifuse/docs/anicrop/image.md)
- **Projeção de Viewport & Câmera:** [docs/anicrop/viewport.md](file:///home/gui/python/anifuse/docs/anicrop/viewport.md)

---

## 8. Memória de Arquitetura, Alinhamento e Composição (Decisões Consolidadas)

*Esta seção registra todas as descobertas matemáticas e decisões arquiteturais de alinhamento e composição acordadas com o autor do projeto.*

### 8.1. Otimização de Janela Ativa (`Region` / `view`)
- **Problema resolvido:** Em sequências longas ($99+$ frames), rodar ORB contra o Canvas acumulado total ($>5500\text{px}$) causava lentidão extrema ($445\text{s}$ no total).
- **Padrão definitivo:**
  1. Inicializar `view = ...` antes do laço (`img1 = layer1.edits[0].image[view]`).
  2. A cada iteração:
     ```python
     view = layer1.global_region.overlap_with(layer2.global_region)
     img1 = layer1.edits[0].image[view]
     ```
  3. O ORB opera sempre em recortes de tamanho constante ($\approx 1920 \times 1080\text{px}$), reduzindo o tempo para **estáveis $\approx 0.22\text{s}$ por frame**.

### 8.2. Mesclagem Perfeita com `BlendMode.SOLID_FILL`
- **Problema resolvido:** O `HARD_MASKING` substituía pixels opacos por valores fracionários do antialiasing de rotação, espalhando mais de $500.000$ pixels semitransparentes.
- **Padrão definitivo:** Utilizar `BlendMode.SOLID_FILL` (*Base-First*). O Canvas consolidado ($\alpha \ge 250$) é imutável e o novo frame preenche lacunas com $\alpha = 255$ puro (**`0` pixels semi-transparentes residuais**).

### 8.3. Diagnóstico e Resolução de Distorções e Deriva (Drift)
- **Causa da deriva:** O estimador afim contínuo detectava micro-escala ($0.9995$). Em 99 frames, $0.9995^{99} = 0.9724$ encolhia a cena em $2.8\%$ e acumulava $4.34^\circ$ de inclinação espúria.
- **Viés de Mínimos Quadrados:** O RANSAC $L_2$ sofre viés puxado por personagens em movimento no primeiro plano. A **MODA discreta de deslocamentos (`mode(diff)`)** trava o cenário de fundo estático com $100\%$ de precisão.
- **Papel da Rotação Prévia:** A rotação prévia do frame coloca o grid de pixels ortogonal e paralelo ao Canvas, permitindo que a MODA discreta de inteiros funcione com precisão absoluta.

### 8.4. Amostragem Única Direta (Single-Pass Resampling)
- **Problema de qualidade:** Interpolar a imagem para girar e depois interpolar novamente no `flatten` degradava a nitidez do traço original.
- **Solução implementada no [`scripts/anicrop_stitcher.py`](file:///home/gui/python/anifuse/scripts/anicrop_stitcher.py):**
  1. A rasterização `img_rot = CanvasRender().render_layer(layer_temp)` é usada **apenas como buffer de consulta leve para o ORB**.
  2. O `Layer` final na composição recebe a **imagem original pura do disco (`img_next`)**.
  3. A translação compensa a expansão da caixa delimitadora AABB:
     $$\text{canvas\_x} = \text{layer1.global\_region.top\_left.x} + \text{view.top\_left.x} - delx\_rot - \text{layer\_temp.global\_region.top\_left.x}$$
     $$\text{canvas\_y} = \text{layer1.global_region.top\_left.y} + \text{view.top\_left.y} - dely\_rot - \text{layer\_temp.global_region.top\_left.y}$$
  4. O `flatten([layer2, layer1], interp=InterpMode.LANCZOS)` amostra o frame original **uma única vez**, preservando $100\%$ da fidelidade visual.

### 8.5. Algoritmos Alternativos de 1 Passo Estudados
- **LMEDS (Least Median of Squares):** `cv2.estimateAffinePartial2D(pts2, pts1, method=cv2.LMEDS)` — rápido ($\approx 21\text{s}$), minimiza a mediana dos resíduos (tolerante a até 50% de outliers).
- **Votação em Histograma 4D (MODA 4D / GHT):** Extensão da MODA para o espaço afim 4D $(\theta, s, t_x, t_y)$ em 1 passo analítico.
- **ECC (`cv2.findTransformECC`):** Otimização de correlação de intensidade direta (subpixel $0.01\text{px}$).

---

## 9. Referência aos Arquivos e Relatórios

- **Relatório Completo com Benchmarks:** [`planos/resumo_otimizacao_alinhamento_e_composicao.md`](file:///home/gui/python/anifuse/planos/resumo_otimizacao_alinhamento_e_composicao.md)
- **Módulo de Costura Puro anicrop:** [`scripts/anicrop_stitcher.py`](file:///home/gui/python/anifuse/scripts/anicrop_stitcher.py)
- **Pipeline Iterativo de Referência:** [`scripts/flatten_pipeline.py`](file:///home/gui/python/anifuse/scripts/flatten_pipeline.py)
