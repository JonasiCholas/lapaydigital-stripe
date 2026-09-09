"""
Lapay Digital — Stripe Integration Backend
FastAPI + Stripe Checkout (PIX focus) + Invoicing
"""

import os
import stripe
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Clear old environment variables to force reload from .env
if "STRIPE_SECRET_KEY" in os.environ:
    del os.environ["STRIPE_SECRET_KEY"]
if "STRIPE_PUBLISHABLE_KEY" in os.environ:
    del os.environ["STRIPE_PUBLISHABLE_KEY"]
if "STRIPE_WEBHOOK_SECRET" in os.environ:
    del os.environ["STRIPE_WEBHOOK_SECRET"]

# Force reload from .env file
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lapaydigital")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
DOMAIN = os.getenv("DOMAIN", "http://localhost:8000")

if not STRIPE_SECRET_KEY:
    logger.warning("STRIPE_SECRET_KEY nao configurada. Copie .env.example para .env e preencha suas chaves.")
    logger.warning("O servidor iniciara, mas as rotas de pagamento vao falhar ate voce configurar as chaves.")

stripe.api_key = STRIPE_SECRET_KEY or "sk_test_placeholder"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lapay Digital - Stripe backend iniciado")
    logger.info(f"   Modo: {'TEST' if STRIPE_SECRET_KEY.startswith('sk_test') else 'LIVE'}")
    logger.info(f"   Dominio: {DOMAIN}")
    yield
    logger.info("Servidor encerrado")


app = FastAPI(
    title="Lapay Digital - Stripe API",
    description="Backend de pagamentos para venda de produtos e ingressos",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em producao: restrinja para lapaydigital.com
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Static files (front-end demo)
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    price_id: str
    quantity: int = 1
    customer_email: Optional[str] = None
    metadata: Optional[dict] = None


class InvoiceItem(BaseModel):
    price_id: str
    quantity: int = 1


class InvoiceRequest(BaseModel):
    customer_name: str
    email: EmailStr
    tax_id: Optional[str] = None
    tax_id_type: str = "br_cpf"           # "br_cpf" ou "br_cnpj"
    items: list[InvoiceItem]
    days_until_due: int = 7


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "stripe_mode": "test" if STRIPE_SECRET_KEY.startswith("sk_test") else "live",
    }


# ---------------------------------------------------------------------------
# Front-end demo (serve index.html)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/sucesso", response_class=HTMLResponse)
async def sucesso():
    with open("static/sucesso.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/cancelado", response_class=HTMLResponse)
async def cancelado():
    with open("static/cancelado.html", "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Stripe Config (chave publica para o front-end)
# ---------------------------------------------------------------------------

@app.get("/config")
async def get_config():
    """Retorna a chave publica do Stripe para o front-end."""
    return {"publishable_key": STRIPE_PUBLISHABLE_KEY}


# ---------------------------------------------------------------------------
# Checkout Session (Payments)
# ---------------------------------------------------------------------------

@app.post("/create-checkout-session")
async def create_checkout_session(req: CheckoutRequest):
    """
    Cria uma Stripe Checkout Session e retorna a URL de pagamento.
    Suporta: PIX, cartao de credito.
    """
    try:
        params: dict = {
            "mode": "payment",
            "line_items": [
                {"price": req.price_id, "quantity": req.quantity}
            ],
            "payment_method_types": ["card", "pix"],
            "success_url": f"{DOMAIN}/sucesso?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{DOMAIN}/cancelado",
            "metadata": req.metadata or {},
            "billing_address_collection": "auto",
        }

        if req.customer_email:
            params["customer_email"] = req.customer_email

        session = stripe.checkout.Session.create(**params)

        logger.info(f"Checkout Session criada: {session.id} - price: {req.price_id}")
        return {"url": session.url, "session_id": session.id}

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe InvalidRequest: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.StripeError as e:
        logger.error(f"Stripe Error: {e}")
        raise HTTPException(status_code=500, detail="Erro no processamento do pagamento.")


# ---------------------------------------------------------------------------
# Session Details (para a pagina de sucesso)
# ---------------------------------------------------------------------------

@app.get("/session-details")
async def session_details(id: str):
    """Retorna detalhes de uma Checkout Session para exibir na pagina de sucesso."""
    try:
        session = stripe.checkout.Session.retrieve(
            id,
            expand=["line_items", "payment_intent"],
        )
        return {
            "id": session.id,
            "status": session.status,
            "payment_status": session.payment_status,
            "customer_email": session.customer_details.email if session.customer_details else None,
            "customer_name": session.customer_details.name if session.customer_details else None,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "line_items": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "amount_total": item.amount_total,
                }
                for item in (session.line_items.data if session.line_items else [])
            ],
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Invoicing (B2B / emissao de cobranças formais)
# ---------------------------------------------------------------------------

@app.post("/create-invoice")
async def create_invoice(req: InvoiceRequest):
    """
    Cria um cliente Stripe com CPF/CNPJ e emite uma Invoice formal.
    Retorna a URL da invoice hospedada pelo Stripe e o link do PDF.
    """
    try:
        customer_params: dict = {
            "name": req.customer_name,
            "email": req.email,
        }
        if req.tax_id:
            customer_params["tax_id_data"] = [
                {"type": req.tax_id_type, "value": req.tax_id}
            ]

        customer = stripe.Customer.create(**customer_params)
        logger.info(f"Customer criado: {customer.id} - {req.email}")

        for item in req.items:
            stripe.InvoiceItem.create(
                customer=customer.id,
                price=item.price_id,
                quantity=item.quantity,
            )

        invoice = stripe.Invoice.create(
            customer=customer.id,
            collection_method="send_invoice",
            days_until_due=req.days_until_due,
            currency="brl",
        )

        finalized = stripe.Invoice.finalize_invoice(invoice.id)  # stripe >= 5.x static method
        logger.info(f"Invoice finalizada: {finalized.id}")

        return {
            "invoice_id": finalized.id,
            "hosted_invoice_url": finalized.hosted_invoice_url,
            "invoice_pdf": finalized.invoice_pdf,
            "status": finalized.status,
            "amount_due": finalized.amount_due,
            "currency": finalized.currency,
        }

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe InvalidRequest: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.StripeError as e:
        logger.error(f"Stripe Error: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar invoice.")


# ---------------------------------------------------------------------------
# Webhook - Confirmacao de Pagamentos
# ---------------------------------------------------------------------------

@app.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Recebe eventos do Stripe via webhook.
    IMPORTANTE: Este endpoint deve receber o body RAW (nao JSON parseado).
    Configure no Stripe Dashboard: Developers -> Webhooks -> Add endpoint
    URL: https://lapaydigital.com/webhook
    Eventos: checkout.session.completed, invoice.paid, payment_intent.payment_failed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        # DEV mode: no signature verification, use raw JSON dict
        logger.warning("STRIPE_WEBHOOK_SECRET nao configurado - pulando verificacao de assinatura (DEV only)")
        try:
            import json
            event = json.loads(payload)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Payload invalido: {e}")
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            logger.error("Assinatura do webhook invalida")
            raise HTTPException(status_code=400, detail="Assinatura invalida")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Webhook recebido: {event_type}")

    if event_type == "checkout.session.completed":
        session_id = data["id"]
        customer_email = data.get("customer_details", {}).get("email")
        amount = data.get("amount_total", 0)
        logger.info(f"Checkout concluido: {session_id} | {customer_email} | R$ {amount/100:.2f}")
        await fulfill_order(data)

    elif event_type == "invoice.paid":
        invoice_id = data["id"]
        customer_email = data.get("customer_email")
        amount = data.get("amount_paid", 0)
        logger.info(f"Invoice paga: {invoice_id} | {customer_email} | R$ {amount/100:.2f}")
        await mark_invoice_paid(data)

    elif event_type == "payment_intent.payment_failed":
        payment_intent_id = data["id"]
        failure_message = data.get("last_payment_error", {}).get("message", "Desconhecido")
        logger.warning(f"Pagamento falhou: {payment_intent_id} | motivo: {failure_message}")

    return {"received": True}


# ---------------------------------------------------------------------------
# Funcoes de fulfillment (implementar conforme seu sistema)
# ---------------------------------------------------------------------------

async def fulfill_order(session: dict):
    """
    Executado quando checkout.session.completed e recebido.
    Adapte para o seu banco de dados e sistema de e-mail.
    """
    metadata = session.get("metadata", {})
    product_type = metadata.get("product_type", "unknown")
    logger.info(f"  -> Fulfillment: tipo={product_type}")

    # TODO: Implemente aqui sua logica de fulfillment:
    # if product_type == "ticket":
    #     await send_ticket_email(session["customer_details"]["email"], metadata)
    #     await db.create_ticket(session_id=session["id"], metadata=metadata)
    # elif product_type == "product":
    #     await send_product_confirmation(session)


async def mark_invoice_paid(invoice: dict):
    """Executado quando invoice.paid e recebido."""
    logger.info(f"  -> Invoice {invoice['id']} marcada como paga no sistema")
    # TODO: atualizar status no banco de dados


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
