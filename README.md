# anifuse

> Motor inteligente para detecção de movimento de câmera, alinhamento afim e fusão/costura não-destrutiva de cenas panorâmicas (*pan shots*) de animes.

---

## 🚀 Arquitetura e Filosofia

O `anifuse` atua como a camada de **visão computacional e orquestração de frames**, consumindo o motor gráfico [`anicrop`](https://github.com/turpek/anicrop) como backend de composição de alta performance:


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

* **Instalar dependências:** `make install`
* **Executar testes:** `make test`
* **Atualizar motor `anicrop` do GitHub:** `make update-core`
