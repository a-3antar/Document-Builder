"""Shared Arabic/English samples and the visual checklist (dev/test only)."""
from __future__ import annotations

from core.models import DocumentContentModel, Heading, ListBlock, Metadata, Paragraph, Table

CHECKLIST = """\
Open the PDF and confirm each item (see docs/arabic_pdf_verification.md):
 1. Letters are joined (not isolated) and read right-to-left.
 2. Punctuation sits at the correct end: ، ؟ ( ) « » " .
 3. Numbers (123 and ١٢٣) keep their digit order inside Arabic text.
 4. Mixed paragraphs keep English words readable and in order.
 5. Long Arabic paragraphs wrap without reversed or duplicated lines.
 6. Ordered list markers are on the right for Arabic items; bullets likewise.
 7. The Arabic table runs right-to-left (first column on the right).
 8. The explicit rtl paragraph (digits/English only) is right-aligned.
 9. The English paragraph and English table stay left-to-right.
10. Header shows the Arabic title; footer shows the page number.
"""


def build_content() -> DocumentContentModel:
    return DocumentContentModel(Metadata("اختبار التقرير العربي", "ar", "Document Builder AI"), [
        Heading("١. الحروف والترقيم", 1),
        Paragraph("مرحبا بالعالم، كيف حالك؟ هذا اختبار (للتأكد) من اتصال الحروف واتجاه النص."),
        Paragraph("قال المدير: «يجب إنهاء التقرير» ثم أضاف \"شكرا لكم\"."),
        Heading("٢. الأرقام والنص المختلط", 1),
        Paragraph("عدد العمال ١٢٣٤٥ وفي عام 2026 بلغ الإنتاج 6789 طنا."),
        Paragraph("اختبار Document Builder AI في القاهرة مع ملف report_v2.xlsx بنجاح."),
        Paragraph("2026-10-15 ABC-123", "rtl"),
        Paragraph("This is an English paragraph to confirm left-to-right layout."),
        Heading("٣. الالتفاف", 1),
        Paragraph("نص عربي طويل لاختبار التفاف الأسطر. " * 25),
        Heading("٤. القوائم", 2),
        ListBlock(("البند الأول", "البند الثاني مع English", "البند الثالث"), True),
        ListBlock(("نقطة عربية", "English point", "نقطة (بين قوسين)")),
        Heading("٥. الجداول", 2),
        Table(("العمود الأول", "العمود الثاني", "Total"),
              (("١", "قيمة", "10"), ("٢", "قيمة أخرى", "20")), "جدول تجريبي"),
        Table(("Name", "Qty"), (("Apples", "3"), ("Pears", "5")), "English table"),
    ])