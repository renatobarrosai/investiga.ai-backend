# src/sintese/__init__.py

"""
O módulo 'sintese' é responsável pela fase final do processo de checagem,
onde as informações e evidências coletadas são consolidadas para gerar
uma resposta final.

Este pacote contém os seguintes componentes principais:

- `Sintetizador`: Analisa todas as evidências, resolve contradições e
  formula um veredito final (ex: VERDADEIRO, FALSO) com um raciocínio
  explicativo.
- `Apresentador`: Pega o resultado técnico do sintetizador e o formata
  em uma linguagem clara, objetiva e fácil de entender para o usuário final,
  incluindo elementos visuais e recomendações.
- `CoordenadorSintese`: Orquestra a interação entre o Sintetizador e o
  Apresentador para garantir que o fluxo da fase de síntese seja executado
  corretamente.
"""
