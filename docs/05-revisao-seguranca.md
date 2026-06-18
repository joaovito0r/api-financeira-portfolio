# Revisão de Segurança — 2026-06-17

Auditoria de segurança da API, com a aplicação rodando e testada de ponta a ponta.

## Resumo

| Área | Status |
|------|--------|
| Multi-tenancy (isolamento por usuário) | ✅ Seguro |
| SQL injection | ✅ Não explorável (ORM parametrizado) |
| Injeção na URL externa (brapi) via ticker | ✅ Corrigido nesta revisão |
| Autenticação / JWT | ✅ Sólido |
| Hash de senha | ✅ Argon2 |
| Prompt injection | ✅ N/A (não há LLM no sistema) |
| Vazamento de existência de recursos | ✅ 404 (não 403) |

## Multi-tenancy

**Toda** operação sobre recursos de usuário filtra por `user_id`:

- `watchlist_service`: `rename`, `delete`, `list_items`, `add_item`, `remove_item`
  validam a posse da watchlist (`WatchlistModel.user_id == user_id`) **antes** de
  qualquer alteração — inclusive operações sobre itens aninhados.
- `alert_service`: idem para todas as operações de alerta.

Verificado ao vivo: o usuário B recebe **404** ao tentar ler/alterar/apagar
watchlists e alertas do usuário A por ID, e não os vê em listagens. O uso de 404
(em vez de 403) evita revelar a existência do recurso.

## SQL injection

Todas as queries usam SQLAlchemy ORM com parâmetros vinculados (`==`). Teste com
ticker `'; DROP TABLE users;--` confirmou que o valor entra como **bound
parameter** (`?`), nunca interpolado. Não há `text()`, f-strings ou concatenação
em SQL.

## Injeção na requisição externa via `ticker` (corrigido)

**Problema:** o `ticker` vinha de path/query sem validação, recebia `.upper()` e
era interpolado direto na URL do brapi (`/api/quote/{ticker}`). Entradas como
`PETR4?foo=bar` poluíam o cache e podiam manipular a requisição externa.

**Correção:** validador central `app/core/validation.py::normalize_ticker`
(regex `^[A-Z0-9]{1,10}$`), aplicado:
- na dependência de rota `deps.py::valid_ticker` (**antes do cache** e de qualquer
  chamada externa) — usada em todas as rotas de cotação, histórico, dividendos,
  fundamentalistas, relatório e comparação;
- nos pontos que **persistem** ticker sem passar pelo brapi (criar alerta,
  `add_item`);
- como defesa em profundidade no próprio `BrapiClient`.

Entradas inválidas agora retornam **422** antes de tocar cache/banco/brapi.

## Autenticação / JWT

- Algoritmo fixado em `HS256` no decode (`algorithms=[ALGORITHM]`) — bloqueia
  ataque de `alg=none`.
- `get_current_user` faz **lookup no banco** pelo `sub` do token; usuário
  inexistente/deletado → token inválido.
- `secret_key` vazia agora gera chave aleatória efêmera fora de produção
  (`@model_validator`), e `check_production_ready()` falha cedo em produção
  (rodando no `lifespan`).
- Senhas com **Argon2** (vencedor do PHC), via `passlib`.

## Não vazamento de dados sensíveis no corpo da resposta

Auditadas todas as respostas (registro, login, `/auth/me`, watchlists, alertas,
cotação, relatório, fundamentalistas, erros):

- **`password_hash` nunca é serializado.** `UserResponse` expõe só
  `id`, `name`, `email`, `created_at`; os dicts dos serviços idem.
- **O valor da senha não é ecoado em erros 422.** O handler customizado de
  `RequestValidationError` (`main.py`) descarta o campo `input` que o Pydantic
  inclui por padrão — retorna apenas `campo` + `mensagem`.
- **`access_token` aparece apenas** em `/auth/register` e `/auth/login` (artefato
  de autenticação esperado). Nenhuma outra rota o devolve.

Travado por regressão em `tests/test_security.py`
(`test_respostas_nao_vazam_hash_de_senha`,
`test_erro_validacao_nao_ecoa_valor_da_senha`,
`test_token_so_aparece_em_login_e_registro`).

> Nota (logs, não corpo): com `settings.debug=True` (dev) o SQLAlchemy faz `echo`
> e registra o `password_hash` nos logs de INSERT. Em produção `debug=False`
> desliga o echo. Não afeta o corpo das respostas HTTP.

## Prompt injection

Não aplicável: o sistema **não usa LLM** nem envia dados do usuário para nenhum
modelo de linguagem. A única integração externa é o brapi.dev (dados de mercado),
já protegida pela validação de ticker acima.

## Recomendações futuras (não bloqueantes)

1. **OpenAPI sem `securityScheme`**: a auth usa um `Header` custom, então o Swagger
   não mostra o cadeado nem o botão "Authorize" (a checagem em runtime funciona).
   Migrar para `HTTPBearer` melhoraria a doc e a DX.
2. **Rate limiting**: não há limite por IP/usuário. Considerar `slowapi` para
   produção.
3. **XSS no frontend**: a API responde JSON (sem risco), mas campos livres como
   `notes` e `name` de watchlist devem ser escapados ao renderizar no dashboard.
4. **CORS**: ok enquanto o front é servido na mesma origem via `/static`.
5. `compare.py` ainda faz chamadas sequenciais por ticker (performance, não
   segurança).
