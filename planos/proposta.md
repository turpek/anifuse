  Sim, é perfeitamente possível.

  O motivo pelo qual o algoritmo padrão (ORB + RANSAC Least Squares) falhava em 1 passo é que o RANSAC tradicional calcula a média quadrática
  (L₂) dos resíduos, sendo "puxado" pelo movimento dos personagens em primeiro plano.
  Abaixo estão as 5 principais alternativas de visão computacional para resolver em 1 único passo, com seus prós, contras e viabilidade
  prática:
  ──────
  ### 1. Votação em Histograma 4D / Transformada de Hough Afim (Generalização da MODA)
  • Como funciona: É a extensão matemática direta da sua MODA para o espaço afim 4D

    ⎛θ,s,t ,t ⎞
    ⎝     x  y⎠

  .
  1. A partir de cada par de pontos correspondentes do ORB (p₁,p₂), calcula-se o voto individual de

    ⎛θ,s,t ,t ⎞
    ⎝     x  y⎠

  .
  2. Todos os pares votam em um acumulador/histograma discreto multidimensional.
  3. O pico do histograma é a MODA multidimensional exata do cenário em 1 único passo.

  • Vantagens: Imunidade total a personagens móveis (mesma precisão da MODA) sem precisar rotacionar imagens.
  • Complexidade: Requer binning (discretização) adequado dos eixos angulares e espaciais.
  ──────
  ### 2. LMEDS (Least Median of Squares — Mediana em vez de Média)

  • Como funciona: Em vez de minimizar a média dos erros quadráticos (que é vulnerável a outliers), o estimador minimiza a mediana dos
  resíduos:
    M, inliers = cv2.estimateAffinePartial2D(pts2, pts1, method=cv2.LMEDS)


    * **Vantagens:**
      * Já é nativo do OpenCV em 1 única linha de código.
      * Extremamente rápido (**`21.27 s`** para 30 frames).
      * Tolerância a até 50% de pontos corrompidos/móveis.
    * **Limitação:** Em cenas com grande volume de personagens ocupando o centro da tela, a mediana contínua ainda pode ter um desvio
  residual de ≈1 px.

    ---

    ### 3. ECC (Enhanced Correlation Coefficient Maximization — `cv2.findTransformECC`)
    * **Como funciona:** É um método direto baseado em gradientes e correlação de intensidade de imagem (Lucas-Kanade Inverso). Ele otimiza
  iterativamente o coeficiente de correlação entre os dois frames sob o modelo afim 2D:


         ⎡ s cos θ  -s sin θ  t  ⎤
         ⎢                     x ⎥

  𝐖(𝐱;𝐩) = ⎢ s sin θ  s cos θ   t  ⎥
  ⎣                     y ⎦


    * **Vantagens:** Precisão subpixel milimétrica (0.01 px) e invariância a variações de brilho/iluminação.
    * **Limitação:** Mais pesado computacionalmente (requer inicialização próxima, podendo ser inicializado pelo ORB em 1 passo).

    ---

    ### 4. Transformada de Fourier-Mellin (Phase Correlation no Espaço Log-Polar)
    * **Como funciona:** Opera 100% no **domínio da frequência** (FFT):
      1. A magnitude da Transformada de Fourier é invariante a translação.
      2. Ao projetar o espectro em coordenadas Log-Polares (ln r,θ), a rotação e a escala tornam-se translações puras.
      3. Uma correlação de fase acha o pico de Dirac de (θ,s).
      4. Uma segunda correlação de fase 2D acha


  ⎛t ,t ⎞
  ⎝ x  y⎠


    .
    * **Vantagens:** Totalmente analítico, sem detecção de cantos ou descritores ORB.
    * **Limitação:** Sensível a grandes áreas com cores sólidas/planas (muito comuns em ilustrações de anime).

    ---

    ### 5. Optical Flow Denso (DIS Optical Flow) + RANSAC de Movimento Global
    * **Como funciona:** O `cv2.DISOpticalFlow` calcula o vetor de movimento (u,v) de **todos os pixels da tela** em ≈10 ms.
      * Com o campo vetorial de milhões de pixels, ajusta-se a matriz afim rejeitando os vetores dos personagens como anomalias locais.
    * **Vantagens:** Altíssima densidade de informação (não depende de achar cantos nítidos).

    ---

    ### Recomendação Prática:
    * Se o objetivo for **velocidade máxima em 1 passo nativo**: **LMEDS** ou **ORB + Votação em Histograma 4D (MODA 4D)** são as opções
  ideais.
    * Se o objetivo for **fidelidade e robustez com o código atual**: A **MODA com rotação prévia** (que já implementamos no
  anicrop_stitcher.py) continua sendo a mais precisa para o estilo de arte de animes.

    Gostaria de testar a implementação da **MODA 4D (Votação em Histograma em 1 passo)** ou do **ECC** em alguma sequência?
