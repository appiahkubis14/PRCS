# yourapp/management/commands/debug_pdf_fields.py
from django.core.management.base import BaseCommand
from django.conf import settings
from pypdf import PdfReader
import os

class Command(BaseCommand):
    help = 'Debug PDF form fields to find field names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf',
            type=str,
            help='Path to PDF file (relative to project root or absolute)',
            required=False
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available PDF templates in common directories',
        )

    def handle(self, *args, **options):
        pdf_path = options.get('pdf')
        
        if options['list']:
            self.list_pdf_templates()
            return
        
        if pdf_path:
            self.debug_single_pdf(pdf_path)
        else:
            # Try common locations
            self.debug_common_locations()

    def list_pdf_templates(self):
        """List all PDF files in common template directories"""
        self.stdout.write(self.style.SUCCESS("Searching for PDF templates..."))
        self.stdout.write("-" * 80)
        
        # Common directories to search
        search_paths = [
            os.path.join(settings.BASE_DIR, 'static', 'pdf_templates'),
            os.path.join(settings.BASE_DIR, 'static'),
            os.path.join(settings.BASE_DIR, 'media', 'pdf_templates'),
            os.path.join(settings.BASE_DIR, 'media'),
            settings.BASE_DIR,
            os.path.join(settings.BASE_DIR, 'templates'),
            os.path.join(settings.BASE_DIR, 'core', 'static', 'pdf_templates'),
            os.path.join(settings.BASE_DIR, 'yourapp', 'static', 'pdf_templates'),  # Change 'yourapp' to your app name
        ]
        
        found_pdfs = []
        
        for path in search_paths:
            if os.path.exists(path):
                self.stdout.write(f"Checking: {path}")
                for file in os.listdir(path):
                    if file.lower().endswith('.pdf'):
                        full_path = os.path.join(path, file)
                        found_pdfs.append(full_path)
                        self.stdout.write(f"  ✓ Found: {file}")
            else:
                self.stdout.write(f"  ✗ Not found: {path}")
        
        if found_pdfs:
            self.stdout.write("\n" + self.style.SUCCESS(f"Total PDFs found: {len(found_pdfs)}"))
            self.stdout.write("\nTo debug a specific PDF, run:")
            self.stdout.write(self.style.WARNING("python manage.py debug_pdf_fields --pdf /path/to/your/file.pdf"))
        else:
            self.stdout.write(self.style.WARNING("\nNo PDF files found in common locations."))

    def debug_single_pdf(self, pdf_path):
        """Debug a single PDF file"""
        # Check if path is absolute or relative
        if not os.path.isabs(pdf_path):
            # Try relative to BASE_DIR
            full_path = os.path.join(settings.BASE_DIR, pdf_path)
            if not os.path.exists(full_path):
                # Try as is
                full_path = pdf_path
        else:
            full_path = pdf_path
        
        if not os.path.exists(full_path):
            self.stdout.write(self.style.ERROR(f"PDF file not found: {full_path}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"Analyzing PDF: {full_path}"))
        self.stdout.write("-" * 80)
        
        try:
            with open(full_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                
                # Basic PDF info
                self.stdout.write(f"Number of pages: {len(pdf_reader.pages)}")
                
                # Get form fields
                fields = pdf_reader.get_fields()
                
                if fields:
                    self.stdout.write(self.style.SUCCESS(f"\nFound {len(fields)} form field(s):"))
                    self.stdout.write("-" * 80)
                    
                    for i, (field_name, field) in enumerate(fields.items(), 1):
                        self.stdout.write(f"\n{i}. Field Name: '{self.style.WARNING(field_name)}'")
                        
                        # Field type
                        field_type = field.get('/FT')
                        if field_type == '/Tx':
                            field_type_str = "Text Field"
                        elif field_type == '/Btn':
                            field_type_str = "Button/Checkbox"
                        elif field_type == '/Ch':
                            field_type_str = "Choice Field"
                        elif field_type == '/Sig':
                            field_type_str = "Signature Field"
                        else:
                            field_type_str = str(field_type)
                        
                        self.stdout.write(f"   Type: {field_type_str}")
                        
                        # Current value
                        current_value = field.get('/V')
                        self.stdout.write(f"   Current Value: {current_value}")
                        
                        # Default value
                        default_value = field.get('/DV')
                        self.stdout.write(f"   Default Value: {default_value}")
                        
                        # Field flags
                        flags = field.get('/Ff')
                        if flags:
                            self.stdout.write(f"   Flags: {flags}")
                        
                        # Alternative field name (if any)
                        alt_name = field.get('/TU')
                        if alt_name:
                            self.stdout.write(f"   Alternative Name: {alt_name}")
                        
                        # Field mapping name (if any)
                        mapping_name = field.get('/TM')
                        if mapping_name:
                            self.stdout.write(f"   Mapping Name: {mapping_name}")
                        
                        # Rectangle position
                        rect = field.get('/Rect')
                        if rect:
                            self.stdout.write(f"   Position (Rect): {rect}")
                        
                        # Page number
                        page = field.get('/P')
                        if page:
                            self.stdout.write(f"   Page: {page}")
                        
                        self.stdout.write("-" * 50)
                    
                    # Generate Python dictionary for easy copy-paste
                    self.stdout.write("\n" + self.style.SUCCESS("Python field mapping dictionary:"))
                    self.stdout.write("-" * 80)
                    self.stdout.write("field_values = {")
                    for field_name in fields.keys():
                        self.stdout.write(f"    '{field_name}': '',  # TODO: Add value")
                    self.stdout.write("}")
                    
                    # Generate Django template context suggestion
                    self.stdout.write("\n" + self.style.SUCCESS("Suggestion for template context:"))
                    self.stdout.write("-" * 80)
                    self.stdout.write("context = {")
                    for field_name in fields.keys():
                        self.stdout.write(f"    '{field_name}': bill.some_field,")
                    self.stdout.write("}")
                    
                else:
                    self.stdout.write(self.style.WARNING("\nNo form fields found in this PDF."))
                    
                    # Check if it's a fillable PDF without fields
                    if '/AcroForm' in pdf_reader.trailer.get('/Root', {}):
                        self.stdout.write("The PDF has an AcroForm but no fields were returned.")
                    else:
                        self.stdout.write("This PDF does not contain any form fields. It might be a regular PDF.")
                        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading PDF: {str(e)}"))

    def debug_common_locations(self):
        """Try to find and debug PDFs in common locations"""
        common_paths = [
            os.path.join(settings.BASE_DIR, 'static', 'pdf_templates', 'bop_bill_template.pdf'),
            os.path.join(settings.BASE_DIR, 'static', 'bop_bill_template.pdf'),
            os.path.join(settings.BASE_DIR, 'media', 'pdf_templates', 'bop_bill_template.pdf'),
            os.path.join(settings.BASE_DIR, 'media', 'bop_bill_template.pdf'),
            os.path.join(settings.BASE_DIR, 'bop_bill_template.pdf'),
        ]
        
        found = False
        for path in common_paths:
            if os.path.exists(path):
                self.stdout.write(self.style.SUCCESS(f"Found template at: {path}"))
                self.debug_single_pdf(path)
                found = True
                break
        
        if not found:
            self.stdout.write(self.style.WARNING("No bop_bill_template.pdf found in common locations."))
            self.stdout.write("\nTry one of these options:")
            self.stdout.write("1. Run with --list to see all available PDFs")
            self.stdout.write("2. Specify a custom path: --pdf /path/to/your/template.pdf")