# Resumo Técnico: Investigação de Desalinhamento, Semântica de Blend e Costura na Amostra 2407

> **Data:** 08/09/2026  
> **Amostra de Teste:** `scripts/sample/rotate/2407_tensei_shitara_slime_datta_ken_3rd_season_11_640` (91 frames: `059.png` a `149.png`)  
> **Modo de Operação:** Reverso (`reverse=True`, partindo do frame `149` descendo até `059`)

---

## 1. Visão Geral do Problema

Durante os testes de costura em modo reverso na cena `2407` (Luminous Valentine sentada no trono, cena com rotação contínua de câmera e corações translúcidos flutuando), observou-se:

1. **Corte horizontal na poltrona:** A almofada vermelha foi fatiada ao meio por uma linha reta em $Y = 1522$ no arquivo `reversed_last_on_top.png`.
2. **Aparente desalinhamento no tornozelo e bota:** Logo abaixo da linha de corte, a bota parecia interrompida ou deslocada em cerca de 30 pixels.
3. **Efeito de pente / scanlines:** Na lateral direita da almofada vermelha, formou-se um padrão estriado de micro-fatias horizontais.
4. **Comportamento do motor legado (`scripts/anicrop`):** O modo legado executou sem esse corte na poltrona, gerando uma imagem visualmente coesa.

---

## 2. Anatomia Geométrica do Alinhamento

### 2.1. O Alinhamento Matemático está Correto (Precisão Subpixel)
Foi realizado um confronto direto entre a transformação calculada pelo `anifuse` e uma homografia afim direta calculada via SIFT com RANSAC rigoroso:
* **Diferença de Centro no Canvas (Anifuse vs. SIFT):**
  * Frame `062`: `[-0.64px, +0.06px]`
  * Frame `061`: `[-0.17px, +0.52px]`
  * Frame `060`: `[+0.04px, -0.38px]`
* **Sobreposição Visual 50/50 (`knee_blend.png` e `knee_blend_060.png`):**
  * O traço dourado da bota, o contorno do joelho e os relevos do trono sobrepõem-se com nitidez perfeita (diferença média de apenas 14 níveis de cinza em 255).
  * **Conclusão:** A personagem **não se moveu** entre os frames e o rastreamento afim do motor não sofreu desvio geométrico significativo.

### 2.2. Por que o pé parecia "deslocado/quebrado"?
1. No Frame `149`, a bota é cortada naturalmente pela borda inferior do enquadramento da câmera ($Y = 1522$ no canvas).
2. Nos frames `063` a `059`, a câmera executa um giro abrupto (*Dutch roll*, de $-25^\circ$ a $-137^\circ$).
3. Com a rotação drástica do retângulo 16:9, **a área onde a ponta da bota deveria continuar ficou fora da tela** desses frames, gerando um vazio transparente ($\alpha = 0$) de 226px de largura logo abaixo do corte.
4. Imediatamente adjacente a esse vazio, os frames rotacionados exibiam a perna dourada do trono.
5. **A ilusão de ótica:** A bota cortada terminando no vazio, lado a lado com a perna dourada da poltrona, fez o cérebro humano interpretar como se a perna tivesse sido quebrada e transladada em 30px.

---

## 3. A Semântica do `BlendMode.SOLID_FILL` e a Inversão nos Acumuladores

### 3.1. O Propósito Original do `SOLID_FILL`
* O `BlendMode.HARD_MASKING` falhou em panoramas com rotação porque copiava cegamente os pixels com antialiasing fracionário ($\alpha \in [1, 249]$) gerados pelo `warpAffine`, gravando semitransparência sobre pixels sólidos da base e furando o canvas.
* O `BlendMode.SOLID_FILL` foi desenvolvido especificamente para stitching sob a regra **Base-First**:
  * O buffer da camada inferior (`bottom`, índice 0) é o **canvas blindado**: se $\alpha \ge 250$, **nada altera esse pixel**.
  * O buffer da camada superior (`top`, índice 1) **só preenche onde a base for transparente** ($\alpha < 250$) e fixa $\alpha = 255$ puro.

### 3.2. A Inversão Oculta em `accumulator.py`
Como o `SOLID_FILL` protege a camada do índice 0:
* No `LastOnTopAccumulator`:
  ```python
  self._base = flatten([bottom, top])  # bottom = self._base (antigo), top = incoming (novo)
  ```
  O canvas antigo (`self._base`) estava no índice 0. Portanto, ele ficava **blindado**, e o novo frame **não conseguia sobrescrever** o que já existia. Ele agia na prática como *First-on-Top*.
* No `FirstOnTopAccumulator`:
  ```python
  self._base = flatten([bottom, top])  # bottom = incoming (novo), top = self._base (antigo)
  ```
  O novo frame estava no índice 0. Portanto, ele sobrescrevia o canvas antigo, agindo como *Last-on-Top*.

### 3.3. A Causa do Corte da Almofada em `reversed_last_on_top.png`
* O primeiro frame a entrar no canvas foi o Frame `149`, que termina na linha $Y = 1522$ (sem a metade inferior da almofada).
* Por estar blindado pelo `SOLID_FILL`, quando os frames `063`/`062` chegaram com a almofada inteira desenhada, eles foram proibidos de sobrepor o Frame `149`.
* Eles só puderam preencher o vazio abaixo de $Y = 1522$, fatiando a almofada ao meio.
* Quando testamos o empilhamento invertido (`flatten([incoming, base])`), a almofada ficou **100% contínua e sem corte** (`crop_true_last_on_top.png`).

---

## 4. O Limite da Abordagem: A Inversão de Camadas não Elimina a Emenda

A inversão da ordem no `accumulator.py` não é a solução definitiva:
> *Se colocamos o frame novo por cima, a borda do frame novo corta o cenário antigo.*  
> *Se colocamos o frame antigo por cima, a borda do frame antigo corta o cenário novo.*

Em qualquer sistema de **empilhamento seco (*hard cut*)**:
* A borda de corte do retângulo da câmera (ou sua projeção rotacionada) é uma reta/diagonal geométrica cega.
* Essa reta frequentemente intercepta objetos contínuos e rígidos (almofada, perna, cabeça).
* Havendo qualquer diferença de iluminação, ruído de compressão DCT ou partículas flutuantes entre os frames, a descontinuidade vira uma emenda visível.

---

## 5. De Onde Veio o Efeito de Pente (Scanlines / Banding)?

* O teste foi executado intencionalmente sem corte de borda (`effects=[]`).
* A câmera possuía uma rotação suave contínua de aproximadamente $-0.04^\circ$ por frame ao longo de 85 frames.
* Ao rotacionar um retângulo sem podar suas bordas, a aresta inferior inclinada forma degraus discretos de 1 a 2 pixels a cada iteração.
* Como o `SOLID_FILL` grava permanentemente qualquer pixel desenhado na base, **53 frames diferentes deixaram fatias de 1px** empilhadas horizontalmente, formando o padrão de scanlines registrado em `crop_banding.png`.
* Isso valida que o `BorderCutEffect` é indispensável para evitar que degraus de rotação se acumulem no canvas.

---

## 6. Comparativo: Motor Legado (`scripts/anicrop`) vs. `anifuse`

| Característica | Motor Legado (`scripts/anicrop`) | Motor Atual (`anifuse`) |
| :--- | :--- | :--- |
| **Escopo de Matching** | **Canvas Global:** Compara o frame contra o canvas acumulado inteiro (`image1`). | **Janela Ativa Local:** `CrossSections` divide em seções de 500px para economizar CPU. |
| **Pontos-Chave ORB** | **100.000 pontos** com `FAST_SCORE`. | **5.000 pontos** (`OrbRotationEstimator`). |
| **Sensibilidade a Rotações Extremas** | Robusto: encontra correspondências no trono global mesmo em giros de $137^\circ$. | Sensível: seções locais pequenas podem conter apenas corações flutuantes ou áreas homogêneas. |
| **Custo Computacional** | Alto em cenas longas ($>5000\text{px}$). | Estável e constante ($\approx 0.22\text{s}$ por frame). |

### 6.1. Validação do Modo Global no `anifuse`
Criamos um teste temporário forçando o `CrossSections` a retornar sempre a `global_region` inteira:
* **Tempo Total:** 37.70s para 91 frames com rotação (média de 0.41s/frame).
* **Consistência:** Confiança $1.00$ em quase todos os frames e escala travada em $1.0000$ estável (rejeição total de ruído).

---

## 7. Propostas de Solução para o Motor

Para que o `anifuse` resolva definitivamente essa classe de problemas sem apenas trocar o endereço do corte, as seguintes frentes técnicas devem ser exploradas:

### 7.1. Seam-Aware Blending (Máscara de Distância Normalizada)
* No overlap entre duas camadas, calcular a distância euclidiana até as respectivas bordas (`cv2.distanceTransform`).
* Gerar uma transição linear ou sigmoide onde os pesos somem exatamente $1.0$ ($W_A + W_B = 1.0$).
* **Vantagem:** O canal alfa final permanece **$\alpha = 255$ puro e sólido** (sem o problema do `HARD_MASKING`), mas a transição de cor entre os frames torna-se suave, eliminando qualquer linha de corte seco.

### 7.2. Costura por Linha Ótima (*Optimal Seam Finding / Graph-Cut*)
* Em vez de cortar na borda retangular da câmera, encontrar um caminho de corte na área de sobreposição onde a diferença de intensidade ($|I_1 - I_2|$) seja mínima ou passe pelo fundo homogêneo.
* Evita que a linha de emenda passe pelo meio de personagens ou móveis detalhados.

### 7.3. Política Adaptativa de Seções no `AdaptiveViewPolicy`
* Implementar chaveamento automático ou configurável para modo global (`GlobalViewPolicy` ou `fallback_to_global=True`) em cenas com rotação contínua expressiva, garantindo que o detector tenha visão do canvas completo quando giros acentuados ocorrerem.

### 7.4. Máscara de Exclusão de Partículas (`MaskView`)
* Utilizar máscaras morfológicas ou de cor para desconsiderar partículas e elementos dinâmicos (como os corações cor-de-rosa) no cálculo de homografia, focando os descritores ORB exclusivamente na geometria rígida do cenário.
