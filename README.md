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

O `anifuse` disponibiliza comandos especializados com suporte a execução individual ou encadeamento em lote (*Multi-Command Chaining*) no mesmo processo:

### 1. Costura de Diretórios (`anifuse stitch dir`)

Processa um ou múltiplos diretórios contendo frames sequenciais:

```bash
# Modo afim (padrão) com corte de borda de 5px em ambos os sentidos
uv run anifuse stitch -b 5 -o ./saida/ dir ./cenas/pan_horizontal/

# Múltiplos diretórios com panning horizontal travado
uv run anifuse stitch --motion-mode translation --direction horizontal -o ./saida/ dir ./cena01/ ./cena02/

# Amostrar frames específicos (começar no frame 10, processar 30 frames, pular de 2 em 2)
uv run anifuse stitch -o ./saida/ dir ./cenas/cena01/ -s 10 -n 30 --step 2
```

### 2. Costura a partir de Arquivos Explícitos (`anifuse stitch image`)

Permite selecionar diretamente uma lista arbitrária de imagens:

```bash
uv run anifuse stitch --motion-mode scale -o ./saida/ image ./frames/f_01.png ./frames/f_02.png ./frames/f_03.png
```

### 3. Costura Direta de Vídeos (`anifuse stitch video`)

Funde cenas a partir de arquivos de vídeo (`.mp4`, `.mkv`, etc.), suportando seleção temporal ou por frames:

```bash
# Por intervalo de tempo (de 01:20 a 01:45)
uv run anifuse stitch -o ./saida/ video ./animes/ep01.mkv --start "01:20" --end "01:45"

# Por duração relativa (a partir de 00:30 com duração de 15 segundos)
uv run anifuse stitch -o ./saida/ video ./animes/ep01.mp4 --start "00:30" --duration "15"

# Por contagem de frames brutos em ordem reversa
uv run anifuse stitch -o ./saida/ video ./animes/pan.mp4 --start 120 --end 240 --reverse
```

### 4. Encadeamento em Lote (*Multi-Command Chaining*)

Execute múltiplos trabalhos com configurações heterogêneas em uma única invocação sem reiniciar o interpretador Python:

```bash
uv run anifuse \
  stitch --motion-mode rotation -b 5 dir ./cena_01 ./cena_02 \
  stitch --motion-mode scale dir ./cena_03 \
  stitch --motion-mode translation video ./animes/take_04.mp4 --start "00:15" --duration "10"
```

---

### ⚙️ Principais Opções da CLI

#### Subcomando `stitch` (Motor, Alinhamento e Composição)

| Parâmetro | Atalho | Padrão | Descrição |
| :--- | :---: | :---: | :--- |
| **Movimento e Eixo** | | | |
| `--motion-mode` | | `affine` | Modo de movimento de câmera (`affine`, `translation`, `scale`, `rotation`). |
| `--direction` | | `auto` | Restrição de eixo no modo `translation` (`auto`, `horizontal`, `vertical`). |
| `--confidence-thresh` | | `0.80` | Limiar mínimo de confiança para alinhamento. |
| `--max-features` | | `5000` | Limite de pontos-chave ORB detectados por frame. |
| `--distance-thresh` | | `40.0` | Distância Hamming máxima aceita para correspondência de descritores. |
| `--nbest` | | `None` | Quantidade de melhores correspondências selecionadas para estimativa. |
| **Composição e Blend** | | | |
| `--stack-order` | | `both` | Ordem das camadas: `both`, `last-on-top`, `first-on-top`. |
| `--blend-mode` | | `hard-masking` | Modo de mesclagem (`hard-masking`, `solid-fill`, `normal`, `normal-linear`, `multiply`, `clip`). |
| `--hard-mask-thresh` | | `150` | Limiar do canal alfa para o modo `hard-masking`. |
| `--interp` | | `lanczos` | Interpolação afim (`lanczos`, `cubic`, `linear`, `nearest`, `area`). |
| `--sections` | | `cross` | Estratégia de janela ativa no canvas (`cross` [veloz], `global`). |
| **Cortes de Emenda** | | | |
| `--border-cut` | `-b` | `None` | Espessura uniforme de corte de borda na sobreposição (pixels). |
| `--border-cut-<lado>` | | `0` | Corte individual por borda (`--border-cut-left`, `--border-cut-right`, `--border-cut-top`, `--border-cut-bottom`). |
| **Saída e Destino** | | | |
| `--output-dir` | `-o` | `.` | Diretório de destino para salvar os panoramas gerados. |
| `--name-template` | | `{name}_top{top}.png` | Template customizado do nome (variáveis: `{name}`, `{top}`, `{ext}`). |
| `--force` | `-f` | `False` | Sobrescreve arquivos existentes em vez de auto-incrementar. |
| `--quiet` | `-q` | `False` | Oculta a barra de progresso interativa. |

#### Subcomandos de Fonte (`dir` e `image`)

| Parâmetro | Atalho | Padrão | Descrição |
| :--- | :---: | :---: | :--- |
| `PATHS...` | | *obrigatório* | Um ou mais diretórios (`dir`) ou arquivos de imagem (`image`). |
| `--start` | `-s` | `0` | Índice inicial do frame. |
| `--frames` | `-n` | `None` | Quantidade máxima de frames para processar. |
| `--step` | | `1` | Passo de amostragem temporal de quadros. |
| `--reverse` | | `False` | Inverte a ordem temporal dos frames selecionados. |
| `--read-strategy` | | `batched` | Estratégia de I/O em disco (`batched`, `stream`). |
| `--batch-size` | | `15` | Tamanho do lote de leitura em memória. |

#### Subcomando de Vídeo (`video`)

| Parâmetro | Atalho | Padrão | Descrição |
| :--- | :---: | :---: | :--- |
| `VIDEOS...` | | *obrigatório* | Um ou mais arquivos de vídeo (`.mp4`, `.mkv`, etc.). |
| `--start` | `-s` | `None` | Ponto inicial: frame (`int`), segundos (`float`) ou timestamp (`str` ex: `"01:30"`). |
| `--end` | `-e` | `None` | Ponto final limite: frame (`int`), segundos (`float`) ou timestamp (`str` ex: `"02:45"`). |
| `--duration` | `-d` | `None` | Duração da cena (frames ou tempo). Mutuamente exclusivo com `--end`. |
| `--step` | | `1` | Passo de amostragem de frames (pula quadros via decodificação rápida). |
| `--indices` | | `None` | Lista explícita de índices de frames separados por vírgula (ex: `"10,15,20"`). |
| `--reverse` | | `False` | Inverte o sentido de leitura do vídeo (retrocesso assíncrono de alta performance). |
| `--batch-size` | | `15` | Capacidade máxima da fila em memória para pré-carregamento concorrente. |

---

## 🐍 Uso via API Python

Você também pode utilizar o motor programmaticamente no seu código:

```python
from anicrop.enums import BlendMode
from anifuse import (
    HorizontalTranslationHandler,
    ImageSequenceReader,
    LinearBorderCutEffect,
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
    effects=[LinearBorderCutEffect(all=5)],
    blend_mode=BlendMode.HARD_MASKING,
)

# 4. Salvar resultado em alta resolução
panorama.save("panorama_cena01.png")
```
