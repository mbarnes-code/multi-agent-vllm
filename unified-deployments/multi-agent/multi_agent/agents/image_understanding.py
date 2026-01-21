"""
Image Understanding Agent - Visual analysis and multimodal tasks.

Handles image analysis, visual question answering, and multimodal reasoning.
"""

import base64
from pathlib import Path
from typing import Optional, List
from ..core import Agent, Result

IMAGE_INSTRUCTIONS = """You are an Image Understanding Agent specialized in visual analysis and multimodal tasks.

## YOUR CAPABILITIES

1. **Image Analysis**: Describe and analyze visual content in detail
2. **Object Detection**: Identify and locate objects in images
3. **Text Extraction (OCR)**: Read and extract text from images
4. **Visual Q&A**: Answer questions about image content
5. **Image Comparison**: Compare multiple images
6. **Scene Understanding**: Understand context, setting, and relationships

## GUIDELINES

- Provide detailed, accurate descriptions
- Note uncertainty when image quality is poor
- Consider cultural and contextual factors
- Respect privacy - don't identify real individuals
- Describe objectively without assumptions

## AVAILABLE TOOLS

- `analyze_image`: Get detailed analysis of an image
- `extract_text`: Extract text from images (OCR)
- `describe_image`: Generate a description of the image
- `compare_images`: Compare two or more images

## RESPONSE FORMAT

When analyzing images:
1. Start with a high-level summary
2. Describe key elements and their relationships
3. Note any text, symbols, or notable features
4. Provide relevant context or interpretation
5. Answer any specific questions asked

If no image is provided, ask the user to share one."""


class ImageUnderstandingAgent:
    """Factory for creating image understanding agents."""
    
    def __init__(
        self,
        model: str = "microsoft/Phi-4",
        vision_model: Optional[str] = None,
        max_image_size: int = 4 * 1024 * 1024,  # 4MB
    ):
        self.model = model
        self.vision_model = vision_model or model
        self.max_image_size = max_image_size
        
    def _create_image_functions(self) -> list:
        """Create image analysis tool functions."""
        
        def analyze_image(image_path: str) -> str:
            """
            Analyze an image and provide detailed description.
            
            Args:
                image_path: Path to the image file or URL
            """
            # Validate image
            validation = _validate_image(image_path, self.max_image_size)
            if validation != "valid":
                return validation
            
            # In production, this would call a vision model
            # For now, return a placeholder that indicates the image was received
            return f"""Image received: {image_path}

To analyze this image, I would examine:
1. **Main subjects**: Objects, people, or elements in focus
2. **Composition**: Layout, framing, and visual hierarchy
3. **Colors and lighting**: Dominant colors, contrast, mood
4. **Text and symbols**: Any visible text or recognizable symbols
5. **Context**: Setting, time of day, location indicators

Please note: Full image analysis requires a vision-capable model.
The current model ({self.model}) may have limited vision capabilities.

For detailed analysis, ensure the VLLM deployment includes a multimodal model."""
        
        def extract_text(image_path: str) -> str:
            """
            Extract text from an image using OCR.
            
            Args:
                image_path: Path to the image file
            """
            validation = _validate_image(image_path, self.max_image_size)
            if validation != "valid":
                return validation
            
            # In production, use an OCR library or vision model
            try:
                # Attempt to use pytesseract if available
                import pytesseract
                from PIL import Image
                
                img = Image.open(image_path)
                text = pytesseract.image_to_string(img)
                
                if text.strip():
                    return f"Extracted text:\n\n{text}"
                return "No text detected in the image."
                
            except ImportError:
                return """OCR extraction requires pytesseract and PIL.
                
To enable OCR:
1. Install Tesseract: apt-get install tesseract-ocr
2. Install Python packages: pip install pytesseract pillow

Alternatively, use a vision-capable model for text extraction."""
            except Exception as e:
                return f"Error extracting text: {str(e)}"
        
        def describe_image(image_path: str, detail_level: str = "medium") -> str:
            """
            Generate a description of the image.
            
            Args:
                image_path: Path to the image file
                detail_level: Level of detail (brief, medium, detailed)
            """
            validation = _validate_image(image_path, self.max_image_size)
            if validation != "valid":
                return validation
            
            detail_prompts = {
                "brief": "Provide a one-sentence description.",
                "medium": "Provide a paragraph describing the main elements.",
                "detailed": "Provide a comprehensive description covering all visible elements.",
            }
            
            prompt = detail_prompts.get(detail_level, detail_prompts["medium"])
            
            return f"""Image: {image_path}
Detail level: {detail_level}

{prompt}

Note: Full image description requires a vision-capable model.
Please ensure your VLLM deployment includes multimodal support."""
        
        def compare_images(image_paths: str) -> str:
            """
            Compare multiple images and describe differences/similarities.
            
            Args:
                image_paths: Comma-separated paths to images
            """
            paths = [p.strip() for p in image_paths.split(",")]
            
            if len(paths) < 2:
                return "Please provide at least 2 images to compare."
            
            if len(paths) > 5:
                return "Maximum 5 images can be compared at once."
            
            # Validate all images
            for path in paths:
                validation = _validate_image(path, self.max_image_size)
                if validation != "valid":
                    return f"Error with {path}: {validation}"
            
            return f"""Comparing {len(paths)} images:
{chr(10).join(f'- {p}' for p in paths)}

Comparison would analyze:
1. **Visual similarities**: Common elements, colors, composition
2. **Differences**: Unique elements in each image
3. **Quality comparison**: Resolution, clarity, lighting
4. **Content relationship**: How images relate to each other

Note: Full comparison requires a vision-capable model."""
        
        def get_image_metadata(image_path: str) -> str:
            """
            Get metadata and technical details about an image.
            
            Args:
                image_path: Path to the image file
            """
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                
                img = Image.open(image_path)
                
                metadata = [
                    f"**Format**: {img.format}",
                    f"**Mode**: {img.mode}",
                    f"**Size**: {img.size[0]}x{img.size[1]} pixels",
                ]
                
                # Get EXIF data if available
                exif = img._getexif()
                if exif:
                    metadata.append("\n**EXIF Data**:")
                    for tag_id, value in list(exif.items())[:10]:
                        tag = TAGS.get(tag_id, tag_id)
                        metadata.append(f"  - {tag}: {value}")
                
                return "\n".join(metadata)
                
            except ImportError:
                return "PIL/Pillow is required for metadata extraction. Install with: pip install pillow"
            except Exception as e:
                return f"Error reading metadata: {str(e)}"
        
        return [
            analyze_image,
            extract_text,
            describe_image,
            compare_images,
            get_image_metadata,
        ]
    
    def create(self) -> Agent:
        """Create the image understanding agent."""
        return Agent(
            name="Image Understanding Agent",
            model=self.model,
            instructions=IMAGE_INSTRUCTIONS,
            functions=self._create_image_functions(),
        )


def _validate_image(image_path: str, max_size: int) -> str:
    """Validate image file exists and is within size limits."""
    if image_path.startswith(("http://", "https://")):
        # URL validation would happen at request time
        return "valid"
    
    path = Path(image_path)
    
    if not path.exists():
        return f"Image file not found: {image_path}"
    
    if not path.is_file():
        return f"Not a file: {image_path}"
    
    # Check file size
    size = path.stat().st_size
    if size > max_size:
        return f"Image too large: {size / 1024 / 1024:.1f}MB (max: {max_size / 1024 / 1024:.1f}MB)"
    
    # Check extension
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    if path.suffix.lower() not in valid_extensions:
        return f"Unsupported image format: {path.suffix}. Supported: {', '.join(valid_extensions)}"
    
    return "valid"


def create_image_agent(
    model: str = "microsoft/Phi-4",
    vision_model: Optional[str] = None,
) -> Agent:
    """
    Create an image understanding agent.
    
    Args:
        model: Model to use for the agent
        vision_model: Specific vision model (if different from main model)
        
    Returns:
        Configured Image Understanding Agent
    """
    factory = ImageUnderstandingAgent(
        model=model,
        vision_model=vision_model,
    )
    return factory.create()
