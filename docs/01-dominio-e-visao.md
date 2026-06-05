# Etapa 1: Domínio e Visão do Projeto

## 🎯 Visão Geral

**API Financeira para Portfólio** — Uma API REST que consome dados da brapi.dev,
armazena em banco local com cache inteligente, e expõe dados financeiros
estruturados do mercado brasileiro (B3) para consulta e análise de portfólio.

### Problema que resolve

Serviços financeiros brasileiros são caros, fragmentados ou mal documentados.
A brapi.dev oferece uma base sólida, mas sem cache, sem persistência e com
limitações no plano gratuito. Esta API adiciona:

- **Cache e persistência** — Evita bater na brapi.dev repetidamente pelos mesmos dados
- **Histórico próprio** — Acumula dados ao longo do tempo mesmo no plano gratuito
- **Camada de abstração** — Se no futuro trocar de fonte, a interface continua a mesma
- **Dados servidos com performance** — Banco local é mais rápido que API externa

### Usuários-alvo

- Investidores pessoa física que querem uma API própria
- Pequenos sistemas de acompanhamento de carteira
- Dashboards e visualizações de dados financeiros

## 🧩 Entidades do Domínio

```
Ativo (Asset)
  ├── Cotação (Quote)
  ├── Preço Histórico (OHLCV)
  ├── Provento (Dividend)
  ├── Perfil (CompanyProfile)
  ├── Balanço Patrimonial (BalanceSheet)
  ├── DRE (IncomeStatement)
  ├── Indicadores (FinancialIndicator)
  └── Estatísticas-Chave (KeyStatistic)
```

### 1. Ativo (Asset)
Entidade central. Todo dado financeiro gira em torno de um ativo.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | Identificador único (ex: PETR4) |
| name | string | Nome do ativo |
| type | enum | stock, fund, etf, bdr, index |
| sector | string | Setor de atuação |
| logo | url | Link do logo |

### 2. Cotação (Quote)
Snapshot do preço em tempo real.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| timestamp | datetime | Hora da última atualização |
| price | decimal | Preço atual |
| change | decimal | Variação absoluta |
| changePercent | decimal | Variação percentual |
| dayHigh | decimal | Máxima do dia |
| dayLow | decimal | Mínima do dia |
| volume | integer | Volume financeiro |
| open | decimal | Abertura do dia |
| previousClose | decimal | Fechamento anterior |
| marketCap | decimal | Valor de mercado |

### 3. Preço Histórico (OHLCV)
Série temporal para gráficos de candle.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| date | date | Data do pregão |
| open | decimal | Abertura |
| high | decimal | Máxima |
| low | decimal | Mínima |
| close | decimal | Fechamento |
| volume | integer | Volume |

### 4. Provento (Dividend)
Distribuição de lucros aos acionistas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| date | date | Data do pagamento |
| value | decimal | Valor por cota |
| type | enum | DIVIDENDO, JCP, BONIFICACAO |
| referenceDate | date | Data base |

### 5. Perfil da Empresa (CompanyProfile)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| address | string | Endereço |
| city | string | Cidade |
| state | string | Estado |
| country | string | País |
| website | string | Site oficial |
| industry | string | Setor de atuação |
| sector | string | Segmento |
| description | text | Descrição do negócio |
| employees | integer | Número de funcionários |

### 6. Balanço Patrimonial (BalanceSheet)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| endDate | date | Data do balanço |
| totalAssets | decimal | Ativo total |
| currentAssets | decimal | Ativo circulante |
| currentLiabilities | decimal | Passivo circulante |
| shareholderEquity | decimal | Patrimônio líquido |
| longTermDebt | decimal | Dívida de longo prazo |
| cash | decimal | Caixa e equivalentes |

### 7. DRE (IncomeStatement)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| endDate | date | Data da demonstração |
| totalRevenue | decimal | Receita líquida |
| costOfRevenue | decimal | Custo dos produtos |
| grossProfit | decimal | Lucro bruto |
| operatingIncome | decimal | Resultado operacional |
| netIncome | decimal | Lucro líquido |
| ebitda | decimal | EBITDA |

### 8. Indicadores Financeiros (FinancialIndicator)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| currentPrice | decimal | Preço atual |
| targetPrice | decimal | Preço-alvo médio |
| recommendation | enum | buy, hold, sell |
| grossMargin | decimal | Margem bruta |
| operatingMargin | decimal | Margem operacional |
| profitMargin | decimal | Margem líquida |
| roe | decimal | ROE |
| roa | decimal | ROA |
| revenueGrowth | decimal | Crescimento da receita |
| earningsGrowth | decimal | Crescimento do lucro |
| debtToEquity | decimal | Dívida/PL |

### 9. Estatísticas-Chave (KeyStatistic)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ticker | string | FK → Asset |
| priceToBook | decimal | P/VP |
| forwardPE | decimal | P/L futuro |
| trailingPE | decimal | P/L corrente |
| enterpriseValue | decimal | Enterprise Value |
| evToEbitda | decimal | EV/EBITDA |
| evToRevenue | decimal | EV/Receita |
| beta | decimal | Beta do ativo |
| dividendYield | decimal | Dividend Yield |
| bookValue | decimal | VPA |
| earningsPerShare | decimal | LPA |
| weekHigh52 | decimal | Máxima 52 semanas |
| weekLow52 | decimal | Mínima 52 semanas |

## 📏 Regras de Negócio

1. **Identidade única**: Todo ativo é identificado pelo ticker (maiúsculo, sem espaços)
2. **Classificação**: Obrigatório classificar o tipo do ativo (stock/fund/etf/bdr/index)
3. **Data única por ticker**: Não pode existir duas cotações OHLCV para o mesmo ticker + data
4. **Cache-first**: Ao consultar um dado, verificar banco local antes de chamar brapi.dev
5. **Histórico acumulativo**: Dados históricos baixados são armazenados e nunca sobrescritos sem confirmação
6. **Rate limit awareness**: Respeitar limites da brapi.dev (plano gratuito: 1 ticker/req)
7. **Proventos por ano**: Um ativo pode ter múltiplos proventos no mesmo ano
8. **Dados fundamentalistas**: BP e DRE são anuais, atrelados ao endDate

## 🔄 Fluxo da Aplicação (MVP)

```
Cliente → [API REST] → [Cache/Banco Local] → [brapi.dev]
                ↓
         Resposta JSON
```

1. Cliente faz requisição GET para a API
2. API verifica se o dado está no banco local (cache válido)
3. Se sim → retorna direto (mais rápido)
4. Se não → busca na brapi.dev, salva no banco, retorna
5. Dados históricos são acumulados progressivamente

## 🚫 Fora do Escopo (MVP)

- Autenticação de usuários
- Múltiplos usuários/carteiras
- Ordens de compra/venda
- Dados em tempo real via WebSocket
- Frontend ou dashboard

## 📝 Notas

- Dados fundamentalistas (BP, DRE) da brapi.dev gratuita são anuais
- Para mais ativos por requisição, upgrade futuro para plano Startup (R$49,99/mês)
- Campos em inglês seguem nomenclatura da brapi.dev; API pode expor em português se desejado
