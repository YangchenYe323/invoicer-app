"""Command-line interface for invoice extraction pipeline."""

import json
from pathlib import Path
from typing import Optional

from invoicer import (
    InvoiceExtractionPipeline,
    FileSystemAttachmentStorage,
    ProcessedEmail,
)


def process_eml_file(
    pipeline: InvoiceExtractionPipeline,
    eml_path: Path,
) -> ProcessedEmail:
    """Process a single .eml file through the pipeline.

    Args:
        pipeline: Initialized pipeline
        eml_path: Path to .eml file

    Returns:
        ProcessedEmail result
    """
    print(f"\nProcessing: {eml_path.name}")

    # Read email as bytes
    with open(eml_path, 'rb') as f:
        email_bytes = f.read()

    # Use filename (without .eml) as identifier for organizing attachments
    email_identifier = eml_path.stem

    # Process through pipeline
    result = pipeline.process_email(email_bytes, email_identifier=email_identifier)

    # Print summary
    print(f"  Classification: {'INVOICE' if result.classification.is_invoice else 'NOT INVOICE'} "
          f"(confidence: {result.classification.confidence})")
    print(f"  Reasoning: {result.classification.reasoning}")

    if result.invoice:
        print(f"  Extracted: {result.invoice.vendor} - "
              f"${result.invoice.total_amount} - {result.invoice.invoice_date}")

    if result.attachments:
        print(f"  Saved {len(result.attachments)} attachment(s)")

    # Print performance metrics
    m = result.metrics
    extract_str = f"extract: {m.extraction_time_sec:.3f}s" if m.extraction_time_sec > 0 else "extract: skipped"
    print(f"  Performance: {m.total_time_sec:.2f}s "
          f"(parse: {m.parse_time_sec:.3f}s, "
          f"classify: {m.classification_time_sec:.3f}s, "
          f"{extract_str})")

    return result


def process_directory(
    pipeline: InvoiceExtractionPipeline,
    directory: Path,
) -> list[ProcessedEmail]:
    """Process all .eml files in a directory.

    Args:
        pipeline: Initialized pipeline
        directory: Path to directory containing .eml files

    Returns:
        List of ProcessedEmail objects
    """
    eml_files = sorted(directory.glob("*.eml"))
    results = []

    for eml_file in eml_files:
        try:
            result = process_eml_file(pipeline, eml_file)
            results.append(result)
        except Exception as e:
            print(f"Error processing {eml_file}: {e}")
            continue

    return results


def save_results(results: list[ProcessedEmail], output_path: Path) -> None:
    """Save processed results to JSON file.

    Args:
        results: List of processed emails
        output_path: Path to output JSON file
    """
    with open(output_path, 'w') as f:
        json.dump(
            [result.model_dump() for result in results],
            f,
            indent=2,
            default=str  # Handle Decimal serialization
        )


def print_summary(results: list[ProcessedEmail]) -> None:
    """Print summary statistics.

    Args:
        results: List of processed emails
    """
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total emails processed: {len(results)}")
    print(f"Classified as invoices: {sum(1 for r in results if r.classification.is_invoice)}")
    print(f"Classified as non-invoices: {sum(1 for r in results if not r.classification.is_invoice)}")
    print(f"Invoice data extracted: {sum(1 for r in results if r.invoice is not None)}")

    # Aggregate performance metrics
    if results:
        total_time = sum(r.metrics.total_time_sec for r in results)
        avg_time = total_time / len(results)
        print(f"\nPerformance:")
        print(f"  Total processing time: {total_time:.2f}s")
        print(f"  Average per email: {avg_time:.2f}s")

        # Model load time (same for all)
        if results[0].metrics.model_load_time_sec:
            print(f"  Model load time: {results[0].metrics.model_load_time_sec:.2f}s")


def print_extracted_invoices(results: list[ProcessedEmail]) -> None:
    """Print detailed invoice information.

    Args:
        results: List of processed emails
    """
    print("\n" + "=" * 80)
    print("EXTRACTED INVOICES")
    print("=" * 80)

    for result in results:
        if result.invoice:
            print(f"\nSubject: {result.subject}")
            print(f"  Vendor: {result.invoice.vendor}")
            print(f"  Invoice #: {result.invoice.invoice_number}")
            print(f"  Date: {result.invoice.invoice_date}")
            print(f"  Amount: {result.invoice.currency} {result.invoice.total_amount}")
            print(f"  Status: {result.invoice.payment_status}")
            if result.invoice.line_items:
                print(f"  Line items: {len(result.invoice.line_items)}")
            if result.attachments:
                print(f"  Attachments: {len(result.attachments)}")
                for att in result.attachments:
                    print(f"    - {att.filename} ({att.size_bytes} bytes) -> {att.path}")


def main():
    """Main CLI entry point."""
    print("=" * 80)
    print("Invoice Extraction Pipeline")
    print("=" * 80)

    # Initialize attachment storage
    attachments_dir = Path("attachments")
    attachment_storage = FileSystemAttachmentStorage(attachments_dir)

    # Initialize pipeline
    pipeline = InvoiceExtractionPipeline(
        model_name="Qwen/Qwen2.5-7B-Instruct",
        gpu_memory_utilization=0.85,
        attachment_storage=attachment_storage,
    )

    # Process test data
    data_dir = Path("my_data")
    invoices_dir = data_dir / "invoices"
    noninvoices_dir = data_dir / "noninvoices"

    all_results = []

    # Process invoices
    if invoices_dir.exists():
        print("\n" + "=" * 80)
        print("Processing INVOICES")
        print("=" * 80)
        invoice_results = process_directory(pipeline, invoices_dir)
        all_results.extend(invoice_results)

    # Process non-invoices
    if noninvoices_dir.exists():
        print("\n" + "=" * 80)
        print("Processing NON-INVOICES")
        print("=" * 80)
        noninvoice_results = process_directory(pipeline, noninvoices_dir)
        all_results.extend(noninvoice_results)

    # Save results
    output_file = Path("results.json")
    save_results(all_results, output_file)
    print(f"\nResults saved to: {output_file}")

    # Print summaries
    print_summary(all_results)
    print_extracted_invoices(all_results)


if __name__ == "__main__":
    main()
