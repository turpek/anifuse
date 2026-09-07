# Guia de Calibração: `fast_threshold` no Detector ORB

Este documento detalha o papel, o comportamento físico e os **valores ideais do `fast_threshold`** para cada cenário de animação e mídia no motor `anifuse`.

---

## 1. O que é o `fast_threshold` e por que ele é crucial?

O algoritmo **ORB** (*Oriented FAST and Rotated BRIEF*) utiliza internamente o detector **FAST** (*Features from Accelerated Segment Test*) para encontrar cantos e pontos de interesse na imagem.

### Princípio de Operação do FAST:
1. Para cada pixel central $p$ com intensidade $I_p$, o algoritmo avalia um círculo de 16 pixels ao seu redor (círculo de Bresenham de raio 3).
2. Um ponto só é considerado um **canto candidato** se houver um conjunto contínuo de $N$ pixels no círculo cuja intensidade seja:
   - Mais brilhante que $I_p + t$, ou
   - Mais escura que $I_p - t$
3. O parâmetro $t$ é exatamente o **`fast_threshold`** (limiar de contraste de intensidade).

---

## 2. O Problema de Domínio: Animes vs. Fotografias Reais

- **Fotografias Reais (Mundo Físico):** Cenas reais possuem granulação de sensor, texturas rugosas (concreto, tijolos, folhagens, tecidos) e variações de iluminação com alto micro-contraste. O valor padrão do OpenCV (`fastThreshold = 20`) foi calibrado para descartar o ruído térmico dessas fotos.
- **Animes (Ilustração Digital & Cel-Shading):**
  - Cenários de fundo são desenhados com traços finos de caneta digital, aquarelas suaves e gradientes de pintura digital.
  - A diferença de intensidade entre pixels em gradientes de céu, paredes de salas ou sombras suaves frequentemente varia entre **$7$ e $15$ unidades de brilho**.
  - **Com `fastThreshold = 20`**, o detector considera o cenário de fundo "completamente liso" e o ignora.
  - Como consequência, os únicos pontos que ultrapassam $t = 20$ são os contornos escuros de personagens em primeiro plano. Se o personagem piscar ou mexer a cabeça, o consenso do fundo é perdido e a confiança desaba para $< 0.60$.

---

## 3. Matriz de Valores Ideais por Cenário

A tabela abaixo estabelece as diretrizes calibradas para cada caso de uso:

| Caso de Uso / Tipo de Cena | `fast_threshold` Recomendado | Comportamento do Detector | Cenários Típicos |
| :--- | :---: | :--- | :--- |
| **Padrão Geral do `anifuse` (Recomendado para Animes)** | **`10`** | **Equilíbrio ideal.** Captura centenas de pontos em linhas finas de cenários e gradientes suaves de cel-shading sem disparar em ruído aleatório. | Cenas urbanas, interiores de salas, cenários normais de estúdio (CloverWorks, Kyoto Animation, ufotable, etc.). |
| **Cenas com Baixo Contraste / Noturnas / Névoa** | **`5` a `7`** | **Sensibilidade ultra-alta.** Garante densidade de pontos mesmo em cenas escuras, com iluminação difusa, névoa volumétrica ou gradientes de aquarela muito suaves. | Céus abertos ao entardecer/madrugada, pores do sol, cenas sob luar fraco, ilustrações estilo aquarela/pastel. |
| **Cenas com Hachuras Densas / Mangá Estilizado** | **`12` a `15`** | **Sensibilidade moderada.** Evita a saturação excessiva em texturas repetitivas de alta frequência (hachuras, tramas de retícula) que podem gerar ambiguidades de matching. | Animes com arte estilo mangá (ex: *JoJo*, *Mob Psycho*), florestas densas com milhares de folhas detalhadas. |
| **Filmes Live-Action / Fotos Reais / CGI Hiper-realista** | **`20`** *(Padrão OpenCV)* | **Filtro de ruído fotográfico.** Projetado para mídias físicas, impedindo que granulação de filme ou ruído térmico de sensor CMOS sejam detectados como cantos. | Filmes live-action, footage de câmera real, sequências 3D hiper-realistas. |
| **Mídias Antigas / Cel-Animation / VHS / Compressão Forte** | **`25` a `30`** | **Insensibilidade a artefatos.** Evita que artefatos de macroblocos de compressão (MPEG-2, XviD) ou poeira/grão de celuloide analógico sejam rastreados. | Rips antigos de TV, animes dos anos 80 e 90 com película granulada ou compressão pesada. |

---

## 4. Evidência Empírica: Diagnóstico na Amostra 2329

No teste comparativo entre os quadros `018.png` e `019.png` da amostra `2329_kami_wa_game_ni_uete_iru_09_807_2` (onde o fundo estava estático e o topo continha animação de personagem):

```text
Configuração Original (fastThreshold = 20):
- Keypoints encontrados: 51
- Matches válidos: 27
- Inliers no fundo estático: 16 de 30 (53.3%)
- Confiança de movimento: 0.520  --> REJEITADO (disparou fallback espúrio)

Configuração Calibrada (fastThreshold = 10):
- Keypoints encontrados: 539  (10.5x mais pontos)
- Matches válidos: 205
- Inliers no fundo estático: 40 de 40 (100.0%)
- Confiança de movimento: 1.000  --> ACEITO COM PRECISÃO MÁXIMA

Configuração Ultra-sensível (fastThreshold = 7):
- Keypoints encontrados: 1457
- Matches válidos: 595
- Inliers no fundo estático: 40 de 40 (100.0%)
- Confiança de movimento: 1.000
```

---

## 5. Como Configurar no Código

### 5.1. Globalmente via `config`
```python
from anifuse.config import config

# Ajusta para cenas escuras ou de aquarela:
config.fast_threshold = 7
```

### 5.2. Diretamente na Fábrica `SceneStitcher.from_default`
```python
from anifuse.stitcher import SceneStitcher

# Passa como parâmetro de conveniência de alto nível:
stitcher = SceneStitcher.from_default(
    fast_threshold=10,
    confidence_threshold=0.50,
)
```

### 5.3. Diretamente nos Estimadores ORB
```python
from anifuse.detection import OrbScaleEstimator, OrbTransformEstimator

estimator = OrbScaleEstimator(
    max_features=5000,
    fast_threshold=10,
)
```
