# Fórmula LaTeX — extensão para Inkscape

Insere código LaTeX no Inkscape (1.0 ou mais recente, testado alvo 1.4+)
como um grupo de caminhos vetoriais totalmente editáveis, sem depender de
fontes instaladas. Usa o mesmo backend que o TexText usa por padrão:
`latex` → `.dvi` → `dvisvgm` → SVG.

Como o `dvisvgm` converte os glifos em *paths*, o resultado funciona mesmo
sem TexText instalado/funcionando, e pode ser editado como qualquer outro
desenho vetorial (Editar nós, Separar, etc.).

## Requisitos

- LaTeX no PATH do sistema (você já confirmou que tem: `latex`, `pdflatex`).
- `dvisvgm` no PATH (normalmente já incluído no TeX Live / MiKTeX / MacTeX).
- Pacotes LaTeX `standalone`, `preview`, `amsmath`, `amssymb` (padrão em
  qualquer instalação "completa" do TeX Live/MiKTeX/MacTeX).

Para conferir rapidamente no terminal:

```
latex --version
dvisvgm --version
```

Se `dvisvgm` não for encontrado, instale o pacote correspondente
(no TeX Live costuma se chamar `dvisvgm` no gerenciador de pacotes tlmgr,
ex.: `tlmgr install dvisvgm`).

## Instalação

Copie os dois arquivos (`latex_formula.inx` e `latex_formula.py`) para a
pasta de extensões de usuário do Inkscape:

- **Linux**: `~/.config/inkscape/extensions/`
- **macOS**: `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
- **Windows**: `%APPDATA%\Inkscape\extensions\`

Se não tiver certeza do caminho exato na sua máquina, abra o Inkscape e vá
em **Editar → Preferências → Sistema**, e veja o campo
"Extensões do usuário" (User extensions) — ele mostra o caminho exato e
tem um botão para abrir a pasta direto.

Depois de copiar os arquivos, reinicie o Inkscape.

No Linux/macOS, dê permissão de execução ao script (opcional, mas recomendado):

```
chmod +x latex_formula.py
```

## Uso

1. No Inkscape, vá em **Extensões → Texto → Fórmula LaTeX...**
2. Digite o código LaTeX (ex.: `x^2 + y^2 = z^2`, ou `\frac{a}{b}`, ou até
   texto normal com `\textbf{negrito}`).
3. Marque "Modo matemático" se quiser que o código seja envolto
   automaticamente em `\[ ... \]` (equivalente ao `$$ ... $$`). Desmarque
   se quiser controlar o modo você mesmo (por exemplo, para inserir texto
   comum ou uma equação com `align`).
4. Se precisar de pacotes extras (ex.: `\usepackage{mathtools}` ou
   `\usepackage{xcolor}`), coloque no campo de preâmbulo, um comando por
   linha.
5. Ajuste o tamanho de fonte base e a escala adicional se necessário.
6. Clique em **Aplicar**. O resultado aparece centralizado na página atual,
   como um grupo de caminhos.

## Limitações conhecidas

- **Não há edição "in-place"**: diferente do TexText, esta extensão não
  reabre um objeto já inserido para editar o código-fonte. O código LaTeX
  original fica salvo em atributos personalizados (`data-latex-code`,
  em Base64) dentro do grupo criado, apenas como referência — para
  alterar a fórmula, edite o código no diálogo e insira novamente,
  substituindo o objeto antigo.
- Erros de compilação do LaTeX são exibidos numa caixa de diálogo do
  Inkscape com o trecho relevante do log; erros de pacotes ausentes vão
  aparecer da mesma forma.
- Fórmulas muito grandes/complexas podem demorar alguns segundos para
  compilar, já que cada clique em Aplicar chama o `latex` e o `dvisvgm`
  do zero.

## Por que isso deve funcionar quando o TexText falha

O TexText depende de uma integração GUI (GTK) própria além do pipeline
LaTeX. Esta extensão evita essa camada extra: usa apenas os parâmetros
padrão de extensão do Inkscape (`.inx`) e chama `latex`/`dvisvgm`
diretamente por `subprocess`, então tende a ter muito menos pontos de
falha relacionados a bibliotecas gráficas, versões do GTK, etc.
