import argparse
import sys
from src.core.document import PDFDocument
from src.services.page_service import PageService
from src.services.image_service import ImageService
from src.services.text_service import TextService
from src.commands.rotate_page import RotatePageCommand
from src.commands.extract_images import ExtractImagesCommand
from src.commands.insert_text import InsertTextCommand

def main():
    parser = argparse.ArgumentParser(description="Robust PDF Editor CLI")
    parser.add_argument("input", help="Path to input PDF")
    
    # We make output optional because extraction doesn't yield a modified PDF
    parser.add_argument("--output", "-o", help="Path to save the modified PDF", default="output.pdf")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # --- Rotate Command ---
    rotate_parser = subparsers.add_parser("rotate", help="Rotate a specific page")
    rotate_parser.add_argument("--page", type=int, required=True, help="0-based page index")
    rotate_parser.add_argument("--angle", type=int, required=True, help="Angle in degrees (multiple of 90)")
    
    # --- Extract Images Command ---
    extract_parser = subparsers.add_parser("extract", help="Extract all images from the PDF")
    extract_parser.add_argument("--outdir", "-d", required=True, help="Directory to save extracted images")
    
    # --- Insert Text Command ---
    text_parser = subparsers.add_parser("text", help="Insert text onto a page")
    text_parser.add_argument("--page", type=int, required=True, help="0-based page index")
    text_parser.add_argument("--text", type=str, required=True, help="Text to insert")
    text_parser.add_argument("--x", type=float, required=True, help="X coordinate from top-left")
    text_parser.add_argument("--y", type=float, required=True, help="Y coordinate from top-left")
    text_parser.add_argument("--size", type=int, default=12, help="Font size")
    
    args = parser.parse_args()
    
    # Instantiate Services
    page_service = PageService()
    image_service = ImageService()
    text_service = TextService()
    
    # Open document using our Core Context Manager
    try:
        with PDFDocument(args.input) as doc:
            command = None
            
            # Map CLI args to Commands
            if args.command == "rotate":
                command = RotatePageCommand(page_service, doc, args.page, args.angle)
            elif args.command == "extract":
                command = ExtractImagesCommand(image_service, doc, args.outdir)
            elif args.command == "text":
                command = InsertTextCommand(text_service, doc, args.page, args.text, (args.x, args.y), args.size)
                
            # Execute mapped command
            if command:
                command.execute()
                
            # Save Document State (if modifying command)
            if args.command in ["rotate", "text"]:
                doc.save(args.output)
                print(f"✅ Saved modified PDF to '{args.output}'")
            elif args.command == "extract":
                print(f"✅ Images successfully extracted to '{args.outdir}'")

    except Exception as e:
        print(f"❌ Error processing PDF: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()