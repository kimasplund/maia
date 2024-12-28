"""
Media processing tools for MAIA.
"""
from typing import Dict, List, Optional, Any, BinaryIO
import logging
import os
import aiofiles
import aiohttp
import asyncio
from datetime import datetime
import mimetypes
import magic
from PIL import Image
import io

_LOGGER = logging.getLogger(__name__)

class MediaTools:
    """Media processing tools."""
    
    def __init__(self, media_dir: str):
        """Initialize media tools."""
        self.media_dir = media_dir
        os.makedirs(media_dir, exist_ok=True)
        
    async def save_media(
        self,
        data: bytes,
        filename: str,
        media_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save media file."""
        try:
            # Determine media type if not provided
            if not media_type:
                media_type = magic.from_buffer(data, mime=True)
                
            # Generate unique filename if needed
            if os.path.exists(os.path.join(self.media_dir, filename)):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{base}_{timestamp}{ext}"
                
            filepath = os.path.join(self.media_dir, filename)
            
            # Save file
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(data)
                
            return {
                "filename": filename,
                "filepath": filepath,
                "media_type": media_type,
                "size": len(data)
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to save media: {str(e)}")
            return {"error": str(e)}
            
    async def load_media(self, filename: str) -> Optional[bytes]:
        """Load media file."""
        try:
            filepath = os.path.join(self.media_dir, filename)
            
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filename}")
                
            async with aiofiles.open(filepath, 'rb') as f:
                return await f.read()
                
        except Exception as e:
            _LOGGER.error(f"Failed to load media: {str(e)}")
            return None
            
    async def delete_media(self, filename: str) -> bool:
        """Delete media file."""
        try:
            filepath = os.path.join(self.media_dir, filename)
            
            if not os.path.exists(filepath):
                return False
                
            os.remove(filepath)
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to delete media: {str(e)}")
            return False
            
    async def list_media(
        self,
        media_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List media files."""
        try:
            files = []
            
            for filename in os.listdir(self.media_dir)[offset:offset+limit]:
                filepath = os.path.join(self.media_dir, filename)
                
                if not os.path.isfile(filepath):
                    continue
                    
                file_type = magic.from_file(filepath, mime=True)
                
                if media_type and not file_type.startswith(media_type):
                    continue
                    
                files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "media_type": file_type,
                    "size": os.path.getsize(filepath),
                    "created": datetime.fromtimestamp(
                        os.path.getctime(filepath)
                    ).isoformat()
                })
                
            return files
            
        except Exception as e:
            _LOGGER.error(f"Failed to list media: {str(e)}")
            return []
            
    async def resize_image(
        self,
        data: bytes,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 85
    ) -> Optional[bytes]:
        """Resize image while maintaining aspect ratio."""
        try:
            # Open image
            img = Image.open(io.BytesIO(data))
            
            # Calculate new dimensions
            width, height = img.size
            ratio = min(max_width/width, max_height/height)
            
            if ratio < 1:
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
            # Save to bytes
            output = io.BytesIO()
            img.save(output, format=img.format, quality=quality)
            return output.getvalue()
            
        except Exception as e:
            _LOGGER.error(f"Failed to resize image: {str(e)}")
            return None
            
    async def convert_format(
        self,
        data: bytes,
        target_format: str,
        quality: int = 85
    ) -> Optional[bytes]:
        """Convert media format."""
        try:
            # Open image
            img = Image.open(io.BytesIO(data))
            
            # Convert and save to bytes
            output = io.BytesIO()
            img.save(output, format=target_format.upper(), quality=quality)
            return output.getvalue()
            
        except Exception as e:
            _LOGGER.error(f"Failed to convert format: {str(e)}")
            return None
            
    async def download_media(self, url: str) -> Optional[bytes]:
        """Download media from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        raise Exception(
                            f"Failed to download media: {response.status}"
                        )
                        
        except Exception as e:
            _LOGGER.error(f"Failed to download media: {str(e)}")
            return None
            
    async def get_media_info(self, filename: str) -> Dict[str, Any]:
        """Get media file information."""
        try:
            filepath = os.path.join(self.media_dir, filename)
            
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filename}")
                
            # Get basic file info
            stat = os.stat(filepath)
            mime_type = magic.from_file(filepath, mime=True)
            
            info = {
                "filename": filename,
                "filepath": filepath,
                "media_type": mime_type,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat()
            }
            
            # Get image-specific info if applicable
            if mime_type.startswith('image/'):
                with Image.open(filepath) as img:
                    info.update({
                        "width": img.width,
                        "height": img.height,
                        "format": img.format,
                        "mode": img.mode
                    })
                    
            return info
            
        except Exception as e:
            _LOGGER.error(f"Failed to get media info: {str(e)}")
            return {"error": str(e)} 