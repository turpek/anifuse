# Makefile para o projeto anifuse

# Extrai os argumentos adicionais passados após o alvo principal (ex: make test -v -k foo)
RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
$(eval $(RUN_ARGS):;@:)

# Declara que os alvos não são arquivos.
.PHONY: install test test_speed test-cov mypy lint format update-core sync-docs push-dev pull-dev sync-main push-main

# Instala o pacote em modo editável e as dependências de desenvolvimento.
install:
	uv sync
	uv pip install -e .

# Roda a suíte de testes com o pytest.
test:
	uv run pytest $(RUN_ARGS)

# Roda a suíte de testes com o pytest excluindo os mais lentos.
test_speed:
	uv run ruff format tests/
	uv run pytest -m "not slow" $(RUN_ARGS)

# Roda os testes e gera um relatório de cobertura HTML na pasta 'htmlcov/'.
test-cov:
	uv run pytest --cov=anifuse --cov-report=html $(RUN_ARGS)

# Roda o checador de tipos Mypy no código-fonte.
mypy:
	uv run mypy src $(RUN_ARGS)

# Roda a verificação de formatação e linter com ruff.
lint:
	uv run ruff check .

# Formata o código com ruff format.
format:
	uv run ruff format .

# Atualiza a dependência do anicrop para o commit mais recente da main no GitHub
update-core:
	@echo "==> Atualizando motor anicrop a partir da branch main do GitHub..."
	uv lock --upgrade-package anicrop
	uv sync

# Sincroniza a documentação mais recente do anicrop para dentro do anifuse
sync-docs:
	@if [ -d "../anicrop/docs" ]; then \
		mkdir -p docs/anicrop && \
		cp -r ../anicrop/docs/* docs/anicrop/ && \
		echo "==> Documentação do anicrop atualizada com sucesso em docs/anicrop!"; \
	else \
		echo "Diretório ../anicrop/docs não encontrado."; \
	fi


# ==============================================================================
# Fluxo de Sincronização Git Multi-PC (dev <-> main)
# ==============================================================================

# Envia todas as alterações da branch dev para o GitHub
push-dev:
	@echo "==> Enviando branch dev para o GitHub..."
	git push origin dev

# Atualiza a branch dev a partir do GitHub (para rodar no outro PC)
pull-dev:
	@echo "==> Atualizando branch dev a partir do GitHub..."
	git pull origin dev

# Sincroniza apenas o código de produção da branch 'dev' para a 'main' (mantendo a main limpa e descritiva)
sync-main:
	@echo "==> Sincronizando código de produção com a branch main..."
	@CHANGES=$$(git log main..dev --oneline --no-merges --invert-grep --grep="docs(plano)" src/ tests/ | sed 's/^[a-f0-9]* /- /'); \
	if [ -z "$$CHANGES" ]; then \
		echo "Nenhuma alteração de produção para sincronizar."; \
	else \
		git checkout main && \
		git checkout dev -- src/ tests/ README.md pyproject.toml Makefile .gitignore .python-version uv.lock && \
		git commit -m "release: sincroniza código de produção da dev" -m "$$CHANGES" && \
		git checkout dev && \
		echo "==> Sincronização concluída! Retornado para a branch dev."; \
	fi

# Envia a branch main limpa para o GitHub
push-main:
	@echo "==> Enviando branch main para o GitHub..."
	git push origin main
