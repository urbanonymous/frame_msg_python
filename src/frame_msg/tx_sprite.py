from dataclasses import dataclass
import struct
import numpy as np
from PIL import Image
import io

@dataclass
class TxSprite:
    """
    A sprite message containing image data with a custom palette.

    Attributes:
        msg_code: Message type identifier
        width: Width of the sprite in pixels
        height: Height of the sprite in pixels
        num_colors: Number of colors in the palette (2, 4, or 16)
        palette_data: RGB values for each color (3 bytes per color)
        pixel_data: Array of palette indices for each pixel
    """
    msg_code: int
    width: int
    height: int
    num_colors: int
    palette_data: bytes
    pixel_data: bytes

    @staticmethod
    def from_image_bytes(msg_code: int, image_bytes: bytes) -> 'TxSprite':
        """Create a sprite from image bytes, quantizing to 16 colors if needed."""
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB mode if not already
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if needed while maintaining aspect ratio
        if img.width > 640 or img.height > 400:
            img.thumbnail((640, 400), Image.Resampling.NEAREST)

        # Quantize to 16 colors if needed
        if not img.mode == 'P' or img.getcolors() is None or len(img.getcolors()) > 16:
            img = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)

        # Quantized Palette comes back in a luminance gradient from lightest to darkest.
        # Ensure darkest is at index 0 and swap the lightest from index 0 out to index 15
        palette = list(img.getpalette()[:48])  # Get first 16 RGB colors
        pixel_data = np.array(img)

        # Swap index 0 with index 15
        palette[0:3], palette[45:48] = palette[45:48], palette[0:3]

        # And update the pixel_data to match
        for i in range(0, pixel_data.shape[0]):
            for j in range(0, pixel_data.shape[1]):
                if pixel_data[i][j] == 0:
                    pixel_data[i][j] = 15
                elif pixel_data[i][j] == 15:
                    pixel_data[i][j] = 0

        # set the first entry to completely black, since the display will treat it as transparent/void
        palette[0:3] = 0, 0, 0

        return TxSprite(
            msg_code=msg_code,
            width=img.width,
            height=img.height,
            num_colors=16,
            palette_data=bytes(palette),
            pixel_data=pixel_data.tobytes()
        )

    def pack(self) -> bytes:
        """Pack the sprite into its binary format."""
        # Calculate bits per pixel based on number of colors
        if self.num_colors <= 2:
            bpp = 1
            pack_func = self._pack_1bit
        elif self.num_colors <= 4:
            bpp = 2
            pack_func = self._pack_2bit
        else:
            bpp = 4
            pack_func = self._pack_4bit

        # Pack pixel data
        packed_pixels = pack_func(self.pixel_data)

        # Create header
        header = struct.pack('>HHBB',
            self.width,
            self.height,
            bpp,
            self.num_colors
        )

        return header + self.palette_data + packed_pixels

    @staticmethod
    def _pack_1bit(data: bytes) -> bytes:
        """Pack 1-bit pixels (2 colors) into bytes."""
        data_array = np.frombuffer(data, dtype=np.uint8)
        packed = np.packbits(data_array)
        return packed.tobytes()

    @staticmethod
    def _pack_2bit(data: bytes) -> bytes:
        """Pack 2-bit pixels (4 colors) into bytes."""
        data_array = np.frombuffer(data, dtype=np.uint8)
        packed = np.zeros(len(data_array) // 4 + (1 if len(data_array) % 4 else 0), dtype=np.uint8)

        for i in range(0, len(data_array)):
            byte_idx = i // 4
            bit_offset = (3 - (i % 4)) * 2
            packed[byte_idx] |= (data_array[i] & 0x03) << bit_offset

        return packed.tobytes()

    @staticmethod
    def _pack_4bit(data: bytes) -> bytes:
        """Pack 4-bit pixels (16 colors) into bytes."""
        data_array = np.frombuffer(data, dtype=np.uint8)
        packed = np.zeros(len(data_array) // 2 + (1 if len(data_array) % 2 else 0), dtype=np.uint8)

        for i in range(0, len(data_array)):
            byte_idx = i // 2
            bit_offset = (1 - (i % 2)) * 4
            packed[byte_idx] |= (data_array[i] & 0x0F) << bit_offset

        return packed.tobytes()
