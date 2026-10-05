# Orquestrador Multiagente Orientado a Eventos com Servidores MCP Distribuídos

Ecossistema onde agentes especializados (Logística, Financeiro, RH) raciocinam
de forma independente, cada um consumindo seu próprio **servidor MCP remoto**
(HTTP/streamable-http), rodando em container isolado. Um **orquestrador**
construído com **LangGraph** coordena os agentes via grafo de estados,
publicando eventos em um **barramento Redis**, e é **tolerante a falhas**: se
um servidor MCP cair no meio do raciocínio, o circuito daquele domínio abre,
o agente degrada graciosamente, e o resto do sistema continua respondendo.

## Arquitetura

```
                        ┌──────────────┐
  cliente ──POST /query→│ orchestrator │──Redis Pub/Sub──→ GET /events (SSE)
                        │  (LangGraph) │
                        └───┬───┬───┬──┘
             supervisor ────┘   │   └──── fan-out (Send)
                                 │
         ┌───────────────┬──────┴───────┬───────────────┐
         │ agente         │ agente       │ agente         │
         │ Logística      │ Financeiro   │ RH             │
         │ (circuit       │ (circuit     │ (circuit       │
         │  breaker)      │  breaker)    │  breaker)      │
         └──────┬─────────┴──────┬───────┴──────┬─────────┘
                │ HTTP           │ HTTP          │ HTTP
         ┌──────┴──────┐  ┌──────┴──────┐ ┌──────┴──────┐
         │ mcp-logistics│  │ mcp-finance │ │   mcp-hr    │
         │  (container) │  │ (container) │ │ (container) │
         └──────────────┘  └─────────────┘ └─────────────┘
```

- **Desacoplamento**: cada domínio de negócio é um servidor MCP independente
  (`mcp-servers/{logistics,finance,hr}`), em seu próprio container, expondo
  tools via protocolo MCP padronizado sobre HTTP.
- **Barramento de eventos**: `orchestrator/app/event_bus/redis_bus.py` publica
  `AgentStarted`/`AgentCompleted`/`AgentFailed`/`ServiceDegraded`/`ServiceRecovered`
  no Redis; `GET /events` repassa esse stream via SSE.
- **Tolerância a falhas**: `orchestrator/app/mcp_client/resilience.py` implementa
  um circuit breaker (CLOSED → OPEN → HALF_OPEN) por domínio. Falhas consecutivas
  abrem o circuito (chamadas seguintes falham rápido, sem tentar conectar); depois
  de um timeout, uma tentativa de reconexão (half-open) fecha o circuito se bem-sucedida.
- **Estado distribuído**: o grafo LangGraph é persistido no Redis a cada superstep
  (`orchestrator/app/state/checkpointer.py`), permitindo retomar uma execução se o
  orchestrator reiniciar no meio de uma consulta.

## Stack

Python · Docker/Docker Compose · Redis · LangGraph · FastAPI · MCP SDK (`mcp`) · Claude (Anthropic)

## Como rodar

```bash
cp .env.example .env
# edite .env e preencha ANTHROPIC_API_KEY

docker compose up --build
```

Serviços: `redis` (6379), `mcp-logistics` (8001), `mcp-finance` (8002), `mcp-hr` (8003), `orchestrator` (8000).

Testar manualmente:

```bash
curl -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"text": "Verifique o pedido 103: estoque, pagamento e disponibilidade do responsável."}'
```

Acompanhar os eventos em tempo real:

```bash
curl -N localhost:8000/events
```

## Demo de tolerância a falhas

Com `docker compose up --build` rodando em um terminal, em outro:

```bash
python scripts/demo.py  # usa só a stdlib, nenhuma dependência extra
```

O script dispara uma consulta cross-domain, derruba `mcp-finance`
(`docker compose stop mcp-finance`), repete a consulta várias vezes — mostrando
a resposta do domínio financeiro degradar (retry → erro → circuito aberto →
resposta rápida "indisponível", enquanto logística e RH continuam respondendo
normalmente) — religa o container e mostra a recuperação automática do circuito.

## Dados de exemplo

Os 3 servidores MCP compartilham chaves mock para permitir consultas
cross-domain coerentes: pedidos `101`/`102`/`103`, cada um com um pagamento e
um funcionário responsável associados (ver `_ORDERS`/`_PAYMENTS`/`_EMPLOYEES`
em cada `server.py`).

## Estrutura

```
shared/mcp_shared/        eventos e DTOs compartilhados (Pydantic)
mcp-servers/{logistics,finance,hr}/   servidores MCP (FastMCP, streamable-http)
orchestrator/app/
  agents/                 supervisor, domain_agent (ReAct), aggregator, tool_specs
  mcp_client/             factory (sessão MCP por chamada) + circuit breaker/retry
  event_bus/              publish/subscribe de eventos via Redis
  state/                  checkpointer Redis do grafo LangGraph
  graph.py                grafo: supervisor → fan-out → agentes → aggregator
  main.py                 FastAPI: POST /query, GET /health, GET /events
scripts/demo.py           demo de consulta cross-domain + falha + recuperação
```
