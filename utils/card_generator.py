"""
BlockForge OS - Card Generator v2.2.0
Generates stats cards and leaderboard images using PIL/Pillow
"""

import io
import math
from datetime import datetime
from typing import Optional, Tuple, List, Dict

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _get_font(size: int, bold: bool = False) -> 'ImageFont.FreeTypeFont':
    """Get a font, with fallback to default."""
    try:
        # Try common system fonts
        font_names = ['arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf', 'FreeSans.ttf']
        if bold:
            font_names = ['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf', 'FreeSansBold.ttf'] + font_names
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: int) -> Tuple[int, int, int]:
    return ((hex_color >> 16) & 0xFF, (hex_color >> 8) & 0xFF, hex_color & 0xFF)


def _create_gradient(width: int, height: int, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> Image.Image:
    """Create a horizontal gradient image."""
    img = Image.new('RGBA', (width, height))
    for x in range(width):
        ratio = x / max(width - 1, 1)
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        for y in range(height):
            img.putpixel((x, y), (r, g, b, 255))
    return img


def _draw_rounded_rect(draw: 'ImageDraw.Draw', xy, radius: int, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * radius, y0 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * radius, y0, x1, y0 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * radius, x0 + 2 * radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * radius, y1 - 2 * radius, x1, y1], 0, 90, fill=fill)


def _get_dominant_color(image: Image.Image) -> Tuple[int, int, int]:
    """Get dominant color from an image."""
    small = image.resize((50, 50)).convert('RGB')
    pixels = list(small.getdata())
    # Filter out very dark and very light pixels
    filtered = [(r, g, b) for r, g, b in pixels if 30 < r + g + b < 700]
    if not filtered:
        return (88, 101, 242)  # Discord blurple fallback
    avg_r = sum(p[0] for p in filtered) // len(filtered)
    avg_g = sum(p[1] for p in filtered) // len(filtered)
    avg_b = sum(p[2] for p in filtered) // len(filtered)
    return (avg_r, avg_g, avg_b)


def _format_number(num: int) -> str:
    """Format large numbers compactly."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def _format_voice_time(minutes: int) -> str:
    """Format voice minutes into readable time."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        return f"{hours}h {mins}m"
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h"


async def generate_stats_card(
    username: str,
    avatar_bytes: bytes,
    level: int,
    total_xp: int,
    xp_for_current: int,
    xp_for_next: int,
    rank: int,
    messages_sent: int,
    voice_minutes: int,
    joined_at: Optional[datetime],
    accent_color: Optional[int] = None,
    banner_bytes: Optional[bytes] = None,
) -> Optional[bytes]:
    """Generate a stats card image (934x282)."""
    if not PIL_AVAILABLE:
        return None

    W, H = 934, 282

    # Determine background color
    bg_color1 = (44, 47, 51)  # Fallback dark gray
    bg_color2 = (32, 34, 37)

    if accent_color:
        bg_color1 = _hex_to_rgb(accent_color)
        bg_color2 = tuple(max(0, c - 40) for c in bg_color1)
    elif banner_bytes:
        try:
            banner_img = Image.open(io.BytesIO(banner_bytes)).convert('RGB')
            bg_color1 = _get_dominant_color(banner_img)
            bg_color2 = tuple(max(0, c - 40) for c in bg_color1)
        except:
            pass
    elif avatar_bytes:
        try:
            av_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGB')
            bg_color1 = _get_dominant_color(av_img)
            bg_color2 = tuple(max(0, c - 40) for c in bg_color1)
        except:
            pass

    # Create background
    card = _create_gradient(W, H, bg_color1, bg_color2)
    draw = ImageDraw.Draw(card)

    # Draw dark overlay for readability
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 120))
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)

    # Avatar
    avatar_size = 160
    avatar_x, avatar_y = 40, (H - avatar_size) // 2

    try:
        avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA').resize((avatar_size, avatar_size))
        # Create circular mask
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, avatar_size - 1, avatar_size - 1], fill=255)
        # White border
        border_size = avatar_size + 8
        border_x = avatar_x - 4
        border_y = avatar_y - 4
        draw.ellipse([border_x, border_y, border_x + border_size, border_y + border_size], fill=(255, 255, 255, 200))
        card.paste(avatar_img, (avatar_x, avatar_y), mask)
    except:
        draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(88, 101, 242))

    # Text area starts after avatar
    text_x = avatar_x + avatar_size + 30
    text_w = W - text_x - 30

    # Fonts
    font_name = _get_font(28, bold=True)
    font_level = _get_font(20)
    font_small = _get_font(16)
    font_xp = _get_font(14)

    # Username
    display_name = username[:20] + '...' if len(username) > 20 else username
    draw.text((text_x, 30), display_name, fill=(255, 255, 255), font=font_name)

    # Level & Rank
    draw.text((text_x, 68), f"Level {level}", fill=(200, 200, 200), font=font_level)
    rank_text = f"Rank #{rank}"
    rank_w = draw.textlength(rank_text, font=font_level)
    draw.text((text_x + text_w - rank_w, 68), rank_text, fill=(200, 200, 200), font=font_level)

    # XP Progress bar
    bar_x = text_x
    bar_y = 108
    bar_w = text_w
    bar_h = 26

    # Background bar
    _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), 13, (60, 60, 60, 200))

    # Progress fill
    xp_in_level = total_xp - xp_for_current
    xp_needed = max(xp_for_next - xp_for_current, 1)
    progress = min(xp_in_level / xp_needed, 1.0)
    fill_w = max(int(bar_w * progress), 26)  # Min width for rounded look

    bar_color = bg_color1 if accent_color else (88, 101, 242)
    bright_bar = tuple(min(255, c + 60) for c in bar_color)
    _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), 13, bright_bar + (255,))

    # XP text on bar
    xp_text = f"{_format_number(xp_in_level)} / {_format_number(xp_needed)} XP"
    xp_text_w = draw.textlength(xp_text, font=font_xp)
    draw.text((bar_x + (bar_w - xp_text_w) / 2, bar_y + 5), xp_text, fill=(255, 255, 255), font=font_xp)

    # Stats row
    stats_y = 155
    stats = [
        ("Messages", _format_number(messages_sent)),
        ("Voice Time", _format_voice_time(voice_minutes)),
        ("Total XP", _format_number(total_xp)),
    ]
    if joined_at:
        stats.append(("Joined", joined_at.strftime("%b %d, %Y")))

    col_w = text_w // len(stats)
    for i, (label, value) in enumerate(stats):
        x = text_x + i * col_w
        draw.text((x, stats_y), label, fill=(150, 150, 150), font=font_small)
        draw.text((x, stats_y + 22), value, fill=(255, 255, 255), font=font_level)

    # Footer line
    draw.line([(text_x, H - 30), (text_x + text_w, H - 30)], fill=(80, 80, 80), width=1)
    draw.text((text_x, H - 25), f"BlockForge OS", fill=(100, 100, 100), font=font_xp)

    # Export
    buffer = io.BytesIO()
    card.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()


async def generate_leaderboard_image(
    guild_name: str,
    period: str,
    entries: List[Dict],
    avatar_data: Dict[int, bytes],
) -> Optional[bytes]:
    """Generate a leaderboard image (934 x variable height)."""
    if not PIL_AVAILABLE:
        return None

    W = 934
    header_h = 80
    entry_h = 60
    padding = 10
    H = header_h + len(entries) * entry_h + padding * 2

    img = Image.new('RGBA', (W, H), (44, 47, 51, 255))
    draw = ImageDraw.Draw(img)

    font_title = _get_font(28, bold=True)
    font_entry = _get_font(20, bold=True)
    font_small = _get_font(16)
    font_xp = _get_font(14)

    # Header
    draw.rectangle([0, 0, W, header_h], fill=(32, 34, 37))
    draw.text((30, 15), guild_name[:40], fill=(255, 255, 255), font=font_title)
    period_label = {"all_time": "All Time", "weekly": "Weekly", "monthly": "Monthly"}.get(period, period)
    draw.text((30, 50), f"Leaderboard — {period_label}", fill=(150, 150, 150), font=font_small)

    # Rank colors
    rank_colors = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}

    for i, entry in enumerate(entries[:15]):
        y = header_h + i * entry_h
        rank = i + 1

        # Alternating row colors
        row_color = (52, 54, 60) if i % 2 == 0 else (44, 47, 51)
        draw.rectangle([0, y, W, y + entry_h], fill=row_color)

        # Rank number
        r_color = rank_colors.get(rank, (200, 200, 200))
        draw.text((20, y + 16), f"#{rank}", fill=r_color, font=font_entry)

        # Avatar
        av_size = 40
        av_x = 80
        av_y = y + (entry_h - av_size) // 2
        user_id = entry.get('user_id')

        if user_id in avatar_data and avatar_data[user_id]:
            try:
                av = Image.open(io.BytesIO(avatar_data[user_id])).convert('RGBA').resize((av_size, av_size))
                mask = Image.new('L', (av_size, av_size), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, av_size - 1, av_size - 1], fill=255)
                img.paste(av, (av_x, av_y), mask)
            except:
                draw.ellipse([av_x, av_y, av_x + av_size, av_y + av_size], fill=(88, 101, 242))
        else:
            draw.ellipse([av_x, av_y, av_x + av_size, av_y + av_size], fill=(88, 101, 242))

        # Username
        name = entry.get('username', 'Unknown')[:25]
        draw.text((140, y + 10), name, fill=(255, 255, 255), font=font_entry)

        # Level + XP
        draw.text((140, y + 36), f"Level {entry.get('level', 0)}", fill=(150, 150, 150), font=font_xp)

        xp_text = f"{_format_number(entry.get('xp', 0))} XP"
        xp_w = draw.textlength(xp_text, font=font_entry)
        draw.text((W - xp_w - 30, y + 16), xp_text, fill=(200, 200, 200), font=font_entry)

    # Export
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()
