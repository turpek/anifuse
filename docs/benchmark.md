# Benchmarks de Performance — anifuse

Registro oficial de benchmarks comparativos de otimização de visão computacional e composição.

---

## Metodologia de Teste

* **Amostra de Teste:** `scripts/sample/rotate/2407_tensei_shitara_slime_datta_ken_3rd_season_11_640`
* **Frames:** 91 frames (`059.png` a `149.png`)
* **Direção:** Reverso (`reverse=True`, de 149 até 059)
* **Gerador de Seções:** `CrossSections` (tamanho de passo 500px)
* **Estimador:** `OrbRotationEstimator(max_features=5000)`
* **Stack Order:** `StackOrder.BOTH`
* **Dimensões do Panorama:** 2041 × 1866 px

---

## Tabela Comparativa dos Cenários

| Cenário | Descrição | Run 1 | Run 2 | Run 3 | Média (Tempo) | Desvio Padrão | Média (FPS) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **Estado Atual (HARD_MASKING legado e ORB não refatorado)** | 32.86s | 35.50s | 32.08s | **33.48s** | ±1.79s | **2.72 fps** |
| **2** | **HARD_MASKING corrigido (anicrop 0.5.3)** | 34.68s | 32.96s | 32.42s | **33.35s** | ±1.18s | **2.73 fps** |
| **3** | **ORB refatorado (reuso de descritores no 2º passo)** | 31.06s | 30.43s | 30.87s | **30.79s** | ±0.32s | **2.96 fps** |

---

## Detalhamento das Execuções

### Cenário 1: Estado Atual (HARD_MASKING legado e ORB não refatorado)

* **Data:** 08/09/2026
* **Branch:** `refactor/orb-rotation-optimization`
* **Versão anicrop:** `< 0.5.3`
* **Configuração:** `blend_mode=BlendMode.HARD_MASKING`, `sections_cls=CrossSections`
* **Métricas Individuais:**
  * **Run 1:** 32.86s (2.77 fps)
  * **Run 2:** 35.50s (2.56 fps)
  * **Run 3:** 32.08s (2.84 fps)
* **Resultado Consolidado:** **33.48s** de média a **2.72 fps** (dimensões: 2041 × 1866 px)

### Cenário 2: HARD_MASKING corrigido (anicrop 0.5.3)

* **Data:** 08/09/2026
* **Branch:** `refactor/orb-rotation-optimization`
* **Versão anicrop:** `0.5.3`
* **Configuração:** `blend_mode=BlendMode.HARD_MASKING`, `sections_cls=CrossSections`
* **Métricas Individuais:**
  * **Run 1:** 34.68s (2.62 fps)
  * **Run 2:** 32.96s (2.76 fps)
  * **Run 3:** 32.42s (2.81 fps)
* **Resultado Consolidado:** **33.35s** de média a **2.73 fps** (dimensões: 2043 × 1868 px)

### Cenário 3: ORB refatorado (reuso de descritores no 2º passo)

* **Data:** 08/09/2026
* **Branch:** `refactor/orb-rotation-optimization`
* **Versão anicrop:** `0.5.3`
* **Configuração:** `blend_mode=BlendMode.HARD_MASKING`, `sections_cls=CrossSections`, `cached_ref=(kp1, desc1)`
* **Métricas Individuais:**
  * **Run 1:** 31.06s (2.93 fps)
  * **Run 2:** 30.43s (2.99 fps)
  * **Run 3:** 30.87s (2.95 fps)
* **Resultado Consolidado:** **30.79s** de média a **2.96 fps** (dimensões: 2043 × 1868 px)
* **Ganho Real:** Redução de **2.56s** de CPU ($\approx 8\%$ mais rápido) com desvio padrão reduzido para apenas $\pm 0.32\text{s}$ (altíssima estabilidade). Dimensões e precisão geométrica 100% preservadas.
