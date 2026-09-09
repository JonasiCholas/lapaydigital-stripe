# Price IDs Configurados

Os seguintes produtos foram criados no Stripe e já estão configurados no `static/index.html`:

## Produtos Disponíveis

| Produto | Price ID | Valor | Status |
|---------|----------|-------|--------|
| **Ingresso — Show de Verão 2025** | `price_1UDoXVRSZgxEHq038Lmg9Drf` | R$ 150,00 | ✅ Ativo |
| **Workshop de Fotografia** | `price_1UDoXWRSZgxEHq03z8iDrTAR` | R$ 299,00 | ✅ Ativo |
| **Festival de Música — VIP** | `price_1UDoXWRSZgxEHq033619nkTx` | R$ 450,00 | ✅ Ativo |

## Para Adicionar Novos Produtos

1. **Via Dashboard Stripe:**
   - Acesse https://dashboard.stripe.com/test/products
   - Clique em `+ Add product`
   - Preencha os dados e salve
   - Copie o Price ID (começa com `price_`)

2. **Via Script Python:**
   - Modifique `DEMO_PRODUCTS` em `setup_stripe.py`
   - Execute: `uv run python setup_stripe.py`

## Para Atualizar o HTML

Edite `static/index.html` - seção `PRODUCTS`:

```javascript
const PRODUCTS = [
  {
    id: 'price_1UDoXVRSZgxEHq038Lmg9Drf',  // ← Seu price_id aqui
    title: 'Nome do Produto',
    description: 'Descrição',
    price: 'R$ XXX,00',
    type: 'event',  // 'event', 'show', ou 'prod'
    emoji: '🎤',
  },
  // ... outros produtos
];
```

## Teste de Pagamento

1. Acesse http://localhost:8000
2. Clique em "Comprar agora"
3. Use PIX ou cartão de teste:
   - Cartão: `4242 4242 4242 4242`
   - Data: qualquer futura
   - CVC: qualquer código

---

**Criado:** 2025-09-09  
**Stripe Account:** acct_1UDUCPRSZgxEHq03
