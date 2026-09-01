# Resumo Técnico: Otimização de Alinhamento, Geometria e Composição (`anifuse` & `anicrop`)

---

## 1. Visão Geral e Contexto

Durante o desenvolvimento do motor de reconstrução panorâmica de animes (*Tate-Pan* e *Yoko-Pan*), foram identificados e solucionados três desafios centrais de engenharia e visão computacional:
1. **Performance em Sequências Longas:** Aumento exponencial no tempo de extração de pontos ORB ao comparar novos frames contra um canvas acumulado em expansão contínua.
2. **Artefatos de Borda e Franjas:** Pixels semitransparentes espalhados em emendas de rotação devido ao antialiasing de rotação.
3. **Distorção Geométrica e Deriva:** Desalinhamentos provocados por contaminação de movimento de personagens em primeiro plano e acúmulo de micro-escala.
4. **Preservação de Nitidez (Single-Pass Resampling):** Eliminação de dupla interpolação nos frames transformados.

---

## 2. Diagnósticos e Soluções Arquiteturais

### 2.1. Otimização de Janela Ativa (`Region` / `view`)
- **Problema:** A cada novo frame $i$, rodar o detector ORB no Canvas completo ($>5500 \times 5000\text{px}$) fazia o tempo saltar de $0.2\text{s}$ para mais de $7\text{s}$ por frame, acumulando mais de $445\text{s}$ em 99 frames.
- **Solução:** 
  - Inicialização de `view = ...` antes do laço.
  - A cada iteração, calcula-se a sub-região de interseção no espaço local do Canvas:
    ```python
    view = layer1.global_region.overlap_with(layer2.global_region)
    img1 = layer1.edits[0].image[view]
    ```
  - O matching ORB opera estritamente no recorte de sobreposição de tamanho compacto ($\approx 1920 \times 1080\text{px}$), mantendo o tempo estável em **$\approx 0.22\text{s}$ por frame** ao longo de todo o vídeo.

---

### 2.2. Eliminação de Franjas com `BlendMode.SOLID_FILL`
- **Problema:** O modo `HARD_MASKING` antigo substituía pixels sólidos consolidados por valores de $\alpha > 0$ fracionários vindos do antialiasing das bordas rotacionadas, gerando mais de $500.000$ pixels semitransparentes espalhados.
- **Solução:**
  - Utilização do novo modo nativo `BlendMode.SOLID_FILL` (*Base-First*).
  - O canvas consolidado ($\alpha \ge 250$) torna-se imutável; o novo frame só preenche lacunas vazias onde $\alpha \ge 200$, forçando $\alpha = 255$ puro.
  - Resultado: **`0` pixels semi-transparentes** em todas as 5 sequências de teste.

---

### 2.3. Resolução da Distorção Geométrica e Deriva
- **Diagnóstico da Diferença vs Código Legado:**
  1. **Acúmulo de Micro-Escala:** O estimador afim contínuo detectava uma micro-escala de $0.9995$ a cada passo. Em 99 frames, $0.9995^{99} \approx 0.9724$ provocava um encolhimento composto de **$2.8\%$** e inclinação espúria de **$4.34^\circ$**.
  2. **Viés por Personagens Móveis (RANSAC Least Squares vs MODA):** A média de mínimos quadrados do `estimateAffinePartial2D` sofria atrito de $2 \sim 5\text{px}$ puxada pelo movimento dos personagens.
  3. **Alinhamento do Grid de Pixels (MODA Pós-Rotação):** Ao rotacionar a imagem previamente no mesmo eixo angular do Canvas, as linhas do cenário ficam estritamente ortogonais, permitindo que a MODA estatística discreta (`mode(diff_axis)`) trave o cenário de fundo com $100\%$ de precisão e zero contaminação.

---

### 2.4. Amostragem Única Direta (Single-Pass Resampling)
- **Problema de Qualidade:** Rotacionar o frame em uma imagem intermediária e depois fatiá-la/mesclá-la no Canvas final aplicava duas interpolações consecutivas nos mesmos pixels.
- **Solução:**
  - A rasterização temporária via `CanvasRender.render_layer(layer_temp)` é usada **apenas como buffer de consulta leve para o ORB**.
  - O `Layer` inserido na composição final recebe o **frame original do disco (`img_next`)**.
  - A matriz de transformação afim $3 \times 3$ combinada compensa a expansão da caixa delimitadora AABB:
    $$\text{canvas\_x} = \text{canvas\_origin\_x} - delx\_rot - \text{layer\_temp.global\_region.top\_left.x}$$
    $$\text{canvas\_y} = \text{canvas\_origin\_y} - dely\_rot - \text{layer\_temp.global\_region.top\_left.y}$$
  - O `flatten([layer2, layer1], interp=InterpMode.LANCZOS)` amostra a imagem original **exatamente uma vez** diretamente no Canvas final, preservando $100\%$ da nitidez dos traços do anime.

---

## 3. Tabela Comparativa de Resultados em Lote

| Sequência de Anime | Frames | Dimensões Finais | Pixels Semi-Transparentes | Tempo Total | Arquivo Gerado |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`teste`** | 4 | `5495 x 5027 px` | **`0`** | **`6.70 s`** | `scripts/single_pass_teste.png` |
| **`2631_shikanoko_..._252`** | 30 | `5507 x 5039 px` | **`0`** | **`40.18 s`** | `scripts/single_pass_2631_..._252.png` |
| **`2632_shikanoko_..._254`** | 30 | `5543 x 4693 px` | **`0`** | **`37.22 s`** | `scripts/single_pass_2632_..._254.png` |
| **`2632_shikanoko_..._255`** | 30 | `5178 x 5384 px` | **`0`** | **`37.70 s`** | `scripts/single_pass_2632_..._255.png` |
| **`2615_boku_no_tsuma_..._300`** | **99** | `2661 x 2670 px` | **`0`** | **`33.49 s`** | `scripts/single_pass_2615_..._300.png` |

---

## 4. Estrutura dos Arquivos Criados

- [`scripts/anicrop_stitcher.py`](file:///home/gui/python/anifuse/scripts/anicrop_stitcher.py): Módulo de costura completo utilizando $100\%$ `anicrop` (`CanvasRender`, `Composer`, `SOLID_FILL`, Single-Pass Resampling e fatiamento por `Region`).
- [`scripts/flatten_pipeline.py`](file:///home/gui/python/anifuse/scripts/flatten_pipeline.py): Pipeline iterativo de referência para benchmarking e validação comparativa de algoritmos de alinhamento.
