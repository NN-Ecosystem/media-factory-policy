# P30K.3 — Linked License Key + Email Activation

Purpose:
A Local/Legacy License Key that has already been linked to a verified email/account
can activate that Account License without another confirmation email.

Proof:
- possession of the linked License Key
- exact linked account/email match
- active/non-expired legacy license
- active linked entitlement
- activation seat availability
- machine binding supplied by Core

Endpoint:
POST /v1/cloud/licenses/linked/activate

The endpoint never grants from email alone. The License Key is the migration possession proof.
Seat allocation remains canonical through P30G Activation Seats.
