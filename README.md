# anifuse

> Motor inteligente para detecção de movimento de câmera, alinhamento afim e fusão/costura não-destrutiva de cenas panorâmicas (*pan shots*) de animes.

---

## 🚀 Arquitetura e Filosofia

O `anifuse` atua como a camada de **visão computacional e orquestração de frames**, consumindo o motor gráfico [`anicrop`](https://github.com/turpek/anicrop) como backend de composição de alta performance:

- **`anifuse` (Visão Computacional):** Rastreamento de trajetória de câmera, alinhamento robusto via ORB e MODA discreta (imune a personagens móveis no primeiro plano), busca de janelas ativas em cruz (`CrossSections`) e orquestração de entrada.
- **`anicrop` (Composição Gráfica):** Pilha de camadas (`LayerStack`, `Layer`), transformações afins contínuas 3x3 sem acúmulo de erro, fusão de pixels via `BlendMode.HARD_MASKING` e `SOLID_FILL` e renderização em alta resolução.

---

## 📦 Instalação

```bash
# Clone e instalação em modo editável com uv:
git clone https://github.com/turpek/anifuse.git
cd anifuse
uv sync
```

Ou instale diretamente como dependência no seu projeto:

```bash
uv pip install git+https://github.com/turpek/anifuse.git
```

---

## 💻 Uso via Linha de Comando (CLI)

O `anifuse` disponibiliza comandos especializados via `typer`:

### 1. Costura de Diretório Único (`anifuse dir`)

Processa uma pasta contendo frames sequenciais e gera o panorama resultante:

```bash
# Panning horizontal travado com corte de borda de 5px
uv run anifuse dir ./cenas/pan_horizontal/ --direction horizontal --border-cut 5 -o ./saida/

# Gerar ambas as versões (top1 e top2) para comparação visual
uv run anifuse dir ./cenas/pan_vertical/ --direction vertical --stack-order both -o ./saida/

# Amostrar frames específicos (começar no frame 10, processar 30 frames, pular de 2 em 2)
uv run anifuse dir ./cenas/cena01/ -s 10 -n 30 --step 2 -o ./saida/
```

### 2. Processamento em Lote (`anifuse dirs`)

Aplica as mesmas configurações a múltiplos diretórios em sequência:

```bash
uv run anifuse dirs ./cena01/ ./cena02/ ./cena03/ --border-cut 8 -o ./resultados/
```

---

### ⚙️ Principais Opções da CLI

| Parâmetro | Atalho | Padrão | Descrição |
| :--- | :---: | :---: | :--- |
| **Entrada e Amostragem** | | | |
| `dir_path` / `dirs` | | *obrigatório* | Caminho do(s) diretório(s) contendo os frames da cena. |
| `--start` | `-s` | `0` | Índice do frame inicial. |
| `--frames` | `-n` | `None` | Quantidade máxima de frames para processar. |
| `--step` | | `1` | Passo de amostragem (ex: `2` pula de 2 em 2 quadros). |
| `--reverse` | | `False` | Inverte a ordem temporal dos frames selecionados. |
| **Composição e Blend** | | | |
| `--stack-order` | | `last-on-top` | Ordem das camadas: `last-on-top`, `first-on-top`, `both`. |
| `--blend-mode` | | `hard-masking` | Modo de mesclagem (`hard-masking`, `solid-fill`, `normal`, `normal-linear`, `multiply`, `clip`). |
| `--interp` | | `lanczos` | Interpolação afim (`lanczos`, `cubic`, `linear`, `nearest`, `area`). |
| **Movimento e Eixo** | | | |
| `--motion-mode` | | `translation` | Restrição de movimento (`translation`, `scale`, `rotation`, `affine`). |
| `--direction` | | `auto` | Restrição de eixo no modo `translation` (`auto`, `horizontal`, `vertical`). |
| `--sections` | | `cross` | Estratégia de janela ativa no canvas (`cross` [veloz], `global`). |
| **Cortes de Emenda** | | | |
| `--border-cut` | | `None` | Espessura uniforme de corte de borda na sobreposição (pixels). |
| `--border-cut-<lado>` | | `0` | Corte individual por borda (`--border-cut-left`, `--border-cut-right`, `--border-cut-top`, `--border-cut-bottom`). |
| **Saída e Destino** | | | |
| `--output-dir` | `-o` | `.` | Diretório de destino para salvar os panoramas gerados. |
| `--name-template` | | `{name}_top{top}.png` | Template customizado do nome (variáveis: `{name}`, `{top}`, `{ext}`). |
| `--force` | `-f` | `False` | Sobrescreve arquivos existentes em vez de auto-incrementar. |
| `--quiet` | `-q` | `False` | Oculta a barra de progresso interativa. |

---

## 🐍 Uso via API Python

Você também pode utilizar o motor programmaticamente no seu código:

```python
from anicrop.enums import BlendMode
from anifuse import (
    BorderCutEffect,
    HorizontalTranslationHandler,
    ImageSequenceReader,
    SceneStitcher,
    StackOrder,
)

# 1. Carregar sequência com amostragem
reader = ImageSequenceReader.from_dir(
    "./frames/cena01/",
    start=0,
    frames=40,
    step=1,
)

# 2. Configurar o orquestrador
stitcher = SceneStitcher.from_default(
    handlers=[HorizontalTranslationHandler()],
)

# 3. Executar a costura panorâmica
panorama = stitcher.stitch(
    reader,
    stack_order=StackOrder.LAST_ON_TOP,
    effects=[BorderCutEffect(all=5)],
    blend_mode=BlendMode.HARD_MASKING,
)

# 4. Salvar resultado em alta resolução
panorama.save("panorama_cena01.png")
```
