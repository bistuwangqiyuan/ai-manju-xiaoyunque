from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import Payment, User, get_db
from ..schemas import CheckoutIn, CheckoutOut, TopUpIn, UserOut
from ..security import get_current_user
from ..settings import settings

router = APIRouter(prefix="/billing", tags=["billing"])

PLANS = {
    "starter": {"name": "试看版（单集）", "amount_cents": 9900},
    "series": {"name": "十集套装", "amount_cents": 129900},
    "studio": {"name": "工作室版", "amount_cents": 0},
}


@router.post("/checkout", response_model=CheckoutOut)
def create_checkout(
    payload: CheckoutIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutOut:
    plan = PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="未知套餐")
    if payload.plan == "studio":
        raise HTTPException(status_code=400, detail="工作室版请联系销售")

    if settings.use_mock_billing:
        # mock 模式：直接给用户加额度（仅用于开发联调）
        user.credits_cents += plan["amount_cents"]
        db.add(
            Payment(
                user_id=user.id,
                amount_cents=plan["amount_cents"],
                plan=payload.plan,
                provider="mock",
                status="paid",
            )
        )
        db.commit()
        return CheckoutOut(
            url=f"{settings.SITE_URL}/billing/success?mock=1",
            mocked=True,
        )

    # 真实 Stripe Checkout
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "cny",
                    "product_data": {"name": plan["name"]},
                    "unit_amount": plan["amount_cents"],
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.SITE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.SITE_URL}/billing/cancel",
        customer_email=user.email,
        metadata={"user_id": str(user.id), "plan": payload.plan},
    )
    db.add(
        Payment(
            user_id=user.id,
            amount_cents=plan["amount_cents"],
            plan=payload.plan,
            provider="stripe",
            external_id=session.id,
            status="pending",
        )
    )
    db.commit()
    return CheckoutOut(url=session.url, mocked=False)


@router.post("/topup", response_model=UserOut)
def topup(
    payload: TopUpIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """开发模式下手动充值（mock 计费时可用）"""
    if not settings.use_mock_billing:
        raise HTTPException(status_code=400, detail="生产环境请走 /checkout")
    user.credits_cents += payload.amount_cents
    db.add(
        Payment(
            user_id=user.id,
            amount_cents=payload.amount_cents,
            plan="topup",
            provider="mock",
            status="paid",
        )
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if settings.use_mock_billing:
        raise HTTPException(status_code=404)
    import stripe

    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"签名验证失败: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        external_id = session["id"]
        pay = db.query(Payment).filter(Payment.external_id == external_id).first()
        if pay and pay.status != "paid":
            pay.status = "paid"
            user = db.get(User, pay.user_id)
            if user:
                user.credits_cents += pay.amount_cents
            db.commit()

    return {"received": True}
