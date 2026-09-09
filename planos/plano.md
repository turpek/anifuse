# Master Plan: Anifuse

Este documento centraliza todos os objetivos arquiteturais, otimizações e o progresso estrutural do desenvolvimento do motor de reconstrução panorâmica de cenas de animes (`anifuse`).

---

## 📋 Lista de Tarefas (Status Atual)

- [x] 1. Configuração e thresholds globais (`Config`: rotate, scale, translation, `fast_threshold`).
- [x] 2. Subsistema de máscaras sem cópia (`MaskView`: Default, Static, Sequence, Dynamic, Composite).
- [x] 3. Estimadores de movimento e rotação via ORB e MODA (`OrbTranslationEstimator`, `OrbTransformEstimator`, `OrbScaleEstimator`, `OrbRotationEstimator`).
- [x] 4. Políticas de busca de janelas ativas (`Section`, `CrossSections`, `AdaptiveViewPolicy`).
- [x] 5. Handlers de transformação geométrica em camadas do anicrop (`RotationHandler`, `ScaleHandler`, `TranslationHandler`, `HorizontalTranslationHandler`, `VerticalTranslationHandler`).
- [x] 6. Subsistema de leitura de imagens (`PathResolver`, `ReadStrategy`, `ImageSequenceReader`).
- [x] 7. Orquestrador de costura e composição de cena (`SceneStitcher`, `FrameAccumulator`, `StackOrder`).
- [ ] 8. Subsistema de leitura de vídeo (integração com primitivas do `GPlayer`).
- [ ] 9. Benchmarks de estresse, testes de ponta a ponta e documentação técnica.
- [ ] 10. **Bugfix no `BorderCutEffect`:** Investigar e corrigir corte indevido da camada de baixo na versão `top1` (`StackOrder.FIRST_ON_TOP`).


---

## 🏗 Detalhamento Arquitetural

---

### Task 6: Subsistema de I/O de Alta Performance (Imagens & Primitivas do GPlayer)

#### 1. Visão Geral e Motivação
A etapa de I/O e decodificação de frames não pode ser um gargalo síncrono no pipeline de stitching. Enquanto o alinhador ORB e o motor gráfico `anicrop` realizam a correlação e o *single-pass flattening* da cena, o próximo conjunto de frames já deve estar pré-carregado na memória via buffers assíncronos. Além disso, sequências de animes demandam frequentemente:
- **Navegação Bidirecional:** Capacidade de ler tanto em ordem natural (*forward*) quanto em ordem reversa (*rewind*).
- **Recorte Temporal e Stride:** Capacidade de fatiar intervalos específicos (`start`, `end`, `step`) pulando quadros desnecessários de forma ultrarrápida.
- **Formato Padronizado:** Entrega direta de instâncias de `anicrop.image.Image` com suporte a `ImageFormat.RGBA` prontas para composição.

---

#### 2. Integração do `GPlayer` (Estilo `anicrop`)
Assim como o `anicrop` é gerenciado como dependência do motor, o `GPlayer` será integrado no `pyproject.toml` via `uv`:

```toml
[project]
dependencies = [
    "anicrop",
    "gplayer",
    ...
]

[tool.uv.sources]
anicrop = { git = "https://github.com/turpek/anicrop.git", branch = "main" }
gplayer = { git = "https://github.com/turpek/GPlayer.git", branch = "main" }
```

---

#### 3. Uso Exclusivo das Primitivas Nucleares do GPlayer (Modo Headless)
Em vez de instanciar a fachada de exibição `VideoCon` (que abre janelas do OpenCV e escuta eventos de teclado), o `anifuse` consumirá diretamente as **duas primitivas assíncronas unidirecionais**:

- **`VideoBufferRight` (Forward):** Utilizado quando `reverse=False`. Lê frames para a frente alimentando a thread de leitura assíncrona.
- **`VideoBufferLeft` (Rewind):** Utilizado quando `reverse=True`. Lê frames em ordem reversa sem a degradação de seeks manuais.
- **`FrameMapper`:** Mapeia `range(start, end, step)`. Frames fora do mapeamento sofrem apenas `cap.grab()` (avanço do codec sem decodificação pesada de pixels), acelerando exponencialmente o processamento.

---

#### 4. Estrutura de Classes e Contratos de I/O

```text
src/anifuse/
├── io.py                 # Interface FrameReader, ImageSequenceReader e VideoReader
```

##### A. Contrato Unificado: `Frame` e `FrameReader`
```python
@dataclass(frozen=True)
class Frame:
    idx: int                    # Índice real do frame no vídeo/origem
    image: Image                # anicrop.image.Image (RGBA)
    timestamp: float = 0.0      # Timestamp em segundos (PTS)


class FrameReader(ABC):
    """Protocolo base para leitura assíncrona de sequências de frames."""

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]:
        """Itera sobre a sequência de frames pré-carregados."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Quantidade total de frames esperados."""
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Encerra threads de buffer e libera descritores de arquivo."""
        pass
```

##### B. `ImageSequenceReader`
- Suporta lista explícita de `Path`, diretório de imagens ou padrões glob (`"scenes/*.png"`).
- Suporta `reverse: bool = False`, fatiamento `[start:end:step]`.
- Implementa fila `queue.Queue` concorrente para pré-carregamento em background com `buffer_size` configurável.

##### C. `VideoReader` (GPlayer Adapter)
- Recebe o caminho do arquivo de vídeo (`.mkv`, `.mp4`, etc.).
- Instancia `cv2.VideoCapture`, `FrameMapper` e seleciona dinamicamente `VideoBufferRight` ou `VideoBufferLeft`.
- Converte os arrays lidos diretamente para `Image(arr, ImageFormat.RGBA)`.
- Libera a thread e o handle do vídeo ao chamar `close()` ou no bloco `with`.

---

### Task 7: Orquestrador de Costura e Acumuladores de Composição (`SceneStitcher`)

#### 1. Decisões Arquiteturais e Padrões de Projeto
- **Injeção Explícita de Dependências:** O construtor `SceneStitcher.__init__` exige explicitamente `handlers: list[TransformHandler]` e `view_policy: ViewPolicy`, eliminando dependências ocultas e acoplamentos rígidos.
- **Factory de Conveniência (`from_default`):** Fornece o caso de uso padrão montando `AdaptiveViewPolicy(OrbTransformEstimator())` com `[TranslationHandler()]` e `StackOrder.BOTH`.
- **Estratégias de Acumulação (`FrameAccumulator`):**
  - `FirstOnTopAccumulator`: Canvas acumulado no topo (`flatten([incoming, base])`), preservando a pose e composição do primeiro frame.
  - `LastOnTopAccumulator`: Novo frame no topo (`flatten([base, incoming])`), priorizando o desfecho da cena.
  - `DualAccumulator`: Gera ambas as composições concorrentemente com custo computacional extra mínimo (apenas um segundo `flatten`).
- **Aproveitamento Direto de `ready_frame`:** O buffer já transformado/rotacionado pelo estimador é encapsulado em `anicrop.image.Image(ready_frame, frame.image.format)` e injetado na camada sem interpolações redundantes.
- **Caso de 1 Frame Delegado:** Zero condicionais no fluxo de `stitch()`; se a sequência contém apenas 1 frame, o laço de alinhamento não roda e o acumulador retorna a imagem diretamente.

---

### Task 10: Bugfix no `BorderCutEffect` (Camada de Baixo Apagada na Versão `top1`)

#### 1. Relato do Problema
* Ao processar composições com `StackOrder.FIRST_ON_TOP` (ou na saída `top1` do `DualAccumulator`), o `BorderCutEffect` está cortando indevidamente a camada de baixo.
* O efeito foi projetado para atuar estritamente na borda da sobreposição da camada do topo a fim de revelar a base intacta, mas na inversão hierárquica do `first-on-top`, o corte está afetando a visibilidade da camada inferior.

#### 2. Escopo da Investigação Futura
- [ ] Reproduzir o bug em teste unitário dedicado com `StackOrder.FIRST_ON_TOP`.
- [ ] Analisar o ciclo de vida dos efeitos no `FirstOnTopAccumulator` e no `DualAccumulator` (`top` vs `bottom` referencial).
- [ ] Verificar a interação entre `LayerTarget.TOP` e a ordem das camadas no `apply_effects` e no `flatten`.
- [ ] Garantir que a camada inferior permaneça 100% preservada em qualquer direção de empilhamento.


