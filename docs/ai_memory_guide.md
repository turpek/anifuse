# Guia de Uso: ai-memory no anifuse (Antigravity CLI)

> **Sobre:** O [`ai-memory`](https://github.com/akitaonrails/ai-memory) é um sistema local em Rust de memória persistente e contínua para agentes de codificação. Ele permite trabalhar com sessões curtas e leves, consolidando aprendizados, regras e handoffs em Markdown puro.

---

## 1. Visão Geral das 5 Áreas / Skills

O `ai-memory` divide sua operação em 5 grandes competências (*Agent Skills*):

```text
┌──────────────────────────────────────────────────────────────────┐
│                           ai-memory                              │
├──────────────────┬─────────────────┬─────────────────────────────┤
│ 1. Retrieval     │ Leitura e Busca │ Consulta contexto passado   │
│ 2. Handoff       │ Passagem Bastão │ Transição entre sessões     │
│ 3. Durable Pages │ Wiki Permanente │ ADRs, regras e preferências │
│ 4. Maintenance   │ Consolidação    │ Lint, sweep e aprendizado   │
│ 5. Routing       │ Instalação      │ Configuração de MCP e hooks │
└──────────────────┴─────────────────┴─────────────────────────────┘
```

---

## 2. Detalhamento de Cada Área

### 2.1. `retrieval` (Consulta e Recuperação de Contexto)
*Foco: Leitura passiva antes de tomar decisões arquiteturais ou iniciar código complexo.*

- **O que faz:** Busca no histórico do projeto por decisões prévias, gotchas, procedimentos ou resumos de sessões anteriores.
- **Ferramentas MCP disponíveis:**
  - `memory_query`: Busca textual e semântica no wiki do projeto atual.
  - `memory_read_page`: Lê o corpo completo de uma página encontrada na busca.
  - `memory_recent`: Lista páginas modificadas recentemente (visão rápida do que mudou).
  - `memory_briefing`: Retorna um snapshot estruturado (regras atuais, contagem de páginas, handoffs pendentes).
  - `memory_read_session_observations`: Lê os eventos brutos capturados pelos hooks (prompts, tool calls).
  - `memory_feedback`: Registra se uma página retornada foi `helpful`, `not_helpful`, `stale` ou `wrong`.
- **Exemplo de uso:**
  - *"Antes de mexer no BorderCutEffect, verifique no ai-memory se já definimos regras sobre corte com rotação."*

---

### 2.2. `handoff` (Continuidade e Passagem de Bastão)
*Foco: Salvar o estado exato de onde paramos para que a próxima sessão retome imediatamente sem perda de contexto.*

- **O que faz:** Cria uma "passagem de bastão" de uso único (*single-use*). A próxima sessão lê o handoff na inicialização e o consome automaticamente.
- **Ferramentas MCP disponíveis:**
  - `memory_handoff_begin`: Registra um handoff com resumo conciso (2 a 3 frases) + bullets de próximos passos.
  - `memory_handoff_list`: Lista handoffs abertos sem consumi-los (leitura passiva).
  - `memory_handoff_accept`: Consome e fecha o handoff aberto ao iniciar uma nova tarefa.
  - `memory_handoff_cancel`: Cancela um handoff criado por engano.
- **Exemplo de uso:**
  - *"Estou fechando esta sessão. Crie um handoff registrando que abandonamos o Liang-Barsky e o próximo passo é implementar a Alternativa 2 no border.py."*

---

### 2.3. `durable-pages` (Memória Permanente e Decisões de Arquitetura)
*Foco: Salvar notas definitivas, decisões arquiteturais (ADRs) ou preferências globais do operador.*

- **O que faz:** Cria e gerencia páginas Markdown persistentes no diretório da wiki (`~/.local/share/ai-memory/wiki`). Diferente das anotações automáticas de sessão, páginas duráveis exigem intenção explícita.
- **Ferramentas MCP disponíveis:**
  - `memory_write_page`: Cria ou atualiza uma página durável.
    - Suporta `pinned: true` (protege contra remoção e auto-curadoria).
    - Suporta `expires_at` (define expiração temporária tipo TTL).
    - Suporta `scope: "global"` (para preferências que valem para todos os projetos do desenvolvedor).
  - `memory_delete_page`: Remove uma página específica pelo caminho exato.
- **Padrão para Decisões Arquiteturais (ADR):**
  Páginas em `decisions/<slug>.md` são salvas com `pinned: true` no formato:
  ```markdown
  # <Título da Decisão>
  **Status:** accepted
  ## Context
  Situação e restrições que forçaram a decisão.
  ## Decision
  O que foi decidido (fato claro).
  ## Consequences
  O que ficou mais fácil, o que ficou mais difícil e alternativas rejeitadas (com o porquê).
  ```

---

### 2.4. `learning-maintenance` (Consolidação e Limpeza)
*Foco: Manutenção periódica, consolidação de sessões e auditoria de qualidade da base de conhecimento.*

- **O que faz:** Processa as observações brutas gravadas pelos hooks durante o trabalho e as compila em páginas consolidadas na wiki.
- **Ferramentas MCP disponíveis:**
  - `memory_consolidate`: Compila observações brutas de sessões recentes em páginas tópicas na wiki.
  - `memory_auto_improve`: Revisa uma sessão finalizada para propor lições aprendidas e regras de projeto.
  - `memory_lint`: Audita a wiki procurando por contradições, links quebrados ou regras desatualizadas.
  - `memory_forget_sweep`: Realiza limpeza de páginas antigas ou expiradas (respeitando páginas com `pinned: true`).
- **No terminal CLI:**
  ```bash
  ai-memory status          # Estatísticas e saúde do banco
  ai-memory lint            # Auditoria de consistência
  ai-memory forget-sweep    # Limpeza de páginas expiradas
  ```

---

### 2.5. `routing-install` (Instalação e Governança de Configuração)
*Foco: Gerenciamento dos arquivos de integração do ai-memory com cada agente de IA.*

- **O que faz:** Instala, atualiza ou repara a fiação entre o `ai-memory` e os agentes instalados no sistema (Antigravity CLI, Claude Code, Codex, etc.).
- **Ferramentas e Comandos CLI:**
  - `ai-memory install-mcp --client antigravity-cli --apply`: Configura `~/.gemini/config/mcp_config.json`.
  - `ai-memory install-hooks --agent antigravity-cli --apply`: Configura `~/.gemini/config/hooks.json`.
  - `ai-memory install-skills --scope global --agent agents`: Instala as skills em `~/.agents/skills/`.
  - `ai-memory install-instructions`: Atualiza os marcadores `<!-- ai-memory:start -->` em arquivos de instruções.

---

## 3. Comandos Úteis do Dia a Dia

```bash
# Verificar status e contagem de memórias
ai-memory status

# Buscar na memória diretamente pelo terminal
ai-memory search "border cut"

# Ler uma página específica da wiki
ai-memory read-page decisions/border-cut-rotation.md

# Finalizar a sessão atual do Antigravity CLI antes de abrir um novo chat
ai-memory finalize-session --agent antigravity-cli
```
