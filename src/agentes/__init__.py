# src/agentes/__init__.py

"""
O módulo 'agentes' contém os componentes inteligentes e especializados do sistema.

Cada sub-módulo aqui representa um "agente" com uma responsabilidade específica
no pipeline de processamento de informação. Por exemplo:

- `Recepcionista`: Recebe e estrutura a entrada inicial.
- `ClassificadorMultimodal`: Determina o tipo e a complexidade do conteúdo.
- `FiltroSeguranca`: Verifica a presença de conteúdo malicioso.
- `Deconstructor`: Quebra o conteúdo em alegações verificáveis.
- `CacheSemantico`: Armazena e recupera análises anteriores.

O `CoordenadorAgentes` orquestra a interação entre esses agentes para executar
as fases iniciais da checagem de fatos.
"""
