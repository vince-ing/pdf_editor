import os
import ctypes
from pathlib import Path

def load_custom_fonts() -> int:
    """
    Scans the /fonts directory (in the project root) and temporarily loads all 
    .ttf, .otf, and .fon files into the Windows OS memory for the current process.
    """
    if os.name != 'nt':
        print("Custom font loading is only supported on Windows.")
        return 0

    # Locate the fonts directory relative to this file 
    # (src/utils/font_loader.py -> src/utils -> src -> root)
    project_root = Path(__file__).resolve().parent.parent.parent
    fonts_dir = project_root / "fonts"

    if not fonts_dir.exists():
        print(f"Fonts directory not found at {fonts_dir}")
        return 0

    # Windows GDI constant for private font loading (cleared on exit)
    FR_PRIVATE = 0x10
    gdi32 = ctypes.windll.gdi32
    fonts_loaded = 0

    for font_file in fonts_dir.iterdir():
        if font_file.suffix.lower() in ['.ttf', '.otf', '.fon']:
            path_str = str(font_file)
            # AddFontResourceExW takes (path, flags, reserved)
            result = gdi32.AddFontResourceExW(path_str, FR_PRIVATE, 0)
            if result > 0:
                fonts_loaded += result
            else:
                print(f"Failed to load font: {font_file.name}")

    print(f"Successfully loaded {fonts_loaded} custom fonts for this session.")
    return fonts_loaded