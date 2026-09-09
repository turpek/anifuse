# Plano: Eliminação de Linhas Sutis de Costura (Stair-stepping & Ringing) em Cenas com Rotação

> **Contexto:** Diagnóstico a partir da inspeção visual de `scripts/comparacao_costura.png` (amostra `2407_tensei_shitara_slime_datta_ken_3rd_season_11_640`), após a correção de padding simétrico no `anicrop` que eliminou as franjas escuras.

---

## 1. Diagnóstico do Problema

Mesmo após a eliminação dos halos pretos de borda (resolvidos pelo padding simétrico em Straight Alpha no `anicrop.transform_image`), persistem **linhas sutis de emenda** visíveis sob ampliação (zoom).

Essas linhas aparecem tanto com `BlendMode.HARD_MASKING` quanto com `BlendMode.NORMAL_LINEAR` (utilizando interpolação `Lanczos`).

### Causas Raízes Identificadas:

1. **Lanczos Sinc Undershoot (Ringing nos extremos de borda):**
   - O filtro Lanczos calcula interpolação usando uma função sinc com lóbulos negativos.
   - Quando um frame rotacionado atinge o limite do seu suporte alfa, os pixels imediatamente adjacentes à borda sofrem uma leve atenuação/escurecimento (undershoot numérico), criando uma sutil linha de contorno de 1px.

2. **Rasterização Discreta e Stair-stepping (Aliasing de Contorno Diagonal):**
   - Uma borda rotacionada não alinha com a grade cartesiana ortogonal de pixels.
   - O rasterizador discretiza a linha diagonal em degraus de 1px (*stair-stepping*). Com cortes abruptos ou máscaras rígidas, essa transição diagonal projeta uma linha dentada visível contra o fundo.

3. **Variações de Iluminação e Ruído de Compressão entre Quadros (Luma Delta):**
   - Em streams de vídeo comprimidos (ex: H.264/H.265), há flutuações discretas de quantização entre quadros subsequentes (ruído temporal de luma).
   - Quando dois quadros com leve diferença de luminância se encontram numa costura nítida, o olho humano detecta o contraste de borda instantaneamente (efeito Mach Banding).

---

## 2. Abordagens Propostas

Para eliminar essas linhas residuais sem degradar a nitidez do restante do cenário, quatro abordagens complementares podem ser exploradas:

### Abordagem 1: Alteração da Interpolação na Rotação (`CUBIC` / `LINEAR`)
- **Conceito:** Substituir a interpolação `Lanczos` por `Cubic` (Bicúbica) ou `Linear` durante o warp da rotação.
- **Mecanismo:** Filtros sem lóbulos negativos eliminam 100% o efeito de undershoot/ringing nas bordas da imagem rotacionada.
- **Vantagem:** Custo computacional zero (já suportado pelo `InterpMode` do `anicrop`); teste imediato.
- **Consideração:** `Cubic` é ligeiramente menos nítido que `Lanczos` em frequências extremas, mas quase imperceptível em traços de anime.

---

### Abordagem 2: Erosão Alfa de Borda (Contour Alpha Erode de 1 a 2px)
- **Conceito:** Fazer uma erosão morfológica mínima (`erode` / `min_pool`) de 1 a 2 pixels no canal alfa do frame rotacionado antes da composição.
- **Mecanismo:**
  ```python
  # Descarta o anel perimétrico de 1-2px afetado pelo ringing de interpolação
  kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
  alpha_eroded = cv2.erode(frame_alpha, kernel, iterations=1)
  ```
- **Vantagem:** Elimina completamente os pixels periféricos corrompidos pelo filtro de rotação, revelando apenas os pixels internos puros do quadro.
- **Consideração:** Requer leve suporte no pipeline de efeitos ou no handler de rotação.

---

### Abordagem 3: Transição Suave na Emenda (Soft Seam Feathering de 2 a 4px)
- **Conceito:** Aplicar uma rampa linear ou sigmoide de opacidade (feathering) muito estreita (2 a 4 pixels) exclusivamente na zona de transição entre as camadas sobrepostas.
- **Mecanismo:**
  - Em vez de um corte binário (0 ou 255), a borda do frame superior decai suavemente ao longo de 2-4 pixels sobre o frame inferior.
  - Dissolve o efeito de escada (*stair-stepping*) e o Mach Banding de quantização de vídeo.
- **Vantagem:** Resultado estético perfeito para transições diagonais e em ângulo.
- **Consideração:** Pode ser implementado como uma extensão ou modo do `BorderCutEffect` (`feather_width=2`).

---

### Abordagem 4: Fusão Multibanda (Laplacian Pyramid Seam Blending)
- **Conceito:** Decomposição da zona de costura em pirâmides de frequências (Laplaciana para detalhes, Gaussiana para iluminação global).
- **Mecanismo:**
  - Altas frequências (traços, detalhes) são mescladas com transição estreita para evitar *ghosting*.
  - Baixas frequências (gradientes de cor, céu, iluminação) são mescladas com transição larga para eliminar descontinuidades de cor.
- **Vantagem:** Estado da arte para costura fotográfica e panoramas complexos.
- **Consideração:** Maior complexidade matemática e custo de processamento. Recomendado apenas se as abordagens 1, 2 e 3 não forem suficientes.

---

## 3. Próximos Passos Recomendados

1. **Teste Rápido 1:** Avaliar `InterpMode.CUBIC` na amostragem da rotação no script de teste.
2. **Teste Rápido 2:** Adicionar teste de erosão de 1px (`cv2.erode`) no canal alfa do quadro sobreposto.
3. **Refinamento:** Se necessário, incorporar a opção `feather_px` no `BorderCutEffect`.


 Porém, na literatura de processamento de imagens e computação gráfica, existem sim outras formas de resolver o problema do Lanczos sem
  precisar cortar a borda:
  ──────
  ### 1. Clamping de Extremos (Anti-Ringing Clamping)

  • Como funciona: Durante a interpolação, o valor de cada novo pixel é travado entre o valor mínimo e máximo dos pixels originais da
  vizinhança:

    pixel = operatornameclamp⎛pixel       ,min (vizinhos),max (vizinhos)⎞
                             ⎝     lanczos                              ⎠

  • Por que resolve: O escurecimento característico da linha ocorre porque o lóbulo negativo do sinc calcula um valor inferior ao menor valor
  existente nos vizinhos (undershoot). O clamp impede matematicamente essa queda abaixo do mínimo, eliminando a linha escura sem perder
  nenhum pixel de borda.
  • Onde é usado: É exatamente a técnica usada por renderizadores de alta fidelidade (como madVR e mpv/libplacebo na opção anti-ringing).
  ──────
  ### 2. Extensão de Cor por Dilatação (Color Bleed / Edge Padding RGB)

  • Como funciona: Antes de aplicar a rotação no frame, o conteúdo RGB é "sangrado" (dilated/replicated) 2 ou 3 pixels além da borda do canal
  alfa.
  • Por que resolve: O filtro Lanczos precisa de pixels válidos ao redor da borda para não colapsar. Com o sangramento de cor, o lóbulo do
  filtro encontra cores idênticas às da borda, impedindo a criação do tom escuro.
  ──────
  ### 3. Interpolação Ponderada por Alfa (Premultiplied Normalized Filter)

  • Como funciona: Em vez de interpolar os canais RGB e o canal Alfa de forma independente, os canais de cor são multiplicados pelo alfa e os
  pesos da convolução de Lanczos são normalizados pela soma da cobertura alfa local.
  • Por que resolve: Garante que a transição de opacidade absorva proporcionalmente a variação de energia do filtro na fronteira.
  ──────
  ### Resumo Prático:

  • Se não quisermos implementar filtros customizados de anti-ringing clamping no nível de C++/OpenCV:
      1. Com corte: Usa Lanczos + corte/erosão de 1px na borda.
      2. Sem corte: Usa **image.md** (que matematicamente não gera undershoot significativo e tem nitidez excelente em traços de anime).
────────────────────────────────────────────────────────────
