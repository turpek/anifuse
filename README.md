# anifuse

> Motor inteligente para detecção de movimento de câmera, alinhamento afim e fusão/costura não-destrutiva de cenas panorâmicas (*pan shots*) de animes.

---

## 🚀 Arquitetura e Filosofia

O `anifuse` atua como a camada de **visão computacional e orquestração de frames**, consumindo o motor gráfico [`anicrop`](https://github.com/turpek/anicrop) como backend de composição de alta performance:

- **`anifuse` (Visão Computacional):** Rastreamento de trajetória de câmera, alinhamento afim robusto (ECC, RANSAC, MODA discreta), mascaramento inteligente de ruídos e orquestração de entrada.
- **`anicrop` (Composição Gráfica):** Pilha de camadas (`LayerStack`, `Layer`), transformações afins contínuas 3x3, fusão de pixels via `BlendMode.SOLID_FILL` e exportação em alta resolução.

---

## 📦 Instalação Rápida

Em qualquer computador com Python 3.12+ e `uv`:

```bash
git clone https://github.com/turpek/anifuse.git
cd anifuse
uv sync
```

---

## 🛠️ Comandos Úteis

### Ambiente e Core
* **Instalar dependências em modo editável:** `make install`
* **Atualizar motor `anicrop` do GitHub:** `make update-core`
* **Sincronizar documentação do anicrop:** `make sync-docs`

### Testes e Qualidade
* **Executar todos os testes:** `make test`
* **Executar suíte de testes rápida:** `make test_speed`
* **Relatório de cobertura HTML:** `make test-cov`
* **Checagem de tipos (Mypy):** `make mypy`
* **Verificação de lint (Ruff):** `make lint`
* **Auto-formatação de código (Ruff + autopep8):** `make format`

### Sincronização Git Multi-PC
* **Enviar alterações de dev:** `make push-dev`
* **Puxar alterações de dev:** `make pull-dev`
* **Sincronizar código de produção para a main:** `make sync-main`
* **Publicar branch main:** `make push-main`
