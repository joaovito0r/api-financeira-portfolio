# Design — Exclusão de conta com janela de recuperação ("soft delete")

**Data:** 2026-06-21
**Projeto:** financial_api (FastAPI + SQLAlchemy async + httpx → brapi.dev)
**Status:** Aprovado no brainstorming; pronto para o plano de implementação.

## Contexto e motivação

O CRUD de conta (`/auth/*`) hoje cobre registro, login, consulta, atualização de nome e troca
de senha — mas não há como o usuário **excluir a própria conta**. Exclusão definitiva e
imediata é arriscada (clique acidental, mudança de ideia) e irreversível. A decisão de produto,
tomada no brainstorming, é um **soft delete com janela de recuperação de 30 dias**: a conta
fica desativada (sem acesso) durante a janela; se o usuário voltar e logar com sucesso dentro
desse período, a conta é reativada automaticamente; se a janela expirar sem retorno, a conta e
todos os dados associados são apagados permanentemente por um job de background.

O projeto **não tem infraestrutura de envio de email**, então a recuperação não pode depender de
link por email — o próprio fluxo de login é o mecanismo de recuperação.

### Defeito latente encontrado durante a investigação

`AlertModel` e `PortfolioPositionModel` declaram `ForeignKey("users.id", ondelete="CASCADE")`,
mas isso só é de fato aplicado pelo Postgres (produção); o SQLite (dev) não aplica regras de FK
por padrão e o projeto não liga essa pragma. Hoje isso é inofensivo porque nada apaga um
`UserModel`. A exclusão permanente desta feature passaria a depender desse comportamento, então
o desenho corrige isso no nível do ORM (ver Seção 1) em vez de depender de uma pragma de SQLite
que mudaria comportamento global do banco.

## Decisões tomadas no brainstorming

| Tema | Decisão |
|------|---------|
| Duração da janela de recuperação | 30 dias |
| Mecanismo de recuperação | Reativação automática no login (sem fluxo/tela separada) |
| Confirmação na exclusão | Modal de confirmação (`showConfirm`, padrão já usado no app) **+** senha atual obrigatória |
| Acesso durante a janela | Bloqueado — todo token (mesmo emitido antes da exclusão) passa a ser rejeitado |
| Apagamento definitivo | Job de background (mesmo padrão de `warm_cache_loop`), não cron externo |

## Seção 1 — Modelo de dados

- **Migração Alembic:** nova coluna `users.deleted_at` (`DateTime`, nullable, sem default).
  `NULL` = conta ativa; preenchida = em limbo desde aquele instante (UTC).
- **`UserModel` ganha duas relações novas**, no mesmo padrão que `watchlists` já usa:
  ```python
  alerts: Mapped[list[AlertModel]] = relationship(cascade="all, delete-orphan")
  portfolio_positions: Mapped[list[PortfolioPositionModel]] = relationship(cascade="all, delete-orphan")
  ```
  Isso garante que `session.delete(user)` cascateia para alertas e posições da carteira via
  ORM, independente de pragma do SQLite — corrige o defeito latente descrito acima sem mudar
  comportamento do banco fora do caminho de exclusão de usuário.
- **`config.py`:** novo setting `account_deletion_grace_days: int = 30` (a janela é
  configurável, não hardcoded, seguindo o padrão dos demais limites do projeto).

## Seção 2 — Exclusão (`DELETE /auth/me`)

- Novo schema `AccountDeletion(BaseModel)`: campo único `password: str`.
- Novo endpoint `DELETE /auth/me`, autenticado (`Depends(rate_limit_user)`, mesmo padrão de
  `change_password`/`update_me`).
- `AuthService.request_deletion(user_id, password)`:
  - Busca o usuário; 404 (`ValueError`) se não existir.
  - Se `deleted_at` já estiver setado → erro (`ValueError`, "Conta já está marcada para
    exclusão") — evita reset acidental da data ao chamar o endpoint duas vezes.
  - Revalida a senha atual (`verify_password`, mesmo padrão de `change_password`); senha errada
    → `ValueError` → 400.
  - Seta `user.deleted_at = datetime.now(timezone.utc)`, commit.
  - Retorna a data-limite (`deleted_at + account_deletion_grace_days`) para o frontend exibir.
- **Não apaga nenhum dado nesse momento** — só marca.

## Seção 3 — Bloqueio de acesso durante o limbo

- `AuthService.get_current_user(token)` (chamado por `deps.get_current_user`, usado em toda
  rota autenticada) passa a checar `user.deleted_at`: se não for `None`, levanta `ValueError`
  → 401. Mensagem: "Conta desativada. Faça login novamente para reativar ou aguarde a exclusão
  definitiva."
- Efeito prático: a partir do clique em excluir, **nenhum token continua funcionando** — nem o
  que está em uso no navegador atual — forçando relogin (que é o próprio mecanismo de
  recuperação, Seção 4).
- `register()` não muda: tentar registrar com o mesmo email de uma conta em limbo continua
  caindo no "Email já cadastrado" (linha already existente) — o usuário deve logar para
  recuperar, não criar conta nova.

## Seção 4 — Reativação automática no login

- `AuthService.login(email, password)`: após validar a senha com sucesso, se
  `user.deleted_at is not None`:
  - Zera `user.deleted_at = None`, commit.
  - Resposta de login ganha campo `"reactivated": true` (ausente/`false` no caminho normal).
- Frontend (`login.html`) lê esse campo e mostra um toast "Sua conta foi reativada com
  sucesso!" antes do redirect normal pro dashboard.
- Não há corrida problemática com o purge (Seção 5): o purge só processa contas com
  `deleted_at` ainda setado no momento em que ele roda; se o login zerou `deleted_at` primeiro,
  a conta já não é mais candidata.

## Seção 5 — Purge definitivo (background loop)

- Novo módulo `app/core/account_purge.py`, mesmo padrão de `app/core/warm_cache.py`:
  - `async def purge_expired_accounts() -> int`: busca usuários com
    `deleted_at <= now(UTC) - timedelta(days=settings.account_deletion_grace_days)`, usando
    `selectinload` nas relações (`watchlists.items`, `alerts`, `portfolio_positions`) para
    evitar lazy-load fora de contexto async. Para cada um, `await session.delete(user)`
    (cascata via Seção 1) e commit. Retorna a quantidade apagada (para log).
  - `async def purge_expired_accounts_loop() -> None`: `while True: try/except
    CancelledError: raise / except Exception: log.exception` (loop não pode morrer por erro
    pontual) `finally: asyncio.sleep(intervalo)`. Intervalo fixo de 1h (constante de módulo,
    não precisa ser configurável — não é sensível a quota de API externa como o warm cache).
- `main.py::lifespan`: inicia a task no startup e cancela no shutdown, no mesmo padrão de
  `warm_task`/`warm_cache_loop`.

## Seção 6 — Frontend (`perfil.html`)

- Nova seção "Danger Zone" (visualmente distinta, abaixo de "Sair da conta"), com botão
  "Excluir Conta".
- Fluxo do clique:
  1. `showConfirm()` (`danger: true`) explicando a janela de 30 dias e que logar de novo
     dentro desse período reativa a conta automaticamente.
  2. Se confirmado, `showPrompt()` pedindo a senha atual.
  3. `DELETE /auth/me` com a senha.
  4. Sucesso → `showToast` com a data-limite devolvida pela API → remove o token do
     `localStorage` → redirect pro login.
  5. Falha (senha errada) → `showAlert` com a mensagem de erro, sem fechar a sessão.
- **`api.js::showPrompt`** ganha um 4º parâmetro opcional `type = 'text'`; quando `'password'`,
  o `<input>` renderizado usa `type="password"` (máscara). Assinatura atual permanece
  compatível — nenhuma chamada existente (`editarPerfil`, `alterarSenha`, etc.) muda
  comportamento, pois todas continuam usando o default.

## Seção 7 — Testes

`tests/test_account_deletion.py`:

- Senha errada em `DELETE /auth/me` → 400, `deleted_at` permanece `None`.
- Senha certa → `deleted_at` setado, resposta traz data-limite.
- Chamar `DELETE /auth/me` de novo numa conta já em limbo → erro (não reseta a data).
- Token emitido antes da exclusão → 401 em qualquer rota autenticada após a exclusão.
- Login com sucesso dentro da janela → `deleted_at` volta a `None`, resposta traz
  `"reactivated": true`, token novo funciona normalmente nas rotas protegidas.
- `purge_expired_accounts()`: conta com `deleted_at` antigo (> janela) é removida junto com
  suas watchlists/items, alerts e portfolio_positions (cascata); conta com `deleted_at` recente
  (dentro da janela) não é tocada; conta ativa (`deleted_at is None`) não é tocada.

Mantém o padrão do projeto: ruff 0, mypy strict 0, suíte completa verde.

## Limitações conhecidas (assumidas nesta versão)

- Sem notificação por email em nenhuma etapa (exclusão, aviso de prazo próximo, confirmação de
  purge) — consistente com o projeto não ter infraestrutura de envio de email hoje.
- O purge roda a cada 1h; uma conta pode ficar até ~1h além dos 30 dias exatos antes de ser
  apagada. Aceitável para este caso de uso.
- Reativação é automática e silenciosa no login — não há tela dedicada de "sua conta será
  excluída em N dias, quer cancelar?" antes do usuário tentar logar.

## Fora de escopo

- Notificações por email em qualquer etapa do fluxo.
- Exportação de dados antes da exclusão ("baixe seus dados").
- Painel administrativo para listar/gerenciar contas em limbo.
- Auditoria/log persistente de exclusões (fica só no log da aplicação).
