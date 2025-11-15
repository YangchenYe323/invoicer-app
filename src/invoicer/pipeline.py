"""Core invoice extraction pipeline - email bytes in, structured data out."""

import json
import time
from typing import Optional

from vllm import LLM, SamplingParams
from pydantic import ValidationError

from .parser import EmailParser
from .models import (
    Attachment,
    EmailClassification,
    Invoice,
    ProcessedEmail,
    ProcessingMetrics,
)
from .storage import AttachmentStorage
from .metrics import MetricsCollector


class InvoiceExtractionPipeline:
    """Pipeline for classifying emails and extracting invoice data using LLM.

    Core abstraction: email bytes (RFC822) in -> structured data out.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        gpu_memory_utilization: float = 0.9,
        attachment_storage: Optional[AttachmentStorage] = None,
    ):
        """Initialize the pipeline with a vLLM model.

        Args:
            model_name: HuggingFace model name to use
            gpu_memory_utilization: Fraction of GPU memory to use (0.0-1.0)
            attachment_storage: Optional storage backend for attachments
        """
        self.metrics_collector = MetricsCollector()

        print(f"Loading model: {model_name}")
        start_time = time.perf_counter()

        self.llm = LLM(
            model=model_name,
            gpu_memory_utilization=gpu_memory_utilization,
            tensor_parallel_size=1,  # Single GPU
            max_model_len=8192,  # Context length
        )

        self.metrics_collector.model_load_time = time.perf_counter() - start_time
        print(f"Model loaded in {self.metrics_collector.model_load_time:.2f}s")

        # Sampling parameters for inference
        self.sampling_params = SamplingParams(
            temperature=0.1,  # Low temperature for more deterministic output
            top_p=0.95,
            max_tokens=2048,
        )

        self.attachment_storage = attachment_storage
        self.parser = EmailParser()

    def process_email(
        self,
        email_bytes: bytes,
        email_identifier: Optional[str] = None,
    ) -> ProcessedEmail:
        """Process a single email through the full pipeline.

        Args:
            email_bytes: Email in RFC822 format (bytes)
            email_identifier: Optional identifier for organizing attachments

        Returns:
            ProcessedEmail object with classification, invoice data, and metrics
        """
        collector = self.metrics_collector

        # Stage 1: Parse email
        collector.start_timer("parse")
        email_data = self.parser.parse(email_bytes)
        parse_time = collector.stop_timer("parse")

        # Stage 2: Extract and save attachments
        collector.start_timer("attachments")
        attachments = self._process_attachments(
            email_data['attachments_raw'],
            email_identifier
        )
        attachment_time = collector.stop_timer("attachments")

        # Stage 3: Classify email
        collector.start_timer("classification")
        classification = self._classify_email(email_data)
        classification_time = collector.stop_timer("classification")

        # Stage 4: Extract invoice data if classified as invoice
        collector.start_timer("extraction")
        invoice = None
        if classification.is_invoice:
            invoice = self._extract_invoice_data(email_data)
        extraction_time = collector.stop_timer("extraction")

        # Calculate metrics
        total_attachment_bytes = sum(att['size_bytes'] for att in email_data['attachments_raw'])
        metrics_dict = collector.create_email_metrics(
            parse_time=parse_time,
            attachment_time=attachment_time,
            classification_time=classification_time,
            extraction_time=extraction_time,
            num_attachments=len(attachments),
            total_attachment_bytes=total_attachment_bytes,
        )

        return ProcessedEmail(
            subject=email_data['subject'],
            from_address=email_data['from'],
            date=email_data['date'],
            classification=classification,
            invoice=invoice,
            attachments=attachments,
            metrics=ProcessingMetrics(**metrics_dict),
        )

    def _process_attachments(
        self,
        attachments_raw: list[dict],
        email_identifier: Optional[str] = None,
    ) -> list[Attachment]:
        """Process and save attachments using storage backend.

        Args:
            attachments_raw: List of raw attachment data from parser
            email_identifier: Optional identifier for grouping

        Returns:
            List of Attachment models with storage paths
        """
        if not self.attachment_storage:
            return []

        attachments = []
        for att_data in attachments_raw:
            try:
                # Save using storage backend
                storage_path = self.attachment_storage.save_attachment(
                    filename=att_data['filename'],
                    data=att_data['data'],
                    content_type=att_data['content_type'],
                    email_identifier=email_identifier,
                )

                attachments.append(Attachment(
                    filename=att_data['filename'],
                    content_type=att_data['content_type'],
                    size_bytes=att_data['size_bytes'],
                    path=storage_path,
                ))

            except Exception as e:
                print(f"Warning: Failed to save attachment {att_data['filename']}: {e}")
                continue

        return attachments

    def _classify_email(self, email_data: dict) -> EmailClassification:
        """Classify whether an email contains an invoice.

        Args:
            email_data: Parsed email data

        Returns:
            EmailClassification object
        """
        prompt = f"""Analyze this email and determine if it contains an invoice or receipt. Respond with ONLY valid JSON, no markdown formatting or extra text.

Subject: {email_data['subject']}
From: {email_data['from']}
Body (first 2000 chars):
{email_data['body'][:2000]}

Return JSON with these fields:
- is_invoice (boolean): true if this is an invoice/receipt, false otherwise
- confidence (string): "high", "medium", or "low"
- reasoning (string): brief explanation

JSON:"""

        sampling_params = SamplingParams(
            temperature=0.1,
            top_p=0.95,
            max_tokens=256,
            stop=["}\n", "}\r\n"],  # Stop after JSON closes
        )

        outputs = self.llm.generate([prompt], sampling_params)
        response_text = outputs[0].outputs[0].text.strip()

        # Ensure JSON is complete
        if not response_text.endswith('}'):
            response_text += '}'

        try:
            # Clean up response - remove markdown code blocks if present
            cleaned = response_text
            if '```' in cleaned:
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
                if json_match:
                    cleaned = json_match.group(1)
                else:
                    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                    if json_match:
                        cleaned = json_match.group(0)

            data = json.loads(cleaned)
            return EmailClassification(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Fallback based on subject keywords
            is_invoice = any(kw in email_data['subject'].lower()
                           for kw in ['invoice', 'receipt', 'payment', 'paid'])
            return EmailClassification(
                is_invoice=is_invoice,
                confidence="low",
                reasoning="Fallback classification based on subject keywords"
            )

    def _extract_invoice_data(self, email_data: dict) -> Optional[Invoice]:
        """Extract structured invoice data from an email.

        Args:
            email_data: Parsed email data

        Returns:
            Invoice object or None if extraction fails
        """
        prompt = f"""Extract invoice information from this email. Respond with ONLY valid JSON, no markdown or extra text.

Subject: {email_data['subject']}
From: {email_data['from']}
Body:
{email_data['body'][:4000]}

Extract these fields in JSON format:
- vendor (string): company name
- invoice_number (string or null): invoice/receipt number
- invoice_date (string or null): date in YYYY-MM-DD format
- due_date (string or null): due date in YYYY-MM-DD format
- total_amount (number or null): total amount
- currency (string): currency code, default "USD"
- payment_status (string or null): "paid", "unpaid", or "unknown"
- line_items (array): list of items with description, quantity, unit_price, total
- notes (string or null): additional info

JSON:"""

        sampling_params = SamplingParams(
            temperature=0.1,
            top_p=0.95,
            max_tokens=1500,
        )

        outputs = self.llm.generate([prompt], sampling_params)
        response_text = outputs[0].outputs[0].text.strip()

        try:
            # Clean up response
            cleaned = response_text
            if '```' in cleaned:
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
                if json_match:
                    cleaned = json_match.group(1)
                else:
                    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                    if json_match:
                        cleaned = json_match.group(0)

            # Find the JSON object
            if not cleaned.startswith('{'):
                import re
                json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if json_match:
                    cleaned = json_match.group(0)

            data = json.loads(cleaned)
            return Invoice(**data)
        except (json.JSONDecodeError, ValidationError):
            return None
