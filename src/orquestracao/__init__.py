# src/orquestracao/__init__.py

"""
O módulo 'orquestracao' implementa a camada de mais alto nível do sistema,
responsável por gerenciar o fluxo de ponta a ponta de forma resiliente e eficiente.

Esta camada lida com conceitos avançados, como:

- `CoordenadorOrquestracao`: O ponto de entrada principal que utiliza os outros
  componentes para executar uma requisição.
- `LangGraphOrchestrator`: Define e executa workflows de processamento
  adaptativos, permitindo que o fluxo mude com base nos dados.
- `LoadBalancer`: Distribui a carga de trabalho entre diferentes recursos
  (workers, GPUs) para otimizar o uso e evitar sobrecarga.
- `CacheMultiLayer`: Fornece um sistema de cache com múltiplos níveis
  (memória, disco) para acelerar respostas e reduzir processamento redundante.
- `MonitoringAvancado`: Coleta métricas de desempenho e dispara alertas,
  garantindo a saúde e a observabilidade do sistema.

Juntos, esses componentes formam uma infraestrutura robusta para a execução
confiável e escalável das tarefas de checagem de fatos.
"""
