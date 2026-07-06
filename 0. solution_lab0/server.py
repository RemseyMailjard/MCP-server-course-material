# /// script
# requires-python = ">=3.10"
# dependencies = ["fastmcp"]
# ///
"""
Your First MCP Server - Built with FastMCP
============================================

This server shows all three MCP building blocks:

    TOOLS     -> The AI model calls these when it makes sense (functions, actions)
    RESOURCES -> You give these to the model as read-only context (data, manuals)
    PROMPTS   -> A person clicks a button and triggers a repeatable workflow

All data here is made up - no real customer or rate information.

HOW TO RUN
==========
The first four lines tell uv which Python packages you need. When you run
uv, it installs them automatically - no virtual environment to set up.

    uv run server.py                 # Test it quickly from the terminal

Connect it to VS Code by creating .vscode/mcp.json in your project folder:

    {
      "servers": {
        "mortgage-advisor": {
          "type": "stdio",
          "command": "uv",
          "args": ["run", "server.py"]
        }
      }
    }

VS Code shows a Start button next to the server. Click it, then open
Copilot Chat to talk to your server directly.
"""

from fastmcp import FastMCP

# Create the server. The name is what clients display.
mcp = FastMCP("rabo-mortgage-advisor")


# Sample rates used by the tools. The lending-policy resource
# in section 2 also contains these rates as a readable document.
MORTGAGE_RATES = {
    "annuity 10 year fixed": 3.65,
    "annuity 20 year fixed": 4.10,
    "annuity 30 year fixed": 4.35,
    "linear 20 year fixed": 4.05,
    "variable rate": 4.80,
}

# Banks don't lend if housing costs are too high.
# Let's say max 30% of your income can go to housing.
MAX_DTI_RATIO = 0.30


# ==============================================
# 1. TOOLS
# ==============================================
# The AI model can call these functions whenever it thinks it needs to.
# The docstring is your instruction manual to the model.
# These two are pure math - they don't change anything.

@mcp.tool
def calculate_monthly_payment(
    principal: float,
    annual_rate_pct: float,
    term_years: int,
) -> dict:
    """Calculate the monthly mortgage payment.

    Args:
        principal: Loan amount in euros.
        annual_rate_pct: Interest rate per year (e.g. 3.65 = 3.65%).
        term_years: How many years to pay it back.

    Returns:
        Monthly payment, total amount paid, and total interest.
    """
    monthly_rate = annual_rate_pct / 100 / 12
    n = term_years * 12

    if monthly_rate == 0:
        monthly_payment = principal / n
    else:
        monthly_payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -n)

    total_paid = monthly_payment * n
    return {
        "monthly_payment": round(monthly_payment, 2),
        "total_paid": round(total_paid, 2),
        "total_interest": round(total_paid - principal, 2),
    }


@mcp.tool
def affordability_check(
    monthly_payment: float,
    gross_monthly_income: float,
) -> dict:
    """Check if a monthly payment is affordable.

    Args:
        monthly_payment: How much the mortgage costs per month (euros).
        gross_monthly_income: Your total monthly income before taxes (euros).

    Returns:
        The debt-to-income ratio and whether it's within the bank's limit.
    """
    ratio = monthly_payment / gross_monthly_income
    return {
        "dti_ratio": round(ratio, 3),
        "max_allowed": MAX_DTI_RATIO,
        "within_limit": ratio <= MAX_DTI_RATIO,
    }

# Note: a tool that CHANGES something (logs data, sends email, books a loan)
# also goes here. That's how you tell the difference from a resource:
# a resource just reads; a tool can change things.


# ==============================================
# 2. RESOURCES
# ==============================================
# A resource is context you hand to the model — not something the model
# decides to call. Think of it as a document you attach before the chat.
# You control when it's available; the model just reads it.

@mcp.resource("docs://lending-policy")
def lending_policy() -> str:
    """Bank lending policy: products, rates, and eligibility rules (synthetic).

    Include this resource as context before advising a client.
    The model reads it — you decide when to make it available.
    """
    return (
        "MORTGAGE LENDING POLICY (synthetic data)\n"
        "=========================================\n\n"
        "Current products and rates:\n"
        "  annuity 10 year fixed : 3.65%\n"
        "  annuity 20 year fixed : 4.10%\n"
        "  annuity 30 year fixed : 4.35%\n"
        "  linear 20 year fixed  : 4.05%\n"
        "  variable rate         : 4.80%\n\n"
        "Eligibility rules:\n"
        "  Max debt-to-income ratio : 30% of gross monthly income\n"
        "  Max loan-to-value        : 100% first-time buyers, 90% otherwise\n"
        "  NHG guarantee up to      : \u20ac435,000\n"
        "  Max age at end of term   : 75 years\n"
        "  Stress test rate         : 5.0%\n\n"
        "Product guide:\n"
        "  Annuity  \u2013 equal monthly payments for the full term\n"
        "  Linear   \u2013 decreasing payments (higher at start, lower at end)\n"
        "  Variable \u2013 payment moves with the market rate"
    )


# ==============================================
# 3. PROMPT
# ==============================================
# A prompt is a workflow a person clicks to start (like a slash-command).
# This one ties everything together: read a rate, calculate a payment,
# check affordability, then give advice. Every time, same sequence.
# The model follows your instructions step-by-step.

@mcp.prompt
def mortgage_advice(
    client_name: str,
    loan_amount: float,
    term_years: int,
    gross_monthly_income: float,
    product: str,
) -> str:
    """Give mortgage advice: rate, payment, affordability.\n\n    A person clicks this, and you help them step-by-step:\n    1. Read the current rate for their product\n    2. Calculate what they'd pay each month\n    3. Check if they can afford it\n    4. Give them a recommendation\n    \"\"\"
    return (
        f"You are a mortgage advisor. Help {client_name}.\n\n"
        f"Step 1: Read the resource docs://lending-policy to get the rate for '{product}' and the eligibility rules.\n"
        f"Step 2: Call calculate_monthly_payment with principal={loan_amount}, "
        f"the rate you just read, and term_years={term_years}.\n"
        f"Step 3: Call affordability_check with that payment and "
        f"gross_monthly_income={gross_monthly_income}.\n"
        f"Step 4: Write a short summary: which product, what's the rate, "
        f"monthly payment, total interest, and is it affordable? "
        f"If not, suggest one alternative.\n\n"
        f"Keep it factual and clear."
    )


# ==============================================
# RUN THE SERVER
# ==============================================
# Default: stdio (direct pipe, good for testing)
# For real use: mcp.run(transport="http")
if __name__ == "__main__":
    mcp.run()
