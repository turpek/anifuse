# Makefile para o projeto anifuse

# Extrai os argumentos adicionais passados após o alvo principal (ex: make test -v -k foo)
RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
$(eval $(RUN_ARGS):;@:)

# Declara que os alvos não são arquivos.
.PHONY: install update-core test test_speed test-cov mypy format lint sync-docs push-dev pull-dev sync-main push-main

# ==============================================================================
# Ambiente e Dependências
# ==============================================================================

# Instala o pacote em modo editável e sincroniza o ambiente virtual
install:
	uv sync
	uv pip install -e .

# Atualiza a dependência do motor central 'anicrop' para a versão mais recente
update-core:
	@echo "==> Atualizando a dependência core (anicrop)..."
	uv lock --upgrade-package anicrop
	uv sync

# ==============================================================================
# Testes e Qualidade de Código
# ==============================================================================

# Roda a suíte completa de testes com o pytest
test:
	uv run pytest $(RUN_ARGS)

# Roda a suíte de testes rápida excluindo testes lentos
test_speed:
	uv run ruff format tests/
	uv run pytest -m "not slow" $(RUN_ARGS)

# Roda os testes com relatório de cobertura HTML em 'htmlcov/'
test-cov:
	uv run pytest --cov=anifuse --cov-report=html $(RUN_ARGS)

# Roda a checagem estática de tipos com o Mypy
mypy:
	uv run mypy src $(RUN_ARGS)

# Executa o linter com o ruff
lint:
	uv run ruff check .

# Formata todo o código-fonte com o ruff format
format:
	uv run ruff format .

# ==============================================================================
# Sincronização de Documentação do Motor Core (anicrop -> anifuse)
# ==============================================================================

# Espelha a documentação do anicrop em docs/anicrop/
sync-docs:
	@echo "==> Sincronizando documentação do anicrop em docs/anicrop/..."
	@mkdir -p docs/anicrop
	@if [ -d "../anicrop/docs" ]; then \
		cp -r ../anicrop/docs/* docs/anicrop/ && \
		echo "==> Documentação copiada com sucesso a partir do diretório local ../anicrop/docs/"; \
	else \
		echo "==> Clonando documentação remota do anicrop..."; \
		TMP_DIR=$$(mktemp -d) && \
		git clone --depth 1 --branch dev https://github.com/turpek/anicrop.git "$$TMP_DIR" && \
		cp -r "$$TMP_DIR/docs/"* docs/anicrop/ && \
		rm -rf "$$TMP_DIR" && \
		echo "==> Documentação sincronizada com sucesso a partir do GitHub!"; \
	fi

# ==============================================================================
# Fluxo Git Multi-PC (dev <-> main com sync-point)
# ==============================================================================

# Envia todas as alterações da branch dev para o GitHub
push-dev:
	@echo "==> Enviando branch dev para o GitHub..."
	git push origin dev

# Atualiza a branch dev a partir do GitHub (para rodar em outro computador)
pull-dev:
	@echo "==> Atualizando branch dev a partir do GitHub..."
	git pull origin dev

# Sincroniza código de produção da 'dev' para a 'main' de forma semântica e sem repetições
sync-main:
	@echo "==> Sincronizando código de produção com a branch main..."
	@LAST_POINT=$$(git log -1 --format="%b" main 2>/dev/null | grep -oE 'sync-point: [a-f0-9]+' | cut -d' ' -f2); \
	CURRENT_DEV=$$(git rev-parse --short dev); \
	if [ -n "$$LAST_POINT" ]; then \
		RANGE="$$LAST_POINT..dev"; \
	else \
		RANGE="main..dev"; \
	fi; \
	CHANGES=$$(git log $$RANGE --oneline --no-merges --invert-grep --grep="bench" --grep="docs(plano)" src/ tests/ README.md pyproject.toml | sed 's/^[a-f0-9]* /- /'); \
	if [ -z "$$CHANGES" ]; then \
		echo "Nenhuma alteração de produção para sincronizar."; \
	else \
		git checkout main && \
		git checkout dev -- src/ tests/ README.md assets/ pyproject.toml Makefile .gitignore .python-version uv.lock && \
		git commit -m "release: sincroniza código de produção da dev" -m "$$CHANGES" -m "sync-point: $$CURRENT_DEV" && \
		git checkout dev && \
		echo "==> Sincronização concluída! Retornado para a branch dev."; \
	fi

# Envia a branch main limpa para o GitHub
push-main:
	@echo "==> Enviando branch main para o GitHub..."
	git push origin main
