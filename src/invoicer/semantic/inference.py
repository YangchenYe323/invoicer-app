"""LLM inference for email classification and invoice extraction."""

import json
import logging
import re
from decimal import Decimal
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError

from ..models import ParsedEmail, EmailClassification, Invoice, LineItem

logger = logging.getLogger(__name__)


class InferenceClient:
    """Client for LLM inference using OpenAI-compatible API (vLLM)."""

    def __init__(self, api_url: str, model_name: str = "Qwen/Qwen3-8B-FP8"):
        """Initialize inference client.

        Args:
            api_url: Base URL for the OpenAI-compatible API (e.g., vLLM endpoint)
            model_name: Model name to use for inference
        """
        self.client = OpenAI(
            base_url=api_url,
            api_key="not-needed",  # vLLM doesn't require authentication
        )
        self.model_name = model_name
        logger.info(f"Inference client initialized with model: {model_name}")

    def classify_email(self, parsed_email: ParsedEmail) -> EmailClassification:
        """Classify whether an email contains an invoice.

        Args:
            parsed_email: Parsed email object

        Returns:
            EmailClassification: Classification result
        """
        # Prepare email body (prefer text, fallback to HTML)
        body = parsed_email.body_text or parsed_email.body_html or ""

        prompt = f"""Analyze this email and determine if it contains an invoice or receipt.

Subject: {parsed_email.subject}
From: {parsed_email.from_address}
Body (first 2000 chars):
{body[:2000]}

Respond with ONLY a JSON object. Do not include thinking process, markdown blocks, or any text before or after the JSON.

Output JSON with these exact fields:
{{
  "is_invoice": true or false,
  "confidence": "high" or "medium" or "low",
  "reasoning": "brief explanation"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                top_p=0.95,
                max_tokens=256,
            )

            response_text = response.choices[0].message.content.strip()

            # Clean up response - remove markdown code blocks if present
            cleaned = self._extract_json(response_text)

            # Ensure JSON is complete
            if not cleaned.endswith('}'):
                cleaned += '}'

            data = json.loads(cleaned)
            return EmailClassification(**data)

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Fallback based on subject keywords
            is_invoice = any(
                kw in parsed_email.subject.lower()
                for kw in ['invoice', 'receipt', 'payment', 'paid', 'bill']
            )
            return EmailClassification(
                is_invoice=is_invoice,
                confidence="low",
                reasoning=f"Fallback classification (error: {str(e)})"
            )

    def extract_invoice(self, parsed_email: ParsedEmail) -> Optional[Invoice]:
        """Extract structured invoice data from an email.

        Args:
            parsed_email: Parsed email object

        Returns:
            Invoice: Extracted invoice data with required fields populated
            None: If extraction fails

        Note:
            The returned Invoice will NOT have database fields (id, user_id, source_id, uid)
            populated. Those must be set by the caller before database insertion.
        """
        # Prepare email body (prefer text, fallback to HTML)
        body = parsed_email.body_text or parsed_email.body_html or ""

        prompt = f"""Extract invoice information from this email.

Subject: {parsed_email.subject}
From: {parsed_email.from_address}
Body:
{body[:4000]}

Respond with ONLY a JSON object. Do not include thinking process, markdown blocks, or any text before or after the JSON.

Output JSON with these exact fields:
{{
  "vendor_name": "company name",
  "invoice_number": "invoice/receipt number or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number or null,
  "currency": "USD",
  "payment_status": "paid" or "unpaid" or "unknown" or null,
  "line_items": [
    {{"description": "item description", "quantity": 1, "unitPrice": 10.00}}
  ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                top_p=0.95,
                max_tokens=1500,
            )

            response_text = response.choices[0].message.content.strip()

            # Clean up response
            cleaned = self._extract_json(response_text)

            # Parse JSON
            data = json.loads(cleaned)

            # Convert line_items to LineItem objects
            line_items = []
            if "line_items" in data and isinstance(data["line_items"], list):
                for item in data["line_items"]:
                    try:
                        # Handle unitPrice conversion
                        if "unitPrice" in item and item["unitPrice"] is not None:
                            item["unitPrice"] = Decimal(str(item["unitPrice"]))
                        line_items.append(LineItem(**item))
                    except Exception as e:
                        logger.warning(f"Skipping invalid line item: {e}")
                        continue

            # Convert total_amount to Decimal
            if "total_amount" in data and data["total_amount"] is not None:
                data["total_amount"] = Decimal(str(data["total_amount"]))

            # Create Invoice (without database fields - caller must set these)
            # Note: user_id, source_id, uid are required but will be set by caller
            # We use placeholder values that will be overwritten
            invoice = Invoice(
                user_id="",  # Placeholder - caller must set
                source_id=0,  # Placeholder - caller must set
                uid=0,  # Placeholder - caller must set
                message_id=parsed_email.message_id,
                vendor_name=data.get("vendor_name"),
                invoice_number=data.get("invoice_number"),
                due_date=data.get("due_date"),
                total_amount=data.get("total_amount"),
                currency=data.get("currency", "USD"),
                payment_status=data.get("payment_status"),
                line_items=line_items,
                attached_files=[],  # Will be populated after S3 uploads
            )

            return invoice

        except Exception as e:
            logger.error(f"Invoice extraction failed: {e}")
            return None

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks or thinking tags.

        Args:
            text: Response text that may contain JSON

        Returns:
            str: Cleaned JSON string
        """
        # Remove thinking tags if present
        if '<think>' in text or '</think>' in text:
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            text = text.strip()

        # Handle markdown code blocks
        if '```' in text:
            # Try to extract from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                return json_match.group(1)
            else:
                # Fallback: find first JSON object
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json_match.group(0)

        # Find the JSON object if it doesn't start with {
        if not text.startswith('{'):
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json_match.group(0)

        return text
