# Master Plan: Anifuse

Este documento centraliza todos os objetivos arquiteturais, otimizações e o progresso estrutural do desenvolvimento do motor de reconstrução panorâmica de cenas de animes (`anifuse`).

---

## 📋 Lista de Tarefas (Status Atual)

- [x] 1. Configuração e thresholds globais (`Config`).
- [x] 2. Subsistema de máscaras sem cópia (`MaskView`: Default, Static, Sequence, Dynamic, Composite).
- [x] 3. Estimadores de movimento e rotação via ORB e MODA (`OrbTranslationEstimator`, `OrbTransformEstimator`).
- [x] 4. Políticas de busca de janelas ativas (`Section`, `CrossSections`, `AdaptiveViewPolicy`).
- [x] 5. Handlers de transformação geométrica em camadas do anicrop (`RotationHandler`, `ScaleHandler`, `TranslationHandler`).
- [x] 6. Subsistema de leitura de imagens (`PathResolver`, `ReadStrategy`, `ImageSequenceReader`).
- [ ] 7. Orquestrador de costura e composição de cena (`SceneStitcher` integrado ao `anicrop`).
- [ ] 8. Subsistema de leitura de vídeo (integração com primitivas do `GPlayer`).
- [ ] 9. Benchmarks de estresse, testes de ponta a ponta e documentação técnica.


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
