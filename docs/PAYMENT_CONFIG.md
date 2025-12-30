# WhatsApp Payment Configuration

## Overview

This document contains the payment configuration details for WhatsApp Business Accounts (WABAs) with native WhatsApp Payments enabled for India.

---

## WABA 1: WECARE.DIGITAL

| Field | Value |
|-------|-------|
| **Phone Number** | +91 9330994400 |
| **Business Name** | WECARE.DIGITAL |
| **WABA ID** | 1347766229904230 |
| **Phone Number ID** | 831049713436137 |

### Razorpay Configuration

| Field | Value |
|-------|-------|
| **Config Name** | WECARE-DIGITAL |
| **Status** | ✅ Active |
| **MCC** | 4722 (Travel agencies and tour operators) |
| **Purpose Code** | 03 (Travel) |
| **Gateway MID** | acc_HDfub6wOfQybuH |

### UPI Configuration

| Field | Value |
|-------|-------|
| **Config Name** | wecare-digital-upi |
| **Status** | ✅ Active |
| **MCC** | 4722 (Travel agencies and tour operators) |
| **Purpose Code** | 03 (Travel) |
| **UPI ID** | 9330994400@sbi |

---

## WABA 2: Manish Agarwal

| Field | Value |
|-------|-------|
| **Phone Number** | +91 9903300044 |
| **Business Name** | Manish Agarwal |
| **WABA ID** | 1390647332755815 |
| **Phone Number ID** | 888782840987368 |

### Razorpay Configuration

| Field | Value |
|-------|-------|
| **Config Name** | ManishAgarwal |
| **Status** | ✅ Active |
| **MCC** | 4722 (Travel agencies and tour operators) |
| **Purpose Code** | 03 (Travel) |
| **Gateway MID** | acc_HDfub6wOfQybuH |

### UPI Configuration

| Field | Value |
|-------|-------|
| **Config Name** | manish-agarwal-upi |
| **Status** | ✅ Active |
| **MCC** | 4722 (Travel agencies and tour operators) |
| **Purpose Code** | 03 (Travel) |
| **UPI ID** | 9330994400@sbi |

---

## Usage Examples

### Send Payment Order (Razorpay)

```json
{
    "action": "send_payment_order",
    "metaWabaId": "1347766229904230",
    "to": "+919876543210",
    "referenceId": "ORDER-001",
    "paymentType": "PG_RAZORPAY",
    "paymentConfigurationName": "WECARE-DIGITAL",
    "currency": "INR",
    "totalAmount": 1000,
    "order": {
        "status": "pending",
        "items": [
            {
                "name": "Travel Package",
                "amount": 1000,
                "quantity": 1,
                "retailerId": "PKG-001"
            }
        ]
    }
}
```

### Send Payment Order (UPI Intent)

```json
{
    "action": "send_payment_order",
    "metaWabaId": "1347766229904230",
    "to": "+919876543210",
    "referenceId": "ORDER-002",
    "paymentType": "UPI_INTENT",
    "upiIntentLink": "upi://pay?pa=9330994400@sbi&pn=WECARE.DIGITAL&am=1000&cu=INR&tr=ORDER-002",
    "currency": "INR",
    "totalAmount": 1000,
    "order": {
        "status": "pending",
        "items": [
            {
                "name": "Travel Package",
                "amount": 1000,
                "quantity": 1
            }
        ]
    }
}
```

### Send Order Status Update

```json
{
    "action": "send_order_status",
    "metaWabaId": "1347766229904230",
    "to": "+919876543210",
    "referenceId": "ORDER-001",
    "status": "completed",
    "description": "Payment received successfully"
}
```

---

## MCC Codes Reference

| MCC | Description |
|-----|-------------|
| 4722 | Travel agencies and tour operators |
| 5411 | Grocery stores, supermarkets |
| 5812 | Eating places, restaurants |
| 5912 | Drug stores, pharmacies |
| 7299 | Miscellaneous recreation services |
| 8099 | Health practitioners |

## Purpose Codes Reference

| Code | Description |
|------|-------------|
| 01 | Family maintenance |
| 02 | Education |
| 03 | Travel |
| 04 | Medical treatment |
| 05 | Gifts |
| 06 | Donations |
| 07 | Investment |
| 08 | Deposits |
| 09 | Tax payment |
| 10 | Utility payment |

---

## Integration Notes

1. **Razorpay Gateway**: Uses embedded checkout within WhatsApp
2. **UPI Intent**: Opens user's UPI app with pre-filled payment details
3. **Order Details Message**: Interactive message type `order_details`
4. **Order Status Message**: Interactive message type `order_status`

## Webhook Events

Payment webhooks are received with the following events:
- `payment.captured` - Payment successful
- `payment.failed` - Payment failed
- `payment.authorized` - Payment authorized (pending capture)
- `refund.processed` - Refund completed

---

*Last Updated: December 30, 2024*
