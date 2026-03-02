from src.commands.base import Command

class ExtractImagesCommand(Command):
    """Command to extract all images from a PDF to a target directory."""
    
    def __init__(self, image_service, document, output_dir: str):
        self.image_service = image_service
        self.document = document
        self.output_dir = output_dir

    def execute(self):
        """Runs the extraction process."""
        self.image_service.extract_images(self.document, self.output_dir)

    def undo(self):
        """
        No-op. Automatically deleting extracted user files on an 'undo' 
        can be dangerous, so we skip it for safety.
        """
        pass

class ExtractSingleImageCommand(Command):
    """Command to extract a specific clicked image using its xref."""
    
    def __init__(self, image_service, document, xref: int, output_path: str):
        self.image_service = image_service
        self.document = document
        self.xref = xref
        self.output_path = output_path

    def execute(self):
        self.image_service.extract_single_image(self.document, self.xref, self.output_path)

    def undo(self):
        pass # No-op for safety