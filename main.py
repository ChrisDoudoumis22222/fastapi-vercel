from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
import stripe

# Initialize FastAPI app
app = FastAPI()

# Stripe configuration
stripe.api_key = "sk_test_51Pn9MbDo5uWbWPXU81NQmpueBJo8XjS9NCxpxt6Z2rVNPysIZ2mR7dUZgYZvdVwq5mHOkauc89LOdfvw1zf2n2Xu00eerSOuqR"
endpoint_secret = "whsec_c5lc8jr7ijEbaMgegU5wVpt1BuQ53mKz"

# Supabase configuration
SUPABASE_URL = "https://zndapvhmixnjomirdmxc.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpuZGFwdmhtaXhuam9taXJkbXhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY0ODU1NTEsImV4cCI6MjA1MjA2MTU1MX0.zOVvbcWEr7VMBzkqLM5JWC0k-WwN-rbkS_7DLYx6W0Q"

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@app.get("/")
def read_root():
    return {"message": "Welcome to the subscription-based FastAPI app with Supabase!"}


@app.get("/getSubscriptionURL")
async def get_subscription_url(email: str):
    try:
        # Save the subscription intent in Supabase
        data = {
            "email": email,
            "status": "pending",
        }
        response = supabase.table("payments").insert(data).execute()
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error saving to database")

        # Retrieve the record's ID for reference
        payment_id = response.data[0]["id"]

        # Create a Stripe customer
        customer = stripe.Customer.create(email=email)

        # Create a subscription checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price": "prod_RYZQTBIlCCyV5j",  # Replace with your Stripe Price ID
                    "quantity": 1,
                }
            ],
            customer=customer.id,
            success_url=f"https://fastapi-vercel-gamma-lemon.vercel.app//success?payment_id={payment_id}",
            cancel_url=f"https://fastapi-vercel-gamma-lemon.vercel.app//cancel?payment_id={payment_id}",
        )

        return {"subscription_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["customer_details"]["email"]
        payment_id = session["metadata"]["payment_id"]

        # Update payment status in Supabase
        response = supabase.table("payments").update({"status": "success"}).eq("id", payment_id).execute()
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error updating database")

    return {"status": "success"}


@app.get("/hasUserPaid")
async def has_user_paid(email: str):
    # Check if the user has an active subscription in Supabase
    response = supabase.table("payments").select("status").eq("email", email).order("created_at", desc=True).limit(1).execute()
    if response.status_code != 200 or len(response.data) == 0:
        return {"email": email, "has_paid": False}

    status = response.data[0]["status"]
    return {"email": email, "has_paid": status == "success"}


@app.get("/success", response_class=HTMLResponse)
def payment_success(payment_id: int):
    html_content = f"""
    <html>
        <head><title>Subscription Successful</title></head>
        <body>
            <h1>Thank you for subscribing!</h1>
            <p>Your subscription with ID {payment_id} was successful.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/cancel", response_class=HTMLResponse)
def payment_cancel(payment_id: int):
    html_content = f"""
    <html>
        <head><title>Subscription Cancelled</title></head>
        <body>
            <h1>Subscription Cancelled</h1>
            <p>Your subscription with ID {payment_id} was cancelled. If this was a mistake, please try again.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
