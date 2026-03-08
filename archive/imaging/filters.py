from PIL import Image, ImageEnhance

def enhance_contrast(image: Image.Image, factor: float) -> Image.Image:
    """
    Adjusts image contrast.
    factor = 1.0 gives the original image.
    factor < 1.0 decreases contrast (e.g., 0.5 is low contrast).
    factor > 1.0 increases contrast (e.g., 1.5 is high contrast).
    """
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)

def sharpen(image: Image.Image, factor: float) -> Image.Image:
    """
    Adjusts image sharpness.
    factor = 1.0 gives the original image.
    factor = 0.0 gives a blurred image.
    factor = 2.0 gives a sharpened image.
    """
    enhancer = ImageEnhance.Sharpness(image)
    return enhancer.enhance(factor)

def adjust_brightness(image: Image.Image, factor: float) -> Image.Image:
    """
    Adjusts image brightness.
    factor = 1.0 gives original image.
    factor = 0.0 gives a black image.
    """
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(factor)