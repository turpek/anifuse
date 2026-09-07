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
  - `pillow>=12.3.0`
- **Ferramentas de Desenvolvimento e Qualidade:**
  - `autopep8>=2.3.2`, `ruff>=0.9.0`, `mypy>=1.10.0`, `pytest>=8.0.0`, `pytest-cov>=5.0.0`.

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

- **Desenvolvimento Orientado a Testes (TDD):** A suíte de testes (`pytest`) é a fonte de verdade absoluta para validação de algoritmos de alinhamento e orquestração. A IA deve propor e executar cenários de teste antes/durante refatorações.
- **Qualidade e Formatação Automática (ruff check & autopep8):** Sempre que a IA for autorizada a alterar, criar ou refatorar qualquer arquivo Python (`.py`), DEVE obrigatoriamente executar lint com auto-fix e formatação via autopep8 no diretório afetado:
  ```bash
  uv run ruff check <diretório> --fix && uv run autopep8 --in-place --recursive --max-line-length 89 --ignore E501,E402,W503,W504 <diretório>
  ```
- **Arquivos Temporários e Scratch:** Scripts de teste temporários ou de debug DEVEM ser gerados em `scratch/` ou `scripts/`, nunca na raiz do projeto.
- **Imports Estritamente no Top-Level:** Todo e qualquer `import` ou `from ... import ...` DEVE residir obrigatoriamente no topo do arquivo (`top-level`).
  - É **estritamente proibido** colocar declarações de `import` dentro de funções, métodos ou blocos de controle de fluxo (prevenindo violações da regra `PLC0415` do Ruff).
  - Para anotações de tipo que poderiam introduzir dependências circulares em tempo de execução, utilize obrigatoriamente o bloco `if TYPE_CHECKING:` no topo do arquivo acompanhado de `from __future__ import annotations`.

### 5.1. Diretrizes Estritas para Criação de Testes (Pytest):
1. **Docstring Concisa:** Exatamente 1 linha limpa na primeira linha de cada função de teste.
2. **Zero Lógica Condicional (`if/else`):** Proibido `if/else` ou ternários no corpo do teste. O fluxo deve ser estritamente linear: *Arrange -> Act -> Assert*.
3. **Parametrização Declarativa (`@pytest.mark.parametrize`):** Variações de entrada e expectativa devem ser expressas como dados na tabela de parâmetros com IDs descritivos (`id="..."`).
4. **Helpers de Dados Dedicados:** Usar geradores sintéticos de frames com movimento controlado para evitar testes lentos ou não-determinísticos.
5. **Asserts Coesos:** Múltiplos asserts são permitidos somente quando pertencerem ao mesmo objeto sob teste e validarem facetas complementares do mesmo resultado.
6. **Casos de Borda Isolados:** Casos específicos (ex: frames sem movimento, falhas de correlação ou parâmetros nulos) devem ser testes dedicados, nunca misturados com `if` dentro de tabelas genéricas.

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
- **Corpo do commit (quando usar):**
  - Explique o porquê, não apenas o que foi feito.
  - Responder, se possível:
    - Qual era o problema?
    - Por que essa solução foi escolhida?
    - Existe impacto ou efeito colateral?

### 5.2.1. Separação Estrita de Commits (Produção vs. Dev-Only):
- **Regra Fundamental:** É estritamente proibido misturar arquivos de produção com arquivos exclusivos de desenvolvimento em um mesmo commit.
- **Commits de Produção (Core / Release):**
  - **Arquivos:** `src/`, `tests/`, `README.md`, `pyproject.toml`, `uv.lock`, `Makefile`, `assets/`.
  - **Prefixos:** `feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `style:`.
  - **Objetivo:** Manter a branch `main` e o changelog automático do `make sync-main` limpos, rastreáveis e focados no motor.
- **Commits de Desenvolvimento (Ambiente / Metadados / Benchmarks):**
  - **Arquivos:** `GEMINI.md`, `docs/` (guias técnicos e documentação interna), `benchmarks/`, `planos/`, `scratch/`, `scripts/`.
  - **Prefixos:** `docs(dev):`, `bench:`, `chore(dev):`, `docs(plano):`.
  - **Objetivo:** Preservar a rastreabilidade de instruções da IA, planos de refatoração e métricas de estresse na `dev` sem contaminar os commits de produto.

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
- **Operações Espaciais & Layout (`pin`, `anchor_point`, `fit`, `align`, `fit_content`):** [docs/anicrop/layout.md](file:///home/gui/python/anifuse/docs/anicrop/layout.md)
- **Transformações & Matrizes 3x3 (`Composer` / `Transform`):** [docs/anicrop/transform.md](file:///home/gui/python/anifuse/docs/anicrop/transform.md)
- **Manipulação de Conteúdo (`crop`, `resize`, `fit`):** [docs/anicrop/content.md](file:///home/gui/python/anifuse/docs/anicrop/content.md)
- **Camadas & EditLayer (`BaseLayer`, `Layer`, `GroupLayer`, `EditLayer`):** [docs/anicrop/layer.md](file:///home/gui/python/anifuse/docs/anicrop/layer.md)
- **Geometria 2D & Álgebra Espacial (`Region`, `Span`, `Point`):** [docs/anicrop/spatial.md](file:///home/gui/python/anifuse/docs/anicrop/spatial.md)
- **Contêineres & Protocolo de Árvore (`LayerStack`, `GroupLayer`, `NodeContainerProtocol`):** [docs/anicrop/container.md](file:///home/gui/python/anifuse/docs/anicrop/container.md)
- **Composição & Mesclagem (`merge`, `flatten`, `bake`, `LayerComposition`):** [docs/anicrop/composition.md](file:///home/gui/python/anifuse/docs/anicrop/composition.md)
- **Modos de Mesclagem & Fusão de Pixels (`BlendMode`, `blend.py`):** [docs/anicrop/blend.md](file:///home/gui/python/anifuse/docs/anicrop/blend.md)
- **Imagens, LOD & Subsistema I/O (`Image`, `PyvipsBackend`, `OpenCVBackend`):** [docs/anicrop/image.md](file:///home/gui/python/anifuse/docs/anicrop/image.md)
- **Projeção de Viewport & Câmera:** [docs/anicrop/viewport.md](file:///home/gui/python/anifuse/docs/anicrop/viewport.md)
- **Sistema de Histórico & Undo/Redo (`GlobalHistory`, `ActionPolicy`, `MacroCommand`):** [docs/anicrop/history.md](file:///home/gui/python/anifuse/docs/anicrop/history.md)
- **Infraestrutura Reativa & Proxies (`ProxyLayer`, `GroupProxy`, `ProxyRegistry`):** [docs/anicrop/proxy.md](file:///home/gui/python/anifuse/docs/anicrop/proxy.md)
- **Métricas de Performance & Benchmarks:** [docs/anicrop/benchmark.md](file:///home/gui/python/anifuse/docs/anicrop/benchmark.md)

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

### 8.3. Alinhamento Robusto por Translação Pura e MODA Discreta
- **Viés de Mínimos Quadrados:** O RANSAC $L_2$ contínuo sofre viés puxado por personagens em movimento no primeiro plano. A **MODA discreta de deslocamentos (`mode(diff)`)** trava o cenário de fundo estático com $100\%$ de precisão.
- **Foco Estrito em Translação:** O motor opera exclusivamente com estimativa e aplicação de translação determinística 2D (`HorizontalTranslationHandler`, `VerticalTranslationHandler` e `TranslationHandler`). Quaisquer estimadores ou handlers de rotação e escala foram totalmente removidos do core ativo.
- **Amostragem Única Direta (Single-Pass Resampling):** O `Layer` na composição recebe sempre a **imagem original pura (`frame.image`)**, sem rotações ou transformações intermediárias destrutivas.

### 8.4. Estimadores de Escala, Rotação e Desacoplamento Afim (Consolidado)
- **Descoberta do Piso de Ruído vs. Sinal Real:**
  - Ruído típico de translação pura: $\|1-s\| \le 0.00057$ e $|\theta| \le 0.082^\circ$.
  - Sinal real de zoom (amostra `2435_kurage`): $\|1-s\| \approx 0.00208$ a $0.00221$ por frame (cerca de $10\times$ o ruído).
  - Limiares calibrados em `config.py`: `scale_threshold = 0.0010`, `rotate_threshold = 0.10` e `fast_threshold = 10` (calibrado para sensibilidade a traços suaves e gradientes de anime).
- **Desacoplamento de Rotação e Escala:**
  - Quando há apenas escala (`has_scale and not has_rotation`), qualquer ângulo é ruído e DEVE ser forçado a $0.0^\circ$.
  - A escala pura utiliza `resize_image` (`cv2.resize` com Lanczos), mantendo os eixos perfeitamente ortogonais, sem o antialiasing destrutivo ou expansão de bounding-box do `warpAffine`.
- **Família de Estimadores ORB Especializados:**
  - `OrbTranslationEstimator`: Translação 2D pura direta via moda discreta.
  - `OrbScaleEstimator`: Especializado em zoom de câmera (`angle = 0.0`, usa `resize_image`).
  - `OrbRotationEstimator`: Especializado em roll / rotação de câmera.
  - `OrbTransformEstimator`: Estimador geral desacoplado (se apenas escala, usa `resize_image`).
  - Construtores (`__init__`) são 100% desacoplados de variáveis globais, recebendo limiares diretamente como parâmetros explícitos com defaults calibrados (`fast_threshold=10`, `scale_threshold=0.0010`, `rotate_threshold=0.10`, `threshold=0.0`); o método de alto nível `SceneStitcher.from_default()` expõe esses mesmos parâmetros explicitamente.
- **Benchmark Validado (Amostra 2435, 30 frames):**
  - Legado: $2033 \times 1266$
  - `OrbScaleEstimator`: $2036 \times 1262$ (diferença residual de apenas 3 a 4px, ortogonalidade e nitidez preservadas).

---

## 9. Referência aos Arquivos e Relatórios

- **Relatório Completo com Benchmarks:** [`planos/resumo_otimizacao_alinhamento_e_composicao.md`](file:///home/gui/python/anifuse/planos/resumo_otimizacao_alinhamento_e_composicao.md)
- **Módulo de Costura Puro anicrop:** [`scripts/anicrop_stitcher.py`](file:///home/gui/python/anifuse/scripts/anicrop_stitcher.py)
- **Pipeline Iterativo de Referência:** [`scripts/flatten_pipeline.py`](file:///home/gui/python/anifuse/scripts/flatten_pipeline.py)

