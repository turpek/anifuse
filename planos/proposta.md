Sim, é perfeitamente possível.

O motivo pelo qual o algoritmo padrão (**ORB + RANSAC Least Squares**) falhava em 1 passo é que o RANSAC tradicional calcula a média quadrática (**L₂**) dos resíduos, sendo "puxado" pelo movimento dos personagens em primeiro plano.

Abaixo estão as **5 principais alternativas de visão computacional** para resolver em 1 único passo, com seus prós, contras e viabilidade prática.

---

### 1. Votação em Histograma 4D / Transformada de Hough Afim (Generalização da MODA)

**Como funciona:** É a extensão matemática direta da sua MODA para o espaço afim 4D:

$$
(\theta, s, t_x, t_y)
$$

1. A partir de cada par de pontos correspondentes do ORB $(p_1, p_2)$, calcula-se o voto individual de:

$$
(\theta, s, t_x, t_y)
$$

2. Todos os pares votam em um acumulador/histograma discreto multidimensional.

3. O pico do histograma é a **MODA multidimensional exata** do cenário em 1 único passo.

**Vantagens:**

* Imunidade total a personagens móveis, mantendo a mesma precisão da MODA.
* Não é necessário rotacionar as imagens previamente.

**Complexidade:**

* Requer um *binning* (discretização) adequado dos eixos angulares e espaciais.

---

### 2. LMEDS (Least Median of Squares — Mediana em vez de Média)

**Como funciona:** Em vez de minimizar a média dos erros quadráticos, que é vulnerável a *outliers*, o estimador minimiza a **mediana dos resíduos**:

```python
M, inliers = cv2.estimateAffinePartial2D(pts2, pts1, method=cv2.LMEDS)
```

**Vantagens:**

* Já é nativo do OpenCV em 1 única linha de código.
* Extremamente rápido (**21,27 s para 30 frames**).
* Tolerância a até 50% de pontos corrompidos/móveis.

**Limitação:**

* Em cenas com grande volume de personagens ocupando o centro da tela, a mediana contínua ainda pode apresentar um desvio residual de aproximadamente **1 px**.

---

### 3. ECC (Enhanced Correlation Coefficient Maximization — `cv2.findTransformECC`)

**Como funciona:** É um método direto baseado em gradientes e correlação de intensidade de imagem (Lucas-Kanade inverso).

Ele otimiza iterativamente o coeficiente de correlação entre os dois frames sob o modelo afim 2D:

$$
W(\mathbf{x};\mathbf{p}) =
\begin{bmatrix}
s\cos\theta & -s\sin\theta & t_x \\
s\sin\theta & \phantom{-}s\cos\theta & t_y
\end{bmatrix}
$$

**Vantagens:**

* Alta precisão, potencialmente em nível subpixel.
* Maior resistência a variações de brilho e iluminação.

**Limitação:**

* É mais pesado computacionalmente.
* Requer uma inicialização razoavelmente próxima.
* Pode ser inicializado pelo resultado do ORB, permitindo uma abordagem híbrida em 1 passo.

---

### 4. Transformada de Fourier-Mellin (Phase Correlation no Espaço Log-Polar)

**Como funciona:** Opera essencialmente no **domínio da frequência**, utilizando FFT:

1. A magnitude da Transformada de Fourier é invariante à translação.
2. Ao projetar o espectro em coordenadas log-polares $(\ln r, \theta)$, rotação e escala tornam-se translações.
3. Uma correlação de fase encontra o pico correspondente a $(\theta, s)$.
4. Uma segunda correlação de fase 2D encontra:

$$
(t_x, t_y)
$$

**Vantagens:**

* Trabalha diretamente no domínio da frequência.
* Não depende de detecção de cantos ou descritores ORB.

**Limitação:**

* É sensível a grandes áreas com cores sólidas ou planas, muito comuns em ilustrações de anime.

---

### 5. Optical Flow Denso (DIS Optical Flow) + RANSAC de Movimento Global

**Como funciona:** O `cv2.DISOpticalFlow` calcula o vetor de movimento $(u,v)$ de praticamente todos os pixels da tela.

Com o campo vetorial denso, contendo milhões de vetores de movimento, ajusta-se uma transformação afim global, rejeitando os vetores associados aos personagens como anomalias locais.

**Vantagens:**

* Altíssima densidade de informação.
* Não depende da existência de cantos ou *features* nítidas.
* Pode funcionar bem em regiões onde o ORB encontra poucos pontos.

---

## Recomendação Prática

* Se o objetivo for **velocidade máxima em 1 passo nativo**: **LMEDS** ou **ORB + Votação em Histograma 4D (MODA 4D)** são as opções ideais.

* Se o objetivo for **fidelidade e robustez com o código atual**: a **MODA com rotação prévia** (que já implementamos no `anicrop_stitcher.py`) continua sendo a mais precisa para o estilo de arte de animes.

Gostaria de testar a implementação da **MODA 4D (Votação em Histograma em 1 passo)** ou do **ECC** em alguma sequência?

