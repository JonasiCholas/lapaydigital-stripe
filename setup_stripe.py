"""
Script de setup: verifica a conta Stripe e cria produtos de demonstracao para Lapay Digital.
Execucao: .venv\Scripts\python setup_stripe.py
"""
import stripe
import json

stripe.api_key = "sk_test_51UDUCPRSZgxEHq03Di0rhmmvC2rhURliKTDBngu5sXzkwVElPoZruj9wIemiqsqa5edWVDWSfsNm2yGtRMn8wlKr00L0PoIav2"

print("=" * 60)
print("Lapay Digital — Stripe Setup")
print("=" * 60)

# 1. Verificar conta
print("\n[1] Verificando conta Stripe...")
account = stripe.Account.retrieve()
print(f"    Conta: {account.id}")
print(f"    Email: {account.get('email', 'N/A')}")
print(f"    País: {account.get('country', 'N/A')}")
print(f"    Moeda padrão: {account.get('default_currency', 'N/A')}")

# 2. Verificar metodos de pagamento existentes
print("\n[2] Verificando Payment Method Configurations...")
try:
    configs = stripe.PaymentMethodConfiguration.list(limit=3)
    if configs.data:
        for c in configs.data:
            print(f"    Config: {c.id} — ativo: {c.active}")
    else:
        print("    Nenhuma configuracao extra. Usando default.")
except Exception as e:
    print(f"    {e}")

# 3. Verificar produtos existentes
print("\n[3] Produtos existentes na conta...")
products = stripe.Product.list(limit=10, active=True)
existing_names = [p.name for p in products.data]
if products.data:
    for p in products.data:
        prices = stripe.Price.list(product=p.id, active=True, limit=1)
        price_str = ""
        if prices.data:
            pr = prices.data[0]
            price_str = f" — R$ {pr.unit_amount/100:.2f}" if pr.unit_amount else ""
        print(f"    [{p.id}] {p.name}{price_str}")
else:
    print("    Nenhum produto encontrado.")

# 4. Criar produtos de demonstracao (se nao existirem)
print("\n[4] Criando produtos de demonstracao...")

DEMO_PRODUCTS = [
    {
        "name": "Ingresso — Show de Verao 2025",
        "description": "Acesso ao show em 15/01/2025, Setor Pista. Portoes abrem as 19h.",
        "price": 15000,  # R$ 150,00
        "metadata": {"type": "ticket", "event": "show-verao-2025"},
    },
    {
        "name": "Workshop de Fotografia",
        "description": "Inscricao para workshop presencial. Inclui material didatico e certificado.",
        "price": 29900,  # R$ 299,00
        "metadata": {"type": "ticket", "event": "workshop-foto"},
    },
    {
        "name": "Festival de Musica — VIP",
        "description": "Ingresso VIP — Area exclusiva, open bar e acesso ao backstage.",
        "price": 45000,  # R$ 450,00
        "metadata": {"type": "ticket", "event": "festival-musica"},
    },
]

created = []
for demo in DEMO_PRODUCTS:
    if demo["name"] in existing_names:
        print(f"    SKIP (ja existe): {demo['name']}")
        # Buscar price_id existente
        existing = next(p for p in products.data if p.name == demo["name"])
        prices = stripe.Price.list(product=existing.id, active=True, limit=1)
        if prices.data:
            created.append({
                "name": demo["name"],
                "product_id": existing.id,
                "price_id": prices.data[0].id,
                "amount": demo["price"],
            })
        continue

    product = stripe.Product.create(
        name=demo["name"],
        description=demo["description"],
        metadata=demo["metadata"],
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=demo["price"],
        currency="brl",
    )
    created.append({
        "name": demo["name"],
        "product_id": product.id,
        "price_id": price.id,
        "amount": demo["price"],
    })
    print(f"    CRIADO: {demo['name']}")
    print(f"      product_id: {product.id}")
    print(f"      price_id:   {price.id}")

# 5. Saida com os IDs para o index.html
print("\n" + "=" * 60)
print("PRICE IDs — cole no static/index.html:")
print("=" * 60)
for i, item in enumerate(created):
    print(f"\nProduto {i+1}: {item['name']}")
    print(f"  price_id: {item['price_id']}")
    print(f"  amount:   R$ {item['amount']/100:.2f}")

print("\n" + "=" * 60)
print("Setup concluido!")
print("=" * 60)

# Salvar resultado em JSON
with open("setup_output.json", "w", encoding="utf-8") as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("Resultado salvo em setup_output.json")
